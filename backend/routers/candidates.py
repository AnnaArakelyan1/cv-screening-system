from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models.candidate import Candidate
from models.job import Job
from models.application import Application
from models.user import User
from schemas.candidate import CandidateOut
from utils.auth import get_current_user
from utils.cv_parser import parse_cv_fast, is_likely_cv, build_embedding_text
from utils.matcher import get_embedding, cluster_candidates
from utils.tasks import enrich_and_match
from utils.audit import log_action
from models.match_result import MatchResult
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: int = Form(...),
    full_name: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from datetime import datetime, timezone
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="This job is closed")
    if job.deadline and datetime.now(timezone.utc) > job.deadline:
        raise HTTPException(status_code=400, detail="The application deadline for this job has passed")

    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()

    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")

    # Verify actual file signature (magic bytes) matches declared extension
    is_pdf  = file_bytes[:4] == b'%PDF'
    is_docx = file_bytes[:4] == b'PK\x03\x04'  # ZIP-based format
    if file.filename.endswith(".pdf") and not is_pdf:
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    if file.filename.endswith(".docx") and not is_docx:
        raise HTTPException(status_code=400, detail="File is not a valid DOCX")
    parsed = parse_cv_fast(file_bytes, file.filename)

    cv_valid, gemini_name = is_likely_cv(parsed)
    if not cv_valid:
        raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a CV")

    resolved_name  = full_name or gemini_name or parsed.get("full_name")
    resolved_email = email    or parsed.get("email")

    if resolved_email:
        existing = db.query(Candidate).filter(Candidate.email == resolved_email).first()
        if existing:
            existing_app = db.query(Application).filter(
                Application.candidate_id == existing.id,
                Application.job_id == job_id
            ).first()
            if existing_app:
                raise HTTPException(status_code=400, detail="This candidate has already applied to this job")
            if full_name:
                existing.full_name = full_name
            db.add(Application(candidate_id=existing.id, job_id=job_id))
            db.commit()
            background_tasks.add_task(enrich_and_match, existing.id, existing.raw_text or "", job_id)
            db.refresh(existing)
            return existing

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
        embedding=None,
        uploaded_by=current_user.id
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    background_tasks.add_task(enrich_and_match, candidate.id, parsed["raw_text"], job_id)

    db.add(Application(candidate_id=candidate.id, job_id=job_id))
    db.commit()
    log_action(db, current_user, "cv_uploaded", {
        "candidate_id": candidate.id,
        "candidate_name": candidate.full_name,
        "job_id": job_id,
        "filename": file.filename,
    })

    if candidate.email:
        background_tasks.add_task(
            send_email,
            candidate.email,
            f"Application Received – {job.title}",
            f"""Dear {candidate.full_name or 'Candidate'},

Thank you for your interest in the {job.title} position. We have successfully received your CV and our HR team will review your profile shortly.

Best regards,
HR Team"""
        )

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
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete candidates")
    log_action(db, current_user, "candidate_deleted", {
        "candidate_id": candidate.id,
        "candidate_name": candidate.full_name,
        "candidate_email": candidate.email,
    })
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted successfully"}