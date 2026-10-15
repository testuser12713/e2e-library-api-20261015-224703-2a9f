"""SQLAlchemy 2.0 ORM models — the shared data contract of the library API."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    This is the single source of timestamps in the product.
    """
    return datetime.now(UTC)


class Book(Base):
    """A book title held by the library."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    publication_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False)

    loans: Mapped[list[Loan]] = relationship(back_populates="book")


class Member(Base):
    """A registered library member."""

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    member_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    loans: Mapped[list[Loan]] = relationship(back_populates="member")


class Loan(Base):
    """A loan of one book copy to one member."""

    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    loaned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    book: Mapped[Book] = relationship(back_populates="loans")
    member: Mapped[Member] = relationship(back_populates="loans")
