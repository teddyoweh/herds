"""The control plane's history must stay bounded — found via a 1.4 GB host.db.

Three growths and a lock mode, each pinned: old finished jobs go, giant job
outputs get capped, metric samples keep only a recent window, and the
connection runs WAL with a busy timeout so eight concurrent jobs contend
gracefully instead of throwing "database is locked".
"""

from __future__ import annotations

import time

from herds.control.store import Store


def _old_ms(days: float) -> int:
    return int((time.time() - days * 86400) * 1000)


def test_old_finished_jobs_are_pruned(tmp_path):
    s = Store(tmp_path / "h.db")
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms) VALUES ('old','m','succeeded',?)", (_old_ms(30),))
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms) VALUES ('new','m','succeeded',?)", (_old_ms(0.5),))
    # A month-old but still RUNNING job must survive — pruning live work would
    # orphan a real process's bookkeeping.
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms) VALUES ('live','m','running',?)", (_old_ms(30),))
    s.db.commit()
    s.prune()
    left = {r["request_id"] for r in s.db.execute("SELECT request_id FROM jobs").fetchall()}
    assert left == {"new", "live"}


def test_giant_outputs_are_capped(tmp_path):
    s = Store(tmp_path / "h.db")
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms, output) VALUES ('big','m','succeeded',?,?)",
                 (_old_ms(0.1), "x" * (Store.PRUNE_OUTPUT_CAP + 500_000)))
    s.db.commit()
    s.prune()
    out = s.db.execute("SELECT output FROM jobs WHERE request_id='big'").fetchone()["output"]
    assert len(out) < Store.PRUNE_OUTPUT_CAP + 100
    assert out.endswith("[truncated by retention]")


def test_giant_commands_are_capped(tmp_path):
    # The bug the first cut missed: bloat lived in `command`, not `output`.
    s = Store(tmp_path / "h.db")
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms, command) VALUES ('bigcmd','m','succeeded',?,?)",
                 (_old_ms(0.1), "base64blob" * 200_000))
    s.db.commit()
    s.prune()
    cmd = s.db.execute("SELECT command FROM jobs WHERE request_id='bigcmd'").fetchone()["command"]
    assert len(cmd) < Store.PRUNE_COMMAND_CAP + 100
    assert cmd.endswith("[truncated by retention]")


def test_metric_samples_keep_a_window(tmp_path):
    s = Store(tmp_path / "h.db")
    keep = Store.PRUNE_METRIC_KEEP
    s.db.executemany("INSERT INTO metric_samples (machine_id, t_ms, cpu, mem) VALUES ('m',?,0,0)",
                     [(i,) for i in range(keep + 500)])
    s.db.commit()
    s.prune()
    n = s.db.execute("SELECT COUNT(*) c FROM metric_samples").fetchone()["c"]
    assert n == keep


def test_wal_and_busy_timeout(tmp_path):
    s = Store(tmp_path / "h.db")
    assert s.db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert int(s.db.execute("PRAGMA busy_timeout").fetchone()[0]) == 5000


def test_prune_runs_at_construction(tmp_path):
    p = tmp_path / "h.db"
    s = Store(p)
    s.db.execute("INSERT INTO jobs (request_id, machine_id, state, created_ms) VALUES ('old','m','failed',?)", (_old_ms(30),))
    s.db.commit()
    s.db.conn.close() if hasattr(s.db, "conn") else None
    s2 = Store(p)  # a restart is the heal
    assert s2.db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 0
