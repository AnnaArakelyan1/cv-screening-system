from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.application import Application
from models.candidate import Candidate
from models.job import Job
from models.user import User
from schemas.application import ApplicationCreate, ApplicationOut
from utils.auth import get_current_user
from typing import List

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

@router.get("/job/{job_id}", response_model=List[ApplicationOut])
def get_applications_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Application).filter(Application.job_id == job_id).all()

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
    application.status = status
    db.commit()
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