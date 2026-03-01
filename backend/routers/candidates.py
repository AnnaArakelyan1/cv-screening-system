from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.candidate import Candidate
from models.user import User
from schemas.candidate import CandidateOut
from utils.auth import get_current_user
from utils.cv_parser import parse_cv
from utils.matcher import get_embedding, cluster_candidates
from typing import List

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
    embedding = get_embedding(parsed["raw_text"])

    candidate = Candidate(
        **parsed,
        cv_filename=file.filename,
        embedding=embedding,
        uploaded_by=current_user.id
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
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
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted successfully"}