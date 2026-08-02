"""Removing a Mac from a fleet.

A Mac could be added but never removed: there was no DELETE route and no CLI
verb, only tag deletion. A decommissioned, sold or stolen machine stayed in the
fleet forever *and kept a valid device token*, so it could reconnect at will.
Hiding the row would not have been enough — revoking the token is the part that
makes this an actual disconnect.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from herds.control import create_app
from herds.control.store import Store


@pytest.fixture
def client_and_store(tmp_path):
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.put_api_key("k_admin", "owner1", "admin", scope="admin")
    store.put_api_key("k_run", "owner1", "runner", scope="run")
    store.db.close()
    app = create_app(db)
    with TestClient(app) as c:
        yield c, Store(db)


def _register(store: Store, mid: str, owner: str = "owner1") -> str:
    from herds.protocol import MachineStatus
    store.upsert_machine(mid, f"name-{mid}", owner, {}, MachineStatus.ONLINE, 0)
    return store.create_device_token(mid, owner)


AUTH = {"Authorization": "Bearer k_admin"}


def test_delete_removes_machine_from_listing(client_and_store):
    c, store = client_and_store
    _register(store, "mac_gone")

    assert any(m["machine_id"] == "mac_gone"
               for m in c.get("/v1/machines", headers=AUTH).json()["machines"])

    r = c.delete("/v1/machines/mac_gone", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["removed"] is True

    assert not any(m["machine_id"] == "mac_gone"
                   for m in c.get("/v1/machines", headers=AUTH).json()["machines"])


def test_delete_revokes_the_device_token(client_and_store):
    """The point of the feature: a removed Mac must not be able to rejoin."""
    c, store = client_and_store
    token = _register(store, "mac_revoke")
    assert store.device_token_info(token)["machine_id"] == "mac_revoke"

    c.delete("/v1/machines/mac_revoke", headers=AUTH)

    assert store.device_token_info(token) is None, "token survived removal"


def test_delete_is_idempotent(client_and_store):
    c, store = client_and_store
    _register(store, "mac_twice")
    assert c.delete("/v1/machines/mac_twice", headers=AUTH).status_code == 200
    assert c.delete("/v1/machines/mac_twice", headers=AUTH).status_code == 404


def test_delete_requires_admin_scope(client_and_store, monkeypatch):
    """Removing a machine is destructive — a run-scoped agent token must not.

    Scope enforcement is gated on HERDS_REQUIRE_AUTH so a local control plane
    works out of the box, so turn it on to exercise the check at all.
    """
    import herds.control as control

    monkeypatch.setattr(control, "REQUIRE_AUTH", True)
    c, store = client_and_store
    _register(store, "mac_scoped")
    r = c.delete("/v1/machines/mac_scoped", headers={"Authorization": "Bearer k_run"})
    assert r.status_code in (401, 403), "a run-scoped token could delete a machine"
    assert store.get_machine("mac_scoped") is not None


def test_cannot_delete_another_owners_machine(client_and_store):
    c, store = client_and_store
    _register(store, "mac_theirs", owner="someone_else")
    assert c.delete("/v1/machines/mac_theirs", headers=AUTH).status_code == 404
    assert store.get_machine("mac_theirs") is not None


def test_job_history_survives_removal(client_and_store):
    """Retiring a Mac must not erase the record of what ran on it."""
    c, store = client_and_store
    _register(store, "mac_hist")
    before = len(store.list_jobs())

    counts = store.delete_machine("mac_hist2", "owner1")  # no-op, different id
    c.delete("/v1/machines/mac_hist", headers=AUTH)

    assert "jobs" not in counts
    assert len(store.list_jobs()) >= before, "job history was destroyed with the machine"


def test_store_delete_reports_what_it_removed(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    from herds.protocol import MachineStatus
    store.upsert_machine("m1", "n", "o", {}, MachineStatus.ONLINE, 0)
    store.add_tags("m1", ["ci", "arm"])
    counts = store.delete_machine("m1", "o")
    assert counts["machines"] == 1
    assert counts["machine_tags"] == 2


def test_store_delete_refuses_wrong_owner(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    from herds.protocol import MachineStatus
    store.upsert_machine("m1", "n", "owner-a", {}, MachineStatus.ONLINE, 0)
    assert store.delete_machine("m1", "owner-b") == {}
    assert store.get_machine("m1") is not None
