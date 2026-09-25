from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.deps import get_session, require_roles
from app.domains.auth.models import UserRole
from app.domains.ledger.models import AccountCreate, AccountRead, JournalEntryCreate, JournalEntryRead
from app.domains.ledger import service

router = APIRouter(prefix="/ledger", tags=["General Ledger"])


@router.post(
    "/accounts",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))]
)
def create_account(account_in: AccountCreate, session: Session = Depends(get_session)):
    """Creates a new general ledger account code."""
    account = service.create_account(session, account_in)
    return AccountRead(
        id=account.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type
    )


@router.get(
    "/accounts",
    response_model=List[AccountRead],
    dependencies=[Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))]
)
def list_accounts(session: Session = Depends(get_session)):
    """Lists all general ledger accounts."""
    accounts = service.list_accounts(session)
    return [
        AccountRead(
            id=a.id,
            code=a.code,
            name=a.name,
            account_type=a.account_type
        )
        for a in accounts
    ]


@router.post(
    "/entries",
    response_model=JournalEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))]
)
def post_journal_entry(entry_in: JournalEntryCreate, session: Session = Depends(get_session)):
    """Posts a balanced double-entry transaction to the general ledger."""
    return service.post_journal_entry(session, entry_in)


@router.get(
    "/entries/{entry_id}",
    response_model=JournalEntryRead,
    dependencies=[Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))]
)
def get_journal_entry(entry_id: UUID, session: Session = Depends(get_session)):
    """Retrieves a journal entry with all line items."""
    return service.get_journal_entry_by_id(session, entry_id)