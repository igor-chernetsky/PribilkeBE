from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.api.auth_deps import CurrentUserId
from pribilka.api.rate_limit import limiter
from pribilka.db.session import get_db
from pribilka.models.user_alert import UserAlert
from pribilka.schemas.alerts import AlertCreate, AlertResponse, AlertUpdate

router = APIRouter()


@router.post("", response_model=AlertResponse, status_code=201)
@limiter.limit("30/minute")
def create_alert(
    request: Request,
    payload: AlertCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    alert = UserAlert(**payload.model_dump(), user_id=user_id)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=list[AlertResponse])
@limiter.limit("60/minute")
def list_alerts(
    request: Request,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    return db.scalars(select(UserAlert).where(UserAlert.user_id == user_id)).all()


@router.put("/{alert_id}", response_model=AlertResponse)
@limiter.limit("30/minute")
def update_alert(
    request: Request,
    alert_id: UUID,
    payload: AlertUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    alert = db.get(UserAlert, alert_id)
    if not alert or alert.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)

    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
@limiter.limit("30/minute")
def delete_alert(
    request: Request,
    alert_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    alert = db.get(UserAlert, alert_id)
    if not alert or alert.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    db.delete(alert)
    db.commit()
