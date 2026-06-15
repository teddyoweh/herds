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
    stderr_frame,
    stdout_frame,
)
from . import machine
from .executor import Executor


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

    # -- connection --------------------------------------------------------- #

    def _ws_url(self) -> str:
        base = self.control_plane.replace("http://", "ws://").replace("https://", "wss://")
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
                print(f"herds daemon: connection lost ({exc}); retrying in {backoff:.0f}s",
                      file=sys.stderr)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.7, 10.0)

    async def _connect_once(self) -> None:
        async with websockets.connect(self._ws_url(), max_size=None, ping_interval=20, ping_timeout=20) as ws:
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
            elif frame.type == FrameType.SANDBOX_CREATE:
                await self._handle_sandbox_create(frame)
            elif frame.type == FrameType.SANDBOX_TERMINATE:
                self.executor.terminate_sandbox(frame.data.get("sandbox_id", ""))
            elif frame.type == FrameType.CANCEL:
                if frame.request_id:
                    self.executor.cancel(frame.request_id)
            elif frame.type in (FrameType.FS_LIST, FrameType.FS_READ, FrameType.FS_WRITE):
                await self._handle_fs(frame)
            elif frame.type == FrameType.HTTP_REQUEST:
                await self._handle_http(frame)
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

    async def _handle_fs(self, frame: Frame) -> None:
        from . import files

        d = frame.data
        try:
            if frame.type == FrameType.FS_LIST:
                result = files.list_dir(d["kind"], d["id"], d.get("path", ""))
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
        self.executor.create_sandbox(sid, image=frame.data.get("image"))
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
        )

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
