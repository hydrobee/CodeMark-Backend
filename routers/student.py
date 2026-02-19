from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Student, AssignmentDB, User, Submission  
from schemas import AssignmentOut, SubmissionOut, SubmissionCreate
from typing import List
from auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/student", tags=["Student"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_student(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this resource")
    student = db.query(Student).filter(Student.user_id == current_user.user_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student

@router.get("/assignments", response_model=List[AssignmentOut])
def view_assignments(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    return db.query(AssignmentDB).all()

@router.post("/submit-assignment", response_model=SubmissionOut)
def submit_assignment(
    assignment_id: int,
    code: str,
    user: User = Depends(get_current_user),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    assignment = db.query(AssignmentDB).filter(AssignmentDB.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    existing = db.query(Submission).filter(  
        Submission.assignment_id == assignment_id,
        Submission.student_id == student.matric_no
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already submitted")

    submission = Submission(  
        assignment_id=assignment_id,
        student_id=student.matric_no,
        file_name="test",
        file_path=code,
        file_type="txt",
        submitted_at=datetime.utcnow()
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {
        "message": f"{user.name} submitted assignment {assignment_id}",
        "assignment": assignment
    }

@router.get("/my-submissions", response_model=List[SubmissionOut])
def get_my_submissions(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    return db.query(Submission).filter(Submission.student_id == student.matric_no).all()

@router.get("/profile")
def get_student_profile(
    student: Student = Depends(get_current_student),
    current_user: User = Depends(get_current_user)
):
    return {
        "matric_no": student.matric_no,
        "group_no": student.group_no,
        "name": current_user.name,
        "email": current_user.email
    }