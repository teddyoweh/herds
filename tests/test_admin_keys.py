"""Admin can mint/revoke a key on behalf of another owner (per-user device tokens)."""

from fastapi.testclient import TestClient

from herds.control import create_app


def test_admin_mint_key_for_owner():
    c = TestClient(create_app(":memory:"))
    r = c.post("/v1/admin/keys", json={"owner": "spawn_user_123", "scope": "run"})
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith("herds_sk_")
    assert body["owner"] == "spawn_user_123"
    assert body["scope"] == "run"


def test_admin_mint_requires_owner():
    c = TestClient(create_app(":memory:"))
    r = c.post("/v1/admin/keys", json={"scope": "run"})
    assert r.status_code == 422  # pydantic: owner is required
