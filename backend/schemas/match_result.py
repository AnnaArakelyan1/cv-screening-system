from pydantic import BaseModel
from datetime import datetime

class MatchResultOut(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    match_score: float
    created_at: datetime

    class Config:
        from_attributes = True