from typing import Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from app.db.base import BaseUUIDModel



class AuditLog(BaseUUIDModel, table=True):

    __tablename__ = "audit_log"

    actor_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True, nullable=True)
    action: str = Field(nullable=False, index=True)          # e.g., "CAMPAIGN_CLOSED", "DONATION_CREATED"
    target_type: str = Field(nullable=False, index=True)     # e.g., "Campaign", "Donation", "User"
    target_id: Optional[UUID] = Field(default=None, index=True, nullable=True)




class AuditLogRead(SQLModel):
    """Response DTO for exposing audit log records to administrators."""
    id: UUID
    actor_id: Optional[UUID]
    action: str
    target_type: str
    target_id: Optional[UUID]
    created_at: str