from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class CandidateOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    education: Optional[str]
    experience: Optional[str]
    skills: Optional[List[str]]
    cv_filename: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class CandidateMatchResult(BaseModel):
    candidate: CandidateOut
    match_score: float