from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class CandidateOut(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = []
    education: Optional[Any] = None
    experience: Optional[Any] = None
    cv_filename: Optional[str] = None
    cluster_id: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True

class CandidateMatchResult(BaseModel):
    candidate: CandidateOut
    match_score: float