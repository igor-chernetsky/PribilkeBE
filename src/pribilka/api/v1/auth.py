from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from pribilka.api.rate_limit import limiter
from pribilka.db.session import get_db
from pribilka.schemas.auth import BootstrapRequest, BootstrapResponse
from pribilka.services.device_auth import (
    issue_access_token,
    resolve_user_id,
    user_has_credentials,
)
from pribilka.api.auth_deps import _extract_bearer_token

router = APIRouter()


@router.post("/bootstrap", response_model=BootstrapResponse)
@limiter.limit("20/minute")
def bootstrap_session(
    request: Request,
    payload: BootstrapRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user_id = payload.user_id.strip()
    raw = _extract_bearer_token(authorization)

    if raw:
        token_user = resolve_user_id(db, raw)
        if token_user != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token does not match user_id",
            )
        return BootstrapResponse(user_id=user_id, access_token=raw, issued=False)

    if user_has_credentials(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required for existing user",
        )

    access_token = issue_access_token(db, user_id)
    db.commit()
    return BootstrapResponse(user_id=user_id, access_token=access_token, issued=True)
