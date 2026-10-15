"""The uniform error contract of the API and its exception handlers.

Every failure — whatever its origin — answers with
``{"error": {"code": ..., "message": ..., "details": ...}}``.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """A route-reported failure rendered through the uniform error body."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


_STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Build the uniform ``{"error": {...}}`` payload."""
    return {"error": {"code": code, "message": message, "details": details}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Render an :class:`ApiError`."""
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_body(exc.code, exc.message, exc.details)),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render a request validation failure as ``422 VALIDATION_ERROR``."""
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(error_body("VALIDATION_ERROR", "Validation failed", exc.errors())),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render any other HTTP error (not found, method not allowed, stubs)."""
    code = _STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_body(code, message, None)),
        headers=getattr(exc, "headers", None),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every error handler to the application."""
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
