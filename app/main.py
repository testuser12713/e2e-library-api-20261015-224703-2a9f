"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models  # noqa: F401  (registers the ORM models on Base.metadata)
from .config import settings
from .database import Base, engine
from .errors import register_exception_handlers
from .routers import books, loans, members


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration and make sure the schema exists on startup."""
    _ = settings.library_api_key  # refuse to start when the key is not configured
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    """Build the FastAPI application with every router and error handler."""
    app = FastAPI(title="Stadtbibliothek API", version="0.1.0", lifespan=lifespan)

    register_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    app.include_router(books.router)
    app.include_router(members.router)
    app.include_router(loans.router)

    return app


app = create_app()
