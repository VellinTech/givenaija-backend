from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.domains.audit.models import AuditLog
from app.db.firestore import write_activity_feed_entry


def log_event(
    session: Session,
    action: str,
    target_type: str,
    actor_id: Optional[UUID] = None,
    target_id: Optional[UUID] = None
) -> AuditLog:
    
    # Appends a new immutable entry to the audit log.
    # Must be called within an active database transaction.
    
    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id
    )
    session.add(audit_entry)
    # Flushed/committed by caller or explicitly committed here
    session.flush()

    # Postgres row above is the real audit trail. This is just a mirror
    # for the admin dashboard's live feed, so it's fire-and-forget.
    write_activity_feed_entry({
        "actor_id": str(actor_id) if actor_id else None,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return audit_entry


def get_audit_logs(
    session: Session,
    skip: int = 0,
    limit: int = 50,
    actor_id: Optional[UUID] = None,
    action: Optional[str] = None
) -> List[AuditLog]:
    
    # Retrieves a paginated list of audit records with optional actor/action filtering.
    
    statement = select(AuditLog)

    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(AuditLog.action == action)

    statement = statement.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    return session.exec(statement).all()