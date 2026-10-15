"""Loans router — creating loans, returning them, listing and overdue."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import ApiError
from ..models import Book, Loan, Member, utcnow
from ..schemas.common import Page
from ..schemas.loans import LoanCreate, LoanRead
from ..security import require_api_key

router = APIRouter(prefix="/loans", tags=["loans"])

LOAN_PERIOD = timedelta(days=14)
MAX_OPEN_LOANS_PER_MEMBER = 3


def _utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_optional(value: datetime | None) -> datetime | None:
    """Return ``value`` as a timezone-aware UTC datetime, or ``None``."""
    return None if value is None else _utc(value)


def _to_read(loan: Loan) -> LoanRead:
    """Build the API representation of a loan with UTC timestamps."""
    return LoanRead(
        id=loan.id,
        book_id=loan.book_id,
        member_id=loan.member_id,
        loaned_at=_utc(loan.loaned_at),
        due_at=_utc(loan.due_at),
        returned_at=_utc_optional(loan.returned_at),
    )


@router.post(
    "",
    response_model=LoanRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_loan(payload: LoanCreate, db: Session = Depends(get_db)) -> LoanRead:
    """Create a loan, enforcing the three lending rules."""
    book = db.get(Book, payload.book_id)
    if book is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Book not found")
    member = db.get(Member, payload.member_id)
    if member is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Member not found")

    open_loans_for_member = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.member_id == member.id, Loan.returned_at.is_(None))
    )
    if (open_loans_for_member or 0) >= MAX_OPEN_LOANS_PER_MEMBER:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            "Member already has the maximum number of open loans",
        )

    open_loans_for_book = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.book_id == book.id, Loan.returned_at.is_(None))
    )
    if (open_loans_for_book or 0) >= book.total_copies:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            "No free copy of this book is available",
        )

    loaned_at = utcnow()
    loan = Loan(
        book_id=book.id,
        member_id=member.id,
        loaned_at=loaned_at,
        due_at=loaned_at + LOAN_PERIOD,
        returned_at=None,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return _to_read(loan)


@router.get("", response_model=Page[LoanRead])
def list_loans(
    member_id: int | None = Query(None),
    book_id: int | None = Query(None),
    active: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[LoanRead]:
    """List loans with filters and pagination."""
    filters = []
    if member_id is not None:
        filters.append(Loan.member_id == member_id)
    if book_id is not None:
        filters.append(Loan.book_id == book_id)
    if active is True:
        filters.append(Loan.returned_at.is_(None))
    elif active is False:
        filters.append(Loan.returned_at.is_not(None))

    total = db.scalar(select(func.count()).select_from(Loan).where(*filters)) or 0
    loans = db.scalars(
        select(Loan).where(*filters).order_by(Loan.id).limit(limit).offset(offset)
    ).all()
    return Page[LoanRead](
        items=[_to_read(loan) for loan in loans],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/overdue", response_model=list[LoanRead])
def list_overdue_loans(db: Session = Depends(get_db)) -> list[LoanRead]:
    """List all overdue loans, sorted by due_at ascending."""
    now = utcnow()
    loans = db.scalars(
        select(Loan)
        .where(Loan.returned_at.is_(None), Loan.due_at < now)
        .order_by(Loan.due_at.asc())
    ).all()
    return [_to_read(loan) for loan in loans]


@router.get("/{id}", response_model=LoanRead)
def get_loan(id: int, db: Session = Depends(get_db)) -> LoanRead:
    """Return a single loan."""
    loan = db.get(Loan, id)
    if loan is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Loan not found")
    return _to_read(loan)


@router.post(
    "/{id}/return",
    response_model=LoanRead,
    dependencies=[Depends(require_api_key)],
)
def return_loan(id: int, db: Session = Depends(get_db)) -> LoanRead:
    """Return a loan, freeing its copy."""
    loan = db.get(Loan, id)
    if loan is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Loan not found")
    if loan.returned_at is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "CONFLICT", "Loan already returned")

    loan.returned_at = utcnow()
    db.commit()
    db.refresh(loan)
    return _to_read(loan)
