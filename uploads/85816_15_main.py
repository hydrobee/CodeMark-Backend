from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers import lecturer, assignment, auth, student, administrator, feedback, grade

app = FastAPI(
    title="CodeMark Backend",
    description="API for managing assignments with role-based access",
    version="1.0.0"
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Include all routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(lecturer.router)
app.include_router(administrator.router)
app.include_router(assignment.router)
app.include_router(feedback.router)
app.include_router(grade.router)

@app.get("/")
def root():
    return {
        "message": "Assignment Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "authentication": "/auth",
            "student": "/student",
            "lecturer": "/lecturer",
            "administrator": "/admin",
            "assignments": "/assignments",
            "feedback": "/feedback"
        }
    }