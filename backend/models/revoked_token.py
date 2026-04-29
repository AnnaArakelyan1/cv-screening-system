from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    token      = Column(String, unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
