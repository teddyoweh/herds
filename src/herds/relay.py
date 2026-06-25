"""Herds relay — the invisible rendezvous that gives every ``herds host`` a stable
branded link (``you.herds.run``) with no inbound ports and no user-facing config.

A host dials the relay over an outbound WebSocket (NAT-friendly). The relay routes
public HTTP by ``Host``-header subdomain → the right host's socket → the host
proxies to its own local control plane and streams the response back. Same
HTTP-over-WS frames (``HTTP_REQUEST``/``HTTP_RESPONSE``) as the agent↔control path.

Three surfaces:
  • the relay server  (``herds relay`` — runs in our cloud)
  • account endpoints (provision / whoami — how the CLI gets a token + subdomain)
  • the host client   (dialed automatically by ``herds host`` when signed in)

Users never see any of this; they only ever ``herds auth`` + ``herds host``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from .protocol import Frame, FrameType

RESERVED = {
    "www", "api", "relay", "app", "admin", "mail", "docs", "status", "dashboard",
    "herds", "spawn", "spawnlabs", "auth", "login", "support", "help", "blog",
}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", (s or "").lower()).strip("-")[:32]


def http_base(relay_ws_url: str) -> str:
    """wss://relay.herds.run → https://relay.herds.run (and ws→http for local)."""
    return relay_ws_url.replace("wss://", "https://").replace("ws://", "http://").rstrip("/")


# --------------------------------------------------------------------------- #
# Server side
# --------------------------------------------------------------------------- #


import base64 as _b64
import hashlib
import hmac
import time as _time


