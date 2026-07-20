"""The Herds control plane.

A small FastAPI service that does three jobs and nothing more:
  1. Holds the persistent WebSocket from each Mac's daemon (the agent).
  2. Accepts ``exec`` requests from the SDK over REST and pushes them down the
     right agent socket.
  3. Fans out the streamed stdout/stderr/exit frames back to whichever SDK
     client is listening, correlated by request_id.

Live connection state is in-memory (single process); durable facts -- machines,
api keys, job history -- live in SQLite via :class:`Store`. For multi-process
scale you'd swap the in-memory fan-out for Redis pub/sub, but the boundaries
here are drawn so that change is local.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from .. import config
from ..protocol import (
    ExecAccepted,
    ExecRequest,
    Frame,
    FrameType,
    JobState,
    MachineStatus,
    exec_frame,
    session_start_frame,
    snapshot_frame,
    stdin_frame,
    tunnel_close_frame,
    tunnel_data_frame,
    tunnel_open_frame,
)
from .store import Store

# In dev (the default for local use) we don't force auth -- the magic should
# work the instant you run it. Set HERDS_REQUIRE_AUTH=1 to enforce keys.
REQUIRE_AUTH = os.environ.get("HERDS_REQUIRE_AUTH") == "1"
# Wildcard domain for named-subdomain port links, e.g. "ports.example.com" →
# https://<name>.ports.example.com. Needs a wildcard tunnel route (Cloudflare
# named tunnel). Without it, links fall back to the universal /p/<id>/<port>/ path.
PORTS_DOMAIN = os.environ.get("HERDS_PORTS_DOMAIN", "").strip().lower()


def _slugify(s: str) -> str:
    import re as _re

    s = _re.sub(r"[^a-z0-9-]+", "-", (s or "").lower()).strip("-")
    return s[:40]
DEFAULT_OWNER = "local"


class AgentConn:
    """A live daemon connection."""

    def __init__(self, machine_id: str, owner: str, ws: WebSocket):
        self.machine_id = machine_id
        self.owner = owner
        self.ws = ws
        self.info: dict = {}
        self.inflight: set[str] = set()   # request_ids dispatched here, awaiting EXIT
        self.tunnels: set[str] = set()    # raw-tunnel stream_ids open on this agent
        # One socket, many concurrent senders (exec dispatch, fs RPC, port proxy,
        # and now high-throughput raw tunnels): serialize sends so frames never
        # interleave on the wire.
        self._send_lock = asyncio.Lock()

    async def send(self, frame: Frame) -> None:
        async with self._send_lock:
            await self.ws.send_text(frame.dump())


class Hub:
    """In-memory routing between agents and SDK clients."""

    def __init__(self, store: Store):
        self.store = store
        self.agents: dict[str, AgentConn] = {}
        # Per-request output buffer (for replay) and live subscriber queues.
        self.buffers: dict[str, list[Frame]] = {}
        self.subscribers: dict[str, set[asyncio.Queue]] = {}
        self.finished: set[str] = set()
        # Durable-ish log accumulation: [stream, text] chunks per request,
        # persisted to the job row on EXIT so finished runs stay inspectable.
        self.logbuf: dict[str, list[list[str]]] = {}
        self._LOG_CAP = 4000
        # request_ids that have produced output (→ job state running).
        self.started: set[str] = set()
        # Live CPU/memory samples per machine: (t_ms, cpu, mem). ~1h at 5s.
        self.metrics: dict[str, deque] = {}
        # Live battery per machine: machine_id -> (pct|None, charging|None). In-memory
        # only (no DB migration) — a UI wants "current", not history.
        self.battery: dict[str, tuple] = {}
        # In-flight request→response RPCs to agents (filesystem ops), by id.
        self.pending: dict[str, asyncio.Future] = {}
        # Raw TCP tunnels: stream_id -> the client WebSocket bound to that tunnel,
        # plus a future resolved when the agent confirms the dial (TUNNEL_READY).
        self.tunnels: dict[str, WebSocket] = {}
        self.tunnel_ready: dict[str, asyncio.Future] = {}
        # Resident sessions: request_id -> future resolved when the agent confirms
        # the process is live (SESSION_READY), so start_session can block until then.
        self.session_ready: dict[str, asyncio.Future] = {}

    def resolve_rpc(self, request_id: str, payload: dict) -> None:
        fut = self.pending.pop(request_id, None)
        if fut and not fut.done():
            fut.set_result(payload)

    def record_metric(self, machine_id: str, t_ms: int, cpu: float, mem: float) -> None:
        buf = self.metrics.setdefault(machine_id, deque(maxlen=720))
        buf.append((t_ms, cpu, mem))

    # -- agent registry ----------------------------------------------------- #

    def add_agent(self, conn: AgentConn) -> None:
        self.agents[conn.machine_id] = conn

    def remove_agent(self, machine_id: str) -> None:
        self.agents.pop(machine_id, None)
        self.store.set_machine_status(machine_id, MachineStatus.OFFLINE, config.now_ms())

    def agent(self, machine_id: str) -> Optional[AgentConn]:
        return self.agents.get(machine_id)

    # -- log fan-out -------------------------------------------------------- #

    def publish(self, frame: Frame) -> None:
        rid = frame.request_id
        if rid is None:
            return
        self.buffers.setdefault(rid, []).append(frame)
        for q in list(self.subscribers.get(rid, ())):
            q.put_nowait(frame)
        # Accumulate stdout/stderr for durable inspection.
        if frame.type in (FrameType.STDOUT, FrameType.STDERR):
            buf = self.logbuf.setdefault(rid, [])
            if len(buf) < self._LOG_CAP:
                buf.append([frame.type.value, frame.data.get("text", "")])
        if frame.type == FrameType.EXIT:
            self.finished.add(rid)
            self.store.set_job_output(rid, self.logbuf.pop(rid, []))

    def subscribe(self, request_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay anything already buffered so a late subscriber misses nothing.
        for frame in self.buffers.get(request_id, []):
            q.put_nowait(frame)
        self.subscribers.setdefault(request_id, set()).add(q)
        return q

    def unsubscribe(self, request_id: str, q: asyncio.Queue) -> None:
        subs = self.subscribers.get(request_id)
        if subs:
            subs.discard(q)
            if not subs:
                self.subscribers.pop(request_id, None)

    def cleanup(self, request_id: str) -> None:
        if request_id in self.finished and not self.subscribers.get(request_id):
            self.buffers.pop(request_id, None)
            self.finished.discard(request_id)


def _cron_field(expr: str, lo: int, hi: int) -> set:
    """Parse one crontab field into the set of matching values. Supports
    ``*``, ``*/N``, ``a-b``, ``a-b/N``, ``a,b,c`` and plain ``N``."""
    out: set = set()
    for part in expr.split(","):
        step = 1
        rng = part
        if "/" in part:
            rng, st = part.split("/", 1)
            step = int(st)
        if rng in ("*", ""):
            start, end = lo, hi
        elif "-" in rng:
            a, b = rng.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(rng)
        v = start
        while v <= end:
            if lo <= v <= hi:
                out.add(v)
            v += step
    return out


def cron_due(expr: str, dt) -> bool:
    """True if a 5-field crontab expression matches datetime ``dt`` (local time)."""
    parts = expr.split()
    if len(parts) != 5:
        return False
    m, h, dom, mon, dow = parts
    if dt.minute not in _cron_field(m, 0, 59):
        return False
    if dt.hour not in _cron_field(h, 0, 23):
        return False
    if dt.month not in _cron_field(mon, 1, 12):
        return False
    # cron weekday: 0/7 = Sunday … 6 = Saturday; python weekday() is Mon=0.
    cron_dow = (dt.weekday() + 1) % 7
    dow_set = _cron_field(dow.replace("7", "0"), 0, 6)
    dom_ok = dt.day in _cron_field(dom, 1, 31)
    dow_ok = cron_dow in dow_set
    dom_r, dow_r = dom.strip() != "*", dow.strip() != "*"
    if dom_r and dow_r:        # Vixie cron: OR when both are restricted
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def create_app(db_path: str | Path = ":memory:") -> FastAPI:
    store = Store(db_path)
    hub = Hub(store)
    app = FastAPI(title="Herds Control Plane", version="0.1.0")
    app.state.store = store
    app.state.hub = hub

    # The Next.js dashboard is a separate origin; allow it to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- auth helpers ------------------------------------------------------- #

    def owner_from_key(authorization: Optional[str]) -> str:
        if not authorization:
            if REQUIRE_AUTH:
                raise HTTPException(401, "missing API key")
            return DEFAULT_OWNER
        key = authorization.removeprefix("Bearer ").strip()
        owner = store.owner_for_api_key(key)
        if owner is None:
            if REQUIRE_AUTH:
                raise HTTPException(401, "invalid API key")
            return DEFAULT_OWNER
        return owner

    _SCOPE_RANK = {"read": 0, "run": 1, "admin": 2}

    def require_scope(authorization: Optional[str], minimum: str = "read") -> str:
        """Validate the key and enforce its scope. read < run < admin."""
        owner = owner_from_key(authorization)
        if not REQUIRE_AUTH:
            return owner
        key = (authorization or "").removeprefix("Bearer ").strip()
        scope = store.scope_for_api_key(key) if key else "admin"
        if _SCOPE_RANK.get(scope, 2) < _SCOPE_RANK.get(minimum, 0):
            raise HTTPException(403, f"token scope '{scope}' cannot perform a '{minimum}' action")
        return owner

    # -- agent socket ------------------------------------------------------- #

    @app.websocket("/agent/ws")
    async def agent_ws(ws: WebSocket):
        machine_id = ws.query_params.get("machine_id")
        token = ws.query_params.get("token")
        if not machine_id:
            await ws.close(code=4400)
            return

        owner = DEFAULT_OWNER
        if token:
            info = store.device_token_info(token)
            if info:
                owner = info["owner"]
                machine_id = info["machine_id"]
            else:
                # Accept a host API key too, so one token works everywhere.
                key_owner = store.owner_for_api_key(token)
                if key_owner:
                    owner = key_owner
                elif REQUIRE_AUTH:
                    await ws.close(code=4401)
                    return
        elif REQUIRE_AUTH:
            await ws.close(code=4401)
            return

        await ws.accept()
        conn = AgentConn(machine_id, owner, ws)
        hub.add_agent(conn)
        try:
            async for raw in ws.iter_text():
                frame = Frame.load(raw)
                if frame.type == FrameType.REGISTERED:
                    conn.info = frame.data.get("machine", {})
                    store.upsert_machine(
                        machine_id,
                        conn.info.get("name", machine_id),
                        owner,
                        conn.info,
                        MachineStatus.ONLINE,
                        config.now_ms(),
                    )
                elif frame.type == FrameType.VOLUMES_REPORT:
                    store.report_volumes(
                        machine_id, frame.data.get("volumes", []), config.now_ms()
                    )
                elif frame.type == FrameType.METRICS_REPORT:
                    _t, _cpu, _mem = config.now_ms(), frame.data.get("cpu", 0.0), frame.data.get("mem", 0.0)
                    hub.record_metric(machine_id, _t, _cpu, _mem)
                    store.record_metric_sample(machine_id, _t, _cpu, _mem)
                    if "battery_pct" in frame.data:  # live-only battery cache (no DB)
                        hub.battery[machine_id] = (
                            frame.data.get("battery_pct"), frame.data.get("battery_charging"),
                        )
                elif frame.type in (FrameType.FS_RESULT, FrameType.HTTP_RESPONSE,
                                    FrameType.SNAPSHOT_RESULT):
                    hub.resolve_rpc(frame.request_id, frame.data)
                elif frame.type == FrameType.TUNNEL_READY:
                    fut = hub.tunnel_ready.get(frame.data.get("stream_id"))
                    if fut is not None and not fut.done():
                        fut.set_result(True)
                elif frame.type == FrameType.SESSION_READY:
                    fut = hub.session_ready.get(frame.request_id)
                    if fut is not None and not fut.done():
                        fut.set_result(True)
                elif frame.type == FrameType.TUNNEL_DATA:
                    cws = hub.tunnels.get(frame.data.get("stream_id"))
                    if cws is not None:
                        try:
                            await cws.send_bytes(base64.b64decode(frame.data.get("data_b64", "")))
                        except Exception:  # noqa: BLE001 — client vanished
                            pass
                elif frame.type == FrameType.TUNNEL_CLOSE:
                    sid = frame.data.get("stream_id")
                    conn.tunnels.discard(sid)
                    fut = hub.tunnel_ready.get(sid)
                    if fut is not None and not fut.done():
                        # Dial failed before it was ever ready.
                        fut.set_exception(RuntimeError(frame.data.get("error") or "tunnel closed"))
                    cws = hub.tunnels.pop(sid, None)
                    if cws is not None:
                        try:
                            await cws.close()
                        except Exception:  # noqa: BLE001
                            pass
                elif frame.type == FrameType.EXIT:
                    hub.started.discard(frame.request_id)
                    conn.inflight.discard(frame.request_id)
                    hub.publish(frame)
                    store.update_job(
                        frame.request_id,
                        JobState.SUCCEEDED if frame.data.get("exit_code") == 0 else JobState.FAILED,
                        frame.data.get("exit_code"),
                        frame.data.get("duration_ms"),
                    )
                else:
                    # First output flips a dispatched job to running (→ sandbox live).
                    if (frame.type in (FrameType.STDOUT, FrameType.STDERR)
                            and frame.request_id and frame.request_id not in hub.started):
                        hub.started.add(frame.request_id)
                        store.update_job(frame.request_id, JobState.RUNNING)
                    hub.publish(frame)
        except WebSocketDisconnect:
            pass
        finally:
            hub.remove_agent(machine_id)
            # Tear down any raw tunnels this Mac was carrying so their client
            # WebSockets don't dangle forever after the daemon drops.
            for sid in list(conn.tunnels):
                fut = hub.tunnel_ready.pop(sid, None)
                if fut is not None and not fut.done():
                    fut.set_exception(RuntimeError("machine disconnected"))
                cws = hub.tunnels.pop(sid, None)
                if cws is not None:
                    try:
                        await cws.close()
                    except Exception:  # noqa: BLE001
                        pass
            conn.tunnels.clear()
            # Unblock any SDK call waiting on a job this Mac was running. Without a
            # synthetic EXIT the log stream — and `mac.run()` — would hang forever.
            for rid in list(conn.inflight):
                if rid not in hub.finished:
                    hub.started.discard(rid)
                    # Unblock a start_session still waiting on SESSION_READY.
                    sfut = hub.session_ready.pop(rid, None)
                    if sfut is not None and not sfut.done():
                        sfut.set_exception(RuntimeError("machine disconnected"))
                    hub.publish(Frame(type=FrameType.EXIT, request_id=rid,
                                      data={"exit_code": -1, "error": "machine disconnected"}))
                    store.update_job(rid, JobState.FAILED, -1, None)
            conn.inflight.clear()

    # -- SDK: machines ------------------------------------------------------ #

    @app.get("/v1/machines")
    def list_machines(authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        machines = store.list_machines(None if owner == DEFAULT_OWNER else owner)
        # Reflect live connection status (sqlite may lag a disconnect) + latest CPU/mem.
        for m in machines:
            m["status"] = "online" if m["machine_id"] in hub.agents else m["status"]
            latest = store.latest_metric(m["machine_id"]) if m["status"] == "online" else None
            m["live_cpu"] = round(latest[0], 1) if latest else None
            m["live_mem"] = round(latest[1], 1) if latest else None
            bat = hub.battery.get(m["machine_id"]) if m["status"] == "online" else None
            m["live_battery"] = bat[0] if bat else None
            m["battery_charging"] = bat[1] if bat else None
        return {"machines": machines}

    @app.get("/v1/machines/{machine_id}")
    def get_machine(machine_id: str, authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        if machine_id in ("default", "mac", "_"):
            machine_id = _resolve_default_machine(store, hub, owner)
        m = store.get_machine(machine_id)
        if not m:
            raise HTTPException(404, "no such machine")
        m["status"] = "online" if machine_id in hub.agents else m["status"]
        return m

    @app.post("/v1/machines/{machine_id}/tags")
    def add_tags_ep(machine_id: str, body: "TagBody", authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        mid = _resolve_machine(machine_id, owner)
        store.add_tags(mid, body.tags)
        return {"machine_id": mid, "tags": store.tags_for(mid)}

    @app.delete("/v1/machines/{machine_id}/tags/{tag}")
    def remove_tag_ep(machine_id: str, tag: str, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        mid = _resolve_machine(machine_id, owner)
        if not store.remove_tag(mid, tag):
            raise HTTPException(404, "tag not found")
        return {"machine_id": mid, "tags": store.tags_for(mid)}

    # -- SDK: exec ---------------------------------------------------------- #

    def _resolve_machine(machine_id: str, owner: str) -> str:
        if machine_id in ("default", "mac", "_"):
            machine_id = _resolve_default_machine(store, hub, owner)
        agent = hub.agent(machine_id)
        if agent is None:
            raise HTTPException(409, f"machine {machine_id} is offline")
        if REQUIRE_AUTH and agent.owner != owner:
            raise HTTPException(403, "machine not owned by caller")
        return machine_id

    def _owns_job(owner: str, request_id: str) -> bool:
        """True if ``owner`` owns the machine the job ran on (same ACL as
        ``_resolve_machine``). The admin/local owner owns everything."""
        if owner == DEFAULT_OWNER:
            return True
        job = store.get_job(request_id)
        if not job:
            return False
        machine = store.get_machine(job["machine_id"])
        return bool(machine and machine.get("owner") == owner)

    async def _dispatch(machine_id: str, req: ExecRequest, owner: str, *, kind: str = "exec") -> str:
        """Create a job, resolve secrets, and push the exec (or session) frame.

        ``kind="session"`` starts a RESIDENT stdin-fed process instead of a
        one-shot command; everything else (job row, secret resolution, sandbox
        bookkeeping, inflight tracking) is identical. Returns the request_id."""
        agent = hub.agent(machine_id)
        if agent is None:  # raced: the Mac went offline between resolve and dispatch
            raise HTTPException(409, f"machine {machine_id} went offline")
        request_id = "req_" + uuid.uuid4().hex[:12]
        cmd_str = req.command if isinstance(req.command, str) else " ".join(req.command)
        # Zero-config apps: the first run naming an app registers it here.
        if req.app:
            store.upsert_app(req.app, owner, config.now_ms())
            store.touch_app(req.app, owner, config.now_ms())
        store.create_job(request_id, machine_id, cmd_str, config.now_ms(),
                         sandbox_id=req.sandbox_id, app=req.app)

        merged_env = dict(req.env)
        for sname in req.secrets:
            values = store.get_secret_values(sname, owner) or store.get_secret_values(sname, DEFAULT_OWNER)
            if values is None:
                raise HTTPException(404, f"no such secret: {sname}")
            merged_env.update(values)

        if req.sandbox_id:
            store.touch_sandbox(req.sandbox_id, machine_id, req.image, config.now_ms(), app=req.app)

        agent.inflight.add(request_id)
        if kind == "session":
            frame = session_start_frame(
                request_id, req.command,
                image=req.image, volumes=req.volumes, workdir=req.workdir, env=merged_env,
                network=req.network, sandbox_id=req.sandbox_id, inherit_home=req.inherit_home,
                setup_commands=req.setup_commands, base=req.base,
            )
        else:
            frame = exec_frame(
                request_id, req.command,
                image=req.image, volumes=req.volumes, workdir=req.workdir, env=merged_env,
                timeout=req.timeout, network=req.network, sandbox_id=req.sandbox_id,
                inherit_home=req.inherit_home, keep_alive=req.keep_alive,
                setup_commands=req.setup_commands, base=req.base,
            )
        # For a resident session, wait until the agent confirms the process is
        # live (SESSION_READY) before returning — so the handle the caller gets
        # back is immediately usable and an early stdin write can't race the
        # launch. Mirrors Modal's create contract. Set up the future BEFORE send.
        session_fut = None
        if kind == "session":
            session_fut = asyncio.get_running_loop().create_future()
            hub.session_ready[request_id] = session_fut
        try:
            await agent.send(frame)
        except Exception:  # the socket died mid-send — don't strand the job
            agent.inflight.discard(request_id)
            if session_fut is not None:
                hub.session_ready.pop(request_id, None)
            store.update_job(request_id, JobState.FAILED, -1, None)
            raise HTTPException(409, f"machine {machine_id} disconnected during dispatch")
        store.update_job(request_id, JobState.DISPATCHED)
        if session_fut is not None:
            try:
                # Generous: a session may provision a toolchain before it's live.
                await asyncio.wait_for(session_fut, timeout=config.SESSION_START_TIMEOUT_S)
            except asyncio.TimeoutError:
                pass  # best-effort — return anyway; the process may still be coming up
            except Exception:  # agent disconnected mid-launch — don't strand the caller
                hub.session_ready.pop(request_id, None)
                raise HTTPException(409, f"machine {machine_id} disconnected during session start")
            finally:
                hub.session_ready.pop(request_id, None)
        return request_id

    @app.post("/v1/machines/{machine_id}/exec", response_model=ExecAccepted)
    async def start_exec(
        machine_id: str, req: ExecRequest, authorization: Optional[str] = Header(None)
    ):
        owner = require_scope(authorization, "run")  # read-only tokens can't execute
        machine_id = _resolve_machine(machine_id, owner)
        request_id = await _dispatch(machine_id, req, owner)
        return ExecAccepted(request_id=request_id, machine_id=machine_id)

    # -- resident stdin-fed sessions ---------------------------------------- #

    @app.post("/v1/machines/{machine_id}/sessions", response_model=ExecAccepted)
    async def start_session_ep(
        machine_id: str, req: ExecRequest, authorization: Optional[str] = Header(None)
    ):
        """Start a RESIDENT process on the Mac that many stdin turns feed into.

        Returns a request_id (== session id): stream its output over
        ``/v1/jobs/{request_id}/logs`` and feed it via ``/v1/sessions/{id}/stdin``.
        Cross-worker input is free — any client that knows the id can POST stdin."""
        owner = require_scope(authorization, "run")  # read-only tokens can't execute
        machine_id = _resolve_machine(machine_id, owner)
        request_id = await _dispatch(machine_id, req, owner, kind="session")
        return ExecAccepted(request_id=request_id, machine_id=machine_id)

    @app.post("/v1/sessions/{request_id}/stdin")
    async def session_stdin_ep(
        request_id: str, body: "StdinBody", authorization: Optional[str] = Header(None)
    ):
        """Deliver a stdin chunk (and/or EOF) to a running session by id."""
        require_scope(authorization, "run")
        job = store.get_job(request_id)
        if job is None:
            raise HTTPException(404, "no such session")
        agent = hub.agent(job["machine_id"])
        if agent is None:
            raise HTTPException(409, "machine offline")
        try:
            await agent.send(stdin_frame(request_id, body.data, eof=body.eof))
        except Exception:
            raise HTTPException(409, "machine disconnected")
        return {"ok": True, "request_id": request_id}

    # -- schedules (recurring jobs) ----------------------------------------- #

    @app.post("/v1/schedules")
    async def create_schedule_ep(body: "ScheduleBody", authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        if len(body.cron.split()) != 5:
            raise HTTPException(400, "cron must have 5 fields: 'min hour day-of-month month day-of-week'")
        sid = "sch_" + uuid.uuid4().hex[:10]
        store.create_schedule(sid, owner, body.machine_id or "default",
                              body.command, body.cron, config.now_ms())
        return {"id": sid, "cron": body.cron, "command": body.command,
                "machine_id": body.machine_id or "default"}

    @app.get("/v1/schedules")
    async def list_schedules_ep(authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "read")
        return {"schedules": store.list_schedules(None if owner == DEFAULT_OWNER else owner)}

    @app.delete("/v1/schedules/{sid}")
    async def delete_schedule_ep(sid: str, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        # admin/local owner may delete any; otherwise only its own.
        target = next((s for s in store.list_schedules() if s["id"] == sid), None)
        if target is None:
            raise HTTPException(404, "no such schedule")
        if owner != DEFAULT_OWNER and target["owner"] != owner:
            raise HTTPException(403, "schedule not owned by caller")
        store.delete_schedule(sid, target["owner"])
        return {"ok": True}

    # -- apps (named projects grouping runs/sandboxes/functions) ------------- #

    @app.get("/v1/apps")
    def list_apps_ep(authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        return {"apps": store.list_apps(None if owner == DEFAULT_OWNER else owner)}

    @app.get("/v1/apps/{name}")
    def get_app_ep(name: str, authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        scope = None if owner == DEFAULT_OWNER else owner
        a = store.get_app(name, scope)
        if not a:
            raise HTTPException(404, "no such app")
        return {
            "app": a,
            "functions": store.list_app_functions(name, a["owner"]),
            "jobs": store.list_jobs(app=name, limit=200),
            "sandboxes": store.list_sandboxes(app=name),
        }

    @app.post("/v1/apps")
    def create_app_ep(body: "AppBody", authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        store.upsert_app(body.name, owner, config.now_ms(), description=body.description)
        return store.get_app(body.name, owner)

    @app.delete("/v1/apps/{name}")
    def delete_app_ep(name: str, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        scope = None if owner == DEFAULT_OWNER else owner
        a = store.get_app(name, scope)
        if a is None:
            raise HTTPException(404, "no such app")
        store.delete_app(name, a["owner"])
        return {"deleted": name}

    @app.post("/v1/apps/{name}/functions")
    async def put_app_function_ep(name: str, body: "FunctionBody",
                                  authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        now = config.now_ms()
        store.upsert_app(name, owner, now)          # ensure the app exists
        store.put_app_function(name, owner, body.name, body.source, body.image,
                               body.schedule, body.kind, now, port=body.port)
        store.mark_app_deployed(name, owner, now)
        # A scheduled function becomes a cron row the scheduler fires (Phase 3).
        if body.schedule:
            sid = "sch_" + uuid.uuid4().hex[:10]
            trigger = json.dumps({"__herds_app__": name, "__herds_fn__": body.name})
            store.create_schedule(sid, owner, "default", trigger, body.schedule, now)
        # A web endpoint boots as a keep-alive sandbox and gets a public URL.
        url = None
        if body.kind == "web" and body.port:
            try:
                url = await _serve_web_endpoint(name, owner, body)
            except Exception as exc:  # noqa: BLE001 — no machine online yet, etc.
                print(f"herds: web endpoint {name}.{body.name} not started ({exc})", file=sys.stderr)
        return {"ok": True, "function": body.name, "url": url}

    async def _serve_web_endpoint(name: str, owner: str, body: "FunctionBody") -> str:
        """Start a web-endpoint function as a supervised server in a sandbox and
        expose its port as a URL. Reuses the sandbox + port-proxy machinery."""
        machine_id = _resolve_machine("default", owner)
        sandbox_id = "sbx_" + uuid.uuid4().hex[:10]
        payload = json.dumps({"args": [], "kwargs": {}})
        req = ExecRequest(command=["python3", "-c", body.source, payload],
                          image=body.image, app=name, sandbox_id=sandbox_id,
                          keep_alive=True)
        await _dispatch(machine_id, req, owner)
        slug = _slugify(f"{name}-{body.name}") or f"s{body.port}"
        pname = store.unique_port_name(slug, sandbox_id, body.port)
        store.expose_port(sandbox_id, body.port, pname, config.now_ms())
        url = _port_url(sandbox_id, body.port, pname)
        store.set_app_function_url(name, owner, body.name, url, sandbox_id)
        return url

    @app.post("/v1/apps/{name}/functions/{fn}")
    async def trigger_app_function_ep(name: str, fn: str, body: "TriggerBody",
                                      authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "run")
        scope = None if owner == DEFAULT_OWNER else owner
        f = store.get_app_function(name, fn, scope)
        if f is None:
            raise HTTPException(404, "no such function")
        payload = json.dumps({"args": body.args, "kwargs": body.kwargs})
        machine_id = _resolve_machine(body.machine_id or "default", owner)
        req = ExecRequest(command=["python3", "-c", f["source"], payload],
                          image=f["image"], app=name)
        request_id = await _dispatch(machine_id, req, owner)
        return {"request_id": request_id, "machine_id": machine_id}

    def _schedule_request(sch: dict) -> ExecRequest:
        """Build the ExecRequest a due schedule dispatches. A plain command runs
        as-is; an app-function trigger (JSON blob) ships that function's stored
        driver and groups the run under its app."""
        cmd = sch["command"] or ""
        if cmd.startswith("{") and "__herds_app__" in cmd:
            spec = json.loads(cmd)
            app_name, fn = spec["__herds_app__"], spec["__herds_fn__"]
            f = store.get_app_function(app_name, fn, sch["owner"])
            if f is not None:
                payload = json.dumps({"args": [], "kwargs": {}})
                return ExecRequest(command=["python3", "-c", f["source"], payload],
                                   image=f["image"], app=app_name)
        return ExecRequest(command=cmd)

    async def _run_scheduler() -> None:
        """Fire due schedules once per minute. Persists in SQLite, so it resumes
        after a control-plane restart; offline machines are skipped (retried next
        matching minute)."""
        import datetime

        while True:
            try:
                now = datetime.datetime.now()
                await asyncio.sleep(max(1.0, 60 - now.second - now.microsecond / 1e6))
                now = datetime.datetime.now()
                key = now.strftime("%Y%m%d%H%M")
                for sch in store.list_schedules():
                    if not sch.get("enabled", 1) or sch.get("last_run_key") == key:
                        continue
                    if not cron_due(sch["cron"], now):
                        continue
                    try:
                        mid = _resolve_machine(sch["machine_id"] or "default", sch["owner"])
                        await _dispatch(mid, _schedule_request(sch), sch["owner"])
                        store.mark_schedule_run(sch["id"], key, config.now_ms())
                    except Exception as exc:  # noqa: BLE001 — offline machine, etc.
                        print(f"herds scheduler: {sch['id']} skipped ({exc})", file=sys.stderr)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — never let the loop die
                print(f"herds scheduler loop error: {exc}", file=sys.stderr)
                await asyncio.sleep(5)

    @app.on_event("startup")
    async def _start_scheduler() -> None:
        asyncio.create_task(_run_scheduler())

    @app.post("/v1/machines/{machine_id}/sandboxes")
    async def create_sandbox(
        machine_id: str, body: CreateSandboxBody, authorization: Optional[str] = Header(None)
    ):
        owner = owner_from_key(authorization)
        machine_id = _resolve_machine(machine_id, owner)
        sandbox_id = "sbx_" + uuid.uuid4().hex[:10]
        store.register_sandbox(sandbox_id, machine_id, body.image, config.now_ms())
        request_id = None
        if body.command:
            req = ExecRequest(
                command=body.command, image=body.image, sandbox_id=sandbox_id,
                secrets=body.secrets, inherit_home=body.inherit_home, keep_alive=body.keep_alive,
                setup_commands=body.setup_commands, base=body.base,
            )
            request_id = await _dispatch(machine_id, req, owner)
        return {"sandbox_id": sandbox_id, "machine_id": machine_id, "request_id": request_id}

    @app.post("/v1/sandboxes/{sandbox_id}/snapshot")
    async def snapshot_sandbox(sandbox_id: str, body: "SnapshotBody",
                               authorization: Optional[str] = Header(None)):
        """Tar a sandbox's fs into a named base image on the Mac (Modal
        ``snapshot_filesystem``). Returns the base's ``image_id`` — feed it back
        as ``base=`` / ``Image.from_id(image_id)`` to seed a fresh sandbox."""
        require_scope(authorization, "run")
        sb = store.get_sandbox(sandbox_id)
        mid = sb["machine_id"] if sb else _resolve_machine("default", owner_from_key(authorization))
        base = body.base or (sandbox_id + "_snap")
        return await _snapshot_rpc(mid, sandbox_id, base)

    async def _snapshot_rpc(machine_id: str, sandbox_id: str, base: str, timeout: float = 240) -> dict:
        agent = hub.agent(machine_id)
        if agent is None:
            raise HTTPException(409, "machine offline")
        request_id = "snap_" + uuid.uuid4().hex[:12]
        fut = asyncio.get_running_loop().create_future()
        hub.pending[request_id] = fut
        await agent.send(snapshot_frame(request_id, sandbox_id, base))
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            hub.pending.pop(request_id, None)
            raise HTTPException(504, "agent did not respond")
        if result.get("error"):
            raise HTTPException(400, result["error"])
        return result

    @app.websocket("/v1/jobs/{request_id}/logs")
    async def job_logs(ws: WebSocket, request_id: str):
        if REQUIRE_AUTH:
            token = ws.query_params.get("token", "")
            owner = store.owner_for_api_key(token)
            if owner is None:
                await ws.close(code=4401)
                return
            # Ownership ACL: a valid token is not enough — it must own the job's
            # machine, or any user could tail any other user's job logs.
            if not _owns_job(owner, request_id):
                await ws.close(code=4403)
                return
        await ws.accept()
        q = hub.subscribe(request_id)
        try:
            while True:
                frame: Frame = await q.get()
                await ws.send_text(frame.dump())
                if frame.type == FrameType.EXIT:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(request_id, q)
            hub.cleanup(request_id)

    # -- raw TCP tunnels: a bidirectional pipe to a sandbox-local port ------- #

    async def _serve_tunnel(ws: WebSocket, machine_id: str, port: int, owner: str) -> None:
        """Bridge a client WebSocket to ``127.0.0.1:port`` on the Mac, byte-for-byte.

        The client sends/receives binary WS messages; each is relayed as a
        ``TUNNEL_DATA`` frame over the agent socket, where the daemon pumps it in
        and out of a real TCP connection. This is the raw counterpart to the
        buffered ``_proxy_port`` HTTP path — it survives CDP, websockets, etc."""
        if machine_id in ("default", "mac", "_"):
            try:
                machine_id = _resolve_default_machine(store, hub, owner)
            except HTTPException:
                await ws.close(code=4404)
                return
        agent = hub.agent(machine_id)
        if agent is None:
            await ws.close(code=4409)
            return
        if REQUIRE_AUTH and agent.owner != owner:
            await ws.close(code=4403)
            return

        await ws.accept()
        sid = "tun_" + uuid.uuid4().hex[:12]
        hub.tunnels[sid] = ws
        agent.tunnels.add(sid)
        fut = asyncio.get_running_loop().create_future()
        hub.tunnel_ready[sid] = fut
        try:
            await agent.send(tunnel_open_frame(sid, port))
        except Exception:  # noqa: BLE001 — socket died mid-open
            hub.tunnels.pop(sid, None)
            hub.tunnel_ready.pop(sid, None)
            agent.tunnels.discard(sid)
            await ws.close(code=4409)
            return
        # Wait for the daemon to confirm the local dial before pumping bytes, so a
        # refused port fails fast and cleanly instead of silently dropping data.
        try:
            await asyncio.wait_for(fut, timeout=15)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001 — dial failed/timeout
            hub.tunnels.pop(sid, None)
            hub.tunnel_ready.pop(sid, None)
            agent.tunnels.discard(sid)
            try:
                await agent.send(tunnel_close_frame(sid))
            except Exception:  # noqa: BLE001
                pass
            await ws.close(code=4502)
            return
        hub.tunnel_ready.pop(sid, None)
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                data = msg.get("bytes")
                if data is None:
                    text = msg.get("text")
                    data = text.encode() if text is not None else b""
                if data:
                    await agent.send(tunnel_data_frame(sid, data))
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            hub.tunnels.pop(sid, None)
            hub.tunnel_ready.pop(sid, None)
            agent.tunnels.discard(sid)
            try:
                await agent.send(tunnel_close_frame(sid))
            except Exception:  # noqa: BLE001
                pass

    @app.websocket("/v1/machines/{machine_id}/tunnel/{port}")
    async def machine_tunnel(ws: WebSocket, machine_id: str, port: int):
        owner = DEFAULT_OWNER
        if REQUIRE_AUTH:
            owner = store.owner_for_api_key(ws.query_params.get("token", "") or "")
            if owner is None:
                await ws.close(code=4401)
                return
        await _serve_tunnel(ws, machine_id, port, owner)

    @app.websocket("/v1/sandboxes/{sandbox_id}/tunnel/{port}")
    async def sandbox_tunnel(ws: WebSocket, sandbox_id: str, port: int):
        owner = DEFAULT_OWNER
        if REQUIRE_AUTH:
            owner = store.owner_for_api_key(ws.query_params.get("token", "") or "")
            if owner is None:
                await ws.close(code=4401)
                return
        sb = store.get_sandbox(sandbox_id)
        if not sb:
            await ws.close(code=4404)
            return
        await _serve_tunnel(ws, sb["machine_id"], port, owner)

    @app.get("/v1/jobs")
    def list_jobs(
        machine_id: Optional[str] = None,
        limit: int = 200,
        authorization: Optional[str] = Header(None),
    ):
        owner_from_key(authorization)
        return {"jobs": store.list_jobs(machine_id, limit=min(limit, 1000))}

    @app.get("/v1/jobs/{request_id}/output")
    def job_output(request_id: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        job = store.get_job(request_id)
        if not job:
            raise HTTPException(404, "no such job")
        # If still running, serve whatever has accumulated live so far.
        output = job["output"] or hub.logbuf.get(request_id, [])
        return {
            "request_id": request_id,
            "state": job["state"],
            "exit_code": job["exit_code"],
            "command": job["command"],
            "output": output,
        }

    # -- SDK/dashboard: sandboxes ------------------------------------------ #

    @app.get("/v1/sandboxes")
    def list_sandboxes(machine_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        sandboxes = store.list_sandboxes(machine_id)
        live = store.live_sandbox_ids()
        for s in sandboxes:
            s["live"] = s["sandbox_id"] in live
        return {"sandboxes": sandboxes}

    @app.get("/v1/sandboxes/{sandbox_id}")
    def get_sandbox(sandbox_id: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        sb = store.get_sandbox(sandbox_id)
        if not sb:
            raise HTTPException(404, "no such sandbox")
        active = store.active_jobs_for_sandbox(sandbox_id)
        sb["live"] = bool(active)
        sb["running"] = len(active)
        return {"sandbox": sb, "jobs": store.list_jobs(sandbox_id=sandbox_id, limit=200)}

    @app.post("/v1/sandboxes/{sandbox_id}/stop")
    async def stop_sandbox(sandbox_id: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        sb = store.get_sandbox(sandbox_id)
        if not sb:
            raise HTTPException(404, "no such sandbox")
        agent = hub.agent(sb["machine_id"])
        if agent is None:
            raise HTTPException(409, "machine offline")
        rids = store.active_jobs_for_sandbox(sandbox_id)
        for rid in rids:
            await agent.send(Frame(type=FrameType.CANCEL, request_id=rid))
        return {"stopped": sandbox_id, "canceled": rids}

    @app.delete("/v1/sandboxes/{sandbox_id}")
    async def terminate_sandbox(sandbox_id: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        sb = store.get_sandbox(sandbox_id)
        if not sb:
            raise HTTPException(404, "no such sandbox")
        agent = hub.agent(sb["machine_id"])
        if agent is not None:
            # stop anything running, then wipe the workspace on the Mac.
            for rid in store.active_jobs_for_sandbox(sandbox_id):
                await agent.send(Frame(type=FrameType.CANCEL, request_id=rid))
            await agent.send(Frame(
                type=FrameType.SANDBOX_TERMINATE, data={"sandbox_id": sandbox_id}
            ))
        store.delete_sandbox(sandbox_id)
        return {"terminated": sandbox_id}

    # -- filesystem RPC to the agent (browse files on the Mac) ------------- #

    async def _fs_rpc(machine_id: str, frame_type: FrameType, data: dict, timeout: float = 10) -> dict:
        agent = hub.agent(machine_id)
        if agent is None:
            raise HTTPException(409, "machine offline")
        request_id = "fs_" + uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        hub.pending[request_id] = fut
        await agent.send(Frame(type=frame_type, request_id=request_id, data=data))
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            hub.pending.pop(request_id, None)
            raise HTTPException(504, "agent did not respond")
        if result.get("error"):
            raise HTTPException(400, result["error"])
        return result

    def _machine_for_sandbox(sandbox_id: str) -> str:
        sb = store.get_sandbox(sandbox_id)
        if not sb:
            raise HTTPException(404, "no such sandbox")
        return sb["machine_id"]

    @app.get("/v1/sandboxes/{sandbox_id}/files")
    async def sandbox_files(sandbox_id: str, path: str = "", authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        mid = _machine_for_sandbox(sandbox_id)
        return await _fs_rpc(mid, FrameType.FS_LIST, {"kind": "sandbox", "id": sandbox_id, "path": path})

    @app.get("/v1/sandboxes/{sandbox_id}/file")
    async def sandbox_file(sandbox_id: str, path: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        mid = _machine_for_sandbox(sandbox_id)
        return await _fs_rpc(mid, FrameType.FS_READ, {"kind": "sandbox", "id": sandbox_id, "path": path})

    @app.get("/v1/volumes/{name}/files")
    async def volume_files(name: str, machine_id: str, path: str = "", authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        return await _fs_rpc(machine_id, FrameType.FS_LIST, {"kind": "volume", "id": name, "path": path})

    @app.get("/v1/volumes/{name}/file")
    async def volume_file(name: str, machine_id: str, path: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        return await _fs_rpc(machine_id, FrameType.FS_READ, {"kind": "volume", "id": name, "path": path})

    @app.get("/v1/volumes/{name}/get")
    async def volume_get(name: str, machine_id: str, path: str, authorization: Optional[str] = Header(None)):
        """Read a whole file *out* of a volume as base64 (SDK ``Volume.get``)."""
        owner_from_key(authorization)
        return await _fs_rpc(machine_id, FrameType.FS_GET, {"kind": "volume", "id": name, "path": path},
                             timeout=240)

    @app.delete("/v1/volumes/{name}/file")
    async def volume_remove(name: str, machine_id: str, path: str, authorization: Optional[str] = Header(None)):
        """Delete a file or directory from a volume (SDK ``Volume.remove``)."""
        require_scope(authorization, "run")  # read-only tokens can't mutate
        return await _fs_rpc(machine_id, FrameType.FS_REMOVE, {"kind": "volume", "id": name, "path": path})

    @app.put("/v1/volumes/{name}/put")
    async def volume_put(name: str, body: FsWriteBody, authorization: Optional[str] = Header(None)):
        """Push a file or an entire directory (tar) into a volume on the Mac."""
        require_scope(authorization, "run")
        data: dict = {"kind": "volume", "id": name, "path": body.path}
        if body.tar_b64 is not None:
            data["tar_b64"], data["clean"] = body.tar_b64, body.clean
        else:
            data["content_b64"] = body.content_b64 or ""
        return await _fs_rpc(body.machine_id, FrameType.FS_WRITE, data, timeout=240)

    @app.put("/v1/sandboxes/{sandbox_id}/put")
    async def sandbox_put(sandbox_id: str, body: FsWriteBody, authorization: Optional[str] = Header(None)):
        """Push a file or directory (tar) into a sandbox on the Mac."""
        owner = require_scope(authorization, "run")
        # Resolve the machine directly — a sandbox may be pushed to before its first
        # exec materializes it (the daemon creates the workspace dir on write).
        mid = _resolve_machine(body.machine_id or "default", owner)
        data: dict = {"kind": "sandbox", "id": sandbox_id, "path": body.path}
        if body.tar_b64 is not None:
            data["tar_b64"], data["clean"] = body.tar_b64, body.clean
        else:
            data["content_b64"] = body.content_b64 or ""
        return await _fs_rpc(mid, FrameType.FS_WRITE, data, timeout=240)

    # -- SDK/dashboard: volumes -------------------------------------------- #

    @app.get("/v1/volumes")
    def list_volumes(machine_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        return {"volumes": store.list_volumes(machine_id)}

    # -- SDK/dashboard: secrets (values are write-only) -------------------- #

    @app.get("/v1/secrets")
    def list_secrets(authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        return {"secrets": store.list_secrets(owner)}

    @app.post("/v1/secrets")
    def create_secret(body: SecretBody, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "admin")
        if not body.name or not body.values:
            raise HTTPException(400, "name and values are required")
        store.put_secret(body.name, owner, body.values, config.now_ms())
        return {"name": body.name, "keys": sorted(body.values.keys())}

    @app.delete("/v1/secrets/{name}")
    def delete_secret(name: str, authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        if not store.delete_secret(name, owner):
            raise HTTPException(404, "no such secret")
        return {"deleted": name}

    # -- dashboard: aggregate metrics for the overview --------------------- #

    @app.get("/v1/metrics")
    def metrics(authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        machines = store.list_machines(None if owner == DEFAULT_OWNER else owner)
        online = sum(1 for m in machines if m["machine_id"] in hub.agents)
        sandboxes = store.list_sandboxes()
        volumes = store.list_volumes()
        jobs = store.list_jobs(limit=500)
        return {
            "machines_total": len(machines),
            "machines_online": online,
            "sandboxes_active": sum(1 for s in sandboxes if s["status"] == "active"),
            "sandboxes_live": len(store.live_sandbox_ids()),
            "sandboxes_total": len(sandboxes),
            "volumes": len({v["name"] for v in volumes}),
            "volumes_bytes": sum(v["size_bytes"] for v in volumes),
            "secrets": len(store.list_secrets(owner)),
            "jobs_total": len(jobs),
            "jobs_running": sum(1 for j in jobs if j["state"] in ("queued", "dispatched", "running")),
            "jobs_succeeded": sum(1 for j in jobs if j["state"] == "succeeded"),
            "jobs_failed": sum(1 for j in jobs if j["state"] == "failed"),
        }

    @app.get("/v1/metrics/timeseries")
    def metrics_timeseries(
        minutes: int = 30,
        buckets: int = 60,
        machine_id: Optional[str] = None,
        authorization: Optional[str] = Header(None),
    ):
        owner_from_key(authorization)
        now = config.now_ms()
        window = minutes * 60_000
        start = now - window
        bsize = max(1, window // buckets)

        def histogram(times: list[int]) -> list[dict]:
            counts = [0] * buckets
            for t in times:
                if t is None or t < start:
                    continue
                idx = min(buckets - 1, (t - start) // bsize)
                counts[idx] += 1
            return [{"t": start + i * bsize, "count": c} for i, c in enumerate(counts)]

        jobs = store.list_jobs(machine_id=machine_id, limit=5000)
        sandboxes = store.list_sandboxes(machine_id)
        runs_hist = histogram([j["created_ms"] for j in jobs])
        sbx_hist = histogram([s["created_ms"] for s in sandboxes])

        # CPU/mem: persisted history, bucketed (one machine or all merged).
        merged: dict[int, list] = {}
        for (t, cpu, mem) in store.metric_samples(start, machine_id):
            slot = start + ((t - start) // bsize) * bsize
            merged.setdefault(slot, []).append((cpu, mem))
        series = []
        for slot in sorted(merged):
            vals = merged[slot]
            series.append({
                "t": slot,
                "cpu": round(sum(v[0] for v in vals) / len(vals), 1),
                "mem": round(sum(v[1] for v in vals) / len(vals), 1),
            })

        latest = store.latest_metric(machine_id)
        return {
            "now": now,
            "minutes": minutes,
            "bucket_ms": bsize,
            "runs": runs_hist,
            "sandboxes": sbx_hist,
            "cpu_mem": series,
            "runs_total": len([j for j in jobs if j["created_ms"] and j["created_ms"] >= start]),
            "live_cpu": latest[0] if latest else (series[-1]["cpu"] if series else 0),
            "live_mem": latest[1] if latest else (series[-1]["mem"] if series else 0),
        }

    # -- settings: API keys ------------------------------------------------ #

    @app.get("/v1/keys")
    def list_keys(authorization: Optional[str] = Header(None)):
        owner = owner_from_key(authorization)
        return {"keys": store.list_api_keys(owner)}

    @app.post("/v1/keys")
    def create_key(body: KeyBody, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "admin")
        scope = body.scope if body.scope in ("read", "run", "admin") else "run"
        key = store.create_api_key(owner, body.label or "default", scope)
        # Full key returned exactly once, at creation.
        return {"key": key, "label": body.label or "default", "scope": scope}

    @app.delete("/v1/keys/{prefix}")
    def revoke_key(prefix: str, authorization: Optional[str] = Header(None)):
        owner = require_scope(authorization, "admin")
        if not store.delete_api_key_by_masked(owner, prefix):
            raise HTTPException(404, "no such key")
        return {"revoked": prefix}

    # -- exposed ports: expose a sandbox server as a URL ------------------- #

    def _port_url(sandbox_id: str, port: int, name: str) -> str:
        if PORTS_DOMAIN and name:
            return f"https://{name}.{PORTS_DOMAIN}/"
        base = os.environ.get("HERDS_PUBLIC_URL", "").rstrip("/")
        return f"{base}/p/{sandbox_id}/{port}/"

    async def _proxy_port(machine_id, port, method, path, query, headers, body) -> Response:
        import base64

        agent = hub.agent(machine_id)
        if agent is None:
            raise HTTPException(409, "machine offline")
        request_id = "http_" + uuid.uuid4().hex[:12]
        fut = asyncio.get_running_loop().create_future()
        hub.pending[request_id] = fut
        await agent.send(Frame(type=FrameType.HTTP_REQUEST, request_id=request_id, data={
            "port": port, "method": method, "path": path, "query": query,
            "headers": headers, "body_b64": base64.b64encode(body).decode() if body else "",
        }))
        try:
            res = await asyncio.wait_for(fut, timeout=25)
        except asyncio.TimeoutError:
            hub.pending.pop(request_id, None)
            raise HTTPException(504, "sandbox did not respond")
        content = base64.b64decode(res["body_b64"]) if res.get("body_b64") else b""
        skip = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        out = {k: v for k, v in (res.get("headers") or {}).items() if k.lower() not in skip}
        return Response(content=content, status_code=res.get("status", 502), headers=out)

    @app.get("/v1/sandboxes/{sandbox_id}/ports")
    def list_ports(sandbox_id: str, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        ports = store.list_ports(sandbox_id)
        for p in ports:
            p["path"] = f"/p/{sandbox_id}/{p['port']}/"
            p["url"] = _port_url(sandbox_id, p["port"], p["name"])
        return {"ports": ports, "domain": PORTS_DOMAIN}

    @app.post("/v1/sandboxes/{sandbox_id}/ports")
    def expose_port(sandbox_id: str, body: PortBody, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        if not store.get_sandbox(sandbox_id):
            raise HTTPException(404, "no such sandbox")
        slug = _slugify(body.name) or f"s{body.port}"
        name = store.unique_port_name(slug, sandbox_id, body.port)
        store.expose_port(sandbox_id, body.port, name, config.now_ms())
        return {"port": body.port, "name": name, "path": f"/p/{sandbox_id}/{body.port}/",
                "url": _port_url(sandbox_id, body.port, name)}

    @app.delete("/v1/sandboxes/{sandbox_id}/ports/{port}")
    def unexpose_port(sandbox_id: str, port: int, authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        store.unexpose_port(sandbox_id, port)
        return {"unexposed": port}

    @app.api_route("/p/{sandbox_id}/{port}/{path:path}",
                   methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"], include_in_schema=False)
    async def sandbox_proxy(sandbox_id: str, port: int, path: str, request: Request):
        if not store.port_machine(sandbox_id, port):
            raise HTTPException(404, "port not exposed for this sandbox")
        mid = store.get_sandbox(sandbox_id)["machine_id"]
        return await _proxy_port(mid, port, request.method, "/" + path,
                                 request.url.query, dict(request.headers), await request.body())

    @app.middleware("http")
    async def subdomain_router(request: Request, call_next):
        if PORTS_DOMAIN:
            host = (request.headers.get("host") or "").split(":")[0].lower()
            if host.endswith("." + PORTS_DOMAIN):
                name = host[: -(len(PORTS_DOMAIN) + 1)]
                info = store.port_by_name(name)
                if info:
                    return await _proxy_port(info["machine_id"], info["port"], request.method,
                                             request.url.path, request.url.query,
                                             dict(request.headers), await request.body())
                return Response(f"no exposed port named '{name}'", status_code=404)
        return await call_next(request)

    @app.get("/v1/host")
    def host_info(authorization: Optional[str] = Header(None)):
        owner_from_key(authorization)
        url = os.environ.get("HERDS_PUBLIC_URL", "")
        token = os.environ.get("HERDS_HOST_TOKEN", "")
        return {
            "public_url": url,
            "token": token,
            "connect": f"herds connect {url} {token}" if url and token else "",
            "hosted": bool(url),
        }

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "agents_online": list(hub.agents.keys())}

    # -- single-origin: serve the dashboard through the control plane -------- #
    # One tunneled origin serves UI + API + WS. API paths win (defined above).
    #  • HERDS_DASHBOARD_URL → reverse-proxy a running Next server (dev).
    #  • else web_dist (bundled static export) → serve files directly (prod).
    import httpx as _httpx

    _API_PREFIXES = ("v1/", "v1", "agent", "healthz", "p/")
    dashboard_url = os.environ.get("HERDS_DASHBOARD_URL")
    web_dist = Path(os.environ.get("HERDS_WEB_DIST") or (Path(__file__).resolve().parent.parent / "web_dist"))

    if dashboard_url:
        proxy = _httpx.AsyncClient(base_url=dashboard_url.rstrip("/"), timeout=30.0)

        @app.api_route("/{path:path}", methods=["GET", "POST", "HEAD"])
        async def dashboard_proxy(path: str, request: Request):
            if path.startswith(_API_PREFIXES):
                raise HTTPException(404)
            url = _httpx.URL(path="/" + path, query=request.url.query.encode("utf-8"))
            headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
            upstream = proxy.build_request(request.method, url, headers=headers, content=await request.body())
            resp = await proxy.send(upstream, stream=True)
            hop = {"transfer-encoding", "connection", "keep-alive"}
            return StreamingResponse(
                resp.aiter_raw(),
                status_code=resp.status_code,
                headers={k: v for k, v in resp.headers.items() if k.lower() not in hop},
                background=__import__("starlette.background", fromlist=["BackgroundTask"]).BackgroundTask(resp.aclose),
            )

    elif web_dist.is_dir():
        from fastapi.responses import FileResponse

        root = web_dist.resolve()

        @app.get("/{path:path}")
        def dashboard_static(path: str):
            if path.startswith(_API_PREFIXES):
                raise HTTPException(404)
            # Static export maps /sandbox → sandbox.html, /_next/... → asset file.
            for cand in ([ "index.html" ] if path in ("", "/") else [path, f"{path}.html", f"{path}/index.html"]):
                fp = (root / cand).resolve()
                if fp.is_file() and str(fp).startswith(str(root)):
                    return FileResponse(fp)
            return FileResponse(root / "index.html")  # SPA fallback

    return app


class SecretBody(BaseModel):
    name: str
    values: dict[str, str]


class FsWriteBody(BaseModel):
    machine_id: str
    path: str = ""
    content_b64: Optional[str] = None   # write one file
    tar_b64: Optional[str] = None       # …or extract a tar (codebase push)
    clean: bool = False                 # wipe the destination dir first


class StdinBody(BaseModel):
    data: str = ""
    eof: bool = False


class CreateSandboxBody(BaseModel):
    image: Optional[str] = None
    command: Optional[str] = None
    secrets: list[str] = []
    inherit_home: bool = False
    keep_alive: bool = False
    setup_commands: list[str] = []
    base: Optional[str] = None


class SnapshotBody(BaseModel):
    base: Optional[str] = None   # name for the base image; defaults to <sandbox>_snap


class KeyBody(BaseModel):
    label: str = ""
    scope: str = "run"   # read | run | admin (default: run — execute, but can't mint keys)


class PortBody(BaseModel):
    port: int
    name: str = ""


class ScheduleBody(BaseModel):
    command: str
    cron: str
    machine_id: Optional[str] = None


class TagBody(BaseModel):
    tags: list[str]


class AppBody(BaseModel):
    name: str
    description: Optional[str] = None


class FunctionBody(BaseModel):
    name: str
    source: str
    image: Optional[str] = None
    schedule: Optional[str] = None
    kind: str = "function"
    port: Optional[int] = None


class TriggerBody(BaseModel):
    args: list = []
    kwargs: dict = {}
    machine_id: Optional[str] = None


def _resolve_default_machine(store: Store, hub: Hub, owner: str) -> str:
    """Pick the machine for ``herds.mac()`` when no id is given: the idlest online
    Mac the caller owns. Picking by load (not store order) stops it from always
    landing on the host — which is online too once `herds host` is running."""
    online = [mid for mid, conn in hub.agents.items()
              if owner == DEFAULT_OWNER or conn.owner == owner]
    if not online:
        raise HTTPException(409, "no machines online; run `herds connect` on a Mac")
    if len(online) == 1:
        return online[0]

    def load(mid: str) -> float:
        samples = hub.metrics.get(mid)
        return samples[-1][1] if samples else 0.0  # no metrics yet (just joined) → idlest

    return min(online, key=load)


def serve(host: str = "127.0.0.1", port: int = 8787, db_path: Optional[str] = None) -> None:
    """Run the control plane with uvicorn (used by ``herds serve``)."""
    import uvicorn

    config.ensure_dirs()
    path = db_path or str(config.HERDS_HOME / "control.db")
    app = create_app(path)
    uvicorn.run(app, host=host, port=port, log_level="warning")
