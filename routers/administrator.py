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
    users = db.query(User).all()
    return [{"user_id": u.user_id, "name": u.name, "email": u.email, "role": u.role} for u in users]

@router.get("/students")
def get_all_students(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    students = db.query(Student).join(User).all()
    return [
        {
            "matric_no": s.matric_no,
            "group_no": s.group_no,
            "name": s.user.name,
            "email": s.user.email
        }
        for s in students
    ]

@router.get("/lecturers")
def get_all_lecturers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    lecturers = db.query(Lecturer).join(User).all()
    return [
        {
            "lecturer_id": l.lecturer_id,
            "staff_id": l.staff_id,
            "name": l.user.name,
            "email": l.user.email,
            "status": l.status
        }
        for l in lecturers
    ]

@router.get("/pending-lecturers")
def get_pending_lecturers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    lecturers = db.query(Lecturer).filter(Lecturer.status == "pending").all()
    return [
        {
            "lecturer_id": l.lecturer_id,
            "staff_id": l.staff_id,
            "name": l.user.name,
            "email": l.user.email,
        }
        for l in lecturers
    ]

@router.patch("/lecturer/{lecturer_id}/status")
def update_lecturer_status(
    lecturer_id: int,
    action: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if action not in ["approved", "rejected", "approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approved' or 'rejected'")
    
    lecturer = db.query(Lecturer).filter(Lecturer.lecturer_id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    
    lecturer.status = action
    db.commit()
    return {"message": f"Lecturer {action} successfully"}

@router.delete("/user/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
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
    
    # Delete role-specific record first before deleting user
    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user_id).first()
        if student:
            db.delete(student)
    
    elif user.role == "lecturer":
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == user_id).first()
        if lecturer:
            db.delete(lecturer)
    
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user.email} deleted successfully"}

@router.get("/system-logs")
def view_system_logs(admin: User = Depends(get_current_admin)):
    return {"message": "System logs feature - to be implemented"}

@router.post("/backup-system")
def backup_system(admin: User = Depends(get_current_admin)):
    return {"message": "System backup feature - to be implemented"}