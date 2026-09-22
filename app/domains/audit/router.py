"""
Audit Domain API Routes.

Restricted routes allowing system administrators to inspect security
and operational audit logs.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.deps import get_session, require_roles
from app.domains.auth.models import User, UserRole
from app.domains.audit.models import AuditLogRead
from app.domains.audit import service

router = APIRouter(prefix="/admin/audit-log", tags=["Audit Log"])


@router.get(
    "",
    response_model=List[AuditLogRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles([UserRole.ADMIN.value]))]
)
def fetch_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    actor_id: Optional[UUID] = Query(default=None),
    action: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    """
    Retrieves system audit logs. Restricted strictly to users with the 'admin' role.
    """
    logs = service.get_audit_logs(
        session=session,
        skip=skip,
        limit=limit,
        actor_id=actor_id,
        action=action
    )
    
    # Format output model timestamps
    return [
        AuditLogRead(
            id=log.id,
            actor_id=log.actor_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]

