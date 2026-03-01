from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.candidate import Candidate
from models.user import User
from schemas.job import JobCreate, JobOut
from schemas.candidate import CandidateMatchResult, CandidateOut
from utils.auth import get_current_user
from utils.matcher import get_embedding, calculate_match_score
from typing import List

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

@router.get("/{job_id}/match", response_model=List[CandidateMatchResult])
def match_candidates(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = db.query(Candidate).filter(Candidate.embedding != None).all()
    results = []
    for candidate in candidates:
        score = calculate_match_score(candidate.embedding, job.embedding)
        results.append({"candidate": candidate, "match_score": score})

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results
