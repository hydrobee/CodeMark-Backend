from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import AssignmentDB, Lecturer, User
from schemas import AssignmentOut, Assignment
from auth import get_current_user
from typing import List

router = APIRouter(prefix="/assignments", tags=["Assignments"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_lecturer(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "lecturer":
        raise HTTPException(status_code=403, detail="Only lecturers can access this resource")
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.user_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer profile not found")
    return lecturer

# Public - all assignments (for students to view)
@router.get("/", response_model=List[AssignmentOut])
def view_assignments(db: Session = Depends(get_db)):
    assignments = db.query(AssignmentDB).all()
    return assignments

# Lecturer - only their own assignments
@router.get("/my-assignments", response_model=List[AssignmentOut])
def get_my_assignments(
    lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    assignments = db.query(AssignmentDB).filter(
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).all()
    return assignments

# Public - get single assignment by ID
@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment_by_id(assignment_id: int, db: Session = Depends(get_db)):
    assignment = db.query(AssignmentDB).filter(
        AssignmentDB.assignment_id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment