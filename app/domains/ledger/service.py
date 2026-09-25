from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.domains.ledger.models import (
    Account, AccountCreate, 
    JournalEntry, JournalEntryCreate, 
    JournalLine, JournalLineRead, JournalEntryRead
)


def create_account(session: Session, account_in: AccountCreate) -> Account:
    """Creates a new ledger account code."""
    existing = session.exec(select(Account).where(Account.code == account_in.code)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account with code '{account_in.code}' already exists."
        )

    account = Account(
        code=account_in.code,
        name=account_in.name,
        account_type=account_in.account_type.value
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


# Single shared account every donation's cash lands in. Auto-created the
# first time it's needed -- no manual seed step required.
CASH_ACCOUNT_CODE = "1010"


def get_or_create_cash_account(session: Session) -> Account:
    account = session.exec(select(Account).where(Account.code == CASH_ACCOUNT_CODE)).first()
    if account:
        return account

    account = Account(
        code=CASH_ACCOUNT_CODE,
        name="Cash - Bank",
        account_type="ASSET"
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


# One revenue account per campaign, so the ledger can report donation
# revenue broken out by campaign, not just as one lump sum. Code is
# derived from the campaign's own id so it's stable and auto-created.
def get_or_create_campaign_revenue_account(session: Session, campaign_id: UUID, campaign_title: str) -> Account:
    code = f"4000-{str(campaign_id)[:8]}"
    account = session.exec(select(Account).where(Account.code == code)).first()
    if account:
        return account

    account = Account(
        code=code,
        name=f"Donation Revenue - {campaign_title}",
        account_type="REVENUE"
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def list_accounts(session: Session) -> List[Account]:
    """Retrieves all general ledger accounts."""
    return session.exec(select(Account).order_by(Account.code)).all()


def post_journal_entry(session: Session, entry_in: JournalEntryCreate) -> JournalEntryRead:
    """
    Posts a double-entry transaction.
    Validates that:
    1. At least two lines are present (Debit and Credit).
    2. Sum of Debits strictly equals Sum of Credits.
    """
    if len(entry_in.lines) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A double-entry transaction requires at least two lines."
        )

    total_debits = sum((line.debit for line in entry_in.lines), Decimal("0.00"))
    total_credits = sum((line.credit for line in entry_in.lines), Decimal("0.00"))

    # Strict double-entry accounting rule check
    if total_debits != total_credits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unbalanced journal entry: Total Debits ({total_debits}) != Total Credits ({total_credits})"
        )

    # 1. Persist Header
    entry = JournalEntry(
        description=entry_in.description,
        reference_id=entry_in.reference_id
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # 2. Persist Lines
    line_responses = []
    for line_in in entry_in.lines:
        account = session.get(Account, line_in.account_id)
        if not account:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account ID {line_in.account_id} not found."
            )

        line = JournalLine(
            journal_entry_id=entry.id,
            account_id=line_in.account_id,
            debit=line_in.debit,
            credit=line_in.credit
        )
        session.add(line)
        session.commit()
        session.refresh(line)

        line_responses.append(
            JournalLineRead(
                id=line.id,
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit
            )
        )

    return JournalEntryRead(
        id=entry.id,
        description=entry.description,
        reference_id=entry.reference_id,
        created_at=entry.created_at.isoformat(),
        lines=line_responses
    )


def get_journal_entry_by_id(session: Session, entry_id: UUID) -> JournalEntryRead:
    """Retrieves a complete journal entry with all line items."""
    entry = session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found."
        )

    lines = session.exec(select(JournalLine).where(JournalLine.journal_entry_id == entry.id)).all()

    return JournalEntryRead(
        id=entry.id,
        description=entry.description,
        reference_id=entry.reference_id,
        created_at=entry.created_at.isoformat(),
        lines=[
            JournalLineRead(
                id=l.id,
                account_id=l.account_id,
                debit=l.debit,
                credit=l.credit
            )
            for l in lines
        ]
    )