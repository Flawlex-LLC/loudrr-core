"""Admin operations API (Ch17) — role-gated, service-backed.

Every privileged action goes through the audited service layer
(services/admin.py, services/waitlist.py, services/x_verification.py) — these
endpoints never touch the DB directly. Access is gated by role:
  * require_admin       — 'admin' or 'superadmin'
  * require_superadmin  — 'superadmin' only (the most sensitive ops, e.g. revoke)

The acting admin's own id is threaded through as the audit actor_id.
Mounted under /api/admin (SQLAdmin owns /admin).
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, func

from app.core.deps import require_admin, require_superadmin
from app.db.session import get_session
from app.models.user import User
from app.models.waitlist_entry import WaitlistEntry
from app.models.x_verification_request import XVerificationRequest
from app.services import admin as admin_svc
from app.services import waitlist as waitlist_svc
from app.services import x_verification as xverify_svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---- request bodies ----
class GrantBody(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = ""


class RevokeBody(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str = ""


class ReasonBody(BaseModel):
    reason: str = ""


class NotesBody(BaseModel):
    notes: str = ""


# ---- user credit + ban operations ----
@router.post("/users/{user_id}/grant-credits/")
async def grant_credits(
    user_id: uuid.UUID,
    body: GrantBody,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    user = await admin_svc.grant_credits(
        db, admin_id=admin.id, user_id=user_id,
        amount=body.amount, description=body.description,
    )
    return {"ok": True, "user_id": str(user.id), "credits": float(user.credits)}


@router.post("/users/{user_id}/revoke-credits/")
async def revoke_credits(
    user_id: uuid.UUID,
    body: RevokeBody,
    admin: User = Depends(require_superadmin),  # sensitive → superadmin only
    db=Depends(get_session),
):
    user = await admin_svc.revoke_credits(
        db, admin_id=admin.id, user_id=user_id,
        amount=body.amount, reason=body.reason,
    )
    return {"ok": True, "user_id": str(user.id), "credits": float(user.credits)}


@router.post("/users/{user_id}/ban/")
async def ban_user(
    user_id: uuid.UUID,
    body: ReasonBody,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    user = await admin_svc.ban_user(
        db, admin_id=admin.id, user_id=user_id, reason=body.reason
    )
    return {"ok": True, "user_id": str(user.id), "is_banned": user.is_banned}


@router.post("/users/{user_id}/unban/")
async def unban_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    user = await admin_svc.unban_user(db, admin_id=admin.id, user_id=user_id)
    return {"ok": True, "user_id": str(user.id), "is_banned": user.is_banned}


# ---- waitlist moderation ----
@router.post("/waitlist/{entry_id}/approve/")
async def approve_waitlist(
    entry_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    created = await waitlist_svc.approve_entry(db, entry_id=entry_id, admin_id=admin.id)
    return {"ok": True, "created_user_id": str(created.id)}


@router.post("/waitlist/{entry_id}/reject/")
async def reject_waitlist(
    entry_id: uuid.UUID,
    body: ReasonBody,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    entry = await waitlist_svc.reject_entry(
        db, entry_id=entry_id, admin_id=admin.id, reason=body.reason
    )
    return {"ok": True, "entry_id": str(entry.id), "status": entry.status}


# ---- X-verification review ----
@router.post("/x-verification/{request_id}/approve/")
async def approve_x_verification(
    request_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    req = await xverify_svc.approve_x_verification(
        db, request_id=request_id, admin_id=admin.id
    )
    return {"ok": True, "request_id": str(req.id), "status": req.status}


@router.post("/x-verification/{request_id}/reject/")
async def reject_x_verification(
    request_id: uuid.UUID,
    body: NotesBody,
    admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    req = await admin_svc.reject_x_verification(
        db, admin_id=admin.id, request_id=request_id, notes=body.notes
    )
    return {"ok": True, "request_id": str(req.id), "status": req.status}


# ---- read endpoints for the admin UI ----
# Lightweight list/search endpoints so the Next.js admin UI can populate its
# tables without us reusing the SQLAdmin panel for browsing. All admin-gated.
@router.get("/waitlist/pending/")
async def list_pending_waitlist(
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    rows = (
        await db.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.status == "submitted")
            .order_by(WaitlistEntry.created_at.asc())  # oldest first — FIFO
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(e.id),
            "email": e.email,
            "telegram_id": e.telegram_id,
            "telegram_username": e.telegram_username,
            "x_username": e.x_username,
            "region": e.region,
            "niche": e.niche,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


@router.get("/x-verification/pending/")
async def list_pending_x_verifications(
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    rows = (
        await db.execute(
            select(XVerificationRequest, User)
            .join(User, User.id == XVerificationRequest.user_id)
            .where(XVerificationRequest.status == "PENDING")
            .order_by(XVerificationRequest.created_at.asc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(req.id),
            "user_id": str(req.user_id),
            "user_telegram_username": user.telegram_username,
            "submitted_x_username": req.submitted_x_username,
            "claimed_x_username": req.claimed_x_username,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        }
        for req, user in rows
    ]


@router.get("/users/")
async def search_users(
    q: str = Query(default="", description="Search telegram_username or x_username (case-insensitive substring)"),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db=Depends(get_session),
):
    """Search users for the admin Users tab. Empty `q` returns most-recent users."""
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if q:
        needle = f"%{q.lower()}%"
        stmt = (
            select(User)
            .where(
                or_(
                    func.lower(User.telegram_username).like(needle),
                    func.lower(User.x_username).like(needle),
                )
            )
            .order_by(User.created_at.desc())
            .limit(limit)
        )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(u.id),
            "telegram_id": u.telegram_id,
            "telegram_username": u.telegram_username,
            "x_username": u.x_username,
            "credits": float(u.credits),
            "role": u.role,
            "is_banned": u.is_banned,
            "is_whitelisted": u.is_whitelisted,
            "x_verified": u.x_verified,
        }
        for u in rows
    ]
