"""The Herds daemon: the agent that lives on a Mac and makes it programmable.

It holds a single persistent WebSocket out to the control plane (so it works
behind NAT with no inbound ports), registers this machine, then services
commands pushed down that socket -- streaming stdout/stderr/exit back up,
correlated by request_id. Reconnects with exponential backoff forever.
"""

from __future__ import annotations

import asyncio
import itertools
import sys
from typing import Optional

import websockets

from .. import config
from ..protocol import (
    Frame,
    FrameType,
    error_frame,
    exit_frame,
    session_ready_frame,
    stderr_frame,
    stdout_frame,
    tunnel_close_frame,
    tunnel_data_frame,
    tunnel_ready_frame,
)
from . import machine
from .executor import Executor


def _is_auth_reject(exc: Exception) -> bool:
    """True when the host/relay rejected our token. The control plane closes with
    WS code 4401/4400 (post-accept) or rejects the handshake with HTTP 401/403;
    the relay uses 4401 for an unknown account. Either way, retrying is pointless."""
    code = getattr(exc, "code", None)  # websockets ConnectionClosed* close code
    if code in (4401, 4400):
        return True
    status = getattr(exc, "status_code", None)  # older websockets InvalidStatusCode
    resp = getattr(exc, "response", None)  # newer websockets InvalidStatus
    if resp is not None:
        status = getattr(resp, "status_code", status)
    return status in (401, 403)


