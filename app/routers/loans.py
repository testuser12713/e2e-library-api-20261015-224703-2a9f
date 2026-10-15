"""Loans router — stub routes; the feature logic is implemented by a later ticket."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.common import Page
from ..schemas.loans import LoanCreate, LoanRead
from ..security import require_api_key

router = APIRouter(prefix="/loans", tags=["loans"])

_NOT_IMPLEMENTED = "The loans endpoints are not implemented yet"


@router.post(
    "",
    response_model=LoanRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_loan(payload: LoanCreate) -> LoanRead:
    """Create a loan."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("", response_model=Page[LoanRead])
def list_loans(
    member_id: int | None = Query(None),
    book_id: int | None = Query(None),
    active: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[LoanRead]:
    """List loans with filters and pagination."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/overdue", response_model=list[LoanRead])
def list_overdue_loans() -> list[LoanRead]:
    """List all overdue loans."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/{id}", response_model=LoanRead)
def get_loan(id: int) -> LoanRead:
    """Return a single loan."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.post(
    "/{id}/return",
    response_model=LoanRead,
    dependencies=[Depends(require_api_key)],
)
def return_loan(id: int) -> LoanRead:
    """Return a loan."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
