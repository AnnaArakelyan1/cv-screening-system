from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.candidate import Candidate
from models.user import User
from models.match_result import MatchResult
from models.application import Application
from schemas.job import JobCreate, JobOut
from utils.auth import get_current_user
from utils.matcher import get_embedding, calculate_match_score
from utils.cv_parser import parse_cv, is_likely_cv
from utils.email_sender import send_email
from typing import List
from pathlib import Path
import logging
import uuid

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
    return db.query(Job).all()

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

    candidates = db.query(Candidate).filter(Candidate.embedding != None).all()
    results = []

    for candidate in candidates:
        scores = calculate_match_score(
            candidate_embedding=candidate.embedding,
            job_embedding=job.embedding,
            candidate_experience_text=candidate.experience,
            candidate_education_text=candidate.education,
            required_experience_years=job.required_experience_years or 0,
            required_education=job.required_education or "",
        )

        is_applied = candidate.id in applied_candidate_ids

        existing = db.query(MatchResult).filter(
            MatchResult.candidate_id == candidate.id,
            MatchResult.job_id == job_id
        ).first()

        if existing:
            existing.match_score = scores["final_score"]
        else:
            db.add(MatchResult(
                candidate_id=candidate.id,
                job_id=job_id,
                match_score=scores["final_score"]
            ))

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
            "match_score": scores["final_score"],
            "semantic_score": scores["semantic_score"],
            "experience_score": scores["experience_score"],
            "education_score": scores["education_score"],
            "candidate_years": scores["candidate_years"],
            "applied": is_applied,
            "application_status": applied_candidate_ids.get(candidate.id, None)
        })

    db.commit()
    results.sort(key=lambda x: (not x["applied"], -x["match_score"]))

    return {
        "results": results,
        "emails_sent": 0
    }

@router.get("/{job_id}/public")
def get_job_public(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
        "required_experience_years": job.required_experience_years,
        "required_education": job.required_education,
    }

@router.post("/{job_id}/apply")
async def public_apply(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="This position is no longer accepting applications")

    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()
    parsed = parse_cv(file_bytes, file.filename)

    if not is_likely_cv(parsed):
        raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a CV")

    candidate = None
    if parsed.get("email"):
        candidate = db.query(Candidate).filter(Candidate.email == parsed["email"]).first()

    if candidate:
        existing_app = db.query(Application).filter(
            Application.candidate_id == candidate.id,
            Application.job_id == job_id
        ).first()
        if existing_app:
            raise HTTPException(status_code=400, detail="You have already applied to this position")
    else:
        embedding = get_embedding(parsed["raw_text"])
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
            uploaded_by=None
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

    application = Application(candidate_id=candidate.id, job_id=job_id)
    db.add(application)
    db.commit()

    if candidate.embedding and job.embedding:
        scores = calculate_match_score(
            candidate_embedding=candidate.embedding,
            job_embedding=job.embedding,
            candidate_experience_text=candidate.experience,
            candidate_education_text=candidate.education,
            required_experience_years=job.required_experience_years or 0,
            required_education=job.required_education or "",
        )
        existing_match = db.query(MatchResult).filter(
            MatchResult.candidate_id == candidate.id,
            MatchResult.job_id == job_id
        ).first()
        if existing_match:
            existing_match.match_score = scores["final_score"]
        else:
            db.add(MatchResult(candidate_id=candidate.id, job_id=job_id, match_score=scores["final_score"]))
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