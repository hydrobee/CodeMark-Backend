from database import SessionLocal
from models import Lecturer

db = SessionLocal()
test_lecturer = Lecturer(name="Dr. Tan", email="dr.tan@example.com", password="1234")
db.add(test_lecturer)
db.commit()
db.refresh(test_lecturer)
print("Lecturer ID:", test_lecturer.lecturer_id)
db.close()
