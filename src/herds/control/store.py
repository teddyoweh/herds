"""Durable control-plane state in SQLite.

The control plane is deliberately tiny: it remembers *who owns what* and the
status/history of machines and jobs. It never stores volumes, sandboxes, or
caches -- those live on the Mac. "The Mac is the cloud."
"""

from __future__ import annotations

import json
import sqlite3
import secrets
import threading
from pathlib import Path
from typing import Optional

from ..protocol import JobState, MachineStatus


_SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (
    machine_id   TEXT PRIMARY KEY,
    name         TEXT,
    owner        TEXT,
    info_json    TEXT,
    status       TEXT NOT NULL DEFAULT 'offline',
    last_seen_ms INTEGER
);
CREATE TABLE IF NOT EXISTS api_keys (
    key        TEXT PRIMARY KEY,
    owner      TEXT NOT NULL,
    label      TEXT,
    scope      TEXT NOT NULL DEFAULT 'admin'
);
CREATE TABLE IF NOT EXISTS device_tokens (
    token      TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL,
    owner      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    request_id  TEXT PRIMARY KEY,
    machine_id  TEXT NOT NULL,
    sandbox_id  TEXT,
    command     TEXT,
    state       TEXT NOT NULL,
    exit_code   INTEGER,
    duration_ms INTEGER,
    created_ms  INTEGER,
    output      TEXT
);
CREATE TABLE IF NOT EXISTS sandboxes (
    sandbox_id  TEXT PRIMARY KEY,
    machine_id  TEXT NOT NULL,
    image       TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_ms  INTEGER,
    last_used_ms INTEGER,
    exec_count  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS secrets (
    name       TEXT NOT NULL,
    owner      TEXT NOT NULL,
    keys_json  TEXT NOT NULL,
    value_json TEXT NOT NULL,
    created_ms INTEGER,
    PRIMARY KEY (name, owner)
);
CREATE TABLE IF NOT EXISTS volumes (
    name       TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    updated_ms INTEGER,
    PRIMARY KEY (name, machine_id)
);
CREATE TABLE IF NOT EXISTS metric_samples (
    machine_id TEXT NOT NULL,
    t_ms       INTEGER NOT NULL,
    cpu        REAL,
    mem        REAL
);
CREATE INDEX IF NOT EXISTS idx_metrics_t ON metric_samples (t_ms);
CREATE TABLE IF NOT EXISTS exposed_ports (
    sandbox_id TEXT NOT NULL,
    port       INTEGER NOT NULL,
    name       TEXT,
    created_ms INTEGER,
    PRIMARY KEY (sandbox_id, port)
);
"""


class _Result:
    """Detached query result — rows are fetched eagerly so callers can iterate
    after the connection lock is released (safe across FastAPI's threadpool)."""

    def __init__(self, rows: list, rowcount: int, lastrowid):
        self._rows = rows
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class _SafeDB:
    """One sqlite connection, serialized across threads. FastAPI runs sync
    endpoints in a worker threadpool, so concurrent dashboard requests would
    otherwise race on a single shared connection (`sqlite3.InterfaceError:
    bad parameter or other API misuse`). Every op runs under one re-entrant lock,
    and ``execute`` fetches eagerly so the returned result is connection-free."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.RLock()

    def execute(self, sql: str, params=()) -> _Result:
        with self._lock:
            cur = self._conn.execute(sql, params)
            try:
                rows = cur.fetchall()
            except sqlite3.Error:
                rows = []
            return _Result(rows, cur.rowcount, cur.lastrowid)

    def executescript(self, sql: str) -> None:
        with self._lock:
            self._conn.executescript(sql)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        self.db = _SafeDB(conn)
        self.db.executescript(_SCHEMA)
        self.db.commit()
        self._ensure_scope_column()

    # -- machines ----------------------------------------------------------- #

    def upsert_machine(
        self,
        machine_id: str,
        name: str,
        owner: str,
        info: dict,
        status: MachineStatus,
        last_seen_ms: int,
    ) -> None:
        self.db.execute(
            """INSERT INTO machines (machine_id, name, owner, info_json, status, last_seen_ms)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(machine_id) DO UPDATE SET
                 name=excluded.name, info_json=excluded.info_json,
                 status=excluded.status, last_seen_ms=excluded.last_seen_ms""",
            (machine_id, name, owner, json.dumps(info), status.value, last_seen_ms),
        )
        self.db.commit()

    def set_machine_status(self, machine_id: str, status: MachineStatus, last_seen_ms: int) -> None:
        self.db.execute(
            "UPDATE machines SET status=?, last_seen_ms=? WHERE machine_id=?",
            (status.value, last_seen_ms, machine_id),
        )
        self.db.commit()

    def list_machines(self, owner: Optional[str] = None) -> list[dict]:
        if owner:
            rows = self.db.execute("SELECT * FROM machines WHERE owner=?", (owner,)).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM machines").fetchall()
        return [self._machine_row(r) for r in rows]

    def get_machine(self, machine_id: str) -> Optional[dict]:
        r = self.db.execute(
            "SELECT * FROM machines WHERE machine_id=?", (machine_id,)
        ).fetchone()
        return self._machine_row(r) if r else None

    @staticmethod
    def _machine_row(r: sqlite3.Row) -> dict:
        return {
            "machine_id": r["machine_id"],
            "name": r["name"],
            "owner": r["owner"],
            "info": json.loads(r["info_json"]) if r["info_json"] else None,
            "status": r["status"],
            "last_seen_ms": r["last_seen_ms"],
        }

    # -- auth --------------------------------------------------------------- #

    def _ensure_scope_column(self) -> None:
        try:  # migrate pre-scope databases
            self.db.execute("ALTER TABLE api_keys ADD COLUMN scope TEXT NOT NULL DEFAULT 'admin'")
            self.db.commit()
        except Exception:  # noqa: BLE001 — column already exists
            pass

    def create_api_key(self, owner: str, label: str = "", scope: str = "admin") -> str:
        key = "herds_sk_" + secrets.token_urlsafe(24)
        self.db.execute(
            "INSERT INTO api_keys (key, owner, label, scope) VALUES (?, ?, ?, ?)",
            (key, owner, label, scope),
        )
        self.db.commit()
        return key

    def put_api_key(self, key: str, owner: str, label: str = "", scope: str = "admin") -> None:
        """Insert a specific (already-known) key — used for the stable host token."""
        self.db.execute(
            "INSERT OR IGNORE INTO api_keys (key, owner, label, scope) VALUES (?, ?, ?, ?)",
            (key, owner, label, scope),
        )
        self.db.commit()

    def owner_for_api_key(self, key: str) -> Optional[str]:
        r = self.db.execute("SELECT owner FROM api_keys WHERE key=?", (key,)).fetchone()
        return r["owner"] if r else None

    def scope_for_api_key(self, key: str) -> str:
        r = self.db.execute("SELECT scope FROM api_keys WHERE key=?", (key,)).fetchone()
        return (r["scope"] if r and r["scope"] else "admin")

    def list_api_keys(self, owner: str) -> list[dict]:
        """Returns masked keys (never the full secret) + label + scope."""
        rows = self.db.execute(
            "SELECT key, label, scope FROM api_keys WHERE owner=?", (owner,)
        ).fetchall()
        out = []
        for r in rows:
            k = r["key"]
            out.append({"label": r["label"], "scope": r["scope"] or "admin", "masked": k[:13] + "…" + k[-4:]})
        return out

    def delete_api_key_by_masked(self, owner: str, masked_prefix: str) -> bool:
        # match by prefix (the visible head) for revoke-by-display.
        rows = self.db.execute("SELECT key FROM api_keys WHERE owner=?", (owner,)).fetchall()
        for r in rows:
            if r["key"].startswith(masked_prefix):
                self.db.execute("DELETE FROM api_keys WHERE key=?", (r["key"],))
                self.db.commit()
                return True
        return False

    def create_device_token(self, machine_id: str, owner: str) -> str:
        token = "herds_dt_" + secrets.token_urlsafe(24)
        self.db.execute(
            "INSERT INTO device_tokens (token, machine_id, owner) VALUES (?, ?, ?)",
            (token, machine_id, owner),
        )
        self.db.commit()
        return token

    def device_token_info(self, token: str) -> Optional[dict]:
        r = self.db.execute(
            "SELECT machine_id, owner FROM device_tokens WHERE token=?", (token,)
        ).fetchone()
        return {"machine_id": r["machine_id"], "owner": r["owner"]} if r else None

    # -- jobs --------------------------------------------------------------- #

    def create_job(
        self,
        request_id: str,
        machine_id: str,
        command: str,
        created_ms: int,
        sandbox_id: Optional[str] = None,
    ) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO jobs
               (request_id, machine_id, sandbox_id, command, state, created_ms)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request_id, machine_id, sandbox_id, command, JobState.QUEUED.value, created_ms),
        )
        self.db.commit()

    def update_job(
        self,
        request_id: str,
        state: JobState,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        self.db.execute(
            "UPDATE jobs SET state=?, exit_code=?, duration_ms=? WHERE request_id=?",
            (state.value, exit_code, duration_ms, request_id),
        )
        self.db.commit()

    def set_job_output(self, request_id: str, output: list) -> None:
        self.db.execute(
            "UPDATE jobs SET output=? WHERE request_id=?",
            (json.dumps(output), request_id),
        )
        self.db.commit()

    def get_job(self, request_id: str) -> Optional[dict]:
        r = self.db.execute("SELECT * FROM jobs WHERE request_id=?", (request_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["output"] = json.loads(d["output"]) if d["output"] else []
        return d

    def list_jobs(
        self,
        machine_id: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses, params = [], []
        if machine_id:
            clauses.append("machine_id=?")
            params.append(machine_id)
        if sandbox_id:
            clauses.append("sandbox_id=?")
            params.append(sandbox_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self.db.execute(
            f"""SELECT request_id, machine_id, sandbox_id, command, state,
                       exit_code, duration_ms, created_ms
                FROM jobs {where} ORDER BY created_ms DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # -- sandboxes ---------------------------------------------------------- #

    def touch_sandbox(
        self, sandbox_id: str, machine_id: str, image: Optional[str], when_ms: int
    ) -> None:
        """Register a sandbox on first use; bump its activity on every exec."""
        self.db.execute(
            """INSERT INTO sandboxes
                 (sandbox_id, machine_id, image, status, created_ms, last_used_ms, exec_count)
               VALUES (?, ?, ?, 'active', ?, ?, 1)
               ON CONFLICT(sandbox_id) DO UPDATE SET
                 last_used_ms=excluded.last_used_ms,
                 exec_count=sandboxes.exec_count + 1,
                 status='active',
                 image=COALESCE(sandboxes.image, excluded.image)""",
            (sandbox_id, machine_id, image, when_ms, when_ms),
        )
        self.db.commit()

    def register_sandbox(
        self, sandbox_id: str, machine_id: str, image: Optional[str], when_ms: int
    ) -> None:
        """Create an empty sandbox (exec_count 0) — used by UI-driven creation."""
        self.db.execute(
            """INSERT OR IGNORE INTO sandboxes
                 (sandbox_id, machine_id, image, status, created_ms, last_used_ms, exec_count)
               VALUES (?, ?, ?, 'active', ?, ?, 0)""",
            (sandbox_id, machine_id, image, when_ms, when_ms),
        )
        self.db.commit()

    # -- exposed ports (sandbox → URL) -------------------------------------- #

    def unique_port_name(self, slug: str, sandbox_id: str, port: int) -> str:
        """Return a globally-unique name slug for routing (append -2, -3… on clash)."""
        base = slug or f"s{port}"
        candidate, i = base, 1
        while True:
            r = self.db.execute(
                "SELECT sandbox_id, port FROM exposed_ports WHERE name=?", (candidate,)
            ).fetchone()
            if r is None or (r["sandbox_id"] == sandbox_id and r["port"] == port):
                return candidate
            i += 1
            candidate = f"{base}-{i}"

    def expose_port(self, sandbox_id: str, port: int, name: str, when_ms: int) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO exposed_ports (sandbox_id, port, name, created_ms)
               VALUES (?, ?, ?, ?)""",
            (sandbox_id, port, name, when_ms),
        )
        self.db.commit()

    def port_by_name(self, name: str) -> Optional[dict]:
        r = self.db.execute(
            """SELECT e.sandbox_id, e.port, s.machine_id
               FROM exposed_ports e JOIN sandboxes s ON e.sandbox_id = s.sandbox_id
               WHERE e.name = ?""",
            (name,),
        ).fetchone()
        return dict(r) if r else None

    def unexpose_port(self, sandbox_id: str, port: int) -> None:
        self.db.execute("DELETE FROM exposed_ports WHERE sandbox_id=? AND port=?", (sandbox_id, port))
        self.db.commit()

    def list_ports(self, sandbox_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT port, name, created_ms FROM exposed_ports WHERE sandbox_id=? ORDER BY port",
            (sandbox_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def port_machine(self, sandbox_id: str, port: int) -> Optional[str]:
        r = self.db.execute("SELECT machine_id FROM sandboxes WHERE sandbox_id=?", (sandbox_id,)).fetchone()
        if not r:
            return None
        p = self.db.execute(
            "SELECT 1 FROM exposed_ports WHERE sandbox_id=? AND port=?", (sandbox_id, port)
        ).fetchone()
        return r["machine_id"] if p else None

    def delete_sandbox(self, sandbox_id: str) -> bool:
        cur = self.db.execute("DELETE FROM sandboxes WHERE sandbox_id=?", (sandbox_id,))
        self.db.commit()
        return cur.rowcount > 0

    def set_sandbox_status(self, sandbox_id: str, status: str) -> None:
        self.db.execute(
            "UPDATE sandboxes SET status=? WHERE sandbox_id=?", (status, sandbox_id)
        )
        self.db.commit()

    def get_sandbox(self, sandbox_id: str) -> Optional[dict]:
        r = self.db.execute(
            "SELECT * FROM sandboxes WHERE sandbox_id=?", (sandbox_id,)
        ).fetchone()
        return dict(r) if r else None

    def list_sandboxes(self, machine_id: Optional[str] = None) -> list[dict]:
        if machine_id:
            rows = self.db.execute(
                "SELECT * FROM sandboxes WHERE machine_id=? ORDER BY last_used_ms DESC",
                (machine_id,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM sandboxes ORDER BY last_used_ms DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # A sandbox is "live" while it has a process still running.
    _ACTIVE = ("queued", "dispatched", "running")

    def live_sandbox_ids(self) -> set[str]:
        q = ",".join("?" * len(self._ACTIVE))
        rows = self.db.execute(
            f"SELECT DISTINCT sandbox_id FROM jobs "
            f"WHERE sandbox_id IS NOT NULL AND state IN ({q})",
            self._ACTIVE,
        ).fetchall()
        return {r["sandbox_id"] for r in rows}

    def active_jobs_for_sandbox(self, sandbox_id: str) -> list[str]:
        q = ",".join("?" * len(self._ACTIVE))
        rows = self.db.execute(
            f"SELECT request_id FROM jobs WHERE sandbox_id=? AND state IN ({q})",
            (sandbox_id, *self._ACTIVE),
        ).fetchall()
        return [r["request_id"] for r in rows]

    # -- secrets ------------------------------------------------------------ #

    def put_secret(
        self, name: str, owner: str, values: dict, created_ms: int
    ) -> None:
        self.db.execute(
            """INSERT INTO secrets (name, owner, keys_json, value_json, created_ms)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name, owner) DO UPDATE SET
                 keys_json=excluded.keys_json,
                 value_json=excluded.value_json""",
            (name, owner, json.dumps(sorted(values.keys())), json.dumps(values), created_ms),
        )
        self.db.commit()

    def get_secret_values(self, name: str, owner: str) -> Optional[dict]:
        r = self.db.execute(
            "SELECT value_json FROM secrets WHERE name=? AND owner=?", (name, owner)
        ).fetchone()
        return json.loads(r["value_json"]) if r else None

    def list_secrets(self, owner: str) -> list[dict]:
        """Returns metadata only -- key NAMES, never values."""
        rows = self.db.execute(
            "SELECT name, keys_json, created_ms FROM secrets WHERE owner=? ORDER BY name",
            (owner,),
        ).fetchall()
        return [
            {"name": r["name"], "keys": json.loads(r["keys_json"]), "created_ms": r["created_ms"]}
            for r in rows
        ]

    def delete_secret(self, name: str, owner: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM secrets WHERE name=? AND owner=?", (name, owner)
        )
        self.db.commit()
        return cur.rowcount > 0

    # -- volumes (reported by the daemon) ----------------------------------- #

    def report_volumes(self, machine_id: str, volumes: list[dict], when_ms: int) -> None:
        self.db.execute("DELETE FROM volumes WHERE machine_id=?", (machine_id,))
        for v in volumes:
            self.db.execute(
                """INSERT OR REPLACE INTO volumes
                     (name, machine_id, size_bytes, file_count, updated_ms)
                   VALUES (?, ?, ?, ?, ?)""",
                (v["name"], machine_id, v.get("size_bytes", 0), v.get("file_count", 0), when_ms),
            )
        self.db.commit()

    # -- metrics history (persisted, survives restarts) --------------------- #

    _metric_inserts = 0

    def record_metric_sample(self, machine_id: str, t_ms: int, cpu: float, mem: float) -> None:
        self.db.execute(
            "INSERT INTO metric_samples (machine_id, t_ms, cpu, mem) VALUES (?, ?, ?, ?)",
            (machine_id, t_ms, cpu, mem),
        )
        # Prune opportunistically (keep ~26h) so the table stays bounded.
        self._metric_inserts += 1
        if self._metric_inserts % 200 == 0:
            self.db.execute(
                "DELETE FROM metric_samples WHERE t_ms < ?", (t_ms - 26 * 3600_000,)
            )
        self.db.commit()

    def metric_samples(self, since_ms: int, machine_id: Optional[str] = None) -> list[tuple]:
        if machine_id:
            rows = self.db.execute(
                "SELECT t_ms, cpu, mem FROM metric_samples WHERE t_ms >= ? AND machine_id=? ORDER BY t_ms",
                (since_ms, machine_id),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT t_ms, cpu, mem FROM metric_samples WHERE t_ms >= ? ORDER BY t_ms",
                (since_ms,),
            ).fetchall()
        return [(r["t_ms"], r["cpu"], r["mem"]) for r in rows]

    def latest_metric(self, machine_id: Optional[str] = None) -> Optional[tuple]:
        if machine_id:
            r = self.db.execute(
                "SELECT cpu, mem FROM metric_samples WHERE machine_id=? ORDER BY t_ms DESC LIMIT 1",
                (machine_id,),
            ).fetchone()
        else:
            r = self.db.execute(
                "SELECT cpu, mem FROM metric_samples ORDER BY t_ms DESC LIMIT 1"
            ).fetchone()
        return (r["cpu"], r["mem"]) if r else None

    def list_volumes(self, machine_id: Optional[str] = None) -> list[dict]:
        if machine_id:
            rows = self.db.execute(
                "SELECT * FROM volumes WHERE machine_id=? ORDER BY name", (machine_id,)
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM volumes ORDER BY name").fetchall()
        return [dict(r) for r in rows]
