from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models.candidate import Candidate
from models.job import Job
from models.user import User
from schemas.candidate import CandidateOut
from utils.auth import get_current_user
from utils.cv_parser import parse_cv, is_likely_cv, build_embedding_text
from utils.matcher import get_embedding, cluster_candidates, calculate_match_score
from utils.email_sender import send_email
from typing import List
from pathlib import Path
import logging
import uuid

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

@router.post("/upload", response_model=CandidateOut)
async def upload_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()
    parsed = parse_cv(file_bytes, file.filename)

    if not is_likely_cv(parsed):
        raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a CV")

    embedding = get_embedding(build_embedding_text(parsed))

    if parsed.get("email"):
        existing = db.query(Candidate).filter(Candidate.email == parsed["email"]).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A candidate with email {parsed['email']} already exists (ID: {existing.id}, Name: {existing.full_name})"
            )

    ext = Path(file.filename).suffix
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)

    candidate = Candidate(
        full_name=parsed["full_name"],
        email=parsed["email"],
        phone=parsed["phone"],
        skills=parsed["skills"],
        education=parsed.get("education"),
        experience=parsed.get("experience"),
        raw_text=parsed["raw_text"],
        cv_filename=stored_filename,
        embedding=embedding,
        uploaded_by=current_user.id
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)


    if candidate.email and candidate.embedding:
        try:
            jobs = db.query(Job).filter(Job.embedding != None).all()

            if jobs:
                job_lines = []
                for job in jobs:
                    scores = calculate_match_score(
                        candidate_embedding=candidate.embedding,
                        job_embedding=job.embedding,
                        candidate_experience_text=candidate.experience or candidate.raw_text,
                        candidate_education_text=candidate.education or candidate.raw_text,
                        required_experience_years=job.required_experience_years or 0,
                        required_education=job.required_education or "",
                    )
                    score = scores["final_score"]
                    if score >= 70:
                        verdict = "Strong Match"
                    elif score >= 40:
                        verdict = "Moderate Match"
                    else:
                        verdict = "Low Match"

                    job_lines.append(
                        f"  {job.title:<35} {score}%  ({verdict})"
                    )

                job_summary = "\n".join(job_lines)

                send_email(
                    to_email=candidate.email,
                    subject="Your CV Has Been Received",
                    body=f"""Dear {candidate.full_name or 'Candidate'},

Thank you for submitting your CV. We have successfully received and analyzed your profile.

YOUR MATCH RESULTS
---------------------------
{job_summary}
---------------------------

Skills detected: {', '.join(candidate.skills or [])}

Our HR team will review your profile and contact you if there is a suitable opportunity.

Best regards,
HR Team"""
                )
        except Exception as e:
            logging.warning(f"Failed to send upload email to {candidate.email}: {e}")

    return candidate

@router.get("/", response_model=List[CandidateOut])
def get_candidates(
    skill: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Candidate)
    if skill:
        query = query.filter(Candidate.skills.contains([skill]))
    return query.all()

@router.post("/cluster")
def cluster_all_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidates = db.query(Candidate).filter(Candidate.embedding != None).all()
    if len(candidates) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 candidates to cluster")

    embeddings = [c.embedding for c in candidates]
    labels = cluster_candidates(embeddings)

    for candidate, label in zip(candidates, labels):
        candidate.cluster_id = label
    db.commit()
    return {"message": f"Clustered {len(candidates)} candidates into groups"}

@router.get("/{candidate_id}/cv")
def download_cv(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.cv_filename:
        raise HTTPException(status_code=404, detail="No CV file stored for this candidate")
    path = UPLOAD_DIR / candidate.cv_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="CV file not found on server")
    return FileResponse(
        path=str(path),
        filename=candidate.cv_filename,
        media_type="application/octet-stream"
    )

@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.delete("/{candidate_id}")
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not current_user.is_admin and candidate.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete candidates you uploaded")
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted successfully"}