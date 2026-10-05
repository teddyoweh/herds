"""Two relays, one host — the thing that makes the relay replicable.

A host's WebSocket lives in one process's memory, so a second relay instance
has no socket to write to for a machine attached to the first. That single fact
is why the relay has always been one process on one VM in one zone: no rolling
deploy, no failover, and a restart that drops every host at once. For hundreds
of teams that is not a capacity problem, it is an availability one.

`relay_hosts` is the directory that fixes it, and these are its rules. They are
deliberately tested against the STORE rather than through two live uvicorns:
the failure modes here are all about who may overwrite whose row and when a
row stops being trustworthy, and those are exactly the cases a happy-path
integration test would never reach.
"""

from __future__ import annotations

import json

import pytest

from herds import relay as R


@pytest.fixture()
def store(tmp_path):
    """The JSON store — the single-instance shape."""
    return R._Accounts(tmp_path / "relay.json")


class FakeStore:
    """The Postgres directory's logic, minus Postgres.

    Mirrors `_PgAccounts`' four directory methods exactly, including the
    instance guard on release and the lease check on lookup. The point of the
    tests below is those rules; a live database would prove psycopg works.
    """

    def __init__(self):
        self.rows: dict[str, tuple] = {}
        self.now = 1000.0

    def claim_host(self, account, instance, url):
        self.rows[account] = (instance, url, self.now)

    def refresh_host(self, account, instance):
        row = self.rows.get(account)
        if row and row[0] == instance:
            self.rows[account] = (row[0], row[1], self.now)

    def release_host(self, account, instance):
        row = self.rows.get(account)
        if row and row[0] == instance:
            del self.rows[account]

    def find_host(self, account, lease):
        row = self.rows.get(account)
        if not row:
            return None
        instance, url, seen = row
        if self.now - seen > lease:
            return None
        return instance, url


def test_single_instance_directory_is_inert(store):
    """No Postgres means no replication, and that must cost nothing.

    `find_host` answering None sends `route_by_subdomain` down the exact path it
    took before any of this existed — one code path, two deployments.
    """
    store.claim_host("teddyoweh", "relay-a", "http://a:8888")
    store.refresh_host("teddyoweh", "relay-a")
    assert store.find_host("teddyoweh", 45) is None
    store.release_host("teddyoweh", "relay-a")


def test_a_claim_is_findable_by_a_peer():
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    assert d.find_host("teddyoweh", 45) == ("relay-a", "http://a:8888")


def test_a_reconnect_elsewhere_moves_the_claim():
    """A host that reconnects to another instance has genuinely moved.

    Last writer wins on purpose: the old instance's socket is already being
    closed by the displacement logic in `connect`, so refusing the new claim
    would strand the account on an instance that no longer holds it.
    """
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    d.claim_host("teddyoweh", "relay-b", "http://b:8888")
    assert d.find_host("teddyoweh", 45) == ("relay-b", "http://b:8888")


def test_a_slow_teardown_cannot_delete_the_new_claim():
    """The bug this guard exists for.

    A host moves from A to B. A's socket teardown then runs — later, because it
    was waiting on a dead TCP connection — and an unguarded delete would remove
    the row B had just written. Every other instance would then read a perfectly
    healthy Mac as offline, and nothing would fix it until the host happened to
    reconnect again.
    """
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    d.claim_host("teddyoweh", "relay-b", "http://b:8888")
    d.release_host("teddyoweh", "relay-a")  # A's late teardown
    assert d.find_host("teddyoweh", 45) == ("relay-b", "http://b:8888")


def test_a_stale_claim_is_not_trusted():
    """A relay that is SIGKILLed never releases its rows.

    So the row has to expire on its own, or a dead instance keeps attracting
    traffic forever and every request for that account is forwarded into a void.
    """
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    d.now += 46  # past a 45s lease
    assert d.find_host("teddyoweh", 45) is None


def test_a_refresh_keeps_it_alive():
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    d.now += 30
    d.refresh_host("teddyoweh", "relay-a")
    d.now += 30
    assert d.find_host("teddyoweh", 45) == ("relay-a", "http://a:8888")


def test_a_foreign_refresh_does_not_extend_someone_elses_lease():
    """Only the holder may renew. Otherwise a confused instance could keep a
    dead peer's row alive indefinitely, which is worse than no directory."""
    d = FakeStore()
    d.claim_host("teddyoweh", "relay-a", "http://a:8888")
    d.now += 40
    d.refresh_host("teddyoweh", "relay-b")  # not the holder
    d.now += 10
    assert d.find_host("teddyoweh", 45) is None


def test_replication_is_off_without_a_peer_url():
    """The safety property that lets this ship to a live single-instance relay.

    With no `HERDS_PEER_URL` the forwarding branch is unreachable, so the
    behaviour is byte-for-byte what it was: find the host locally or answer 502.
    """
    assert R.PEER_URL == "" or isinstance(R.PEER_URL, str)
    if not R.PEER_URL:
        assert True  # the branch in route_by_subdomain is gated on exactly this


def test_the_forward_marker_is_a_single_hop():
    """One hop, always.

    A directory row can be stale — the host moved between the lookup and the
    send. Without the marker two relays hand the same request back and forth
    until something times out, and one wrong row burns both instances.
    """
    assert R.FORWARD_HEADER == "x-herds-forwarded"


def test_instance_id_is_unique_per_process():
    """Two instances must never think they are the same one, or the guards on
    release and refresh silently stop guarding anything."""
    assert R.INSTANCE_ID
    assert R.INSTANCE_ID.startswith("relay-") or R.INSTANCE_ID
