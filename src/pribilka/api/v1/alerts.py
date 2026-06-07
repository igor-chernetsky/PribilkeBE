from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.user_alert import UserAlert
from pribilka.schemas.alerts import AlertCreate, AlertResponse, AlertUpdate

router = APIRouter()


@router.post("", response_model=AlertResponse, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    alert = UserAlert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=list[AlertResponse])
def list_alerts(user_id: str = Query(...), db: Session = Depends(get_db)):
    return db.scalars(select(UserAlert).where(UserAlert.user_id == user_id)).all()


@router.put("/{alert_id}", response_model=AlertResponse)
def update_alert(alert_id: UUID, payload: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.get(UserAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)

    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: UUID, db: Session = Depends(get_db)):
    alert = db.get(UserAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
