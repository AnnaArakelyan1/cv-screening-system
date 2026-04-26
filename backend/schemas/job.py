from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: List[str] = []
    required_experience_years: int = 0
    required_education: Optional[str] = None
    deadline: Optional[datetime] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    required_experience_years: Optional[int] = None
    required_education: Optional[str] = None
    deadline: Optional[datetime] = None

class JobOut(JobCreate):
    id: int
    is_open: bool = True
    deadline: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
