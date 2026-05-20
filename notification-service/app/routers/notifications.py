import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter()
logger = logging.getLogger(__name__)


# ── GET /notifications/ ───────────────────────────────────────────────────────
@router.get("/", response_model=List[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    # Devuelve todas las notificaciones del usuario autenticado, más recientes primero.
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


# ── GET /notifications/unread-count ──────────────────────────────────────────
@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    # Devuelve el número de notificaciones no leídas del usuario.
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    count = len(result.scalars().all())
    return {"unread": count}


# ── PATCH /notifications/mark-all-read ───────────────────────────────────────
@router.patch("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    # Marca todas las notificaciones del usuario como leídas.
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    return {"detail": "Todas las notificaciones marcadas como leídas"}


# ── PATCH /notifications/{notif_id}/read ──────────────────────────────────────
@router.patch("/{notif_id}/read", response_model=NotificationOut)
async def mark_read(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    # Marca una notificación como leída. Solo el destinatario puede hacerlo.
    result = await db.execute(
        select(Notification).where(Notification.id == notif_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada")
    if notif.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    notif.is_read = True
    await db.flush()
    await db.refresh(notif)
    return notif


# ── DELETE /notifications/{notif_id} ─────────────────────────────────────────
@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    # Elimina una notificación. Solo el destinatario puede hacerlo.
    result = await db.execute(
        select(Notification).where(Notification.id == notif_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada")
    if notif.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    await db.delete(notif)
