import logging
import threading
from database import SessionLocal
from models.candidate import Candidate
from models.job import Job
from models.match_result import MatchResult
from utils.matcher import get_embedding, parse_and_match
from utils.cv_parser import build_embedding_text

logger = logging.getLogger(__name__)

# In-memory set of (candidate_id, job_id) pairs currently being processed.
# Cleared on every server restart, so after a restart any analysis=None in DB
# is treated as a dead task and will be re-triggered.
_in_progress: set = set()
_in_progress_lock = threading.Lock()


def mark_in_progress(candidate_id: int, job_id: int) -> bool:
    """Returns True if successfully marked (wasn't already in progress)."""
    with _in_progress_lock:
        key = (candidate_id, job_id)
        if key in _in_progress:
            return False
        _in_progress.add(key)
        return True


def unmark_in_progress(candidate_id: int, job_id: int):
    with _in_progress_lock:
        _in_progress.discard((candidate_id, job_id))


def is_in_progress(candidate_id: int, job_id: int) -> bool:
    with _in_progress_lock:
        return (candidate_id, job_id) in _in_progress


def enrich_and_match(candidate_id: int, raw_text: str, job_id: int):
    if not mark_in_progress(candidate_id, job_id):
        logger.info(f"enrich_and_match already in progress candidate={candidate_id} job={job_id}, skipping")
        return

    # unmark_in_progress MUST be called no matter what happens after mark succeeds
    try:
        logger.info(f"enrich_and_match START candidate={candidate_id} job={job_id}")
        db = SessionLocal()
        try:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            job = db.query(Job).filter(Job.id == job_id).first()
            if not candidate or not job:
                logger.warning(f"enrich_and_match: candidate={candidate_id} or job={job_id} not found")
                return

            existing_mr = db.query(MatchResult).filter(
                MatchResult.candidate_id == candidate_id,
                MatchResult.job_id == job_id
            ).first()
            if existing_mr and existing_mr.analysis not in (None, "Analysis unavailable", "Analysis unavailable."):
                logger.info(f"enrich_and_match SKIP (already done) candidate={candidate_id}")
                return

            try:
                logger.info(f"enrich_and_match calling parse_and_match candidate={candidate_id}")
                result = parse_and_match(
                    raw_text=raw_text,
                    job_title=job.title,
                    job_description=job.description,
                    required_skills=job.required_skills or [],
                    required_experience_years=job.required_experience_years or 0,
                    required_education=job.required_education or "",
                )

                # Re-fetch candidate after the slow Groq/embedding call to avoid stale data
                db.expire(candidate)
                candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
                if not candidate:
                    logger.warning(f"enrich_and_match: candidate {candidate_id} deleted during processing")
                    return

                if result.get("full_name"):
                    candidate.full_name = result["full_name"]
                if result.get("skills"):
                    deduped = {}
                    for skill in list(candidate.skills or []) + list(result["skills"]):
                        k = skill.lower()
                        if k not in deduped or (skill != skill.lower() and deduped[k] == deduped[k].lower()):
                            deduped[k] = skill
                    candidate.skills = list(deduped.values())
                if result.get("experience"):
                    candidate.experience = result["experience"]
                if result.get("education"):
                    candidate.education = result["education"]
                if result.get("email") and not candidate.email:
                    candidate.email = result["email"]
                candidate.embedding = get_embedding(build_embedding_text(result))

                # Re-fetch MR after the slow call
                existing_mr = db.query(MatchResult).filter(
                    MatchResult.candidate_id == candidate_id,
                    MatchResult.job_id == job_id
                ).first()

                if existing_mr:
                    existing_mr.match_score = result["match_score"]
                    existing_mr.matched_skills = result["matched_skills"]
                    existing_mr.missing_skills = result["missing_skills"]
                    existing_mr.experience_match = result["experience_match"]
                    existing_mr.education_match = result["education_match"]
                    existing_mr.analysis = result["summary"]
                else:
                    db.add(MatchResult(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        match_score=result["match_score"],
                        matched_skills=result["matched_skills"],
                        missing_skills=result["missing_skills"],
                        experience_match=result["experience_match"],
                        education_match=result["education_match"],
                        analysis=result["summary"],
                    ))
                db.commit()
                logger.info(f"enrich_and_match DONE candidate={candidate_id} score={result.get('match_score')}")

            except Exception as e:
                logger.error(f"enrich_and_match inner error for candidate {candidate_id}: {e}", exc_info=True)
                try:
                    db.rollback()
                    mr = db.query(MatchResult).filter(
                        MatchResult.candidate_id == candidate_id,
                        MatchResult.job_id == job_id
                    ).first()
                    if mr:
                        mr.analysis = "Analysis unavailable"
                        mr.match_score = mr.match_score or 0
                        db.commit()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"enrich_and_match outer error for candidate {candidate_id}: {e}", exc_info=True)
            try:
                db.rollback()
                mr = db.query(MatchResult).filter(
                    MatchResult.candidate_id == candidate_id,
                    MatchResult.job_id == job_id
                ).first()
                if mr and mr.analysis is None:
                    mr.analysis = "Analysis unavailable"
                    mr.match_score = mr.match_score or 0
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    finally:
        unmark_in_progress(candidate_id, job_id)
