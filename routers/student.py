from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from database import SessionLocal
from models import Student, AssignmentDB, User, Submission, Feedback, Grade, Rubric
from schemas import AssignmentOut, SubmissionOut, SubmissionCreate
from typing import List
from auth import get_current_user
from datetime import datetime
from AI.ai_grader import check_code_with_ai

import shutil
import os
import re
import json

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

def run_ai_grading(
    submission_id: int,
    assignment_id: int,
    lecturer_id: int,
    student_id: str,
    file_path: str,
    criteria: list,
    db: Session
):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        ai_result = check_code_with_ai(code_content, criteria)

        grade = Grade(
            submission_id=submission_id,
            student_id=student_id,
            final_score=ai_result["score"],
            approved=False
        )
        db.add(grade)

        feedback = Feedback(
            assignment_id=assignment_id,
            lecturer_id=lecturer_id,
            student_id=student_id,
            comments=ai_result["comments"],
            strengths=ai_result["strengths"],
            areas_for_improvement=ai_result["improvements"],
            grade=ai_result["score"],
            ai_generated=True,
            status="pending",
            released=False
        )
        db.add(feedback)
        db.commit()

    except Exception as e:
        db.rollback()
        print(f"AI grading failed for submission {submission_id}: {e}")
    finally:
        db.close()

@router.get("/", response_model=List[AssignmentOut])
def view_assignments(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):

    assignments_data = (
        db.query(
            AssignmentDB,
            Submission.submission_id,
            Feedback.comments.label("feedback"),
            Grade.final_score.label("grade")
        )
        .outerjoin(
            Submission,
            (Submission.assignment_id == AssignmentDB.assignment_id) &
            (Submission.student_id == student.matric_no)
        )
        # Only join feedback if it has been released by the lecturer
        .outerjoin(
            Feedback,
            (Feedback.assignment_id == AssignmentDB.assignment_id) &
            (Feedback.student_id == student.matric_no) &
            (Feedback.released == True)
        )
        # Only join grade if it has been approved by the lecturer
        .outerjoin(
            Grade,
            (Grade.submission_id == Submission.submission_id) &
            (Grade.approved == True)
        )
        .all()
    )

    result = []
    for assignment, submission_id, feedback_text, grade_score in assignments_data:
        result.append({
            "assignment_id": assignment.assignment_id,
            "lecturer_id": assignment.lecturer_id,
            "course_name": assignment.course_name,
            "title": assignment.title,
            "description": assignment.description,
            "deadline": assignment.deadline,
            "submission_status": "Submitted" if submission_id else "No submissions have been made yet",
            "feedback": feedback_text if feedback_text is not None else "Pending for Feedback",
            "grade": grade_score if grade_score is not None else "Not Graded"
        })

    return result

@router.post("/submit-assignment", response_model=SubmissionOut)
def submit_assignment(
    assignment_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # 1. Fetch assignment
    assignment = db.query(AssignmentDB).filter(AssignmentDB.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # 2. Check if already submitted
    existing = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == student.matric_no
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already submitted")

    # 3. Validate file extension
    allowed_extensions = [".py", ".java", ".cpp", ".js", ".c"]
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # 4. Check rubric exists before accepting submission
    rubric = db.query(Rubric).filter(Rubric.assignment_id == assignment_id).first()
    if not rubric:
        raise HTTPException(status_code=400, detail="Lecturer has not set a rubric for this assignment yet")

    # 5. Save file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{student.matric_no}_{assignment_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 6. Save submission immediately
    submission = Submission(
        assignment_id=assignment.assignment_id,
        student_id=student.matric_no,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext,
        submitted_at=datetime.utcnow()
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 7. Fetch user for response
    user = db.query(User).filter(User.user_id == student.user_id).first()

    # 8. Kick off AI grading in background (new db session so it doesn't conflict)
    background_db = SessionLocal()
    background_tasks.add_task(
        run_ai_grading,
        submission_id=submission.submission_id,
        assignment_id=assignment.assignment_id,
        lecturer_id=assignment.lecturer_id,
        student_id=student.matric_no,
        file_path=file_path,
        criteria=rubric.criteria,  # ← pass rubric criteria to AI grader
        db=background_db
    )

    # 9. Return immediately
    return SubmissionOut(
        submission_id=submission.submission_id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student_name=user.name,
        course_name=assignment.course_name,
        title=assignment.title,
        file_name=submission.file_name,
        file_path=submission.file_path,
        file_type=submission.file_type,
        submitted_at=submission.submitted_at,
        grade=None
    )

@router.get("/my-submissions", response_model=List[SubmissionOut])
def get_my_submissions(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    results = (
        db.query(
            Submission,
            AssignmentDB.title,
            AssignmentDB.course_name,
            User.name.label("student_name"),
            Feedback.comments,
            Feedback.strengths,
            Feedback.areas_for_improvement,
            Feedback.grade,
            Feedback.released
        )
        .join(AssignmentDB, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Student, Submission.student_id == Student.matric_no)
        .join(User, Student.user_id == User.user_id)
        # Only join feedback if it has been released by the lecturer
        .outerjoin(
            Feedback,
            (Feedback.assignment_id == Submission.assignment_id) &
            (Feedback.student_id == Submission.student_id) &
            (Feedback.released == True)
        )
        .filter(Submission.student_id == student.matric_no)
        .all()
    )

    submissions = []
    for result in results:
        submission, title, course_name, student_name, comments, strengths, improvements, grade, released = result

        submissions.append({
            "submission_id": submission.submission_id,
            "assignment_id": submission.assignment_id,
            "student_id": submission.student_id,
            "student_name": student_name,
            "title": title,
            "course_name": course_name,
            "file_name": submission.file_name,
            "file_path": submission.file_path,
            "file_type": submission.file_type,
            "submitted_at": submission.submitted_at,
            "grade": grade,
            "comments": comments,
            "strengths": strengths,
            "areas_for_improvement": improvements
        })

    return submissions


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


@router.get("/performance")
def student_performance(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    results = (
        db.query(
            AssignmentDB.course_name,
            AssignmentDB.title,
            Grade.final_score
        )
        .join(Submission, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Grade, Grade.submission_id == Submission.submission_id)
        .filter(Submission.student_id == student.matric_no)
        .filter(Grade.approved == True)
        .order_by(AssignmentDB.assignment_id)
        .all()
    )

    performance = []
    for course_name, title, score in results:
        performance.append({
            "course_name": course_name,
            "assignment": title,
            "score": score
        })

    return performance