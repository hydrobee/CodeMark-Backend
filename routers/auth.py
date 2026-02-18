from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Student, Lecturer
from schemas import UserRegister, UserLogin, Token, UserOut
from auth import hash_password, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from datetime import timedelta
from typing import Optional
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password=hash_password(user_data.password),
        role=user_data.role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    if user_data.role == "student":
        if not user_data.matric_no or not user_data.group_no:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Matric number and group number required for students"
            )
        student = Student(
            matric_no=user_data.matric_no,
            group_no=user_data.group_no,
            user_id=new_user.user_id
        )
        db.add(student)
    
    elif user_data.role == "lecturer":
        if not user_data.staff_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff ID required for lecturers"
            )
        lecturer = Lecturer(
            staff_id=user_data.staff_id,
            user_id=new_user.user_id
        )
        db.add(lecturer)
    
    db.commit()

    # Notify lecturer that approval is pending
    if user_data.role == "lecturer":
        return JSONResponse(
            status_code=201,
            content={
                "message": "Registration successful. Your account is pending admin approval before you can log in.",
                "user": {
                    "user_id": new_user.user_id,
                    "name": new_user.name,
                    "email": new_user.email,
                    "role": new_user.role
                }
            }
        )

    return new_user


@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login user and return access token (OAuth2 compatible)"""
    
    user = db.query(User).filter(User.email == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Block pending/rejected lecturers
    if user.role == "lecturer":
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == user.user_id).first()
        if lecturer and lecturer.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending for admin approval" if lecturer.status == "pending" else "Your account has been rejected by the admin."
            )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.user_id, "email": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # Get role-specific data
    role_data = None

    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user.user_id).first()
        if student:
            role_data = {
                "matric_no": student.matric_no,
                "group_no": student.group_no
            }
    
    elif user.role == "lecturer":
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == user.user_id).first()
        if lecturer:
            role_data = {
                "lecturer_id": lecturer.lecturer_id,
                "staff_id": lecturer.staff_id,
                "status": lecturer.status
            }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "role_data": role_data
        }
    }


@router.post("/logout")
def logout():
    """Logout endpoint (client should delete token)"""
    return {"message": "Successfully logged out"}


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information with role-specific data"""
    
    role_data = None
    
    if current_user.role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.user_id).first()
        if student:
            role_data = {
                "matric_no": student.matric_no,
                "group_no": student.group_no
            }
    
    elif current_user.role == "lecturer":
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.user_id).first()
        if lecturer:
            role_data = {
                "lecturer_id": lecturer.lecturer_id,
                "staff_id": lecturer.staff_id,
                "status": lecturer.status
            }
    
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "role_data": role_data
    }