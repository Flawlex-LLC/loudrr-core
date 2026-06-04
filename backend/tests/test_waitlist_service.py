"""Service-level tests for the waitlist use cases (register/status/approve/reject).
These exercise the service + both repositories against the real DB."""
import pytest

from app.core.errors import BadRequest, Conflict
from app.schemas.waitlist import WaitlistRegisterRequest
from app.services import waitlist as svc


def _payload(email="alice@example.com", x_link="https://x.com/alice", **kw):
    return WaitlistRegisterRequest(email=email, x_link=x_link, **kw)


def _tg(id=111, username="alice", first_name="Alice"):
    return {"id": id, "username": username, "first_name": first_name}


async def test_register_creates_entry(db_session):
    result = await svc.register_entry(db_session, tg_user=_tg(), payload=_payload())
    assert result.was_new is True
    assert result.entry.x_username == "alice"
    assert result.entry.status == "submitted"
    assert result.entry.email == "alice@example.com"
    assert result.entry.referral_code  # a code was generated


async def test_register_idempotent_on_telegram_id(db_session):
    first = await svc.register_entry(db_session, tg_user=_tg(), payload=_payload())
    # same telegram id, different email/handle -> still treated as the same user
    second = await svc.register_entry(
        db_session, tg_user=_tg(),
        payload=_payload(email="other@example.com", x_link="https://x.com/bob"),
    )
    assert second.was_new is False
    assert second.entry.id == first.entry.id


async def test_register_rejects_bad_x_link(db_session):
    with pytest.raises(BadRequest):
        await svc.register_entry(
            db_session, tg_user=_tg(), payload=_payload(x_link="https://x.com/home"),
        )


async def test_register_rejects_duplicate_email(db_session):
    await svc.register_entry(db_session, tg_user=_tg(id=1), payload=_payload())
    with pytest.raises(BadRequest):
        await svc.register_entry(
            db_session, tg_user=_tg(id=2),
            payload=_payload(x_link="https://x.com/bob"),  # same email, new tg id
        )


async def test_status_lifecycle(db_session):
    assert (await svc.get_status(db_session, telegram_id=999)).status == "not_registered"
    await svc.register_entry(db_session, tg_user=_tg(id=999), payload=_payload())
    assert (await svc.get_status(db_session, telegram_id=999)).status == "waitlisted"


async def test_approve_creates_user(db_session, make_user):
    admin = await make_user()  # approved_by_id is a real FK -> users.id
    reg = await svc.register_entry(db_session, tg_user=_tg(), payload=_payload())
    user = await svc.approve_entry(
        db_session, entry_id=reg.entry.id, admin_id=admin.id
    )
    assert user.x_username == "alice"
    await db_session.refresh(reg.entry)
    assert reg.entry.status == "approved"
    assert reg.entry.created_user_id == user.id
    # the user now exists -> status flips to approved
    assert (await svc.get_status(db_session, telegram_id=111)).status == "approved"


async def test_approve_twice_conflicts(db_session, make_user):
    admin = await make_user()
    reg = await svc.register_entry(db_session, tg_user=_tg(), payload=_payload())
    await svc.approve_entry(db_session, entry_id=reg.entry.id, admin_id=admin.id)
    with pytest.raises(Conflict):
        await svc.approve_entry(db_session, entry_id=reg.entry.id, admin_id=admin.id)


async def test_reject_sets_status(db_session, make_user):
    admin = await make_user()
    reg = await svc.register_entry(db_session, tg_user=_tg(), payload=_payload())
    entry = await svc.reject_entry(
        db_session, entry_id=reg.entry.id, admin_id=admin.id, reason="spam"
    )
    assert entry.status == "rejected"
    assert entry.rejection_reason == "spam"