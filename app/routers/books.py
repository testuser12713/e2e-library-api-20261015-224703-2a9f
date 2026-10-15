"""Books router — stub routes; the feature logic is implemented by a later ticket."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.books import BookCreate, BookRead, BookUpdate
from ..schemas.common import Page
from ..security import require_api_key

router = APIRouter(prefix="/books", tags=["books"])

_NOT_IMPLEMENTED = "The books endpoints are not implemented yet"


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_book(payload: BookCreate) -> BookRead:
    """Create a book."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("", response_model=Page[BookRead])
def list_books(
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[BookRead]:
    """List books with search and pagination."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/{id}", response_model=BookRead)
def get_book(id: int) -> BookRead:
    """Return a single book."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.put(
    "/{id}",
    response_model=BookRead,
    dependencies=[Depends(require_api_key)],
)
def replace_book(id: int, payload: BookCreate) -> BookRead:
    """Fully update a book."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.patch(
    "/{id}",
    response_model=BookRead,
    dependencies=[Depends(require_api_key)],
)
def update_book(id: int, payload: BookUpdate) -> BookRead:
    """Partially update a book."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_book(id: int) -> None:
    """Delete a book."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
