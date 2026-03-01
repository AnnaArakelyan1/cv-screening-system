from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.candidate import Candidate
from models.user import User
from models.match_result import MatchResult
from schemas.job import JobCreate, JobOut
from schemas.candidate import CandidateMatchResult
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

        # Save or update match result in database
        existing = db.query(MatchResult).filter(
            MatchResult.candidate_id == candidate.id,
            MatchResult.job_id == job_id
        ).first()

        if existing:
            existing.match_score = score
        else:
            match_result = MatchResult(
                candidate_id=candidate.id,
                job_id=job_id,
                match_score=score
            )
            db.add(match_result)

        results.append({"candidate": candidate, "match_score": score})

    db.commit()
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results

@router.get("/{job_id}/match/history")
def get_match_history(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = db.query(MatchResult).filter(MatchResult.job_id == job_id).all()
    return results


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}