from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.application import Application
from models.candidate import Candidate
from models.job import Job
from models.user import User
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

def _send_status_email(candidate_email: str, candidate_name: str, job_title: str, status: str):
    try:
        if status == "accepted":
            subject = f"Congratulations! Your application for {job_title} was accepted"
            body = (
                f"Dear {candidate_name},\n\n"
                f"We are pleased to inform you that your application for the position of "
                f"{job_title} has been accepted.\n\n"
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
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = application.status
    application.status = status
    db.commit()

    if status in ("accepted", "rejected") and status != old_status:
        candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
        job = db.query(Job).filter(Job.id == application.job_id).first()
        if candidate and candidate.email and job:
            threading.Thread(
                target=_send_status_email,
                args=(candidate.email, candidate.full_name or "Candidate", job.title, status),
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