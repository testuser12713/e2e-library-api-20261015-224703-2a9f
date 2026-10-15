"""Books router — CRUD with case-insensitive search and pagination."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import ApiError
from ..models import Book, Loan
from ..schemas.books import BookCreate, BookRead, BookUpdate
from ..schemas.common import Page
from ..security import require_api_key

router = APIRouter(prefix="/books", tags=["books"])


def _get_book_or_404(db: Session, book_id: int) -> Book:
    """Return the book with ``book_id`` or report a uniform 404."""
    book = db.get(Book, book_id)
    if book is None:
        raise ApiError(404, "NOT_FOUND", f"Book {book_id} not found")
    return book


def _ensure_isbn_available(db: Session, isbn: str, *, exclude_id: int | None = None) -> None:
    """Report a uniform 409 when ``isbn`` already belongs to another book."""
    stmt = select(Book.id).where(Book.isbn == isbn)
    if exclude_id is not None:
        stmt = stmt.where(Book.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise ApiError(409, "CONFLICT", f"ISBN {isbn} is already taken")


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_book(payload: BookCreate, db: Session = Depends(get_db)) -> BookRead:
    """Create a book."""
    _ensure_isbn_available(db, payload.isbn)
    book = Book(**payload.model_dump())
    db.add(book)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", f"ISBN {payload.isbn} is already taken") from exc
    db.refresh(book)
    return BookRead.model_validate(book)


@router.get("", response_model=Page[BookRead])
def list_books(
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[BookRead]:
    """List books with search and pagination."""
    count_stmt = select(func.count()).select_from(Book)
    items_stmt = select(Book)
    if q:
        pattern = f"%{q.lower()}%"
        condition = or_(
            func.lower(Book.title).like(pattern),
            func.lower(Book.author).like(pattern),
        )
        count_stmt = count_stmt.where(condition)
        items_stmt = items_stmt.where(condition)
    total = db.execute(count_stmt).scalar_one()
    books = db.execute(items_stmt.order_by(Book.id).limit(limit).offset(offset)).scalars().all()
    return Page[BookRead](
        items=[BookRead.model_validate(book) for book in books],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=BookRead)
def get_book(id: int, db: Session = Depends(get_db)) -> BookRead:
    """Return a single book."""
    return BookRead.model_validate(_get_book_or_404(db, id))


@router.put(
    "/{id}",
    response_model=BookRead,
    dependencies=[Depends(require_api_key)],
)
def replace_book(id: int, payload: BookCreate, db: Session = Depends(get_db)) -> BookRead:
    """Fully update a book."""
    book = _get_book_or_404(db, id)
    _ensure_isbn_available(db, payload.isbn, exclude_id=id)
    for field, value in payload.model_dump().items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return BookRead.model_validate(book)


@router.patch(
    "/{id}",
    response_model=BookRead,
    dependencies=[Depends(require_api_key)],
)
def update_book(id: int, payload: BookUpdate, db: Session = Depends(get_db)) -> BookRead:
    """Partially update a book."""
    book = _get_book_or_404(db, id)
    changes = {
        field: value
        for field, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if "isbn" in changes:
        _ensure_isbn_available(db, changes["isbn"], exclude_id=id)
    for field, value in changes.items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return BookRead.model_validate(book)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_book(id: int, db: Session = Depends(get_db)) -> None:
    """Delete a book."""
    book = _get_book_or_404(db, id)
    open_loans = db.execute(
        select(func.count()).select_from(Loan).where(Loan.book_id == id, Loan.returned_at.is_(None))
    ).scalar_one()
    if open_loans:
        raise ApiError(409, "CONFLICT", f"Book {id} still has open loans")
    # The book has no open loans, so only closed loans remain. A loan row cannot
    # outlive its book (``loans.book_id`` is NOT NULL), so they go with it.
    db.execute(delete(Loan).where(Loan.book_id == id))
    db.delete(book)
    db.commit()
