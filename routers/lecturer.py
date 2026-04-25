import os
import shutil
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import Lecturer, AssignmentDB, User, Submission, Feedback, Grade, Student, Rubric
from schemas import Assignment, AssignmentOut, SubmissionOut, FeedbackOut, FeedbackCreate, RubricCreate, RubricOut
from typing import List
from auth import get_current_user
from AI.ai_grader import check_submission_with_files, check_code_with_ai

router = APIRouter(prefix="/lecturer", tags=["Lecturer"])

# ── Upload directories ─────────────────────────────────────────────────────────
QUESTION_UPLOAD_DIR = "uploads/assignment_questions"
RUBRIC_UPLOAD_DIR   = "uploads/rubrics"

# ── Allowed MIME types ─────────────────────────────────────────────────────────
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}

# ── MIME type map for submission files ────────────────────────────────────────
EXTENSION_MIME_MAP = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".py":   "text/plain",
    ".java": "text/plain",
    ".c":    "text/plain",
    ".cpp":  "text/plain",
    ".txt":  "text/plain",
    ".js":   "text/plain",
    ".ts":   "text/plain",
    ".html": "text/plain",
    ".css":  "text/plain",
}

# ── DB dependency ──────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Auth dependency ────────────────────────────────────────────────────────────
def get_current_lecturer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify that the current user is a lecturer."""
    if current_user.role != "lecturer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers can access this resource"
        )

    lecturer = db.query(Lecturer).filter(
        Lecturer.user_id == current_user.user_id
    ).first()

    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )

    return lecturer


# ══════════════════════════════════════════════════════════════════════════════
#  ASSIGNMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/my-assignments", response_model=List[AssignmentOut])
def get_my_assignments(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    assignments = db.query(AssignmentDB).filter(
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).all()
    return assignments or []


@router.post("/create-assignment", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    data: Assignment,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Create a new assignment (authenticated lecturer only)."""
    if data.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create assignments for yourself"
        )

    assignment_obj = AssignmentDB(
        lecturer_id=data.lecturer_id,
        course_name=data.course_name,
        title=data.title,
        description=data.description,
        deadline=data.deadline
    )
    db.add(assignment_obj)
    db.commit()
    db.refresh(assignment_obj)
    return assignment_obj


