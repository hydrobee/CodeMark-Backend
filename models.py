from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import enum

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

class Lecturer(Base):
    __tablename__ = "lecturers"

    lecturer_id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)

class AssignmentDB(Base):
    __tablename__ = "assignment_list"
    
    assignment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lecturer_id = Column(Integer, ForeignKey('lecturers.lecturer_id'), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    deadline = Column(DateTime, nullable=False)