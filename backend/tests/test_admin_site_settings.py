"""Tests for the 3 admin tunables/metrics endpoints:

* GET  /api/admin/site-settings/       — list every known setting (admin)
* PUT  /api/admin/site-settings/{key}  — upsert one setting (superadmin)
* GET  /api/admin/stats/               — dashboard metrics (admin)

These match the style of test_admin_endpoints.py: ``?telegram_id=`` debug
bypass for auth, Decimal for credit amounts, and assertions on persisted
side effects (SiteSetting row, AuditLog row) where relevant.
"""
from decimal import Decimal

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.site_setting import SiteSetting


# ---------------------------------------------------------------------------
# GET /api/admin/site-settings/
# ---------------------------------------------------------------------------
async def test_site_settings_list_admin_ok(client, make_user):
    """Admin can list site settings, response shape matches ALL_GROUPS."""
    admin = await make_user(role="admin")
    r = await client.get(
        "/api/admin/site-settings/",
        params={"telegram_id": admin.telegram_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert len(data["groups"]) >= 1

    # collect every known key across all groups; POST_COST must be present
    all_keys = {s["key"] for g in data["groups"] for s in g["settings"]}
    assert "POST_COST" in all_keys
    assert "DAILY_EARN_CAP" in all_keys
    assert "TIER_NORMIE_THRESHOLD" in all_keys

    # first group has the expected shape: name, description, settings[]
    g0 = data["groups"][0]
    assert "name" in g0
    assert "description" in g0
    assert isinstance(g0["settings"], list)
    s0 = g0["settings"][0]
    for field in ("key", "value", "default", "data_type", "description", "live", "persisted"):
        assert field in s0, f"missing field {field!r} on setting payload"


async def test_site_settings_list_unauthenticated_401(client):
    r = await client.get("/api/admin/site-settings/")
    assert r.status_code == 401


async def test_site_settings_list_regular_user_403(client, make_user):
    user = await make_user(role="")
    r = await client.get(
        "/api/admin/site-settings/",
        params={"telegram_id": user.telegram_id},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/admin/site-settings/{key}
# ---------------------------------------------------------------------------
async def test_site_settings_update_superadmin_ok(client, make_user, db_session):
    """Superadmin updates POST_COST: SiteSetting row written + audit_log row."""
    admin = await make_user(role="superadmin")
    r = await client.put(
        "/api/admin/site-settings/POST_COST",
        params={"telegram_id": admin.telegram_id},
        json={"value": "100"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["key"] == "POST_COST"
    assert body["value"] == "100"
    assert body["data_type"] == "int"

    # SiteSetting row is persisted with the new value
    row = (
        await db_session.execute(
            select(SiteSetting).where(SiteSetting.key == "POST_COST")
        )
    ).scalar_one()
    assert row.value == "100"
    assert row.data_type == "int"

    # AuditLog row written with detail.new_value
    log = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "update_site_setting")
        )
    ).scalar_one()
    assert log.actor_id == admin.id
    assert log.detail["key"] == "POST_COST"
    assert log.detail["new_value"] == "100"


async def test_site_settings_update_admin_forbidden(client, make_user):
    """Plain admin cannot tune money math — that's superadmin-only."""
    admin = await make_user(role="admin")
    r = await client.put(
        "/api/admin/site-settings/POST_COST",
        params={"telegram_id": admin.telegram_id},
        json={"value": "100"},
    )
    assert r.status_code == 403


async def test_site_settings_update_unknown_key_404(client, make_user):
    admin = await make_user(role="superadmin")
    r = await client.put(
        "/api/admin/site-settings/NOT_A_REAL_KEY",
        params={"telegram_id": admin.telegram_id},
        json={"value": "whatever"},
    )
    assert r.status_code == 404


async def test_site_settings_update_bad_type_422(client, make_user):
    """POST_COST is an int; non-int value must 422."""
    admin = await make_user(role="superadmin")
    r = await client.put(
        "/api/admin/site-settings/POST_COST",
        params={"telegram_id": admin.telegram_id},
        json={"value": "not-an-int"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/admin/stats/
# ---------------------------------------------------------------------------
async def test_stats_admin_ok(client, make_user):
    """Admin gets a dashboard payload with all the expected top-level keys."""
    admin = await make_user(role="admin")
    r = await client.get(
        "/api/admin/stats/",
        params={"telegram_id": admin.telegram_id},
    )
    assert r.status_code == 200
    data = r.json()
    for top in ("users", "credits", "posts", "engagements", "queues", "recent_audit"):
        assert top in data, f"missing top-level key {top!r}"

    # users: total + by_role + flag counts
    for k in ("total", "by_role", "banned", "whitelisted", "x_verified", "new_this_week"):
        assert k in data["users"]
    assert isinstance(data["users"]["by_role"], dict)
    for role_key in ("regular", "admin", "superadmin"):
        assert role_key in data["users"]["by_role"]

    # credits: three sums
    for k in ("in_circulation", "total_earned", "total_spent"):
        assert k in data["credits"]

    # posts: status counts + escrow
    for k in ("active", "completed", "cancelled", "total_escrow_active"):
        assert k in data["posts"]

    # engagements: three windowed counts
    for k in ("total", "today", "this_week"):
        assert k in data["engagements"]

    # queues: three backlog counts
    for k in ("pending_waitlist", "pending_x_verifications", "pending_batches"):
        assert k in data["queues"]

    # recent_audit: list of dicts
    assert isinstance(data["recent_audit"], list)


async def test_stats_unauthenticated_401(client):
    r = await client.get("/api/admin/stats/")
    assert r.status_code == 401


async def test_stats_regular_user_403(client, make_user):
    user = await make_user(role="")
    r = await client.get(
        "/api/admin/stats/",
        params={"telegram_id": user.telegram_id},
    )
    assert r.status_code == 403


async def test_stats_with_data(client, make_user):
    """Seed a few users with credits, expect totals to reflect them."""
    admin = await make_user(role="admin")  # 1 admin user
    # three regular users with known credit balances
    u1 = await make_user(credits=Decimal("20"), total_credits_earned=Decimal("20"))
    u2 = await make_user(credits=Decimal("30"), total_credits_earned=Decimal("30"))
    u3 = await make_user(credits=Decimal("50"), total_credits_earned=Decimal("50"))

    r = await client.get(
        "/api/admin/stats/",
        params={"telegram_id": admin.telegram_id},
    )
    assert r.status_code == 200
    data = r.json()

    # at least the four users we just made
    assert data["users"]["total"] >= 4
    # by_role rolls them up correctly
    assert data["users"]["by_role"]["admin"] >= 1
    assert data["users"]["by_role"]["regular"] >= 3

    # in_circulation is the sum of every user's credits; ours add to 100
    # (the admin user has 0 by default) — assert >= in case of seeded rows
    expected_min = float(u1.credits + u2.credits + u3.credits)
    assert data["credits"]["in_circulation"] >= expected_min
    assert data["credits"]["total_earned"] >= expected_min
