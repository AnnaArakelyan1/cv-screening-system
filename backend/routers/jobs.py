from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.candidate import Candidate
from models.user import User
from models.match_result import MatchResult
from models.application import Application
from schemas.job import JobCreate, JobUpdate, JobOut
from datetime import datetime, timezone
from utils.auth import get_current_user
from utils.matcher import get_embedding, match_cv_with_gemini
from utils.cv_parser import parse_cv, is_likely_cv, build_embedding_text, _gemini_parse
from utils.email_sender import send_email
from typing import List
from pathlib import Path
import logging
import uuid
import time

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

@router.post("/", response_model=JobOut)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embedding = get_embedding(job_data.description + " " + " ".join(job_data.required_skills))
    job = Job(**job_data.model_dump(), embedding=embedding, created_by=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.get("/", response_model=List[JobOut])
def get_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    jobs = db.query(Job).all()
    now = datetime.now(timezone.utc)
    changed = False
    for job in jobs:
        if job.is_open and job.deadline and now > job.deadline:
            job.is_open = False
            changed = True
    if changed:
        db.commit()
    return jobs

@router.get("/{job_id}/match")
def match_candidates(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    applications = db.query(Application).filter(Application.job_id == job_id).all()
    applied_candidate_ids = {app.candidate_id: app.status for app in applications}

    candidates = db.query(Candidate).filter(
        Candidate.id.in_(list(applied_candidate_ids.keys()))
    ).all()
    results = []

    for candidate in candidates:
        is_applied = True

        existing = db.query(MatchResult).filter(
            MatchResult.candidate_id == candidate.id,
            MatchResult.job_id == job_id
        ).first()

        if existing and existing.analysis is not None:
            gemini_score = existing.match_score
            matched_skills = existing.matched_skills or []
            missing_skills = existing.missing_skills or []
            experience_match = existing.experience_match or "unknown"
            education_match = existing.education_match or "unknown"
            analysis = existing.analysis
        else:
            # Re-parse candidate from raw_text if structured fields are empty
            needs_reparse = (
                not candidate.skills and
                not candidate.experience and
                not candidate.education and
                candidate.raw_text
            )
            if needs_reparse:
                parsed = _gemini_parse(candidate.raw_text)
                if parsed.get("full_name"):
                    candidate.full_name = parsed["full_name"]
                if parsed.get("skills"):
                    candidate.skills = parsed["skills"]
                if parsed.get("experience"):
                    candidate.experience = parsed["experience"]
                if parsed.get("education"):
                    candidate.education = parsed["education"]
                db.commit()
                time.sleep(5)  # 1 req used — wait before next call

            cv_data = {
                "skills": candidate.skills or [],
                "experience": candidate.experience,
                "education": candidate.education,
                "raw_text": candidate.raw_text,
            }
            gemini = match_cv_with_gemini(
                cv_data=cv_data,
                job_title=job.title,
                job_description=job.description,
                required_skills=job.required_skills or [],
                required_experience_years=job.required_experience_years or 0,
                required_education=job.required_education or "",
            )
            time.sleep(5)  # proactive spacing between Gemini calls
            gemini_score = gemini["score"]
            matched_skills = gemini["matched_skills"]
            missing_skills = gemini["missing_skills"]
            experience_match = gemini["experience_match"]
            education_match = gemini["education_match"]
            analysis = gemini["summary"]

            if existing:
                existing.match_score = gemini_score
                existing.matched_skills = matched_skills
                existing.missing_skills = missing_skills
                existing.experience_match = experience_match
                existing.education_match = education_match
                existing.analysis = analysis
            else:
                db.add(MatchResult(
                    candidate_id=candidate.id,
                    job_id=job_id,
                    match_score=gemini_score,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    experience_match=experience_match,
                    education_match=education_match,
                    analysis=analysis,
                ))
            db.commit()

        results.append({
            "candidate": {
                "id": candidate.id,
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "skills": candidate.skills,
                "cluster_id": candidate.cluster_id,
                "uploaded_at": candidate.uploaded_at.isoformat(),
                "cv_filename": candidate.cv_filename,
            },
            "match_score": gemini_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "experience_match": experience_match,
            "education_match": education_match,
            "analysis": analysis,
            "applied": is_applied,
            "application_status": applied_candidate_ids.get(candidate.id, None)
        })

    results.sort(key=lambda x: -x["match_score"])

    return {
        "results": results,
        "emails_sent": 0
    }

@router.get("/{job_id}/public")
def get_job_public(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deadline_passed = job.deadline and datetime.now(timezone.utc) > job.deadline
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
        "required_experience_years": job.required_experience_years,
        "required_education": job.required_education,
        "is_open": job.is_open and not deadline_passed,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "deadline_passed": bool(deadline_passed),
    }

@router.post("/{job_id}/apply")
async def public_apply(
    job_id: int,
    file: UploadFile = File(...),
    full_name: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="This position is no longer accepting applications")
    if job.deadline and datetime.now(timezone.utc) > job.deadline:
        raise HTTPException(status_code=400, detail="The application deadline for this position has passed")

    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()
    parsed = parse_cv(file_bytes, file.filename)

    if not is_likely_cv(parsed):
        raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a CV")

    resolved_email = email or parsed.get("email")
    resolved_name = full_name or parsed.get("full_name")

    candidate = None
    if resolved_email:
        candidate = db.query(Candidate).filter(Candidate.email == resolved_email).first()

    if candidate:
        existing_app = db.query(Application).filter(
            Application.candidate_id == candidate.id,
            Application.job_id == job_id
        ).first()
        if existing_app:
            raise HTTPException(status_code=400, detail="You have already applied to this position")
    else:
        embedding = get_embedding(build_embedding_text(parsed))
        ext = Path(file.filename).suffix
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)
        candidate = Candidate(
            full_name=resolved_name,
            email=resolved_email,
            phone=parsed["phone"],
            skills=parsed["skills"],
            education=parsed.get("education"),
            experience=parsed.get("experience"),
            raw_text=parsed["raw_text"],
            cv_filename=stored_filename,
            embedding=embedding,
            uploaded_by=None
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

    application = Application(candidate_id=candidate.id, job_id=job_id)
    db.add(application)
    db.commit()

    if candidate.email:
        try:
            send_email(
                to_email=candidate.email,
                subject=f"Application Received – {job.title}",
                body=f"""Dear {candidate.full_name or 'Candidate'},

Thank you for applying for the position of {job.title}.

We have successfully received your CV and our HR team will review your profile shortly.

Best regards,
HR Team"""
            )
        except Exception as e:
            logging.warning(f"Failed to send confirmation email: {e}")

    return {"message": "Your CV has been received. We will be in touch soon!"}

@router.patch("/{job_id}/toggle")
def toggle_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    job.is_open = not job.is_open
    db.commit()
    return {"is_open": job.is_open}

@router.patch("/{job_id}")
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    if data.deadline is not None:
        job.deadline = data.deadline
    else:
        job.deadline = None
    db.commit()
    db.refresh(job)
    return job

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own job postings")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}