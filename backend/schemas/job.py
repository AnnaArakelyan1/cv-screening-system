from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: List[str] = []
    required_experience_years: int = 0
    required_education: Optional[str] = None

class JobOut(JobCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True