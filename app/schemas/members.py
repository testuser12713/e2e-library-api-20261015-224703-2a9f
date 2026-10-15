"""Member request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemberCreate(BaseModel):
    """Payload for creating a member."""

    name: str
    email: str
    member_since: datetime | None = None


class MemberUpdate(BaseModel):
    """Payload for partially updating a member; every field is optional."""

    name: str | None = None
    email: str | None = None
    member_since: datetime | None = None


class MemberRead(BaseModel):
    """A member as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    member_since: datetime
