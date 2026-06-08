from typing import Annotated

from fastapi import Header, HTTPException

from pribilka.config import get_settings


def require_admin_api_key(
    x_admin_api_key: Annotated[str | None, Header()] = None,
) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="Admin API is not configured (set ADMIN_API_KEY)",
        )
    if not x_admin_api_key or x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
