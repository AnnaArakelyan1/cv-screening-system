from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from database import get_db
from models.user import User
from schemas.user import UserOut
from utils.auth import get_current_user, hash_password, verify_password
from routers.auth import validate_password

router = APIRouter()

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class SetPassword(BaseModel):
    new_password: str

@router.patch("/me", response_model=UserOut)
def update_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.full_name:
        current_user.full_name = data.full_name.strip()

    if data.email and data.email != current_user.email:
        if db.query(User).filter(User.email == data.email, User.id != current_user.id).first():
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = data.email

    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(data.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        validate_password(data.new_password)
        current_user.hashed_password = hash_password(data.new_password)

    db.commit()
    db.refresh(current_user)
    return current_user

@router.patch("/{user_id}/set-password")
def set_password(
    user_id: int,
    data: SetPassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can set passwords")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    validate_password(data.new_password)
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": f"Password updated for {user.email}"}

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/", response_model=List[UserOut])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return db.query(User).all()

@router.delete("/me")
def delete_own_account(current_user: User = Depends(get_current_user)):
    raise HTTPException(status_code=403, detail="Account deletion must be done by an administrator")

@router.patch("/{user_id}/toggle-active")
def toggle_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate an admin account")
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active}

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} deleted"}