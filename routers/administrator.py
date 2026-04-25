from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload
from database import SessionLocal
from models import User, Student, Lecturer
from auth import get_current_user
from system_log import SystemLog
from log_utils import write_log
from datetime import datetime
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/admin", tags=["Administrator"])


# ---------------------------------------------------------------------------
# DB / Auth helpers
# ---------------------------------------------------------------------------

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
            detail="Only administrators can access this resource",
        )
    return current_user


# ---------------------------------------------------------------------------
# User / Student / Lecturer reads
# ---------------------------------------------------------------------------

@router.get("/users")
def get_all_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role: student, lecturer, administrator"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort_by: str = Query("created_at", description="Sort by: name, email, role, created_at"),
    sort_order: str = Query("desc", description="asc or desc"),
):
    """
    Get all users with unified view, search, filter, and pagination.
    """
    query = db.query(User).options(
        joinedload(User.student),
        joinedload(User.lecturer)
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )

    if role:
        role = role.lower()
        if role in ["student", "lecturer", "administrator"]:
            query = query.filter(User.role == role)

    # Count before pagination — use a subquery to avoid joinedload inflating count
    total = db.query(User).filter(query.whereclause).count() if query.whereclause is not None else db.query(User).count()

    if sort_by == "name":
        order_column = User.name
    elif sort_by == "email":
        order_column = User.email
    elif sort_by == "role":
        order_column = User.role
    else:
        order_column = User.created_at if hasattr(User, 'created_at') else User.user_id

    if sort_order.lower() == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    users = query.offset(offset).limit(limit).all()

    result = []
    for user in users:
        user_data: Dict[str, Any] = {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None,
        }

        # ✅ Use the already-loaded relationships — no extra DB queries
        if user.role == "student" and user.student:
            user_data.update({
                "matric_no": getattr(user.student, "matric_no", None),
                "group_no": getattr(user.student, "group_no", None),
            })
        elif user.role == "lecturer" and user.lecturer:
            user_data.update({
                "lecturer_id": user.lecturer.lecturer_id,
                "staff_id": user.lecturer.staff_id,
                "status": user.lecturer.status,
            })

        result.append(user_data)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": result
    }


