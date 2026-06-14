from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.api.auth_deps import CurrentUserId
from pribilka.api.rate_limit import limiter
from pribilka.db.session import get_db
from pribilka.models.device_token import DeviceToken
from pribilka.schemas.devices import DeviceRegisterRequest, DeviceRegisterResponse

router = APIRouter()


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
@limiter.limit("20/minute")
def register_device(
    request: Request,
    payload: DeviceRegisterRequest,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == payload.token))
    if existing and existing.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Push token already registered to another user",
        )

    if existing:
        existing.platform = payload.platform
        existing.push_enabled = payload.push_enabled
        existing.locale = payload.locale
        db.commit()
        return DeviceRegisterResponse(registered=True, token=payload.token)

    device = DeviceToken(
        user_id=user_id,
        token=payload.token,
        platform=payload.platform,
        push_enabled=payload.push_enabled,
        locale=payload.locale,
    )
    db.add(device)
    db.commit()
    return DeviceRegisterResponse(registered=True, token=payload.token)


@router.delete("/{token}", status_code=204)
@limiter.limit("20/minute")
def unregister_device(
    request: Request,
    token: str,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    device = db.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if not device or device.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device token not found")
    db.delete(device)
    db.commit()
