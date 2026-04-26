from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from database import Base

class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"))
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"))
    match_score = Column(Float, nullable=True)
    matched_skills = Column(ARRAY(String), nullable=True)
    missing_skills = Column(ARRAY(String), nullable=True)
    experience_match = Column(String, nullable=True)
    education_match = Column(String, nullable=True)
    analysis = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())