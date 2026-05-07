import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import lecturer, assignment, auth, student, administrator, feedback, grade
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from system_log import SystemLog

RENDER_URL = "https://codemark-ai-assisted-student-programming.onrender.com"

async def keep_alive():
    while True:
        await asyncio.sleep(900)  
        try:
            async with httpx.AsyncClient() as client:
                await client.get(f"{RENDER_URL}/health")
                print("Keep-alive ping sent")
        except Exception as e:
            print(f"Keep-alive failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(keep_alive())
    yield

app = FastAPI(
    title="CodeMark Backend",
    description="API for managing assignments with role-based access",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "https://code-mark-frontend-vcwp.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

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