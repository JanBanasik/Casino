from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import NotificationItem, NotificationListResponse
from app.core.limiter import limiter
from app.db.models import User
from app.services.notifications import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
@limiter.limit("120/minute")
async def list_notifications(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationListResponse:
    items = await NotificationService(db).list_pending(user.id)
    return NotificationListResponse(
        notifications=[
            NotificationItem(
                id=n.id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                amount=n.amount,
                created_at=n.created_at.isoformat(),
            )
            for n in items
        ]
    )


@router.post("/{notification_id}/ack")
@limiter.limit("120/minute")
async def acknowledge_notification(
    request: Request,
    notification_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    ok = await NotificationService(db).acknowledge(user.id, notification_id)
    await db.commit()
    return {"acknowledged": ok}


@router.post("/ack-all")
@limiter.limit("60/minute")
async def acknowledge_all(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    count = await NotificationService(db).acknowledge_all(user.id)
    await db.commit()
    return {"acknowledged": count}