def _hash_pw(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + _b64.b64encode(salt).decode() + "$" + _b64.b64encode(dk).decode()


def _verify_pw(password: str, stored: str) -> bool:
    try:
        _algo, salt_b64, dk_b64 = stored.split("$")
        salt, dk = _b64.b64decode(salt_b64), _b64.b64decode(dk_b64)
        test = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(test, dk)
    except Exception:  # noqa: BLE001
        return False


class _Accounts:
    """Account store: name → {token, email, pwhash}. JSON-backed (the relay's state).

    Two ways in: `provision` (CLI, passwordless token) and `register`/`login`
    (web, email + password). Both yield the same {token, account} identity."""

    def __init__(self, path: Path):
        self.path = path
        self.records: dict[str, dict] = {}     # account -> {token, email, pwhash, created}
        self.by_token: dict[str, str] = {}     # token -> account
        self.by_email: dict[str, str] = {}     # email -> account
        self.taken: set[str] = set()
        if path.exists():
            raw = json.loads(path.read_text())
            if "records" in raw:
                self.records = raw["records"]
            else:  # migrate old {by_token: {token: account}}
                for tok, acct in raw.get("by_token", {}).items():
                    self.records[acct] = {"token": tok, "email": None, "pwhash": None}
            for acct, rec in self.records.items():
                self.by_token[rec["token"]] = acct
                if rec.get("email"):
                    self.by_email[rec["email"]] = acct
                self.taken.add(acct)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"records": self.records}, indent=2))

    def whoami(self, token: str) -> Optional[str]:
        return self.by_token.get(token or "")

    def _new_name(self, want: str) -> str:
        name = _slug(want) or ("m" + secrets.token_hex(4))
        if name in RESERVED or not _NAME_RE.match(name):
            name = "m" + secrets.token_hex(4)
        base, i = name, 1
        while name in self.taken:
            i += 1
            name = f"{base}-{i}"
        return name

    def _create(self, name: str, email: Optional[str], pwhash: Optional[str]) -> dict:
        token = "hx_" + secrets.token_urlsafe(24)
        self.records[name] = {"token": token, "email": email, "pwhash": pwhash, "created": int(_time.time())}
        self.by_token[token] = name
        if email:
            self.by_email[email] = name
        self.taken.add(name)
        self._save()
        return {"token": token, "account": name}

    def provision(self, want: str = "") -> dict:
        return self._create(self._new_name(want), None, None)

    def register(self, email: str, password: str, want: str = "") -> dict:
        email = (email or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        if email in self.by_email:
            raise ValueError("That email already has an account — log in instead.")
        return self._create(self._new_name(want or email.split("@")[0]), email, _hash_pw(password))

    def login(self, email: str, password: str) -> Optional[dict]:
        acct = self.by_email.get((email or "").strip().lower())
        if not acct:
            return None
        rec = self.records.get(acct) or {}
        if not rec.get("pwhash") or not _verify_pw(password or "", rec["pwhash"]):
            return None
        return {"token": rec["token"], "account": acct}

    def exists(self, account: str) -> bool:
        return account in self.taken

    def get_record(self, account: str) -> Optional[dict]:
        rec = self.records.get(account)
        return {**rec, "account": account} if rec else None


def _valid_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


class _PgAccounts:
    """Postgres-backed account store (Neon). Durable, atomic, and secure: unique
    constraints enforce one-token / one-email; queries are parameterized; the DSN
    is read from the env (never committed). Same interface as ``_Accounts``."""

    def __init__(self, dsn: str, migrate_from: Optional[Path] = None):
        import psycopg
        from psycopg_pool import ConnectionPool

        self._psycopg = psycopg
        # A small checked pool survives Neon's pooler dropping idle connections.
        self.pool = ConnectionPool(
            dsn, min_size=1, max_size=8, max_idle=60, timeout=15,
            check=ConnectionPool.check_connection, kwargs={"autocommit": True},
        )
        self.pool.wait(timeout=20)
        with self.pool.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS relay_accounts (
                    account TEXT PRIMARY KEY,
                    token   TEXT UNIQUE NOT NULL,
                    email   TEXT UNIQUE,
                    pwhash  TEXT,
                    created BIGINT
                )"""
            )
        if migrate_from and migrate_from.exists():
            self._migrate_json(migrate_from)

    def _migrate_json(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            return
        records = raw.get("records") or {
            acct: {"token": tok, "email": None, "pwhash": None}
            for tok, acct in raw.get("by_token", {}).items()
        }
        n = 0
        with self.pool.connection() as conn:
            for acct, rec in records.items():
                cur = conn.execute(
                    "INSERT INTO relay_accounts (account, token, email, pwhash, created) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (account) DO NOTHING",
                    (acct, rec.get("token"), rec.get("email"), rec.get("pwhash"), rec.get("created") or 0),
                )
                n += cur.rowcount or 0
        try:  # don't re-import on the next boot
            path.rename(path.with_suffix(".migrated"))
        except OSError:
            pass
        print(f"herds relay: migrated {n} account(s) from {path} → postgres", file=sys.stderr)

    def whoami(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self.pool.connection() as conn:
            r = conn.execute("SELECT account FROM relay_accounts WHERE token=%s", (token,)).fetchone()
            return r[0] if r else None

    def exists(self, account: str) -> bool:
        with self.pool.connection() as conn:
            return conn.execute("SELECT 1 FROM relay_accounts WHERE account=%s", (account,)).fetchone() is not None

    def get_record(self, account: str) -> Optional[dict]:
        with self.pool.connection() as conn:
            r = conn.execute(
                "SELECT account, token, email, pwhash, created FROM relay_accounts WHERE account=%s", (account,)
            ).fetchone()
        if not r:
            return None
        return {"account": r[0], "token": r[1], "email": r[2], "pwhash": r[3], "created": r[4]}

    def _base_name(self, want: str) -> str:
        name = _slug(want) or ("m" + secrets.token_hex(4))
        if name in RESERVED or not _NAME_RE.match(name):
            name = "m" + secrets.token_hex(4)
        return name

    def _create(self, base: str, email: Optional[str], pwhash: Optional[str]) -> dict:
        for attempt in range(64):
            name = base if attempt == 0 else f"{base}-{attempt + 1}"
            token = "hx_" + secrets.token_urlsafe(24)
            try:
                with self.pool.connection() as conn:
                    conn.execute(
                        "INSERT INTO relay_accounts (account, token, email, pwhash, created) VALUES (%s,%s,%s,%s,%s)",
                        (name, token, email, pwhash, int(_time.time())),
                    )
                return {"token": token, "account": name}
            except self._psycopg.errors.UniqueViolation as e:
                cname = (getattr(e, "diag", None) and e.diag.constraint_name) or ""
                if "email" in cname:
                    raise ValueError("That email already has an account — log in instead.")
                continue  # account/token collision → try the next name
        raise ValueError("Could not allocate an account name. Try a different one.")

    def provision(self, want: str = "") -> dict:
        return self._create(self._base_name(want), None, None)

    def register(self, email: str, password: str, want: str = "") -> dict:
        email = (email or "").strip().lower()
        if not _valid_email(email):
            raise ValueError("Enter a valid email address.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        with self.pool.connection() as conn:
            if conn.execute("SELECT 1 FROM relay_accounts WHERE email=%s", (email,)).fetchone():
                raise ValueError("That email already has an account — log in instead.")
        return self._create(self._base_name(want or email.split("@")[0]), email, _hash_pw(password))

    def login(self, email: str, password: str) -> Optional[dict]:
        email = (email or "").strip().lower()
        with self.pool.connection() as conn:
            r = conn.execute(
                "SELECT account, token, pwhash FROM relay_accounts WHERE email=%s", (email,)
            ).fetchone()
        if not r or not r[2] or not _verify_pw(password or "", r[2]):
            return None
        return {"token": r[1], "account": r[0]}


def make_accounts(state_path: Path):
    """Postgres if HERDS_DATABASE_URL is set (production), else the JSON file."""
    dsn = os.environ.get("HERDS_DATABASE_URL")
    if dsn:
        return _PgAccounts(dsn, migrate_from=state_path)
    return _Accounts(state_path)


class _HostConn:
    def __init__(self, account: str, ws):
        self.account = account
        self.ws = ws
        self.pending: dict[str, asyncio.Future] = {}      # request_id -> HTTP response future
        self.ws_streams: dict[str, object] = {}            # stream_id -> tunnelled agent WebSocket
        self._lock = asyncio.Lock()

    async def send(self, frame: Frame) -> None:
        async with self._lock:
            await self.ws.send_text(frame.dump())


def create_relay_app(domain: str = "herds.run") -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Herds Relay")
    relay_domain = domain  # the relay's own zone, e.g. relay.herds.run
    # The platform site (herds.run) calls /relay/provision + /relay/whoami from the
    # browser — token-based, no cookies, so a permissive CORS policy is fine.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )
    accounts = make_accounts(Path(os.environ.get("HERDS_RELAY_STATE", "/tmp/herds_relay.json")))
    hosts: dict[str, _HostConn] = {}

    # --- Device-authorization flow (browser sign-in for `herds auth`) --------- #
    # The CLI asks for a code, opens the browser to /activate, the user approves
    # there, and the CLI polls until the token is bound. In-memory is fine: the
    # relay runs a single uvicorn worker and these records live ~10 minutes.
    devices: dict[str, dict] = {}      # device_code -> {user_code, status, token, account, url, created}
    by_user_code: dict[str, str] = {}  # user_code   -> device_code
    DEVICE_TTL = 600                   # seconds a pending request stays valid

    def _prune_devices() -> None:
        now = int(_time.time())
        for dc in [dc for dc, d in devices.items() if now - d["created"] > DEVICE_TTL]:
            d = devices.pop(dc, None)
            if d:
                by_user_code.pop(d["user_code"], None)

    def _gen_user_code() -> str:
        # Unambiguous alphabet (no 0/O/1/I) so it's easy to read off a screen.
        alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        raw = "".join(secrets.choice(alpha) for _ in range(8))
        return raw[:4] + "-" + raw[4:]

    def _site() -> str:
        return os.environ.get("HERDS_SITE", f"https://{domain}").rstrip("/")

    @app.post("/relay/device/start")
    async def device_start(request: Request):
        _prune_devices()
        body = json.loads(await request.body() or b"{}") or {}
        device_code = secrets.token_urlsafe(32)
        user_code = _gen_user_code()
        while user_code in by_user_code:
            user_code = _gen_user_code()
        devices[device_code] = {
            "user_code": user_code, "status": "pending", "token": None,
            "account": None, "url": None, "want": body.get("name", "") or "",
            "created": int(_time.time()),
        }
        by_user_code[user_code] = device_code
        return JSONResponse({
            "device_code": device_code, "user_code": user_code,
            "verification_uri": f"{_site()}/activate",
            "verification_uri_complete": f"{_site()}/activate?code={user_code}",
            "interval": 2, "expires_in": DEVICE_TTL,
        })

    @app.get("/relay/device/poll")
    def device_poll(device_code: str = ""):
        _prune_devices()
        d = devices.get(device_code)
        if not d:
            return {"status": "expired"}
        if d["status"] == "approved":  # one-shot: hand off the token, then forget it
            devices.pop(device_code, None)
            by_user_code.pop(d["user_code"], None)
            return {"status": "approved", "token": d["token"], "account": d["account"], "url": d["url"]}
        return {"status": d["status"]}

    @app.get("/relay/device/lookup")
    def device_lookup(code: str = ""):
        # Lets /activate confirm a code is real before asking the user to sign in.
        _prune_devices()
        dc = by_user_code.get((code or "").strip().upper())
        d = devices.get(dc) if dc else None
        if not d:
            return JSONResponse({"error": "Unknown or expired code."}, status_code=404)
        return {"user_code": d["user_code"], "status": d["status"]}

    @app.post("/relay/device/approve")
    async def device_approve(request: Request):
        # Called by /activate once the user holds a valid account token: binds the
        # code to that account so the waiting CLI receives it on its next poll.
        _prune_devices()
        body = json.loads(await request.body() or b"{}") or {}
        dc = by_user_code.get((body.get("user_code") or "").strip().upper())
        d = devices.get(dc) if dc else None
        if not d:
            return JSONResponse({"error": "Unknown or expired code."}, status_code=404)
        account = accounts.whoami(body.get("token") or "")
        if not account:
            return JSONResponse({"error": "Invalid account token."}, status_code=401)
        d.update(status="approved", token=body["token"], account=account, url=f"https://{account}.{domain}")
        return {"account": account}

    @app.post("/relay/provision")
    async def provision(request: Request):
        body = await request.body()
        want = (json.loads(body or b"{}") or {}).get("name", "") if body else ""
        info = accounts.provision(want)
        info["url"] = f"https://{info['account']}.{domain}"
        return JSONResponse(info)

    @app.post("/relay/register")
    async def register(request: Request):
        body = json.loads(await request.body() or b"{}") or {}
        try:
            info = accounts.register(body.get("email", ""), body.get("password", ""), body.get("name", ""))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        info["url"] = f"https://{info['account']}.{domain}"
        return JSONResponse(info)

    @app.post("/relay/login")
    async def login(request: Request):
        body = json.loads(await request.body() or b"{}") or {}
        info = accounts.login(body.get("email", ""), body.get("password", ""))
        if not info:
            return JSONResponse({"error": "Invalid email or password."}, status_code=401)
        info["url"] = f"https://{info['account']}.{domain}"
        return JSONResponse(info)

    @app.get("/relay/status")
    def status(token: str = ""):
        # Lets the platform dashboard show whether the account's Mac is connected.
        acct = accounts.whoami(token)
        if not acct:
            return JSONResponse({"error": "invalid token"}, status_code=401)
        rec = accounts.get_record(acct) or {}
        return {"account": acct, "url": f"https://{acct}.{domain}",
                "email": rec.get("email"), "online": acct in hosts}

    @app.get("/relay/whoami")
    def whoami(token: str = ""):
        acct = accounts.whoami(token)
        if not acct:
            return JSONResponse({"error": "invalid token"}, status_code=401)
        return {"account": acct, "url": f"https://{acct}.{domain}"}

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "online": sorted(hosts.keys())}

    @app.get("/internal/tls-allow")
    def tls_allow(domain: str = ""):
        # Caddy on-demand TLS gate: only mint a cert for a real account's subdomain.
        d = (domain or "").lower()
        if d == relay_domain.lower() or d == f"www.{relay_domain}".lower():
            return Response(status_code=200)
        if d.endswith("." + relay_domain):
            sub = d[: -(len(relay_domain) + 1)]
            if "." not in sub and (sub in RESERVED or accounts.exists(sub)):
                return Response(status_code=200)
        return Response(status_code=404)

    @app.websocket("/relay/connect")
    async def connect(ws: WebSocket):
        token = ws.query_params.get("token") or ""
        # Off-load the (possibly Postgres) lookup so a reconnect storm can't block
        # the event loop and starve keepalive pings for every other host.
        account = await asyncio.to_thread(accounts.whoami, token)
        if not account:
            await ws.close(code=4401)
            return
        await ws.accept()
        conn = _HostConn(account, ws)
        # A reconnect replaces the old link: tear down its tunnelled streams and
        # fail its pending requests so half-attached agents/SDKs don't wedge.
        old = hosts.get(account)
        if old is not None and old is not conn:
            for aws in list(old.ws_streams.values()):
                try:
                    await aws.close()
                except Exception:  # noqa: BLE001
                    pass
            old.ws_streams.clear()
            for fut in list(old.pending.values()):
                if not fut.done():
                    fut.cancel()
            old.pending.clear()
        hosts[account] = conn
        try:
            async for raw in ws.iter_text():
                frame = Frame.load(raw)
                if frame.type == FrameType.HTTP_RESPONSE:
                    fut = conn.pending.pop(frame.request_id, None)
                    if fut and not fut.done():
                        fut.set_result(frame.data)
                elif frame.type == FrameType.WS_DATA:
                    aws = conn.ws_streams.get(frame.data.get("stream_id"))
                    if aws is not None:
                        try:
                            await aws.send_text(frame.data.get("text", ""))
                        except Exception:  # noqa: BLE001
                            pass
                elif frame.type == FrameType.WS_CLOSE:
                    aws = conn.ws_streams.pop(frame.data.get("stream_id"), None)
                    if aws is not None:
                        try:
                            await aws.close()
                        except Exception:  # noqa: BLE001
                            pass
        except WebSocketDisconnect:
            pass
        finally:
            if hosts.get(account) is conn:
                hosts.pop(account, None)

    @app.websocket("/{ws_path:path}")
    async def proxy_ws(ws: WebSocket, ws_path: str):
        # Tunnel a subdomain WebSocket (e.g. you.relay.herds.run/v1/jobs/…/logs)
        # through the host's control channel — so remote agents get live streams.
        import uuid

        sub = _subdomain(ws.headers.get("host", ""))
        conn = hosts.get(sub) if (sub and sub not in RESERVED) else None
        if conn is None:
            await ws.close(code=4404)
            return
        await ws.accept()
        sid = "ws_" + uuid.uuid4().hex[:12]
        conn.ws_streams[sid] = ws
        await conn.send(Frame(type=FrameType.WS_OPEN, data={
            "stream_id": sid, "path": "/" + ws_path, "query": ws.url.query,
            "headers": {k: v for k, v in ws.headers.items() if k.lower() != "host"},
        }))
        try:
            while True:
                msg = await ws.receive_text()
                await conn.send(Frame(type=FrameType.WS_DATA, data={"stream_id": sid, "text": msg}))
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            conn.ws_streams.pop(sid, None)
            try:
                await conn.send(Frame(type=FrameType.WS_CLOSE, data={"stream_id": sid}))
            except Exception:  # noqa: BLE001
                pass

    def _subdomain(host_header: str) -> Optional[str]:
        h = (host_header or "").split(":")[0].lower()
        for suffix in ("." + domain, ".localhost"):
            if h.endswith(suffix):
                sub = h[: -len(suffix)]
                return sub if sub and "." not in sub else None
        return None

    @app.middleware("http")
    async def route_by_subdomain(request: Request, call_next):
        sub = _subdomain(request.headers.get("host", ""))
        if not sub or sub in RESERVED:
            return await call_next(request)  # relay's own endpoints
        conn = hosts.get(sub)
        if conn is None:
            return Response(f"No Herds host '{sub}' is connected.", status_code=502)
        import uuid

        body = await request.body()
        rid = "rq_" + uuid.uuid4().hex[:12]
        fut = asyncio.get_running_loop().create_future()
        conn.pending[rid] = fut
        await conn.send(Frame(type=FrameType.HTTP_REQUEST, request_id=rid, data={
            "method": request.method, "path": request.url.path, "query": request.url.query,
            "headers": dict(request.headers),
            "body_b64": base64.b64encode(body).decode() if body else "",
        }))
        try:
            res = await asyncio.wait_for(fut, timeout=30)
        except asyncio.TimeoutError:
            conn.pending.pop(rid, None)
            return Response("Herds host did not respond.", status_code=504)
        content = base64.b64decode(res["body_b64"]) if res.get("body_b64") else b""
        skip = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {k: v for k, v in (res.get("headers") or {}).items() if k.lower() not in skip}
        return Response(content=content, status_code=res.get("status", 502), headers=headers)

    return app


def serve_relay(host: str = "0.0.0.0", port: int = 8888, domain: str = "herds.run") -> None:
    import uvicorn

    # The server pings hosts to keep links warm; a generous timeout tolerates a host
    # whose loop is briefly busy serving a burst of dashboard assets.
    uvicorn.run(
        create_relay_app(domain), host=host, port=port, log_level="warning",
        ws_ping_interval=20, ws_ping_timeout=60,
    )


# --------------------------------------------------------------------------- #
# Account endpoints — used by `herds auth`
# --------------------------------------------------------------------------- #


def provision_account(relay_ws_url: str, want: str = "") -> dict:
    import httpx

    r = httpx.post(f"{http_base(relay_ws_url)}/relay/provision", json={"name": want}, timeout=15)
    r.raise_for_status()
    return r.json()


def whoami(relay_ws_url: str, token: str) -> Optional[dict]:
    import httpx

    r = httpx.get(f"{http_base(relay_ws_url)}/relay/whoami", params={"token": token}, timeout=15)
    return r.json() if r.status_code == 200 else None


def device_start(relay_ws_url: str, want: str = "") -> dict:
    """Begin a browser sign-in: returns a device_code (CLI polls it) and a
    user_code + verification URL (the human approves it in the browser)."""
    import httpx

    r = httpx.post(f"{http_base(relay_ws_url)}/relay/device/start", json={"name": want}, timeout=15)
    r.raise_for_status()
    return r.json()


def device_poll(relay_ws_url: str, device_code: str) -> dict:
    """Check a pending sign-in. Returns {status: pending|approved|expired, …}."""
    import httpx

    r = httpx.get(f"{http_base(relay_ws_url)}/relay/device/poll", params={"device_code": device_code}, timeout=15)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- #
# Host side — dialed automatically by `herds host` when signed in
# --------------------------------------------------------------------------- #


async def _run_client(relay_ws_url: str, token: str, local_url: str) -> None:
    import httpx
    import websockets

    url = f"{relay_ws_url.rstrip('/')}/relay/connect?token={token}"
    backoff = 1.0
    while True:
        try:
            # Client-initiated pings are essential: without them a half-open
            # connection (Wi-Fi drop / network switch — no TCP close arrives) would
            # hang the read loop forever and never reconnect. A failed ping raises
            # within ping_timeout, breaking out to the reconnect loop below. (The
            # event-loop starvation that once made these self-close was fixed by
            # offloading response encoding to a thread, so they're safe under load.)
            async with websockets.connect(
                url, max_size=None, ping_interval=20, ping_timeout=20,
                open_timeout=20, close_timeout=5,
            ) as ws:
                backoff = 1.0
                print("herds relay: link up", file=sys.stderr)
                send_lock = asyncio.Lock()
                streams: dict[str, object] = {}  # stream_id -> local WebSocket connection
                async with httpx.AsyncClient(base_url=local_url, timeout=30.0) as client:
                    async for raw in ws:
                        frame = Frame.load(raw)
                        if frame.type == FrameType.HTTP_REQUEST:
                            asyncio.create_task(_serve_one(ws, send_lock, client, frame))
                        elif frame.type == FrameType.WS_OPEN:
                            asyncio.create_task(_tunnel_ws(ws, send_lock, local_url, frame, streams))
                        elif frame.type == FrameType.WS_DATA:
                            local = streams.get(frame.data.get("stream_id"))
                            if local is not None:
                                try:
                                    await local.send(frame.data.get("text", ""))
                                except Exception:  # noqa: BLE001
                                    pass
                        elif frame.type == FrameType.WS_CLOSE:
                            local = streams.pop(frame.data.get("stream_id"), None)
                            if local is not None:
                                try:
                                    await local.close()
                                except Exception:  # noqa: BLE001
                                    pass
        except Exception as exc:  # noqa: BLE001 — reconnect on anything (drops, DNS, network switch)
            print(f"herds relay: link lost ({exc}); reconnecting in {backoff:.0f}s…", file=sys.stderr)
        # Fast, bounded backoff so the host self-heals within seconds of the network
        # coming back — it stays up until you stop it, no matter how often Wi-Fi flaps.
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.7, 10.0)


async def _tunnel_ws(ws, send_lock, local_url: str, frame: Frame, streams: dict) -> None:
    """Open a WS to the local control plane and pump it to the agent via the relay."""
    import websockets

    d = frame.data
    sid = d["stream_id"]
    base = local_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    url = f"{base}{d.get('path', '/')}" + (f"?{d['query']}" if d.get("query") else "")
    try:
        local = await websockets.connect(url, max_size=None, open_timeout=10)
    except Exception:  # noqa: BLE001
        async with send_lock:
            await ws.send(Frame(type=FrameType.WS_CLOSE, data={"stream_id": sid}).dump())
        return
    streams[sid] = local
    try:
        async for msg in local:
            text = msg if isinstance(msg, str) else msg.decode("utf-8", "ignore")
            async with send_lock:
                await ws.send(Frame(type=FrameType.WS_DATA, data={"stream_id": sid, "text": text}).dump())
    except Exception:  # noqa: BLE001
        pass
    finally:
        streams.pop(sid, None)
        try:
            await local.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            async with send_lock:
                await ws.send(Frame(type=FrameType.WS_CLOSE, data={"stream_id": sid}).dump())
        except Exception:  # noqa: BLE001
            pass


def _encode_response(request_id, status, headers, content) -> str:
    return Frame(type=FrameType.HTTP_RESPONSE, request_id=request_id, data={
        "status": status, "headers": headers,
        "body_b64": base64.b64encode(content).decode(),
    }).dump()


async def _serve_one(ws, send_lock, client, frame: Frame) -> None:
    d = frame.data
    path = d.get("path", "/")
    query = d.get("query", "")
    skip = {"host", "connection", "keep-alive", "transfer-encoding", "content-length"}
    headers = {k: v for k, v in (d.get("headers") or {}).items() if k.lower() not in skip}
    body = base64.b64decode(d["body_b64"]) if d.get("body_b64") else b""
    try:
        r = await client.request(d.get("method", "GET"), path + (f"?{query}" if query else ""),
                                 headers=headers, content=body)
        status, rheaders, content = r.status_code, dict(r.headers), r.content[: 16 * 1024 * 1024]
    except Exception as exc:  # noqa: BLE001
        status, rheaders, content = 502, {}, f"host unreachable: {exc}".encode()
    # Encode off the event loop: base64 + JSON of a large asset would otherwise
    # block it, stalling keepalive pongs and other requests (→ dropped relay link).
    payload = await asyncio.to_thread(_encode_response, frame.request_id, status, rheaders, content)
    async with send_lock:
        await ws.send(payload)


def run_relay_client(relay_ws_url: str, token: str, local_url: str) -> None:
    """Blocking entry point — `herds host` spawns this to expose its control plane."""
    try:
        asyncio.run(_run_client(relay_ws_url, token, local_url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # python -m herds.relay client <relay_ws> <token> <local_url>
    if len(sys.argv) >= 5 and sys.argv[1] == "client":
        run_relay_client(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        serve_relay(port=int(os.environ.get("HERDS_RELAY_PORT", "8888")),
                    domain=os.environ.get("HERDS_RELAY_DOMAIN", "herds.run"))
