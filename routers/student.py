from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Student, AssignmentDB, User
from schemas import AssignmentOut
from typing import List
from auth import get_current_user

router = APIRouter(prefix="/student", tags=["Student"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_student(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify that the current user is a student"""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this resource"
        )
    
    student = db.query(Student).filter(Student.user_id == current_user.user_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    return student

@router.get("/assignments", response_model=List[AssignmentOut])
def view_assignments(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get all available assignments for the student"""
    assignments = db.query(AssignmentDB).all()
    return assignments

@router.post("/submit-assignment/{assignment_id}")
def submit_assignment(
    assignment_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Submit an assignment"""
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    # You'll implement submission logic here
    return {
        "message": f"Student {student.matric_no} submitting assignment {assignment_id}",
        "assignment": assignment
    }

@router.get("/my-submissions")
def get_my_submissions(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get assignments submitted by this student"""
    # You'll need to create a Submission model for this
    return {"message": "Submissions endpoint - implement after creating Submission model"}

@router.get("/profile")
def get_student_profile(
    student: Student = Depends(get_current_student),
    current_user: User = Depends(get_current_user)
):
    """Get student profile information"""
    return {
        "matric_no": student.matric_no,
        "group_no": student.group_no,
        "name": current_user.name,
        "email": current_user.email
    }