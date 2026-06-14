from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.services.device_auth import resolve_user_id


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> str:
    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    user_id = resolve_user_id(db, raw)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    return user_id


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
