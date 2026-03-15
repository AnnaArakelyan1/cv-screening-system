from fastapi import APIRouter, Depends, HTTPException
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

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own job postings")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}