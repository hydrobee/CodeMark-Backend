from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import Lecturer, AssignmentDB, User, Submission, Feedback, Grade, Lecturer, Student, User, Rubric
from schemas import Assignment, AssignmentOut, SubmissionOut, FeedbackOut, FeedbackCreate, RubricCreate, RubricOut
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

@router.post("/assignment/{assignment_id}/rubric", response_model=RubricOut, status_code=status.HTTP_201_CREATED)
def create_or_update_rubric(
    assignment_id: int,
    data: RubricCreate,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    # Verify assignment belongs to this lecturer
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id,
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Validate weights sum to 100
    total = sum(c.weight for c in data.criteria)
    if total != 100:
        raise HTTPException(status_code=400, detail=f"Rubric weights must sum to 100, got {total}")

    # Upsert — replace if already exists
    existing = db.query(Rubric).filter(Rubric.assignment_id == assignment_id).first()
    if existing:
        existing.criteria = [c.model_dump() for c in data.criteria]
        db.commit()
        db.refresh(existing)
        return existing

    rubric = Rubric(
        assignment_id=assignment_id,
        criteria=[c.model_dump() for c in data.criteria]
    )
    db.add(rubric)
    db.commit()
    db.refresh(rubric)
    return rubric


@router.get("/assignment/{assignment_id}/rubric", response_model=RubricOut)
def get_rubric(
    assignment_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    rubric = db.query(Rubric).filter(Rubric.assignment_id == assignment_id).first()
    if not rubric:
        raise HTTPException(status_code=404, detail="No rubric set for this assignment yet")
    return rubric

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

    # 1. Delete feedback first (references both assignment and submission)
    db.query(Feedback).filter(Feedback.assignment_id == assignment_id).delete(synchronize_session=False)
    
    # 2. Delete grades tied to submissions for this assignment
    submission_ids = db.query(Submission.submission_id).filter(
        Submission.assignment_id == assignment_id
    ).subquery()
    db.query(Grade).filter(Grade.submission_id.in_(submission_ids)).delete(synchronize_session=False)

    # 3. Delete submissions
    db.query(Submission).filter(Submission.assignment_id == assignment_id).delete(synchronize_session=False)

    # 4. Now safe to delete the assignment
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
            Feedback.strengths.label("strengths"),
            Feedback.areas_for_improvement.label("areas_for_improvement"),
            Feedback.grade.label("grade"),
            Feedback.released.label("released")
        )
        .join(AssignmentDB, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Student, Submission.student_id == Student.matric_no)
        .join(User, Student.user_id == User.user_id)
        .outerjoin(
            Feedback,
            (Feedback.assignment_id == Submission.assignment_id) &
            (Feedback.student_id == Submission.student_id)
        )
        .filter(AssignmentDB.lecturer_id == lecturer.lecturer_id)
        .all()
    )

    result = []
    for submission, title, course_name, student_name, feedback_text, strengths, areas, grade_score, released in submissions_data:
        # Only show feedback/grade if released
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
            "feedback": feedback_text if released else None,
            "strengths": strengths if released else None,
            "areas_for_improvement": areas if released else None,
            "grade": grade_score if released else None
        })

    return result

@router.get("/pending", response_model=List[FeedbackOut])
def view_ai_feedback(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    feedbacks = db.query(Feedback).filter(
        Feedback.lecturer_id == lecturer.lecturer_id,
        Feedback.status == "pending"
    ).all()

    return feedbacks

@router.put("/edit/{feedback_id}", response_model=FeedbackOut)
def edit_feedback(
    feedback_id: int,
    data: FeedbackCreate,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    feedback = db.query(Feedback).filter(
        Feedback.feedback_id == feedback_id,
        Feedback.lecturer_id == lecturer.lecturer_id
    ).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.comments = data.comments
    feedback.strengths = data.strengths
    feedback.areas_for_improvement = data.areas_for_improvement
    feedback.grade = data.grade

    db.commit()
    db.refresh(feedback)

    return feedback

@router.put("/approve/{feedback_id}")
def approve_feedback(
    feedback_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    feedback = db.query(Feedback).filter(
        Feedback.feedback_id == feedback_id,
        Feedback.lecturer_id == lecturer.lecturer_id
    ).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.status = "approved"
    feedback.released = True

    # Also approve the grade
    grade = db.query(Grade).filter(
        Grade.student_id == feedback.student_id,
        Grade.submission_id == db.query(Submission.submission_id).filter(
            Submission.assignment_id == feedback.assignment_id,
            Submission.student_id == feedback.student_id
        ).scalar_subquery()
    ).first()

    if grade:
        grade.approved = True

    db.commit()

    return {"message": "Feedback and grade approved and released to student"}

@router.put("/reject/{feedback_id}")
def reject_feedback(
    feedback_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):

    feedback = db.query(Feedback).filter(
        Feedback.feedback_id == feedback_id,
        Feedback.lecturer_id == lecturer.lecturer_id
    ).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.status = "rejected"

    db.commit()

    return {"message": "AI feedback rejected"}

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