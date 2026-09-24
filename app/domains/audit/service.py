"""
Audit Domain Business Logic.

Provides transaction-safe append-only logging helpers and administrator
query operations for auditing compliance.
"""

from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select
from app.domains.audit.models import AuditLog


def log_event(
    session: Session,
    action: str,
    target_type: str,
    actor_id: Optional[UUID] = None,
    target_id: Optional[UUID] = None
) -> AuditLog:
    """
    Stages a new audit_log row for insertion (session.add only).

    IMPORTANT: this function does NOT commit. The whole point of the audit
    trail is that it is written in the SAME transaction as the business
    change it records — so the caller (e.g. create_donation, create_campaign)
    must call session.commit() itself, exactly once, after calling this and
    everything else that belongs to that one business action. If this
    function committed on its own, a crash between this commit and the
    caller's own commit could leave an audit row with no matching donation,
    or a donation with no matching audit row — precisely what the brief's
    "append-only audit trail" guarantee exists to prevent.
    """
    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id
    )
    session.add(audit_entry)
    return audit_entry


def get_audit_logs(
    session: Session,
    skip: int = 0,
    limit: int = 50,
    actor_id: Optional[UUID] = None,
    action: Optional[str] = None
) -> List[AuditLog]:
    """
    Retrieves a paginated list of audit records with optional actor/action filtering.
    """
    statement = select(AuditLog)

    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(AuditLog.action == action)

    statement = statement.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    return session.exec(statement).all()