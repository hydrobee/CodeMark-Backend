from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# replace YOUR_PASSWORD with your PostgreSQL password
DATABASE_URL = "postgresql+psycopg://postgres:Unimas!021112131121@localhost:5432/codemark_fyp_database"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)