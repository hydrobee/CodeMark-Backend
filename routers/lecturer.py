from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Lecturer, AssignmentDB, User
from schemas import Assignment, AssignmentOut
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
    """Get assignments created by the authenticated lecturer"""
    assignments = db.query(AssignmentDB).filter(
        AssignmentDB.lecturer_id == lecturer.lecturer_id
    ).all()
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