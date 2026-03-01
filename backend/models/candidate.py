from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    skills = Column(ARRAY(String), default=[])
    education = Column(JSONB, default=[])
    experience = Column(JSONB, default=[])
    raw_text = Column(String, nullable=True)
    cv_filename = Column(String, nullable=True)
    embedding = Column(ARRAY(Float), nullable=True)
    cluster_id = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())