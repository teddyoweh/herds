"""A job in flight belongs to a process that no longer exists.

Everything that asks "how busy is this Mac?" treats `queued`/`dispatched`/
`running` as live: `live_sandbox_ids`, the `/v1/stats` counter, and the
daemon's 8-wide admission gate. A job only leaves those states when the
executor that owns it reports back — so a daemon that is killed, crashes, or
loses power strands every job it had in flight, permanently.

The capacity is what makes it fatal. Observed on a real Mac mini: 57 jobs stuck
in `dispatched`, and the machine answered every new request with "admission cap
reached (8/8 live, 32/32 queued)" — through a stop, a kill and a clean restart,
because the count is rebuilt from these rows. An idle Mac, unable to accept
work, with nothing naming the reason.
"""

from __future__ import annotations

import time

from herds.control.store import Store


def _job(store: Store, rid: str, state: str) -> None:
    """`created_ms` is NOW on purpose: `Store.__init__` also prunes, and a row
    dated 0 is older than the 7-day retention, so it vanishes before the
    assertion — which looks exactly like the reap eating finished jobs."""
    store.db.execute(
        "INSERT INTO jobs (request_id, machine_id, command, state, created_ms) "
        "VALUES (?,?,?,?,?)",
        (rid, "mac_test", "echo hi", state, int(time.time() * 1000)),
    )
    store.db.commit()


def test_in_flight_jobs_are_failed_at_open(tmp_path):
    """The whole fix: a fresh Store must not inherit somebody else's work."""
    path = tmp_path / "host.db"
    s = Store(path)
    for i, st in enumerate(("queued", "dispatched", "running")):
        _job(s, f"rq_{i}", st)
    assert len(s.live_sandbox_ids()) == 0  # no sandbox ids on these rows
    live = s.db.execute(
        "SELECT count(*) c FROM jobs WHERE state IN ('queued','dispatched','running')"
    ).fetchone()["c"]
    assert live == 3

    # Reopening is what a restart looks like.
    s2 = Store(path)
    live2 = s2.db.execute(
        "SELECT count(*) c FROM jobs WHERE state IN ('queued','dispatched','running')"
    ).fetchone()["c"]
    assert live2 == 0, "a restart must not inherit in-flight jobs"


def test_finished_jobs_are_untouched(tmp_path):
    """Reaping must never rewrite history — `succeeded` is a result, not a state
    to be tidied. Losing it would make the job list lie about what ran."""
    path = tmp_path / "host.db"
    s = Store(path)
    _job(s, "rq_ok", "succeeded")
    _job(s, "rq_bad", "failed")
    _job(s, "rq_hung", "running")
    Store(path)  # restart

    s3 = Store(path)
    rows = dict(
        (r["request_id"], r["state"])
        for r in s3.db.execute("SELECT request_id, state FROM jobs").fetchall()
    )
    assert rows["rq_ok"] == "succeeded"
    assert rows["rq_bad"] == "failed"
    assert rows["rq_hung"] == "failed", "the hung one is the ghost"


def test_reap_reports_how_many_it_cleared(tmp_path):
    s = Store(tmp_path / "host.db")
    for i in range(5):
        _job(s, f"rq_{i}", "dispatched")
    assert s.reap_orphaned_jobs() == 5
    assert s.reap_orphaned_jobs() == 0, "reaping twice must be a no-op"


def test_an_exit_code_is_left_alone_when_it_exists(tmp_path):
    """A job that reported an exit code before dying keeps it: the reap marks
    the row finished, it does not invent a result the executor never gave."""
    s = Store(tmp_path / "host.db")
    s.db.execute(
        "INSERT INTO jobs (request_id, machine_id, command, state, exit_code, created_ms) "
        "VALUES (?,?,?,?,?,?)",
        ("rq_x", "mac_test", "echo", "running", 7, int(time.time() * 1000)),
    )
    s.db.commit()
    s.reap_orphaned_jobs()
    r = s.db.execute("SELECT state, exit_code FROM jobs WHERE request_id='rq_x'").fetchone()
    assert r["state"] == "failed"
    assert r["exit_code"] == 7
