from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON
from datetime import datetime
from database import Base

class JobReport(Base):
    __tablename__ = "job_reports"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    data = Column(JSON, nullable=False)