# ── Upload assignment question file (PDF / DOCX) ───────────────────────────────
@router.post("/assignment/{assignment_id}/upload-question", status_code=status.HTTP_200_OK)
def upload_assignment_question(
    assignment_id: int,
    file: UploadFile = File(...),
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF or DOCX file that contains the assignment question/brief.
    The AI grading service will use this file to understand the assignment
    objectives when evaluating student submissions.
    """
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id,
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are allowed"
        )

    if assignment.question_file_path and os.path.exists(assignment.question_file_path):
        os.remove(assignment.question_file_path)

    os.makedirs(QUESTION_UPLOAD_DIR, exist_ok=True)
    safe_filename = f"{assignment_id}_{file.filename}"
    file_path = os.path.join(QUESTION_UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    assignment.question_file_name = file.filename
    assignment.question_file_path = file_path
    assignment.question_file_type = file.content_type
    db.commit()

    return {
        "message": "Assignment question file uploaded successfully",
        "file_name": file.filename,
        "file_type": file.content_type
    }


@router.put("/update-assignment/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: Assignment,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Update an existing assignment (only by the creator)."""
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.lecturer_id != lecturer.lecturer_id:
        raise HTTPException(status_code=403, detail="You can only update your own assignments")

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
    """Delete an assignment (only by the creator)."""
    try:
        assignment = db.query(AssignmentDB).filter(
            AssignmentDB.assignment_id == assignment_id
        ).first()

        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment.lecturer_id != lecturer.lecturer_id:
            raise HTTPException(status_code=403, detail="You can only delete your own assignments")

        if assignment.question_file_path and os.path.exists(assignment.question_file_path):
            os.remove(assignment.question_file_path)

        # 1. Delete feedback first
        db.query(Feedback).filter(
            Feedback.assignment_id == assignment_id
        ).delete(synchronize_session=False)

        # 2. Delete grades tied to submissions of this assignment
        submission_ids = [
            row.submission_id
            for row in db.query(Submission.submission_id).filter(
                Submission.assignment_id == assignment_id
            ).all()
        ]
        if submission_ids:
            db.query(Grade).filter(
                Grade.submission_id.in_(submission_ids)
            ).delete(synchronize_session=False)

        # 3. Delete submissions
        db.query(Submission).filter(
            Submission.assignment_id == assignment_id
        ).delete(synchronize_session=False)

        # 4. Delete rubric file from disk + rubric record
        rubric = db.query(Rubric).filter(
            Rubric.assignment_id == assignment_id
        ).first()
        if rubric:
            if rubric.rubric_file_path and os.path.exists(rubric.rubric_file_path):
                os.remove(rubric.rubric_file_path)
            db.delete(rubric)
            db.flush()

        # 5. Finally delete the assignment
        db.delete(assignment)
        db.commit()

        return {"message": "Assignment deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"DELETE /delete-assignment/{assignment_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assignment/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """Get a specific assignment by ID."""
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return assignment


# ══════════════════════════════════════════════════════════════════════════════
#  RUBRIC — manual JSON criteria only, no file extraction
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/assignment/{assignment_id}/rubric",
    response_model=RubricOut,
    status_code=status.HTTP_201_CREATED
)
def create_or_update_rubric(
    assignment_id: int,
    data: RubricCreate,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """Create or replace the JSON criteria rubric for an assignment."""
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id,
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    total = sum(c.weight for c in data.criteria)
    if total != 100:
        raise HTTPException(
            status_code=400,
            detail=f"Rubric weights must sum to 100, got {total}"
        )

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


@router.post("/assignment/{assignment_id}/rubric/upload", status_code=status.HTTP_200_OK)
def upload_rubric_file(
    assignment_id: int,
    file: UploadFile = File(...),
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """
    Upload a rubric PDF or DOCX as a reference document for students.
    This file is stored on disk only — it is NEVER passed to the AI grader.
    Grading is driven solely by the JSON criteria saved in the database.
    """
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id,
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    rubric = db.query(Rubric).filter(Rubric.assignment_id == assignment_id).first()
    if not rubric:
        raise HTTPException(
            status_code=400,
            detail="Please create the rubric criteria first before uploading a rubric file"
        )

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are allowed"
        )

    # Remove old file if one exists
    if rubric.rubric_file_path and os.path.exists(rubric.rubric_file_path):
        os.remove(rubric.rubric_file_path)

    os.makedirs(RUBRIC_UPLOAD_DIR, exist_ok=True)
    safe_filename = f"{assignment_id}_{file.filename}"
    file_path = os.path.join(RUBRIC_UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    rubric.rubric_file_name = file.filename
    rubric.rubric_file_path = file_path
    rubric.rubric_file_type = file.content_type
    db.commit()

    return {
        "message": "Rubric reference file uploaded successfully",
        "file_name": file.filename,
        "file_type": file.content_type
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SUBMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

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
            Submission.group_no.label("group_no"),
            Feedback.feedback_id.label("feedback_id"),
            Feedback.comments.label("feedback"),
            Feedback.strengths.label("strengths"),
            Feedback.areas_for_improvement.label("areas_for_improvement"),
            Feedback.grade.label("grade"),
            Feedback.rubric_scores.label("rubric_scores"),
            Feedback.released.label("released"),
            Feedback.status.label("grade_status")
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
    for (
        submission, title, course_name, student_name, group_no,
        feedback_id, feedback_text, strengths, areas, grade_score,
        rubric_scores, released, grade_status
    ) in submissions_data:
        result.append({
            "submission_id": submission.submission_id,
            "assignment_id": submission.assignment_id,
            "title": title,
            "course_name": course_name,
            "student_id": submission.student_id,
            "student_name": student_name,
            "group_no": group_no,
            "feedback_id": feedback_id,
            "file_name": submission.file_name,
            "file_path": submission.file_path,
            "file_type": submission.file_type,
            "submitted_at": submission.submitted_at,
            "comments": feedback_text if released else None,
            "strengths": strengths if released else None,
            "areas_for_improvement": areas if released else None,
            "grade": grade_score if released else None,
            "rubric_scores": rubric_scores if released else [],
            "grade_status": grade_status
        })

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  PENDING FEEDBACK (AI-generated, awaiting lecturer review)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/pending")
def view_ai_feedback(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    feedbacks = (
        db.query(
            Feedback,
            AssignmentDB.title.label("title"),
            AssignmentDB.course_name.label("course_name"),
            User.name.label("student_name"),
            Submission.group_no.label("group_no"),
            Submission.submitted_at.label("submitted_at"),
            Submission.submission_id.label("submission_id")
        )
        .join(AssignmentDB, Feedback.assignment_id == AssignmentDB.assignment_id)
        .join(Student, Feedback.student_id == Student.matric_no)
        .join(User, Student.user_id == User.user_id)
        .join(
            Submission,
            (Submission.assignment_id == Feedback.assignment_id) &
            (Submission.student_id == Feedback.student_id)
        )
        .filter(
            Feedback.lecturer_id == lecturer.lecturer_id,
            Feedback.status == "pending"
        )
        .all()
    )

    result = []
    for fb, title, course_name, student_name, group_no, submitted_at, submission_id in feedbacks:
        feedback_dict = {
            column.name: getattr(fb, column.name)
            for column in Feedback.__table__.columns
        }
        feedback_dict.update({
            "title": title,
            "course_name": course_name,
            "student_name": student_name,
            "group_no": group_no,
            "submitted_at": submitted_at,
            "submission_id": submission_id,
        })
        result.append(feedback_dict)

    return result


@router.get("/pending/{feedback_id}")
def get_pending_feedback_detail(
    feedback_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    feedback = db.query(Feedback).filter(
        Feedback.feedback_id == feedback_id,
        Feedback.lecturer_id == lecturer.lecturer_id,
        Feedback.status == "pending"
    ).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Pending feedback not found")

    submission = (
        db.query(
            Submission,
            AssignmentDB.title,
            AssignmentDB.course_name,
            User.name.label("student_name"),
            Submission.group_no
        )
        .join(AssignmentDB, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Student, Submission.student_id == Student.matric_no)
        .join(User, Student.user_id == User.user_id)
        .filter(
            Submission.assignment_id == feedback.assignment_id,
            Submission.student_id == feedback.student_id
        )
        .first()
    )

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    sub, title, course_name, student_name, group_no = submission

    return {
        **feedback.__dict__,
        "submission_id": sub.submission_id,
        "file_name": sub.file_name,
        "file_path": sub.file_path,
        "submitted_at": sub.submitted_at,
        "student_name": student_name,
        "group_no": group_no,
        "course_name": course_name,
        "title": title,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GENERATE FEEDBACK ON DEMAND
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/submission/{submission_id}/generate-feedback")
def generate_feedback_for_submission(
    submission_id: int,
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    """
    Trigger AI feedback generation for a submission that has no feedback yet.
    """
    submission = (
        db.query(Submission)
        .join(AssignmentDB, Submission.assignment_id == AssignmentDB.assignment_id)
        .filter(
            Submission.submission_id == submission_id,
            AssignmentDB.lecturer_id == lecturer.lecturer_id
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    existing = db.query(Feedback).filter(
        Feedback.assignment_id == submission.assignment_id,
        Feedback.student_id == submission.student_id
    ).first()
    if existing:
        return {
            "feedback_id": existing.feedback_id,
            "message": "Feedback already exists"
        }

    rubric = db.query(Rubric).filter(
        Rubric.assignment_id == submission.assignment_id
    ).first()
    if not rubric or not rubric.criteria:
        raise HTTPException(
            status_code=400,
            detail="No rubric found for this assignment. Please set up a rubric first."
        )

    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == submission.assignment_id
    ).first()

    submission_mime = EXTENSION_MIME_MAP.get(
        submission.file_type.lower() if submission.file_type else "",
        "text/plain"
    )

    try:
        result = check_submission_with_files(
            criteria=rubric.criteria,
            submission_file_path=submission.file_path,
            submission_mime_type=submission_mime,
            question_file_path=getattr(assignment, "question_file_path", None),
            question_mime_type=getattr(assignment, "question_file_type", None),
            rubric_file_path=None,   # no rubric file — criteria come from DB only
            rubric_mime_type=None,
        )
    except Exception as e:
        print(f"AI grading failed for submission {submission_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI grading failed: {str(e)}"
        )

    feedback = Feedback(
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        lecturer_id=lecturer.lecturer_id,
        comments=result.get("comments"),
        strengths=result.get("strengths"),
        areas_for_improvement=result.get("improvements"),
        grade=result.get("percentage"),
        rubric_scores=result.get("rubric_scores", []),
        status="pending",
        released=False,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {
        "feedback_id": feedback.feedback_id,
        "message": "Feedback generated successfully"
    }


# ══════════════════════════════════════════════════════════════════════════════
#  FEEDBACK ACTIONS (edit / approve / reject)
# ══════════════════════════════════════════════════════════════════════════════

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

    submission = db.query(Submission).filter(
        Submission.assignment_id == feedback.assignment_id,
        Submission.student_id == feedback.student_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found for this feedback")

    grade = db.query(Grade).filter(
        Grade.submission_id == submission.submission_id,
        Grade.student_id == feedback.student_id
    ).first()

    if grade:
        grade.final_score = feedback.grade
        grade.approved = True
    else:
        grade = Grade(
            submission_id=submission.submission_id,
            student_id=feedback.student_id,
            final_score=feedback.grade,
            approved=True
        )
        db.add(grade)

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


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE & PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/profile")
def get_lecturer_profile(
    lecturer: Lecturer = Depends(get_current_lecturer),
    current_user: User = Depends(get_current_user)
):
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
            func.avg(Feedback.grade).label("average_score")
        )
        .join(Submission, Submission.assignment_id == AssignmentDB.assignment_id)
        .join(Feedback,
              (Feedback.assignment_id == Submission.assignment_id) &
              (Feedback.student_id == Submission.student_id))
        .filter(
            AssignmentDB.lecturer_id == lecturer.lecturer_id,
            Feedback.released == True,
            Feedback.grade.isnot(None)
        )
        .group_by(AssignmentDB.title)
        .all()
    )

    return [
        {
            "title": title,
            "average_score": round(float(avg), 2) if avg else 0.0
        }
        for title, avg in results
    ]


@router.get("/feedback/{feedback_id}", response_model=FeedbackOut)
def get_feedback(
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
    return feedback