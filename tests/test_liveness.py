"""Machine liveness: the heartbeat, and what "online" is allowed to mean.

Two bugs met here. `last_seen_ms` was written only on REGISTERED, so it froze at
the moment an agent connected — a Mac up for hours reported "last seen 3h ago"
while its CPU gauge ticked live. And status was read straight off the sqlite row
whenever the machine wasn't on a live socket, so a control plane that restarted
inherited rows marked ONLINE and served them as up forever.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from herds import config
from herds.control import STALE_AFTER_MS, create_app
from herds.control.store import Store
from herds.protocol import Frame, FrameType, MachineStatus


def _metrics(cpu: float = 12.5, mem: float = 40.0) -> str:
    return Frame(type=FrameType.METRICS_REPORT,
                 data={"cpu": cpu, "mem": mem, "battery_pct": 80.0}).dump()


def _machine(c: TestClient, mid: str) -> dict:
    rows = c.get("/v1/machines").json()["machines"]
    return next(m for m in rows if m["machine_id"] == mid)


# -- the heartbeat ---------------------------------------------------------- #
#
# These backdate the row after REGISTERED. Without it the whole test runs inside
# a few milliseconds, so a last_seen frozen at connect time still *looks* fresh
# and the assertions pass against the bug. Backdating stands in for the wall
# clock the real fleet ran against: the Mac whose gauge was live while its
# timestamp sat 33 minutes in the past.


def _backdate(store: Store, mid: str, age_ms: int) -> int:
    old = config.now_ms() - age_ms
    store.set_machine_status(mid, MachineStatus.ONLINE, old)
    return old


def test_metrics_report_advances_last_seen(store_and_client):
    """A metrics frame is the heartbeat; it must move last_seen_ms."""
    store, c = store_and_client
    with c.websocket_connect("/agent/ws?machine_id=m1") as agent:
        agent.send_text(Frame(type=FrameType.REGISTERED,
                              data={"machine": {"name": "M1"}}).dump())
        c.get("/v1/machines")
        stale = _backdate(store, "m1", 33 * 60_000)   # the observed symptom
        assert _machine(c, "m1")["last_seen_ms"] == stale

        agent.send_text(_metrics())
        c.get("/v1/machines")  # round-trip so the frame above is processed
        after_beat = _machine(c, "m1")["last_seen_ms"]

    assert after_beat > stale, "a heartbeat did not refresh last_seen"
    assert config.now_ms() - after_beat < 5_000, "last_seen is not current"


def test_last_seen_tracks_repeated_beats(store_and_client):
    """Every beat refreshes — not just the first after a connect."""
    store, c = store_and_client
    with c.websocket_connect("/agent/ws?machine_id=m1") as agent:
        agent.send_text(Frame(type=FrameType.REGISTERED,
                              data={"machine": {"name": "M1"}}).dump())
        c.get("/v1/machines")
        for cpu in (10.0, 20.0, 30.0):
            stale = _backdate(store, "m1", 10 * 60_000)
            agent.send_text(_metrics(cpu=cpu))
            c.get("/v1/machines")
            assert _machine(c, "m1")["last_seen_ms"] > stale


def test_live_cpu_and_last_seen_agree(store_and_client):
    """The symptom that surfaced this: a live gauge beside a stale timestamp."""
    store, c = store_and_client
    with c.websocket_connect("/agent/ws?machine_id=m1") as agent:
        agent.send_text(Frame(type=FrameType.REGISTERED,
                              data={"machine": {"name": "M1"}}).dump())
        c.get("/v1/machines")
        _backdate(store, "m1", 33 * 60_000)

        agent.send_text(_metrics(cpu=37.5))
        c.get("/v1/machines")
        m = _machine(c, "m1")

    assert m["live_cpu"] == 37.5           # telemetry is flowing
    assert config.now_ms() - m["last_seen_ms"] < 5_000   # …and so is the clock


# -- what "online" may claim ------------------------------------------------ #


def test_connected_machine_is_online_regardless_of_row():
    """A live socket is proof of life even if the row says OFFLINE."""
    app = create_app(":memory:")
    c = TestClient(app)
    with c.websocket_connect("/agent/ws?machine_id=m1") as agent:
        agent.send_text(Frame(type=FrameType.REGISTERED,
                              data={"machine": {"name": "M1"}}).dump())
        c.get("/v1/machines")
        assert _machine(c, "m1")["status"] == "online"


@pytest.fixture
def store_and_client(tmp_path):
    db = str(tmp_path / "t.db")
    s = Store(db)
    s.db.close()
    app = create_app(db)
    with TestClient(app) as c:
        yield Store(db), c


def test_stale_online_row_reads_offline(store_and_client):
    """A row left ONLINE by a crashed control plane stops claiming to be up."""
    store, c = store_and_client
    stale = config.now_ms() - (STALE_AFTER_MS + 60_000)
    store.upsert_machine("mac_ghost", "Ghost", "local", {}, MachineStatus.ONLINE, stale)

    m = _machine(c, "mac_ghost")
    assert m["status"] == "offline", "a machine silent for minutes is not online"
    # Single-machine route must agree with the listing.
    assert c.get("/v1/machines/mac_ghost").json()["status"] == "offline"


def test_fresh_online_row_stays_online(store_and_client):
    """Inside the grace window a recent beat still counts — no flapping."""
    store, c = store_and_client
    recent = config.now_ms() - 3_000  # one missed 5s beat at most
    store.upsert_machine("mac_ok", "Ok", "local", {}, MachineStatus.ONLINE, recent)

    assert _machine(c, "mac_ok")["status"] == "online"
    assert c.get("/v1/machines/mac_ok").json()["status"] == "online"


def test_offline_row_is_left_alone(store_and_client):
    """Staleness only ever downgrades; it never resurrects an offline machine."""
    store, c = store_and_client
    store.upsert_machine("mac_off", "Off", "local", {}, MachineStatus.OFFLINE,
                         config.now_ms())
    assert _machine(c, "mac_off")["status"] == "offline"


def test_offline_machine_reports_no_live_telemetry(store_and_client):
    """Gauges must not linger on a machine that just went stale."""
    store, c = store_and_client
    stale = config.now_ms() - (STALE_AFTER_MS + 60_000)
    store.upsert_machine("mac_ghost", "Ghost", "local", {}, MachineStatus.ONLINE, stale)

    m = _machine(c, "mac_ghost")
    assert m["live_cpu"] is None and m["live_mem"] is None
    assert m["live_battery"] is None
