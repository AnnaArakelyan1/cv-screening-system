from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ApplicationCreate(BaseModel):
    candidate_id: int
    job_id: int

class ApplicationOut(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    status: str
    applied_at: datetime

    class Config:
        from_attributes = True