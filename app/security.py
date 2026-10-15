"""Authentication dependencies.

``require_api_key`` guards every write route: it reads the ``X-API-Key`` header
and compares it in constant time with the configured ``LIBRARY_API_KEY``. A
missing or wrong key is reported as ``401 UNAUTHORIZED`` in the uniform error
body.
"""

import secrets

from fastapi import Header

from .config import settings
from .errors import ApiError


def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """Validate the ``X-API-Key`` header against the configured key.

    Raises :class:`ApiError` with status ``401`` when the header is missing or
    does not match; returns ``None`` when it is valid. The comparison is done in
    constant time so the header value cannot be probed byte by byte.
    """
    expected = settings.library_api_key
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise ApiError(401, "UNAUTHORIZED", "A valid X-API-Key header is required")