@router.get("/students")
def get_all_students(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    students = db.query(Student).join(User).all()
    return [
        {
            "matric_no": s.matric_no,
            "group_no": s.group_no,
            "name": s.user.name,
            "email": s.user.email,
        }
        for s in students
    ]


@router.get("/lecturers")
def get_all_lecturers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lecturers = db.query(Lecturer).join(User).all()
    return [
        {
            "lecturer_id": l.lecturer_id,
            "staff_id": l.staff_id,
            "name": l.user.name,
            "email": l.user.email,
            "status": l.status,
        }
        for l in lecturers
    ]


@router.get("/pending-lecturers")
def get_pending_lecturers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
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


# ---------------------------------------------------------------------------
# Lecturer status update
# ---------------------------------------------------------------------------

@router.patch("/lecturer/{lecturer_id}/status")
def update_lecturer_status(
    lecturer_id: int,
    action: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    action = action.lower()

    if action not in ["approved", "rejected", "approve", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be approve/approved or reject/rejected",
        )

    if action == "approve":
        action = "approved"
    elif action == "reject":
        action = "rejected"

    lecturer = db.query(Lecturer).filter(Lecturer.lecturer_id == lecturer_id).first()
    if not lecturer:
        write_log(
            db,
            action="UPDATE_LECTURER_STATUS",
            actor_id=admin.user_id,
            actor_email=admin.email,
            target_type="lecturer",
            target_id=lecturer_id,
            detail=f"Attempted to {action} lecturer ID {lecturer_id} — not found",
            status="failure",
        )
        raise HTTPException(status_code=404, detail="Lecturer not found")

    lecturer.status = action
    db.commit()

    write_log(
        db,
        action="UPDATE_LECTURER_STATUS",
        actor_id=admin.user_id,
        actor_email=admin.email,
        target_type="lecturer",
        target_id=lecturer_id,
        detail=f"Lecturer '{lecturer.user.name}' (staff_id={lecturer.staff_id}) status set to '{action}'",
    )

    return {"message": f"Lecturer {action} successfully"}


# ---------------------------------------------------------------------------
# Delete user
# ---------------------------------------------------------------------------

@router.delete("/user/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from models import AssignmentDB, Submission, Feedback, Grade, Rubric

    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        write_log(
            db,
            action="DELETE_USER",
            actor_id=admin.user_id,
            actor_email=admin.email,
            target_type="user",
            target_id=user_id,
            detail=f"Attempted to delete user ID {user_id} — not found",
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    if user.role == "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be deleted",
        )

    deleted_email = user.email
    deleted_role = user.role

    try:
        if user.role == "student":
            student = db.query(Student).filter(Student.user_id == user_id).first()
            if student:
                matric = student.matric_no

                # 1️⃣ Get all submission IDs for this student
                submission_ids = [
                    s.submission_id
                    for s in db.query(Submission.submission_id)
                                .filter(Submission.student_id == matric).all()
                ]

                # 2️⃣ Delete grades tied to those submissions
                if submission_ids:
                    db.query(Grade).filter(Grade.submission_id.in_(submission_ids)).delete(synchronize_session=False)

                # 3️⃣ Delete feedback for this student
                db.query(Feedback).filter(Feedback.student_id == matric).delete(synchronize_session=False)

                # 4️⃣ Delete submissions
                db.query(Submission).filter(Submission.student_id == matric).delete(synchronize_session=False)

                # 5️⃣ Delete student row
                db.delete(student)

        elif user.role == "lecturer":
            lecturer = db.query(Lecturer).filter(Lecturer.user_id == user_id).first()
            if lecturer:
                lid = lecturer.lecturer_id

                # 1️⃣ Get all assignment IDs for this lecturer
                assignment_ids = [
                    a.assignment_id
                    for a in db.query(AssignmentDB.assignment_id)
                                .filter(AssignmentDB.lecturer_id == lid).all()
                ]

                if assignment_ids:
                    # 2️⃣ Get all submission IDs under those assignments
                    submission_ids = [
                        s.submission_id
                        for s in db.query(Submission.submission_id)
                                    .filter(Submission.assignment_id.in_(assignment_ids)).all()
                    ]

                    # 3️⃣ Delete grades tied to those submissions
                    if submission_ids:
                        db.query(Grade).filter(Grade.submission_id.in_(submission_ids)).delete(synchronize_session=False)

                    # 4️⃣ Delete feedback under those assignments
                    db.query(Feedback).filter(Feedback.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)

                    # 5️⃣ Delete submissions under those assignments
                    db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)

                    # 6️⃣ Delete rubrics under those assignments
                    db.query(Rubric).filter(Rubric.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)

                    # 7️⃣ Delete the assignments themselves
                    db.query(AssignmentDB).filter(AssignmentDB.lecturer_id == lid).delete(synchronize_session=False)

                # 8️⃣ Delete any feedback this lecturer issued (different assignments)
                db.query(Feedback).filter(Feedback.lecturer_id == lid).delete(synchronize_session=False)

                # 9️⃣ Delete lecturer row
                db.delete(lecturer)

        db.delete(user)
        db.commit()

    except Exception as e:
        db.rollback()
        write_log(
            db,
            action="DELETE_USER",
            actor_id=admin.user_id,
            actor_email=admin.email,
            target_type="user",
            target_id=user_id,
            detail=f"Failed to delete {deleted_role} '{deleted_email}': {str(e)}",
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}",
        )

    write_log(
        db,
        action="DELETE_USER",
        actor_id=admin.user_id,
        actor_email=admin.email,
        target_type="user",
        target_id=user_id,
        detail=f"Deleted {deleted_role} account '{deleted_email}'",
    )

    return {"message": f"User {deleted_email} deleted successfully"}


# ---------------------------------------------------------------------------
# System logs endpoint
# ---------------------------------------------------------------------------

@router.get("/system-logs")
def view_system_logs(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    action: Optional[str] = Query(None, description="Filter by action keyword, e.g. DELETE_USER"),
    actor_id: Optional[int] = Query(None, description="Filter by actor user_id"),
    target_type: Optional[str] = Query(None, description="Filter by target type, e.g. lecturer"),
    log_status: Optional[str] = Query(None, alias="status", description="Filter by status: success | failure"),
    from_date: Optional[datetime] = Query(None, description="ISO datetime lower bound, e.g. 2024-01-01T00:00:00"),
    to_date: Optional[datetime] = Query(None, description="ISO datetime upper bound"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return (1–1000)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Return audit logs, newest first.
    """
    query = db.query(SystemLog)

    if action:
        query = query.filter(SystemLog.action.ilike(f"%{action}%"))
    if actor_id is not None:
        query = query.filter(SystemLog.actor_id == actor_id)
    if target_type:
        query = query.filter(SystemLog.target_type == target_type)
    if log_status:
        query = query.filter(SystemLog.status == log_status)
    if from_date:
        query = query.filter(SystemLog.created_at >= from_date)
    if to_date:
        query = query.filter(SystemLog.created_at <= to_date)

    total = query.count()
    logs = query.order_by(desc(SystemLog.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "log_id": log.log_id,
                "actor_id": log.actor_id,
                "actor_email": log.actor_email,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "detail": log.detail,
                "status": log.status,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ---------------------------------------------------------------------------
# Backup stub
# ---------------------------------------------------------------------------

@router.post("/backup-system")
def backup_system(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    write_log(
        db,
        action="BACKUP_SYSTEM",
        actor_id=admin.user_id,
        actor_email=admin.email,
        detail="Manual backup triggered",
    )
    return {"message": "System backup feature - to be implemented"}