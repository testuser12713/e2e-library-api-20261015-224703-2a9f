"""Members router — stub routes; the feature logic is implemented by a later ticket."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.common import Page
from ..schemas.members import MemberCreate, MemberRead, MemberUpdate
from ..security import require_api_key

router = APIRouter(prefix="/members", tags=["members"])

_NOT_IMPLEMENTED = "The members endpoints are not implemented yet"


@router.post(
    "",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_member(payload: MemberCreate) -> MemberRead:
    """Create a member."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("", response_model=Page[MemberRead])
def list_members(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[MemberRead]:
    """List members with pagination."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/{id}", response_model=MemberRead)
def get_member(id: int) -> MemberRead:
    """Return a single member."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.put(
    "/{id}",
    response_model=MemberRead,
    dependencies=[Depends(require_api_key)],
)
def replace_member(id: int, payload: MemberCreate) -> MemberRead:
    """Fully update a member."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.patch(
    "/{id}",
    response_model=MemberRead,
    dependencies=[Depends(require_api_key)],
)
def update_member(id: int, payload: MemberUpdate) -> MemberRead:
    """Partially update a member."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_member(id: int) -> None:
    """Delete a member."""
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
