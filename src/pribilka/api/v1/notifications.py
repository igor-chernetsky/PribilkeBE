from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.api.auth_deps import CurrentUserId
from pribilka.api.rate_limit import limiter
from pribilka.db.session import get_db
from pribilka.models.notification import Notification
from pribilka.schemas.alerts import MarkNotificationsReadRequest, NotificationResponse

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
@limiter.limit("60/minute")
def list_notifications(
    request: Request,
    user_id: CurrentUserId,
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return db.scalars(query.order_by(Notification.created_at.desc())).all()


@router.post("/read")
@limiter.limit("30/minute")
def mark_notifications_read(
    request: Request,
    payload: MarkNotificationsReadRequest,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
):
    if not payload.notification_ids:
        return {"marked_read": 0}

    notifications = db.scalars(
        select(Notification).where(Notification.id.in_(payload.notification_ids))
    ).all()

    if len(notifications) != len(payload.notification_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more notifications not found",
        )

    if any(notification.user_id != user_id for notification in notifications):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another user's notifications",
        )

    now = datetime.now(UTC)
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now

    db.commit()
    return {"marked_read": len(notifications)}


@router.post("/read-all")
@limiter.limit("10/minute")
def mark_all_notifications_read(
    request: Request,
    user_id: CurrentUserId,
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
