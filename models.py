from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime

Base = declarative_base()

class UserRole(str, enum.Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    ADMINISTRATOR = "administrator"

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # Will store hashed password
    role = Column(Enum(UserRole), nullable=False)

class Student(Base):
    __tablename__ = "students"
    
    matric_no = Column(String, primary_key=True)
    group_no = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)

    user = relationship("User")

class Lecturer(Base):
    __tablename__ = "lecturers"

    lecturer_id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    status = Column(String, default="pending")

    user = relationship("User")

class AssignmentDB(Base):
    __tablename__ = "assignment_list"
    
    assignment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lecturer_id = Column(Integer, ForeignKey('lecturers.lecturer_id'), nullable=False)
    course_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    deadline = Column(DateTime, nullable=False)

class Feedback(Base):
    __tablename__ = "feedback_list"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignment_list.assignment_id"), nullable=False)
    lecturer_id = Column(Integer, ForeignKey("lecturers.lecturer_id"), nullable=False)
    student_id = Column(String, ForeignKey("students.matric_no"), nullable=False)
    comments = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)

class Submission(Base):
    __tablename__ = "submission_list"

    submission_id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignment_list.assignment_id"), nullable=False)
    student_id = Column(String, ForeignKey("students.matric_no"), nullable=False)

    # Submission File Info
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)

    submitted_at = Column(DateTime, nullable=False)

    student = relationship("Student")
    assignment = relationship("AssignmentDB")

class Grade(Base):
    __tablename__ = "grade_list"

    grade_id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer,ForeignKey("submission_list.submission_id"), nullable=False)
    student_id = Column(String, ForeignKey("students.matric_no"), nullable=False)
    final_score = Column(Float, nullable=True)
    approved = Column(Boolean, nullable=False, default=False)
