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


class _Accounts:
    """Token → account map. Simple JSON-backed store (the relay's own state)."""

    def __init__(self, path: Path):
        self.path = path
        self.by_token: dict[str, str] = {}
        self.taken: set[str] = set()
        if path.exists():
            raw = json.loads(path.read_text())
            self.by_token = raw.get("by_token", {})
            self.taken = set(self.by_token.values())

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"by_token": self.by_token}, indent=2))

    def whoami(self, token: str) -> Optional[str]:
        return self.by_token.get(token or "")

    def provision(self, want: str = "") -> dict:
        name = _slug(want) or ("m" + secrets.token_hex(4))
        if name in RESERVED or not _NAME_RE.match(name):
            name = "m" + secrets.token_hex(4)
        base, i = name, 1
        while name in self.taken:
            i += 1
            name = f"{base}-{i}"
        token = "hx_" + secrets.token_urlsafe(24)
        self.by_token[token] = name
        self.taken.add(name)
        self._save()
        return {"token": token, "account": name}


class _HostConn:
    def __init__(self, account: str, ws):
        self.account = account
        self.ws = ws
        self.pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def send(self, frame: Frame) -> None:
        async with self._lock:
            await self.ws.send_text(frame.dump())


def create_relay_app(domain: str = "herds.run") -> FastAPI:
    app = FastAPI(title="Herds Relay")
    relay_domain = domain  # the relay's own zone, e.g. relay.herds.run
    accounts = _Accounts(Path(os.environ.get("HERDS_RELAY_STATE", "/tmp/herds_relay.json")))
    hosts: dict[str, _HostConn] = {}

    @app.post("/relay/provision")
    async def provision(request: Request):
        body = await request.body()
        want = (json.loads(body or b"{}") or {}).get("name", "") if body else ""
        info = accounts.provision(want)
        info["url"] = f"https://{info['account']}.{domain}"
        return JSONResponse(info)

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
            if "." not in sub and sub in accounts.taken:
                return Response(status_code=200)
        return Response(status_code=404)

    @app.websocket("/relay/connect")
    async def connect(ws: WebSocket):
        token = ws.query_params.get("token") or ""
        account = accounts.whoami(token)
        if not account:
            await ws.close(code=4401)
            return
        await ws.accept()
        conn = _HostConn(account, ws)
        hosts[account] = conn
        try:
            async for raw in ws.iter_text():
                frame = Frame.load(raw)
                if frame.type == FrameType.HTTP_RESPONSE:
                    fut = conn.pending.pop(frame.request_id, None)
                    if fut and not fut.done():
                        fut.set_result(frame.data)
        except WebSocketDisconnect:
            pass
        finally:
            if hosts.get(account) is conn:
                hosts.pop(account, None)

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

    uvicorn.run(create_relay_app(domain), host=host, port=port, log_level="warning")


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
            async with websockets.connect(url, max_size=None, ping_interval=20) as ws:
                backoff = 1.0
                send_lock = asyncio.Lock()
                async with httpx.AsyncClient(base_url=local_url, timeout=30.0) as client:
                    async for raw in ws:
                        frame = Frame.load(raw)
                        if frame.type == FrameType.HTTP_REQUEST:
                            asyncio.create_task(_serve_one(ws, send_lock, client, frame))
        except Exception as exc:  # noqa: BLE001 — reconnect on anything
            print(f"herds relay: link lost ({exc}); retrying in {backoff:.0f}s", file=sys.stderr)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


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
        data = {"status": r.status_code, "headers": dict(r.headers),
                "body_b64": base64.b64encode(r.content[: 16 * 1024 * 1024]).decode()}
    except Exception as exc:  # noqa: BLE001
        data = {"status": 502, "body_b64": base64.b64encode(f"host unreachable: {exc}".encode()).decode()}
    async with send_lock:
        await ws.send(Frame(type=FrameType.HTTP_RESPONSE, request_id=frame.request_id, data=data).dump())


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
