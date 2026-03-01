from sqlalchemy import Column, Integer, String, Float, DateTime, ARRAY, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    education = Column(Text, nullable=True)
    experience = Column(Text, nullable=True)
    skills = Column(ARRAY(String), nullable=True)
    raw_text = Column(Text, nullable=True)
    cv_filename = Column(String, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())