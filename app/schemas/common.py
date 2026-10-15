"""Shared Pydantic schemas."""

from pydantic import BaseModel


class Page[T](BaseModel):
    """The pagination envelope used by the list endpoints."""

    items: list[T]
    total: int
    limit: int
    offset: int
