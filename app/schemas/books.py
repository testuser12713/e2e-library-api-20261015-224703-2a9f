"""Book request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class BookCreate(BaseModel):
    """Payload for creating a book."""

    title: str
    author: str
    isbn: str
    publication_year: int
    total_copies: int = Field(ge=1)


class BookUpdate(BaseModel):
    """Payload for partially updating a book; every field is optional."""

    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    publication_year: int | None = None
    total_copies: int | None = Field(default=None, ge=1)


class BookRead(BaseModel):
    """A book as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: str
    publication_year: int
    total_copies: int
