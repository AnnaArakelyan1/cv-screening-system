from sqlalchemy.orm import Session
from models.audit_log import AuditLog

def log_action(db: Session, user, action: str, details: dict = None):
    entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        action=action,
        details=details or {},
    )
    db.add(entry)
    db.commit()
