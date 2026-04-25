from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.application import Application
from models.candidate import Candidate
from models.job import Job
from models.user import User
from models.match_result import MatchResult
from schemas.application import ApplicationCreate, ApplicationOut
from utils.auth import get_current_user
from utils.email_sender import send_email
from typing import List
import threading

router = APIRouter()

@router.post("/", response_model=ApplicationOut)
def apply_to_job(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Check job exists
    job = db.query(Job).filter(Job.id == data.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already applied
    existing = db.query(Application).filter(
        Application.candidate_id == data.candidate_id,
        Application.job_id == data.job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied to this job")

    application = Application(**data.model_dump())
    db.add(application)
    db.commit()
    db.refresh(application)
    return application

@router.get("/", response_model=List[ApplicationOut])
def get_all_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Application).all()

@router.get("/job/{job_id}", response_model=List[ApplicationOut])
def get_applications_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Application).filter(Application.job_id == job_id).all()

VALID_STATUSES = {"applied", "reviewed", "shortlisted", "accepted", "rejected"}

def _send_status_email(candidate_email: str, candidate_name: str, job_title: str, status: str, match: dict = None):
    try:
        score         = match.get("score")          if match else None
        matched       = match.get("matched_skills") if match else []
        missing       = match.get("missing_skills") if match else []
        summary       = match.get("summary")        if match else None

        score_line    = f"Your CV matched {score}% with our requirements.\n\n" if score is not None else ""
        matched_line  = ("Skills you matched: " + ", ".join(matched) + ".\n") if matched else ""
        missing_line  = ("Skills we were looking for that were missing from your profile: " + ", ".join(missing) + ".\n") if missing else ""
        summary_line  = ""

        if status == "shortlisted":
            subject = f"Interview Invitation – {job_title}"
            body = (
                f"Dear {candidate_name},\n\n"
                f"We are pleased to inform you that after reviewing your CV, you have been "
                f"selected for an interview for the position of {job_title}.\n\n"
                f"{score_line}"
                f"{matched_line}"
                f"{summary_line}\n"
                f"Our HR team will contact you shortly to schedule the interview.\n\n"
                f"Best regards,\nHR Team"
            )
        elif status == "accepted":
            subject = f"Congratulations! You have been hired – {job_title}"
            body = (
                f"Dear {candidate_name},\n\n"
                f"We are delighted to inform you that following your interview, you have been "
                f"selected for the position of {job_title}.\n\n"
                f"Our HR team will be in touch with you shortly regarding next steps.\n\n"
                f"Best regards,\nHR Team"
            )
        else:
            subject = f"Update on your application for {job_title}"
            body = (
                f"Dear {candidate_name},\n\n"
                f"Thank you for your interest in the {job_title} position. After careful "
                f"consideration, we regret to inform you that we will not be moving forward "
                f"with your application at this time.\n\n"
                f"{score_line}"
                f"{missing_line}"
                f"{summary_line}\n"
                f"We appreciate the time you invested and wish you the best in your job search.\n\n"
                f"Best regards,\nHR Team"
            )
        send_email(candidate_email, subject, body)
    except Exception:
        pass

@router.patch("/{application_id}/status")
def update_status(
    application_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = application.status
    if old_status == status:
        return {"message": "Status unchanged"}

    application.status = status
    db.commit()

    if status in ("shortlisted", "accepted", "rejected"):
        candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
        job = db.query(Job).filter(Job.id == application.job_id).first()
        if candidate and candidate.email and job:
            mr = db.query(MatchResult).filter(
                MatchResult.candidate_id == application.candidate_id,
                MatchResult.job_id == application.job_id
            ).first()
            match_data = {
                "score":          mr.match_score,
                "matched_skills": mr.matched_skills or [],
                "missing_skills": mr.missing_skills or [],
                "summary":        mr.analysis,
            } if mr else None
            threading.Thread(
                target=_send_status_email,
                args=(candidate.email, candidate.full_name or "Candidate", job.title, status, match_data),
                daemon=True
            ).start()

    return {"message": f"Status updated to {status}"}

@router.delete("/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(application)
    db.commit()
    return {"message": "Application deleted"}