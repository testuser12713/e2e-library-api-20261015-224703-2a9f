"""Members CRUD: creation, pagination, lookup and updates with unique emails."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import ApiError
from ..models import Loan, Member, utcnow
from ..schemas.common import Page
from ..schemas.members import MemberCreate, MemberRead, MemberUpdate
from ..security import require_api_key

router = APIRouter(prefix="/members", tags=["members"])


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    SQLite stores datetimes without an offset, so a value read back from the
    database is naive even though it always represents UTC. A naive value is
    therefore interpreted as UTC; an aware one is converted to UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_read(member: Member) -> MemberRead:
    """Build the API representation of a member with an explicit UTC member_since."""
    return MemberRead(
        id=member.id,
        name=member.name,
        email=member.email,
        member_since=_as_utc(member.member_since),
    )


def _get_member_or_404(db: Session, member_id: int) -> Member:
    """Return the member with ``member_id`` or raise a 404."""
    member = db.get(Member, member_id)
    if member is None:
        raise ApiError(404, "NOT_FOUND", f"Member {member_id} not found")
    return member


def _email_taken(db: Session, email: str, exclude_id: int | None = None) -> bool:
    """Return whether another member already holds ``email``."""
    stmt = select(Member.id).where(Member.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Member.id != exclude_id)
    return db.scalar(stmt) is not None


@router.post(
    "",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)) -> MemberRead:
    """Create a member, rejecting an email that already exists."""
    if _email_taken(db, payload.email):
        raise ApiError(409, "CONFLICT", f"A member with email {payload.email!r} already exists")

    member_since = payload.member_since if payload.member_since is not None else utcnow()
    member = Member(
        name=payload.name,
        email=payload.email,
        member_since=_as_utc(member_since),
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "CONFLICT", f"A member with email {payload.email!r} already exists"
        ) from None
    return _to_read(member)


@router.get("", response_model=Page[MemberRead])
def list_members(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[MemberRead]:
    """List members with pagination."""
    total = db.scalar(select(func.count()).select_from(Member)) or 0
    rows = db.scalars(select(Member).order_by(Member.id).limit(limit).offset(offset)).all()
    return Page[MemberRead](
        items=[_to_read(member) for member in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=MemberRead)
def get_member(id: int, db: Session = Depends(get_db)) -> MemberRead:
    """Return a single member."""
    return _to_read(_get_member_or_404(db, id))


@router.put(
    "/{id}",
    response_model=MemberRead,
    dependencies=[Depends(require_api_key)],
)
def replace_member(id: int, payload: MemberCreate, db: Session = Depends(get_db)) -> MemberRead:
    """Fully update a member."""
    member = _get_member_or_404(db, id)
    if _email_taken(db, payload.email, exclude_id=id):
        raise ApiError(409, "CONFLICT", f"A member with email {payload.email!r} already exists")

    member.name = payload.name
    member.email = payload.email
    if payload.member_since is not None:
        member.member_since = _as_utc(payload.member_since)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "CONFLICT", f"A member with email {payload.email!r} already exists"
        ) from None
    return _to_read(member)


@router.patch(
    "/{id}",
    response_model=MemberRead,
    dependencies=[Depends(require_api_key)],
)
def update_member(id: int, payload: MemberUpdate, db: Session = Depends(get_db)) -> MemberRead:
    """Partially update a member."""
    member = _get_member_or_404(db, id)
    changes = payload.model_dump(exclude_unset=True)

    new_email = changes.get("email")
    if (
        new_email is not None
        and new_email != member.email
        and _email_taken(db, new_email, exclude_id=id)
    ):
        raise ApiError(409, "CONFLICT", f"A member with email {new_email!r} already exists")

    if changes.get("name") is not None:
        member.name = changes["name"]
    if new_email is not None:
        member.email = new_email
    if changes.get("member_since") is not None:
        member.member_since = _as_utc(changes["member_since"])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CONFLICT", "A member with this email already exists") from None
    return _to_read(member)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_member(id: int, db: Session = Depends(get_db)) -> None:
    """Delete a member, refusing while the member still has open loans."""
    member = _get_member_or_404(db, id)
    open_loans = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.member_id == id, Loan.returned_at.is_(None))
    )
    if open_loans:
        raise ApiError(409, "CONFLICT", f"Member {id} has open loans")
    # Only closed loans can remain here; remove them first so the member's
    # mandatory foreign key is not nullified by SQLAlchemy's default cascade.
    db.execute(delete(Loan).where(Loan.member_id == id))
    db.delete(member)
    db.commit()
