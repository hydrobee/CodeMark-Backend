from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import AssignmentDB
from schemas import AssignmentOut
from typing import List

router = APIRouter(prefix="/assignments", tags=["Assignments"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[AssignmentOut])
def get_all_assignments(db: Session = Depends(get_db)):
    """Get all assignments (public endpoint)"""
    assignments = db.query(AssignmentDB).all()
    return assignments

@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment_by_id(assignment_id: int, db: Session = Depends(get_db)):
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