class Daemon:
    def __init__(self, control_plane: str, machine_id: str, device_token: Optional[str]):
        self.control_plane = control_plane
        self.machine_id = machine_id
        self.device_token = device_token
        self.executor = Executor()
        self.info = machine.gather(machine_id)
        self._seqs: dict[str, itertools.count] = {}
        self._send_lock = asyncio.Lock()
        self._ws = None  # the live websocket connection, set per session
        # Live raw TCP tunnels keyed by stream_id -> the local socket's writer.
        self._tunnels: dict[str, asyncio.StreamWriter] = {}

    # -- connection --------------------------------------------------------- #

    def _ws_url(self) -> str:
        # Accept a bare host ("you.herds.run") as well as a full URL: without a
        # scheme the ws/wss replace below is a no-op and websockets.connect() can't
        # dial it. Default schemeless hosts to TLS (wss), matching the relay.
        base = self.control_plane.strip()
        if "://" not in base:
            base = "https://" + base
        base = base.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
        url = f"{base}/agent/ws?machine_id={self.machine_id}"
        if self.device_token:
            url += f"&token={self.device_token}"
        return url

    async def run_forever(self) -> None:
        backoff = 1.0
        while True:
            try:
                await self._connect_once()
                backoff = 1.0  # reset after a clean session
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — never let the daemon die; always reconnect
                if _is_auth_reject(exc):
                    # A bad/expired token loops forever otherwise. Stop and say so.
                    print("herds daemon: the host rejected this token. Re-run "
                          "`herds connect <link> <token>` with a fresh token from `herds host`.",
                          file=sys.stderr)
                    return
                print(f"herds daemon: connection lost ({exc}); retrying in {backoff:.0f}s",
                      file=sys.stderr)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.7, 10.0)

    async def _connect_once(self) -> None:
        from ..relay import _wss_ssl_context

        url = self._ws_url()
        async with websockets.connect(
            url, max_size=None, ping_interval=20, ping_timeout=20,
            ssl=_wss_ssl_context(url),
        ) as ws:
            self._ws = ws
            # Handshake: announce who we are and what we are.
            await self._send(Frame(
                type=FrameType.REGISTERED,
                data={"machine": self.info.model_dump()},
            ))
            print(f"herds daemon: connected as {self.machine_id} "
                  f"({self.info.name}) -> {self.control_plane}", file=sys.stderr)
            await self._report_volumes()
            await self._report_metrics()
            # Fleet reapers (idle-session + sandbox-dir GC) are machine-level, not
            # connection-level; start_reapers() is idempotent across reconnects.
            self.executor.start_reapers()
            heartbeat = asyncio.create_task(self._volume_heartbeat())
            metricbeat = asyncio.create_task(self._metrics_heartbeat())
            try:
                async for raw in ws:
                    frame = Frame.load(raw)
                    # Each command runs concurrently; the socket keeps flowing.
                    asyncio.create_task(self._handle(frame))
            finally:
                heartbeat.cancel()
                metricbeat.cancel()
                self._ws = None  # don't let stale sends race the next session

    async def _volume_heartbeat(self) -> None:
        while True:
            await asyncio.sleep(15)
            await self._report_volumes()

    async def _metrics_heartbeat(self) -> None:
        while True:
            await asyncio.sleep(5)
            await self._report_metrics()

    async def _report_metrics(self) -> None:
        from . import metrics

        await self._send(Frame(type=FrameType.METRICS_REPORT, data=metrics.sample()))

    async def _report_volumes(self) -> None:
        vols = []
        if config.VOLUMES_DIR.exists():
            for p in config.VOLUMES_DIR.iterdir():
                if not p.is_dir():
                    continue
                size = 0
                count = 0
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            size += f.stat().st_size
                            count += 1
                        except OSError:
                            pass
                vols.append({"name": p.name, "size_bytes": size, "file_count": count})
        await self._send(Frame(type=FrameType.VOLUMES_REPORT, data={"volumes": vols}))

    async def _send(self, frame: Frame) -> None:
        if self._ws is None:
            return
        async with self._send_lock:
            await self._ws.send(frame.dump())

    def _next_seq(self, request_id: str) -> int:
        counter = self._seqs.setdefault(request_id, itertools.count())
        return next(counter)

    # -- command handlers --------------------------------------------------- #

    async def _handle(self, frame: Frame) -> None:
        try:
            if frame.type in (FrameType.EXEC, FrameType.SANDBOX_EXEC):
                await self._handle_exec(frame)
            elif frame.type == FrameType.SESSION_START:
                await self._handle_session_start(frame)
            elif frame.type == FrameType.STDIN:
                if frame.request_id:
                    await self.executor.session_send(
                        frame.request_id,
                        frame.data.get("data", ""),
                        eof=bool(frame.data.get("eof")),
                    )
            elif frame.type == FrameType.SANDBOX_CREATE:
                await self._handle_sandbox_create(frame)
            elif frame.type == FrameType.SANDBOX_TERMINATE:
                self.executor.terminate_sandbox(frame.data.get("sandbox_id", ""))
            elif frame.type == FrameType.SNAPSHOT:
                await self._handle_snapshot(frame)
            elif frame.type == FrameType.CANCEL:
                if frame.request_id:
                    self.executor.cancel(frame.request_id)
            elif frame.type in (FrameType.FS_LIST, FrameType.FS_READ, FrameType.FS_GET,
                                 FrameType.FS_WRITE, FrameType.FS_REMOVE):
                await self._handle_fs(frame)
            elif frame.type == FrameType.HTTP_REQUEST:
                await self._handle_http(frame)
            elif frame.type == FrameType.TUNNEL_OPEN:
                await self._handle_tunnel_open(frame)
            elif frame.type == FrameType.TUNNEL_DATA:
                await self._handle_tunnel_data(frame)
            elif frame.type == FrameType.TUNNEL_CLOSE:
                await self._handle_tunnel_close(frame)
            elif frame.type == FrameType.PING:
                await self._send(Frame(type=FrameType.PONG, request_id=frame.request_id))
        except Exception as exc:  # never let one bad frame kill the socket
            if frame.request_id:
                await self._send(error_frame(frame.request_id, str(exc)))

    async def _handle_http(self, frame: Frame) -> None:
        """Proxy an HTTP request to a server running inside a sandbox (localhost:port)."""
        import base64

        import httpx

        d = frame.data
        port = d.get("port")
        path = d.get("path", "/")
        query = d.get("query", "")
        url = f"http://127.0.0.1:{port}{path}" + (f"?{query}" if query else "")
        body = base64.b64decode(d["body_b64"]) if d.get("body_b64") else b""
        # Drop hop-by-hop / host headers; the upstream sees localhost.
        skip = {"host", "connection", "keep-alive", "transfer-encoding", "content-length"}
        headers = {k: v for k, v in (d.get("headers") or {}).items() if k.lower() not in skip}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.request(d.get("method", "GET"), url, headers=headers, content=body)
            result = {
                "status": r.status_code,
                "headers": dict(r.headers),
                "body_b64": base64.b64encode(r.content[: 8 * 1024 * 1024]).decode(),
            }
        except Exception as exc:
            result = {"status": 502, "error": str(exc),
                      "body_b64": base64.b64encode(f"sandbox port {port} unreachable: {exc}".encode()).decode()}
        await self._send(Frame(type=FrameType.HTTP_RESPONSE, request_id=frame.request_id, data=result))

    # -- raw TCP tunnels ---------------------------------------------------- #

    async def _handle_tunnel_open(self, frame: Frame) -> None:
        """Dial a sandbox-local TCP port and pump bytes both directions.

        Unlike :meth:`_handle_http` (one buffered request/response), this opens a
        persistent bidirectional pipe: everything the local port emits is shipped
        up as :class:`TUNNEL_DATA` frames, and every :class:`TUNNEL_DATA` from the
        control plane is written straight into the socket. This is what lets
        long-lived protocols (CDP, websockets, a screencast) survive."""
        d = frame.data
        sid = d.get("stream_id")
        port = int(d.get("port", 0))
        host = d.get("host", "127.0.0.1")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10
            )
        except Exception as exc:  # noqa: BLE001 — nothing listening / refused / timeout
            await self._send(tunnel_close_frame(sid, error=str(exc)))
            return
        self._tunnels[sid] = writer
        await self._send(tunnel_ready_frame(sid))
        asyncio.create_task(self._pump_tunnel(sid, reader))

    async def _pump_tunnel(self, sid: str, reader: asyncio.StreamReader) -> None:
        """Drain the local socket into TUNNEL_DATA frames until it closes."""
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                await self._send(tunnel_data_frame(sid, chunk))
        except Exception:  # noqa: BLE001 — socket reset/closed mid-read
            pass
        finally:
            writer = self._tunnels.pop(sid, None)
            if writer is not None:
                try:
                    writer.close()
                except Exception:  # noqa: BLE001
                    pass
            await self._send(tunnel_close_frame(sid))

    async def _handle_tunnel_data(self, frame: Frame) -> None:
        import base64

        sid = frame.data.get("stream_id")
        writer = self._tunnels.get(sid)
        if writer is None:
            return
        try:
            writer.write(base64.b64decode(frame.data.get("data_b64", "")))
            await writer.drain()
        except Exception:  # noqa: BLE001 — local side went away; tear the tunnel down
            self._tunnels.pop(sid, None)
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass
            await self._send(tunnel_close_frame(sid))

    async def _handle_tunnel_close(self, frame: Frame) -> None:
        sid = frame.data.get("stream_id")
        writer = self._tunnels.pop(sid, None)
        if writer is not None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _handle_fs(self, frame: Frame) -> None:
        from . import files

        d = frame.data
        try:
            if frame.type == FrameType.FS_LIST:
                result = files.list_dir(d["kind"], d["id"], d.get("path", ""))
            elif frame.type == FrameType.FS_GET:
                result = files.get_file(d["kind"], d["id"], d.get("path", ""))
            elif frame.type == FrameType.FS_REMOVE:
                result = files.remove(d["kind"], d["id"], d.get("path", ""),
                                      recursive=bool(d.get("recursive", True)))
            elif frame.type == FrameType.FS_WRITE:
                if d.get("tar_b64") is not None:
                    result = files.extract_tar(d["kind"], d["id"], d.get("path", ""),
                                               d["tar_b64"], clean=bool(d.get("clean")))
                else:
                    result = files.write_file(d["kind"], d["id"], d.get("path", ""), d.get("content_b64", ""))
            else:
                result = files.read_file(d["kind"], d["id"], d.get("path", ""))
        except (PermissionError, ValueError, OSError) as exc:
            result = {"error": str(exc)}
        await self._send(Frame(type=FrameType.FS_RESULT, request_id=frame.request_id, data=result))

    async def _handle_sandbox_create(self, frame: Frame) -> None:
        sid = frame.data["sandbox_id"]
        # A base restores a snapshot image into the fresh sandbox tree.
        self.executor.create_sandbox(
            sid, image=frame.data.get("image"), base=frame.data.get("base")
        )
        await self._send(Frame(
            type=FrameType.SANDBOX_READY,
            request_id=frame.request_id,
            data={"sandbox_id": sid},
        ))
        # An optional entrypoint command runs as the sandbox's main process.
        if frame.data.get("command"):
            await self._run_and_stream(
                frame.request_id,
                frame.data["command"],
                sandbox_id=sid,
                image=frame.data.get("image"),
                volumes=frame.data.get("volumes"),
                env=frame.data.get("env"),
                timeout=frame.data.get("timeout"),
                network=frame.data.get("network", True),
                setup_commands=frame.data.get("setup_commands"),
            )

    async def _handle_exec(self, frame: Frame) -> None:
        d = frame.data
        await self._run_and_stream(
            frame.request_id,
            d["command"],
            sandbox_id=d.get("sandbox_id"),
            image=d.get("image"),
            volumes=d.get("volumes"),
            workdir=d.get("workdir"),
            env=d.get("env"),
            timeout=d.get("timeout"),
            network=d.get("network", True),
            inherit_home=d.get("inherit_home", False),
            keep_alive=d.get("keep_alive", False),
            setup_commands=d.get("setup_commands"),
            base=d.get("base"),
        )

    async def _handle_snapshot(self, frame: Frame) -> None:
        """Tar a sandbox's fs into a named base image and reply with its facts.

        Replies as a SNAPSHOT_RESULT RPC (correlated by request_id) so the control
        plane can resolve the awaiting SDK call, mirroring FS_RESULT."""
        d = frame.data
        try:
            result = self.executor.snapshot(d["sandbox_id"], d["base"])
        except Exception as exc:  # noqa: BLE001 — surface as an RPC error payload
            result = {"error": str(exc)}
        await self._send(Frame(
            type=FrameType.SNAPSHOT_RESULT, request_id=frame.request_id, data=result
        ))

    async def _handle_session_start(self, frame: Frame) -> None:
        """Start a resident, stdin-fed session and stream it until it exits.

        This handler task lives for the whole session: it launches the process,
        then blocks on ``session_wait``. Meanwhile STDIN frames arrive as their
        own tasks and are routed to the live process by request_id — so input can
        flow in from any worker via the control plane while output streams back."""
        request_id = frame.request_id
        d = frame.data

        async def sink(stream: str, text: str) -> None:
            seq = self._next_seq(request_id)
            f = (stdout_frame if stream == "stdout" else stderr_frame)(request_id, seq, text)
            await self._send(f)

        try:
            await self.executor.start_session(
                request_id,
                d["command"],
                sink=sink,
                sandbox_id=d.get("sandbox_id"),
                image=d.get("image"),
                volumes=d.get("volumes"),
                workdir=d.get("workdir"),
                env=d.get("env"),
                network=d.get("network", True),
                inherit_home=d.get("inherit_home", False),
                setup_commands=d.get("setup_commands"),
                base=d.get("base"),
            )
        except Exception as exc:  # launch failed — report a terminal EXIT
            await self._send(error_frame(request_id, str(exc)))
            self._seqs.pop(request_id, None)
            await self._send(exit_frame(request_id, 127, 0))
            return

        # The process is live now — tell the control plane so its start_session
        # POST can return a handle that's immediately usable (no stdin race).
        await self._send(session_ready_frame(request_id))

        code, ms = await self.executor.session_wait(request_id)
        self._seqs.pop(request_id, None)
        await self._send(exit_frame(request_id, code, ms))

    async def _run_and_stream(self, request_id, command, **kwargs) -> None:
        async def sink(stream: str, text: str) -> None:
            seq = self._next_seq(request_id)
            frame = (stdout_frame if stream == "stdout" else stderr_frame)(request_id, seq, text)
            await self._send(frame)

        code, ms = await self.executor.run(request_id, command, sink=sink, **kwargs)
        self._seqs.pop(request_id, None)
        await self._send(exit_frame(request_id, code, ms))


def main() -> None:
    """Entry point for the ``herdsd`` console script and ``herds connect``."""
    config.ensure_dirs()
    cfg = config.Config.load()
    creds = config.Credentials.load()
    if not cfg.machine_id:
        cfg.machine_id = machine.new_machine_id()
        cfg.machine_name = machine.gather(cfg.machine_id).name
        cfg.save()
    daemon = Daemon(cfg.control_plane, cfg.machine_id, creds.device_token)
    try:
        asyncio.run(daemon.run_forever())
    except KeyboardInterrupt:
        print("herds daemon: shutting down", file=sys.stderr)


if __name__ == "__main__":
    main()
