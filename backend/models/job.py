from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, ARRAY, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    required_skills = Column(ARRAY(String), default=[])
    required_experience_years = Column(Integer, default=0)
    required_education = Column(String, nullable=True)
    embedding = Column(ARRAY(Float), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())