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
from typing import Optional, Union

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
CREATE TABLE IF NOT EXISTS machine_tags (
    machine_id TEXT NOT NULL,
    tag        TEXT NOT NULL,
    PRIMARY KEY (machine_id, tag)
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
CREATE TABLE IF NOT EXISTS schedules (
    id           TEXT PRIMARY KEY,
    owner        TEXT NOT NULL,
    machine_id   TEXT NOT NULL,
    command      TEXT NOT NULL,
    cron         TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    last_run_key TEXT,
    last_run_ms  INTEGER,
    created_ms   INTEGER
);
CREATE TABLE IF NOT EXISTS apps (
    name           TEXT NOT NULL,
    owner          TEXT NOT NULL,
    description    TEXT,
    created_ms     INTEGER,
    last_active_ms INTEGER,
    deployed_ms    INTEGER,
    PRIMARY KEY (name, owner)
);
CREATE TABLE IF NOT EXISTS app_functions (
    app        TEXT NOT NULL,
    owner      TEXT NOT NULL,
    name       TEXT NOT NULL,
    source     TEXT NOT NULL,
    image      TEXT,
    schedule   TEXT,
    kind       TEXT NOT NULL DEFAULT 'function',
    port       INTEGER,
    url        TEXT,
    sandbox_id TEXT,
    created_ms INTEGER,
    PRIMARY KEY (app, owner, name)
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
    def __init__(self, path: Union[str, Path] = ":memory:"):
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        """
        WAL + busy_timeout, because this file is the whole control plane's spine.

        The default journal mode makes every reader block the writer and hands
        out "database is locked" the instant two things touch the file — and
        the daemon runs up to eight jobs at once, each writing state and output
        here while the HTTP API reads. Watched live on a Mac mini: a 1.4 GB
        host.db (months of sync-tar output and metric samples, see prune()) had
        the whole machine reading as wedged — every run queued for minutes,
        /v1/jobs timing out — while the daemon's 8-wide admission gate sat
        mostly idle. Parallelism was never the problem; the single flat-out
        contended journal was.
        """
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        self.db = _SafeDB(conn)
        self.db.executescript(_SCHEMA)
        self.db.commit()
        self._ensure_scope_column()
        self._ensure_app_columns()
        # History must not grow until the machine drowns. Best-effort: a store
        # that cannot prune is still a store.
        try:
            self.prune()
        except Exception:  # noqa: BLE001
            pass

    # How long finished jobs are worth keeping, and how much of one job's
    # output. Debugging wants recent history; nothing wants February's.
    PRUNE_JOB_AGE_MS = 7 * 24 * 3600 * 1000
    PRUNE_OUTPUT_CAP = 256 * 1024
    PRUNE_METRIC_KEEP = 50_000

    def prune(self) -> dict:
        """Keep the control plane's history bounded.

        Three unbounded growths, found the hard way on a 1.4 GB host.db:

          - finished jobs accumulate forever;
          - a job's ``output`` column holds whatever the job printed — and the
            pre-0.9.7 sync path printed multi-megabyte base64 tars, so the jobs
            table became a blob store nobody meant to build;
          - ``metric_samples`` gains a row every heartbeat, forever.

        Runs at every Store construction (host start), so a machine heals on
        restart without anyone knowing this table exists. VACUUM only when a
        meaningful amount was reclaimed — on a healthy db this is a no-op.
        """
        import time as _time

        now = int(_time.time() * 1000)
        stats = {"jobs_deleted": 0, "outputs_truncated": 0, "metrics_deleted": 0}

        cur = self.db.execute(
            "DELETE FROM jobs WHERE created_ms < ? AND state NOT IN ('running','dispatched')",
            (now - self.PRUNE_JOB_AGE_MS,),
        )
        stats["jobs_deleted"] = cur.rowcount

        cur = self.db.execute(
            "UPDATE jobs SET output = substr(output, 1, ?) || '…[truncated by retention]' "
            "WHERE LENGTH(output) > ?",
            (self.PRUNE_OUTPUT_CAP, self.PRUNE_OUTPUT_CAP),
        )
        stats["outputs_truncated"] = cur.rowcount

        cur = self.db.execute(
            "DELETE FROM metric_samples WHERE rowid < "
            "(SELECT COALESCE(MIN(rowid), 0) FROM "
            " (SELECT rowid FROM metric_samples ORDER BY rowid DESC LIMIT ?))",
            (self.PRUNE_METRIC_KEEP,),
        )
        stats["metrics_deleted"] = cur.rowcount
        self.db.commit()

        if stats["jobs_deleted"] + stats["metrics_deleted"] > 2000 or stats["outputs_truncated"] > 20:
            try:
                self.db.execute("VACUUM")
            except sqlite3.OperationalError:
                pass  # busy db — the space comes back on the next quiet start
        return stats

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
        out = [self._machine_row(r) for r in rows]
        for m in out:
            m["tags"] = self.tags_for(m["machine_id"])
        return out

    def get_machine(self, machine_id: str) -> Optional[dict]:
        r = self.db.execute(
            "SELECT * FROM machines WHERE machine_id=?", (machine_id,)
        ).fetchone()
        if not r:
            return None
        m = self._machine_row(r)
        m["tags"] = self.tags_for(machine_id)
        return m

    # -- tags (labels for routing) ------------------------------------------ #

    def tags_for(self, machine_id: str) -> list:
        rows = self.db.execute(
            "SELECT tag FROM machine_tags WHERE machine_id=? ORDER BY tag", (machine_id,)
        ).fetchall()
        return [r["tag"] for r in rows]

    def add_tags(self, machine_id: str, tags: list) -> None:
        for tag in tags:
            t = tag.strip().lower()
            if t:
                self.db.execute(
                    "INSERT OR IGNORE INTO machine_tags (machine_id, tag) VALUES (?, ?)",
                    (machine_id, t),
                )
        self.db.commit()

    def remove_tag(self, machine_id: str, tag: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM machine_tags WHERE machine_id=? AND tag=?", (machine_id, tag.strip().lower())
        )
        self.db.commit()
        return cur.rowcount > 0

    def delete_machine(self, machine_id: str, owner: Optional[str] = None) -> dict:
        """Remove a Mac from the fleet and revoke its ability to rejoin.

        A Mac could be added but never removed, so a decommissioned machine sat
        in the fleet forever and its device token stayed valid — meaning it could
        silently reconnect. Deleting the token is the part that actually makes
        this a disconnect rather than a cosmetic hide.

        Job rows are kept: they are the audit trail of what ran, and losing that
        because a machine was retired would be worse than an orphan reference.
        Returns per-table delete counts.
        """
        row = self.get_machine(machine_id)
        if not row or (owner and row.get("owner") != owner):
            return {}

        counts = {}
        for table in ("machine_tags", "device_tokens", "sandboxes", "volumes",
                      "metric_samples", "schedules"):
            try:
                cur = self.db.execute(f"DELETE FROM {table} WHERE machine_id=?", (machine_id,))
                counts[table] = cur.rowcount
            except sqlite3.OperationalError:
                pass  # table without a machine_id column in an older db
        cur = self.db.execute("DELETE FROM machines WHERE machine_id=?", (machine_id,))
        counts["machines"] = cur.rowcount
        self.db.commit()
        return counts

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

    def _ensure_app_columns(self) -> None:
        # Group jobs/sandboxes under a named app — added to pre-app databases.
        for table in ("jobs", "sandboxes"):
            try:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN app TEXT")
                self.db.commit()
            except Exception:  # noqa: BLE001 — column already exists
                pass
        # Web-endpoint columns on app_functions (added after the table shipped).
        for col in ("port INTEGER", "url TEXT", "sandbox_id TEXT"):
            try:
                self.db.execute(f"ALTER TABLE app_functions ADD COLUMN {col}")
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
        app: Optional[str] = None,
    ) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO jobs
               (request_id, machine_id, sandbox_id, command, state, created_ms, app)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (request_id, machine_id, sandbox_id, command, JobState.QUEUED.value, created_ms, app),
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
        app: Optional[str] = None,
    ) -> list[dict]:
        clauses, params = [], []
        if machine_id:
            clauses.append("machine_id=?")
            params.append(machine_id)
        if sandbox_id:
            clauses.append("sandbox_id=?")
            params.append(sandbox_id)
        if app:
            clauses.append("app=?")
            params.append(app)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self.db.execute(
            f"""SELECT request_id, machine_id, sandbox_id, command, state,
                       exit_code, duration_ms, created_ms, app
                FROM jobs {where} ORDER BY created_ms DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # -- sandboxes ---------------------------------------------------------- #

    def touch_sandbox(
        self, sandbox_id: str, machine_id: str, image: Optional[str], when_ms: int,
        app: Optional[str] = None,
    ) -> None:
        """Register a sandbox on first use; bump its activity on every exec."""
        self.db.execute(
            """INSERT INTO sandboxes
                 (sandbox_id, machine_id, image, status, created_ms, last_used_ms, exec_count, app)
               VALUES (?, ?, ?, 'active', ?, ?, 1, ?)
               ON CONFLICT(sandbox_id) DO UPDATE SET
                 last_used_ms=excluded.last_used_ms,
                 exec_count=sandboxes.exec_count + 1,
                 status='active',
                 image=COALESCE(sandboxes.image, excluded.image),
                 app=COALESCE(sandboxes.app, excluded.app)""",
            (sandbox_id, machine_id, image, when_ms, when_ms, app),
        )
        self.db.commit()

    def register_sandbox(
        self, sandbox_id: str, machine_id: str, image: Optional[str], when_ms: int,
        app: Optional[str] = None,
    ) -> None:
        """Create an empty sandbox (exec_count 0) — used by UI-driven creation."""
        self.db.execute(
            """INSERT OR IGNORE INTO sandboxes
                 (sandbox_id, machine_id, image, status, created_ms, last_used_ms, exec_count, app)
               VALUES (?, ?, ?, 'active', ?, ?, 0, ?)""",
            (sandbox_id, machine_id, image, when_ms, when_ms, app),
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

    def list_sandboxes(self, machine_id: Optional[str] = None,
                       app: Optional[str] = None) -> list[dict]:
        clauses, params = [], []
        if machine_id:
            clauses.append("machine_id=?")
            params.append(machine_id)
        if app:
            clauses.append("app=?")
            params.append(app)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            f"SELECT * FROM sandboxes {where} ORDER BY last_used_ms DESC", params,
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

    # -- schedules (recurring jobs) ----------------------------------------- #

    def create_schedule(self, sid: str, owner: str, machine_id: str, command: str,
                        cron: str, created_ms: int) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO schedules
               (id, owner, machine_id, command, cron, enabled, created_ms)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (sid, owner, machine_id, command, cron, created_ms),
        )
        self.db.commit()

    def list_schedules(self, owner: Optional[str] = None) -> list[dict]:
        if owner is None:
            rows = self.db.execute("SELECT * FROM schedules ORDER BY created_ms").fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM schedules WHERE owner=? ORDER BY created_ms", (owner,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_schedule(self, sid: str, owner: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM schedules WHERE id=? AND owner=?", (sid, owner)
        )
        self.db.commit()
        return cur.rowcount > 0

    def mark_schedule_run(self, sid: str, run_key: str, run_ms: int) -> None:
        self.db.execute(
            "UPDATE schedules SET last_run_key=?, last_run_ms=? WHERE id=?",
            (run_key, run_ms, sid),
        )
        self.db.commit()

    # -- apps (named projects that group runs/sandboxes/functions) ----------- #

    def upsert_app(self, name: str, owner: str, when_ms: int,
                   description: Optional[str] = None) -> None:
        """Register an app on first mention; refresh description if given.
        Zero-config: any run/sandbox naming an app calls this."""
        self.db.execute(
            """INSERT INTO apps (name, owner, description, created_ms, last_active_ms)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name, owner) DO UPDATE SET
                 description=COALESCE(excluded.description, apps.description)""",
            (name, owner, description, when_ms, when_ms),
        )
        self.db.commit()

    def touch_app(self, name: str, owner: str, when_ms: int) -> None:
        self.db.execute(
            "UPDATE apps SET last_active_ms=? WHERE name=? AND owner=?",
            (when_ms, name, owner),
        )
        self.db.commit()

    def mark_app_deployed(self, name: str, owner: str, when_ms: int) -> None:
        self.db.execute(
            "UPDATE apps SET deployed_ms=? WHERE name=? AND owner=?",
            (when_ms, name, owner),
        )
        self.db.commit()

    def list_apps(self, owner: Optional[str] = None) -> list[dict]:
        """Apps with rollup counts. Owner ``None`` (local/admin) sees all."""
        where, params = ("WHERE owner=?", [owner]) if owner else ("", [])
        rows = self.db.execute(f"SELECT * FROM apps {where} ORDER BY last_active_ms DESC",
                               params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["job_count"] = self.db.execute(
                "SELECT COUNT(*) AS c FROM jobs WHERE app=?", (d["name"],)
            ).fetchone()["c"]
            d["sandbox_count"] = self.db.execute(
                "SELECT COUNT(*) AS c FROM sandboxes WHERE app=?", (d["name"],)
            ).fetchone()["c"]
            d["function_count"] = self.db.execute(
                "SELECT COUNT(*) AS c FROM app_functions WHERE app=? AND owner=?",
                (d["name"], d["owner"]),
            ).fetchone()["c"]
            out.append(d)
        return out

    def get_app(self, name: str, owner: Optional[str] = None) -> Optional[dict]:
        where, params = ("name=? AND owner=?", [name, owner]) if owner else ("name=?", [name])
        r = self.db.execute(f"SELECT * FROM apps WHERE {where}", params).fetchone()
        return dict(r) if r else None

    def delete_app(self, name: str, owner: str) -> bool:
        cur = self.db.execute("DELETE FROM apps WHERE name=? AND owner=?", (name, owner))
        self.db.execute("DELETE FROM app_functions WHERE app=? AND owner=?", (name, owner))
        self.db.commit()
        return cur.rowcount > 0

    # -- app functions (deployed source that runs without the client) ------- #

    def put_app_function(self, app: str, owner: str, name: str, source: str,
                         image: Optional[str], schedule: Optional[str],
                         kind: str, when_ms: int, port: Optional[int] = None) -> None:
        self.db.execute(
            """INSERT INTO app_functions
                 (app, owner, name, source, image, schedule, kind, port, created_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(app, owner, name) DO UPDATE SET
                 source=excluded.source, image=excluded.image,
                 schedule=excluded.schedule, kind=excluded.kind, port=excluded.port""",
            (app, owner, name, source, image, schedule, kind, port, when_ms),
        )
        self.db.commit()

    def set_app_function_url(self, app: str, owner: str, name: str,
                            url: str, sandbox_id: str) -> None:
        self.db.execute(
            "UPDATE app_functions SET url=?, sandbox_id=? WHERE app=? AND owner=? AND name=?",
            (url, sandbox_id, app, owner, name),
        )
        self.db.commit()

    def list_app_functions(self, app: str, owner: Optional[str] = None) -> list[dict]:
        where, params = ("app=? AND owner=?", [app, owner]) if owner else ("app=?", [app])
        rows = self.db.execute(
            f"SELECT app, owner, name, image, schedule, kind, port, url, sandbox_id, created_ms "
            f"FROM app_functions WHERE {where} ORDER BY name", params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_app_function(self, app: str, name: str,
                         owner: Optional[str] = None) -> Optional[dict]:
        where, params = (("app=? AND name=? AND owner=?", [app, name, owner])
                         if owner else ("app=? AND name=?", [app, name]))
        r = self.db.execute(f"SELECT * FROM app_functions WHERE {where}", params).fetchone()
        return dict(r) if r else None

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
