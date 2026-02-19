from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Student, Lecturer, User, AssignmentDB, Grade, Submission
from schemas import GradeCreate, GradeOut
from typing import List
from auth import get_current_user

router = APIRouter(prefix="/grade", tags=["Grade"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Student Verification
def get_current_student(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access this resource")
    
    student = db.query(Student).filter(Student.user_id == current_user.user_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    
    return student

# Lecturer Verification
def get_current_lecturer(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only lecturers can access this resource")
    
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.user_id).first()
    if not lecturer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecturer profile not found")
    
    return lecturer

# Student views their grade
@router.get("/student", response_model=List[GradeOut])
def grade_student_view(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    grades = db.query(Grade).filter(
        Grade.student_id == student.matric_no,
        Grade.approved == True
        ).all()
    return grades

# Lecturer create grade
@router.post("/", response_model=GradeOut)
def final_score(
    data: GradeCreate,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(
        Submission.submission_id == data.submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == submission.assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Authorization check
    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(
            status_code=403,
            detail="You can only grade submissions for your own assignments"
        )

    # Prevent duplicate grading
    existing_grade = db.query(Grade).filter(
        Grade.submission_id == data.submission_id
    ).first()

    if existing_grade:
        raise HTTPException(
            status_code=400,
            detail="This submission has already been graded"
        )

    final_score_approval = Grade(
        submission_id=data.submission_id,
        final_score=data.final_score,
        student_id=submission.student_id
    )

    db.add(final_score_approval)
    db.commit()
    db.refresh(final_score_approval)

    return final_score_approval

@router.patch("/{grade_id}/approve")
def approve_grade(
    grade_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    grade = db.query(Grade).filter(Grade.grade_id == grade_id).first()

    if not grade:
        raise HTTPException(404, "Grade not found")

    grade.approved = True
    db.commit()
    db.refresh(grade)

    return grade




