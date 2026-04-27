from pydantic import BaseModel, EmailStr
from datetime import datetime
from enum import Enum
from typing import Optional, Union, List

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
    matric_no: Optional[str] = None
   # group_no: Optional[str] = None
    staff_id: Optional[str] = None

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
        from_attributes = True

# Token Response
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

# Assignment (request body)
class Assignment(BaseModel):
    lecturer_id: int
    course_name: str
    title: str
    description: str
    deadline: datetime
    submission_status: Optional[str] = None

# Assignment (response) — includes question file fields
class AssignmentOut(BaseModel):
    assignment_id: int
    lecturer_id: int
    course_name: str
    title: str
    description: str
    deadline: datetime
    submission_status: Optional[str] = None
    submission_id: Optional[str] = None
    feedback: Optional[str] = None
    grade: Union[float, str, None] = None

    # Question file fields (already there)
    question_file_name: Optional[str] = None
    question_file_path: Optional[str] = None
    question_file_type: Optional[str] = None

    # === ADD THESE RUBRIC FIELDS ===
    rubric_file_name: Optional[str] = None
    rubric_file_path: Optional[str] = None
    rubric_file_type: Optional[str] = None

    class Config:
        from_attributes = True

class LecturerBase(BaseModel):
    name: str
    email: str

class LecturerOut(BaseModel):
    lecturer_id: int
    staff_id: str
    user_id: int
    name: str = None

    model_config = {"from_attributes": True}

class StudentOut(BaseModel):
    matric_no: str
   # group_no: str
    user_id: int
    name: str = None

    model_config = {"from_attributes": True}

# Feedback
class FeedbackCreate(BaseModel):
    assignment_id: Optional[int] = None
    student_id: Optional[str] = None

class FeedbackOut(BaseModel):
    feedback_id: int
    assignment_id: int
    lecturer_id: int
    student_id: str
    submission_status: str | None = None
    grade: Union[float, str, None] = None
    comments: str | None
    strengths: str | None
    areas_for_improvement: str | None

    model_config = {"from_attributes": True}

class SubmissionCreate(BaseModel):
    assignment_id: int
    group_no: Optional[str] = None

class SubmissionOut(BaseModel):
    submission_id: int
    assignment_id: int
    title: str
    course_name: str
    student_id: str
    group_no: Optional[str] = None
    student_name: str
    feedback_id: Optional[int] = None
    file_name: str
    file_path: str
    file_type: str
    submitted_at: datetime

    grade: Optional[float] = None
    grade_status: Optional[str] = None
    comments: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None

    model_config = {"from_attributes": True}

class GradeCreate(BaseModel):
    submission_id: int
    final_score: float
    student_id: str

class GradeOut(BaseModel):
    grade_id: int
    submission_id: int
    student_id: str
    final_score: float
    approved: bool = False

    model_config = {"from_attributes": True}

class RubricCriteria(BaseModel):
    name: str
    weight: int  # all weights must sum to 100

class RubricCreate(BaseModel):
    criteria: List[RubricCriteria]

# Rubric (response) — includes rubric file fields
class RubricOut(BaseModel):
    rubric_id: int
    assignment_id: int
    criteria: List[RubricCriteria]

    # Rubric document upload fields
    rubric_file_name: Optional[str] = None
    rubric_file_path: Optional[str] = None
    rubric_file_type: Optional[str] = None

    model_config = {"from_attributes": True}