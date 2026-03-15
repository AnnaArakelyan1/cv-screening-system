from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from utils.auth import get_current_user
from utils.email_sender import send_email
from models.user import User

router = APIRouter()

class EmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str

@router.post("/send")
def send_candidate_email(
    data: EmailRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        send_email(data.to_email, data.subject, data.body)
        return {"message": f"Email sent to {data.to_email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))