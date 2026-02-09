from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Student, Lecturer
from auth import get_current_user
from typing import List

router = APIRouter(prefix="/admin", tags=["Administrator"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_admin(current_user: User = Depends(get_current_user)):
    """Verify that the current user is an administrator"""
    if current_user.role != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this resource"
        )
    return current_user

@router.get("/users")
def get_all_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all users in the system"""
    users = db.query(User).all()
    return [{"user_id": u.user_id, "name": u.name, "email": u.email, "role": u.role} for u in users]

@router.get("/students")
def get_all_students(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all students"""
    students = db.query(Student).join(User).all()
    return students

@router.get("/lecturers")
def get_all_lecturers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all lecturers"""
    lecturers = db.query(Lecturer).join(User).all()
    return lecturers

@router.delete("/user/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user.email} deleted successfully"}

@router.get("/system-logs")
def view_system_logs(admin: User = Depends(get_current_admin)):
    """View system logs (placeholder)"""
    return {"message": "System logs feature - to be implemented"}

@router.post("/backup-system")
def backup_system(admin: User = Depends(get_current_admin)):
    """Backup the system (placeholder)"""
    return {"message": "System backup feature - to be implemented"}