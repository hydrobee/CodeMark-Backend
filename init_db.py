from database import engine
from models import Base

print("Creating tables...")

# This will create all tables defined in models.py
Base.metadata.create_all(bind=engine)

print("Tables created successfully!")
