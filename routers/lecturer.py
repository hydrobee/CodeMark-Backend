from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import Lecturer, AssignmentDB, User, Submission, Feedback, Grade, Lecturer, Student, User
from schemas import Assignment, AssignmentOut, SubmissionOut
from typing import List
from auth import get_current_user

router = APIRouter(prefix="/lecturer", tags=["Lecturer"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_lecturer(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify that the current user is a lecturer"""
    if current_user.role != "lecturer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers can access this resource"
        )
    
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.user_id).first()
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    return lecturer

@router.get("/assignments", response_model=List[AssignmentOut])
def get_all_assignments(db: Session = Depends(get_db)):
    """Get all assignments"""
    assignments = db.query(AssignmentDB).all()
    return assignments

@router.get("/my-assignments", response_model=List[AssignmentOut])
def get_my_assignments(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    assignments = db.query(AssignmentDB).filter(
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).all()

    if not assignments:
        return []
    
    return assignments

@router.post("/create-assignment", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    data: Assignment,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Create a new assignment (authenticated lecturer only)"""
    
    # Ensure the lecturer_id in the data matches the authenticated lecturer
    if data.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create assignments for yourself"
        )

    assignment_obj = AssignmentDB(
        lecturer_id=data.lecturer_id,
        course_name= data.course_name,
        title=data.title,
        description=data.description,
        deadline=data.deadline
    )
    
    db.add(assignment_obj)
    db.commit()
    db.refresh(assignment_obj)
    
    return assignment_obj

@router.put("/update-assignment/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: Assignment,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Update an existing assignment (only by the creator)"""
    
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own assignments"
        )
    
    assignment.title = data.title
    assignment.description = data.description
    assignment.deadline = data.deadline
    
    db.commit()
    db.refresh(assignment)
    
    return assignment

@router.delete("/delete-assignment/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Delete an assignment (only by the creator)"""
    
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own assignments"
        )
    
    db.delete(assignment)
    db.commit()
    
    return {"message": "Assignment deleted successfully"}

@router.get("/assignment/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """Get a specific assignment by ID"""
    
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    return assignment

@router.get("/view-submission", response_model=List[SubmissionOut])
def view_submissions(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    submissions_data = (
        db.query(
            Submission,
            AssignmentDB.title.label("title"),
            AssignmentDB.course_name.label("course_name"),
            User.name.label("student_name"),
            Feedback.comments.label("feedback"),
            Grade.final_score.label("grade")
        )
        .join(AssignmentDB, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Student, Submission.student_id == Student.matric_no)
        .join(User, Student.user_id == User.user_id)
        .outerjoin(Feedback,
            (Feedback.assignment_id == AssignmentDB.assignment_id) &
            (Feedback.student_id == Submission.student_id)
        )
        .outerjoin(Grade, Grade.submission_id == Submission.submission_id)
        .filter(AssignmentDB.lecturer_id == lecturer.lecturer_id)
        .all()
    )

    if not submissions_data:
        return []

    result = []
    for submission, title, course_name, student_name, feedback_text, grade_score in submissions_data:
        result.append({
            "submission_id": submission.submission_id,
            "assignment_id": submission.assignment_id,
            "title": title,
            "course_name": course_name,
            "student_id": submission.student_id,
            "student_name": student_name,
            "file_name": submission.file_name,
            "file_path": submission.file_path,
            "file_type": submission.file_type,
            "submitted_at": submission.submitted_at,
            "feedback": feedback_text if feedback_text is not None else "Pending for Feedback",
            "grade": str(grade_score) if grade_score is not None else "Pending for Grading"
        })

    return result

@router.get("/profile")
def get_lecturer_profile(
    lecturer: Lecturer = Depends(get_current_lecturer),
    current_user: User = Depends(get_current_user)
):
    """Get lecturer profile information"""
    return {
        "lecturer_id": lecturer.lecturer_id,
        "staff_id": lecturer.staff_id,
        "name": current_user.name,
        "email": current_user.email
    }

@router.get("/performance")
def lecturer_performance(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    results = (
        db.query(
            AssignmentDB.title,
            func.avg(Grade.final_score).label("average_score")
        )
        .join(Submission, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Grade, Grade.submission_id == Submission.submission_id)
        .filter(AssignmentDB.lecturer_id == lecturer.lecturer_id)
        .group_by(AssignmentDB.title)
        .all()        
    )

    return [
        {"title": title, "average_score": round(float(avg), 2) if avg else 0} 
        for title, avg in results
    ]