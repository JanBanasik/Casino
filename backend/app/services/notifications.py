"""Persistent, must-acknowledge player notifications (bonuses, system alerts)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update

from app.db.models import Notification


class NotificationService:
    def __init__(self, session):
        self.session = session

    async def create(
        self, user_id: UUID, *, kind: str, title: str, body: str, amount: float = 0.0
    ) -> Notification:
        notif = Notification(
            user_id=user_id, kind=kind, title=title, body=body, amount=amount
        )
        self.session.add(notif)
        await self.session.flush()
        return notif

    async def list_pending(self, user_id: UUID, limit: int = 20) -> list[Notification]:
        q = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.acknowledged.is_(False))
            .order_by(Notification.created_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def acknowledge(self, user_id: UUID, notification_id: UUID) -> bool:
        res = await self.session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.acknowledged.is_(False),
            )
            .values(acknowledged=True)
        )
        return res.rowcount > 0

    async def acknowledge_all(self, user_id: UUID) -> int:
        res = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.acknowledged.is_(False),
            )
            .values(acknowledged=True)
        )
        return res.rowcount
