"""SQLAdmin panel (Ch17) — an instant CRUD admin UI over the models.

FastAPI has no free admin like Django's, so we mount SQLAdmin at /admin with a
separate session-based login (admin auth is NOT the user HMAC auth). Read-only
views guard the immutable trails (transactions, audit log).
"""
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend

from app.core.config import settings
from app.db.session import engine
from app.models.audit_log import AuditLog
from app.models.feature_interest import FeatureInterest
from app.models.outbox_event import OutboxEvent
from app.models.post import Post
from app.models.site_setting import SiteSetting
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_batch import VerificationBatch
from app.models.waitlist_entry import WaitlistEntry
from app.models.x_verification_request import XVerificationRequest


class AdminAuth(AuthenticationBackend):
    async def login(self, request) -> bool:
        form = await request.form()
        ok = (
            bool(settings.admin_password)
            and form.get("username") == settings.admin_username
            and form.get("password") == settings.admin_password
        )
        if ok:
            request.session["admin"] = settings.admin_username
        return ok

    async def logout(self, request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request) -> bool:
        return bool(request.session.get("admin"))


class UserAdmin(ModelView, model=User):
    name_plural = "Users"
    column_list = [
        User.id, User.telegram_username, User.x_username, User.credits,
        User.is_whitelisted, User.is_banned, User.x_verified, User.tweetscout_score,
    ]
    column_searchable_list = [User.telegram_username, User.x_username]
    can_delete = False


class WaitlistAdmin(ModelView, model=WaitlistEntry):
    name_plural = "Waitlist Entries"
    column_list = [
        WaitlistEntry.id, WaitlistEntry.email, WaitlistEntry.x_username,
        WaitlistEntry.status, WaitlistEntry.created_at,
    ]


class TransactionAdmin(ModelView, model=Transaction):
    name_plural = "Transactions"
    column_list = [
        Transaction.id, Transaction.user_id, Transaction.type,
        Transaction.amount, Transaction.balance_after, Transaction.created_at,
    ]
    can_create = can_edit = can_delete = False  # immutable audit trail


class PostAdmin(ModelView, model=Post):
    column_list = [Post.id, Post.user_id, Post.status, Post.escrow, Post.created_at]


class XVerificationAdmin(ModelView, model=XVerificationRequest):
    name_plural = "X Verifications"
    column_list = [
        XVerificationRequest.id, XVerificationRequest.user_id,
        XVerificationRequest.claimed_x_username, XVerificationRequest.status,
    ]


class BatchAdmin(ModelView, model=VerificationBatch):
    name_plural = "Verification Batches"
    column_list = [
        VerificationBatch.id, VerificationBatch.user_id, VerificationBatch.status,
        VerificationBatch.credits_awarded,
    ]


class OutboxAdmin(ModelView, model=OutboxEvent):
    name_plural = "Outbox Events"
    column_list = [OutboxEvent.id, OutboxEvent.event_type, OutboxEvent.status, OutboxEvent.retry_count]


class SiteSettingAdmin(ModelView, model=SiteSetting):
    name_plural = "Site Settings"
    column_list = [SiteSetting.key, SiteSetting.value, SiteSetting.data_type]


class FeatureInterestAdmin(ModelView, model=FeatureInterest):
    name_plural = "Feature Interests"
    column_list = [FeatureInterest.id, FeatureInterest.user_id, FeatureInterest.feature]


class AuditLogAdmin(ModelView, model=AuditLog):
    name_plural = "Audit Log"
    column_list = [
        AuditLog.id, AuditLog.actor_id, AuditLog.action,
        AuditLog.target_type, AuditLog.target_id, AuditLog.created_at,
    ]
    can_create = can_edit = can_delete = False  # append-only


def mount_admin(app) -> Admin:
    admin = Admin(
        app, engine,
        authentication_backend=AdminAuth(secret_key=settings.secret_key),
    )
    for view in (
        UserAdmin, WaitlistAdmin, TransactionAdmin, PostAdmin, XVerificationAdmin,
        BatchAdmin, OutboxAdmin, SiteSettingAdmin, FeatureInterestAdmin, AuditLogAdmin,
    ):
        admin.add_view(view)
    return admin
