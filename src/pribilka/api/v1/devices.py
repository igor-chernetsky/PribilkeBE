from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.device_token import DeviceToken
from pribilka.schemas.devices import DeviceRegisterRequest, DeviceRegisterResponse

router = APIRouter()


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_device(payload: DeviceRegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == payload.token))
    if existing:
        existing.user_id = payload.user_id
        existing.platform = payload.platform
        existing.push_enabled = payload.push_enabled
        db.commit()
        return DeviceRegisterResponse(registered=True, token=payload.token)

    device = DeviceToken(
        user_id=payload.user_id,
        token=payload.token,
        platform=payload.platform,
        push_enabled=payload.push_enabled,
    )
    db.add(device)
    db.commit()
    return DeviceRegisterResponse(registered=True, token=payload.token)


@router.delete("/{token}", status_code=204)
def unregister_device(token: str, db: Session = Depends(get_db)):
    device = db.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if not device:
        raise HTTPException(status_code=404, detail="Device token not found")
    db.delete(device)
    db.commit()
