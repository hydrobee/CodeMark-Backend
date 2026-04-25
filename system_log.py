from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from models import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, nullable=True)          # user_id of who did the action
    actor_email = Column(String, nullable=True)        # email snapshot (handy if user is later deleted)
    action = Column(String, nullable=False)            # e.g. "APPROVE_LECTURER", "DELETE_USER"
    target_type = Column(String, nullable=True)        # e.g. "lecturer", "user"
    target_id = Column(String, nullable=True)          # ID of the affected record (stored as str for flexibility)
    detail = Column(Text, nullable=True)               # free-form extra context
    status = Column(String, default="success")         # "success" | "failure"
    created_at = Column(DateTime(timezone=True), server_default=func.now())