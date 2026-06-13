from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.db.session import get_db
from pribilka.models.notification import Notification
from pribilka.schemas.alerts import MarkNotificationsReadRequest, NotificationResponse

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    user_id: str = Query(...),
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return db.scalars(query.order_by(Notification.created_at.desc())).all()


@router.post("/read")
def mark_notifications_read(
    payload: MarkNotificationsReadRequest, db: Session = Depends(get_db)
):
    notifications = db.scalars(
        select(Notification).where(Notification.id.in_(payload.notification_ids))
    ).all()

    now = datetime.now(UTC)
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now

    db.commit()
    return {"marked_read": len(notifications)}


@router.post("/read-all")
def mark_all_notifications_read(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ).all()

    now = datetime.now(UTC)
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now

    db.commit()
    return {"marked_read": len(notifications)}
