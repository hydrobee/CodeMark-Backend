from sqlalchemy.orm import Session
from system_log import SystemLog


def write_log(
    db: Session,
    action: str,
    actor_id: int | None = None,
    actor_email: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
    status: str = "success",
):
    """
    Write a single audit entry to system_logs.

    Args:
        db:           Active SQLAlchemy session.
        action:       Short uppercase identifier, e.g. "APPROVE_LECTURER".
        actor_id:     user_id of the admin who triggered the action.
        actor_email:  Email snapshot of the actor.
        target_type:  The kind of entity being acted on ("user", "lecturer", …).
        target_id:    Primary-key of the target (cast to str for flexibility).
        detail:       Any extra human-readable context.
        status:       "success" (default) or "failure".
    """
    log = SystemLog(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
        status=status,
    )
    db.add(log)
    db.commit()