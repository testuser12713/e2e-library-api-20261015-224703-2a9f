"""Authentication dependencies.

The API-key check itself is implemented by the ticket that protects the write
endpoints. This module only fixes the dependency signature every write route
declares.
"""

from fastapi import Header


def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """Validate the ``X-API-Key`` header.

    Enforcement is added by a later ticket; for now the dependency accepts every
    call so the skeleton routes stay reachable.
    """
    return None
