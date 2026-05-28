from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Student, AssignmentDB, User, Submission, Feedback, Grade, Rubric, Lecturer
from schemas import AssignmentOut, SubmissionOut, SubmissionCreate
from typing import List, Optional
from auth import get_current_user
from datetime import datetime, timezone, timedelta
from AI.ai_grader import check_code_with_ai, check_submission_with_files
from supabase_storage import upload_to_supabase, download_to_tmp
import os

router = APIRouter(prefix="/student", tags=["Student"])

MY_TZ = timezone(timedelta(hours=8))

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
        assignment = db.query(AssignmentDB).filter(
            AssignmentDB.assignment_id == assignment_id
        ).first()

        rubric = db.query(Rubric).filter(
            Rubric.assignment_id == assignment_id
        ).first()

        # Download all files from Supabase to /tmp
        local_submission_path = download_to_tmp(file_path)

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        if ext == '.pdf':
            submission_mime = 'application/pdf'
        elif ext == '.docx':
            submission_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            submission_mime = 'text/plain'

        question_path = download_to_tmp(assignment.question_file_path if assignment else None)
        rubric_path = download_to_tmp(rubric.rubric_file_path if rubric else None)
        local_submission_path = download_to_tmp(file_path)
        print(f"[DEBUG] local_submission_path: {local_submission_path}")
        print(f"[DEBUG] exists: {os.path.exists(local_submission_path)}")

        ai_result = check_submission_with_files(
            criteria=criteria,
            submission_file_path=local_submission_path,
            submission_mime_type=submission_mime,
            question_file_path=question_path,
            question_mime_type=assignment.question_file_type if assignment else None,
            rubric_file_path=rubric_path,
            rubric_mime_type=rubric.rubric_file_type if rubric else None,
        )

        grade = Grade(
            submission_id=submission_id,
            student_id=student_id,
            final_score=ai_result["percentage"],
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
            rubric_scores=ai_result.get("rubric_scores", []),
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
def view_assignments(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    assignments_data = (
        db.query(
            AssignmentDB,
            Submission.submission_id,
            Feedback.comments.label("feedback"),
            Grade.final_score.label("grade"),
            Rubric.rubric_file_path,
            Rubric.rubric_file_name,
            Rubric.rubric_file_type,
            User.name.label("lecturer_name"),
            User.email.label("lecturer_email"),
        )
        .outerjoin(
            Submission,
            (Submission.assignment_id == AssignmentDB.assignment_id) &
            (Submission.student_id == student.matric_no)
        )
        .outerjoin(
            Feedback,
            (Feedback.assignment_id == AssignmentDB.assignment_id) &
            (Feedback.student_id == student.matric_no) &
            (Feedback.released == True)
        )
        .outerjoin(
            Grade,
            (Grade.submission_id == Submission.submission_id) &
            (Grade.approved == True)
        )
        .outerjoin(Rubric, Rubric.assignment_id == AssignmentDB.assignment_id)
        .join(Lecturer, Lecturer.lecturer_id == AssignmentDB.lecturer_id)
        .join(User, User.user_id == Lecturer.user_id)
        .all()
    )

    result = []
    for (assignment, submission_id, feedback_text, grade_score,
         rubric_file_path, rubric_file_name, rubric_file_type,
         lecturer_name, lecturer_email) in assignments_data:

        result.append({
            "assignment_id": assignment.assignment_id,
            "lecturer_id": assignment.lecturer_id,
            "course_name": assignment.course_name,
            "title": assignment.title,
            "description": assignment.description,
            "deadline": assignment.deadline,
            "question_file_name": assignment.question_file_name,
            "question_file_path": assignment.question_file_path,
            "question_file_type": assignment.question_file_type,
            "rubric_file_name": rubric_file_name,
            "rubric_file_path": rubric_file_path,
            "rubric_file_type": rubric_file_type,
            "submission_status": "Submitted" if submission_id else "No submissions have been made yet",
            "feedback": feedback_text if feedback_text is not None else "Pending for Feedback",
            "grade": grade_score if grade_score is not None else "Not Graded",
            "lecturer_name": lecturer_name,
            "lecturer_email": lecturer_email,
        })

    return result


@router.post("/submit-assignment", response_model=SubmissionOut)
async def submit_assignment(
    assignment_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    group_no: Optional[str] = None,
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
    allowed_extensions = [".py", ".java", ".cpp", ".c++", ".js", ".c"]
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # 4. Check rubric exists
    rubric = db.query(Rubric).filter(Rubric.assignment_id == assignment_id).first()
    if not rubric:
        raise HTTPException(status_code=400, detail="Lecturer has not set a rubric for this assignment yet")

    # 5. Upload file to Supabase Storage
    file_bytes = await file.read()
    safe_filename = f"{student.matric_no}_{assignment_id}_{file.filename}"
    file_path = upload_to_supabase(file_bytes, safe_filename, "submissions")

    # 6. Save submission
    submission = Submission(
        assignment_id=assignment.assignment_id,
        student_id=student.matric_no,
        group_no=group_no,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext,
        submitted_at=datetime.now(MY_TZ).replace(tzinfo=None)
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 7. Fetch user for response
    user = db.query(User).filter(User.user_id == student.user_id).first()

    # 8. AI grading background task
    background_db = SessionLocal()
    background_tasks.add_task(
        run_ai_grading,
        submission_id=submission.submission_id,
        assignment_id=assignment.assignment_id,
        lecturer_id=assignment.lecturer_id,
        student_id=student.matric_no,
        file_path=file_path,
        criteria=rubric.criteria,
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
        group_no=group_no,
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
        "name": current_user.name,
        "email": current_user.email
    }


@router.get("/performance")
def student_performance(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    print(f"/performance hit for student: {student.matric_no}")
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