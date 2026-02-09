from pydantic import BaseModel, EmailStr
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    ADMINISTRATOR = "administrator"

# User Registration
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    # Additional fields based on role
    matric_no: str = None  # For students
    group_no: str = None   # For students
    staff_id: str = None   # For lecturers

# User Login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# User Response
class UserOut(BaseModel):
    user_id: int
    name: str
    email: str
    role: UserRole

    class Config:
        from_attributes = True  # Updated from orm_mode

# Token Response
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

# Assignment
class Assignment(BaseModel):
    lecturer_id: int
    title: str
    description: str
    deadline: datetime

# For returning an assignment (response)
class AssignmentOut(BaseModel):
    assignment_id: int
    lecturer_id: int
    title: str
    description: str
    deadline: datetime

    class Config:
        from_attributes = True

class LecturerBase(BaseModel):
    name: str
    email: str

class LecturerOut(LecturerBase):
    lecturer_id: int
    staff_id: str

    class Config:
        from_attributes = True

class StudentOut(BaseModel):
    matric_no: str
    group_no: str
    user_id: int

    class Config:
        from_attributes = True