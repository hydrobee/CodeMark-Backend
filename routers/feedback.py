from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Student, Lecturer, User, AssignmentDB, Feedback
from schemas import FeedbackCreate, FeedbackOut
from typing import List
from auth import get_current_user

router = APIRouter(prefix="/feedback", tags=["Feedback"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Student verification
# -----------------------------
def get_current_student(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this resource")
    
    student = db.query(Student).filter(Student.user_id == current_user.user_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    
    return student

# -----------------------------
# Lecturer verification
# -----------------------------
def get_current_lecturer(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only lecturers can access this resource")
    
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.user_id).first()
    if not lecturer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecturer profile not found")
    
    return lecturer

# -----------------------------
# Student views their feedback
# -----------------------------
@router.get("/student", response_model=List[FeedbackOut])
def feedback_student_view(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    feedbacks = db.query(Feedback).filter(Feedback.student_id == student.matric_no).all()
    return feedbacks

# # Student view feedback
# @router.get("/", response_model=List[FeedbackOut])
# def feedback_student_view(
#     student: Student = Depends(get_current_student),
#     db: Session = Depends(get_db)
# ):
    

# -----------------------------
# Lecturer creates feedback
# -----------------------------
@router.post("/", response_model=FeedbackOut)
def create_feedback(
    data: FeedbackCreate,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    assignment = db.query(AssignmentDB).filter(AssignmentDB.assignment_id == data.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(status_code=403, detail="You can only give feedback for your own assignments")
    
    new_feedback = Feedback(
        assignment_id=data.assignment_id,
        lecturer_id=lecturer.lecturer_id,
        student_id=data.student_id,
        comments=data.comments,
        strengths = data.strengths,
        areas_for_improvement = data.areas_for_improvement
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)
    return new_feedback

# -----------------------------
# Lecturer views feedback for their assignment
# -----------------------------
@router.get("/assignment/{assignment_id}", response_model=List[FeedbackOut])
def get_feedback_for_assignment(
    assignment_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    assignment = db.query(AssignmentDB).filter(AssignmentDB.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(status_code=403, detail="Not your assignment")
    
    feedbacks = db.query(Feedback).filter(Feedback.assignment_id == assignment_id).all()
    return feedbacks
