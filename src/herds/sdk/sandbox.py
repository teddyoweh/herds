"""``Sandbox`` -- an isolated, persistent workspace on a Mac.

    sbx = dc.Sandbox.create(image="xcode:26")
    sbx.exec("git clone ...")
    sbx.exec("xcodebuild build")
    sbx.terminate()

Every ``exec`` reuses the same workspace directory on the Mac (same
``sandbox_id``), so files written by one command are visible to the next --
the Modal Sandbox mental model, backed by a real local directory.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Iterator, Optional, Union

from ..protocol import ExecRequest, FrameType
from .client import HerdsClient, Result, default_client
from .image import Image
from .volume import Volume

if TYPE_CHECKING:
    from .mac import Mac

ImageLike = Union[Image, str, None]
VolumesLike = Optional[dict[str, Union[Volume, str]]]


class Sandbox:
    def __init__(
        self,
        sandbox_id: str,
        machine_id: str,
        *,
        image: ImageLike = None,
        volumes: VolumesLike = None,
        secrets=None,
        inherit_home: bool = False,
        client: Optional[HerdsClient] = None,
        app: Optional[str] = None,
    ):
        self.id = sandbox_id
        self.machine_id = machine_id
        self._client = client or default_client()
        self._image = image
        self._volumes = volumes
        self._secrets = secrets
        self._inherit_home = inherit_home
        self._app = app
        self._terminated = False

    @staticmethod
    def create(
        *,
        image: ImageLike = None,
        volumes: VolumesLike = None,
        secrets=None,
        inherit_home: bool = False,
        mac: Optional["Mac"] = None,
        machine_id: str = "default",
        client: Optional[HerdsClient] = None,
        app: Optional[str] = None,
    ) -> "Sandbox":
        sid = "sbx_" + uuid.uuid4().hex[:10]
        mid = mac.machine_id if mac is not None else machine_id
        return Sandbox(
            sid, mid, image=image, volumes=volumes, secrets=secrets, inherit_home=inherit_home,
            client=client or (mac._client if mac else default_client()), app=app,
        )

    def put(self, local: str, remote: str = "", *, clean: bool = False, ignore=None) -> dict:
        """Copy a local file or directory into this sandbox's workspace.

            sbx = herds.Sandbox.create()
            sbx.put("./my-project")          # whole codebase → workspace root
            sbx.exec("python3 main.py")
        """
        import base64
        from pathlib import Path
        from .client import HerdsError, error_detail
        from .volume import _DEFAULT_IGNORE, _tar_dir

        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        src = Path(local).expanduser()
        if not src.exists():
            raise FileNotFoundError(f"no such path: {src}")
        if src.is_dir():
            ignored = set(_DEFAULT_IGNORE) | set(ignore or [])
            body = {"machine_id": self.machine_id, "path": remote,
                    "tar_b64": base64.b64encode(_tar_dir(src, ignored)).decode(), "clean": clean}
        else:
            rel = remote.rstrip("/") + "/" + src.name if remote.endswith("/") else (remote or src.name)
            body = {"machine_id": self.machine_id, "path": rel,
                    "content_b64": base64.b64encode(src.read_bytes()).decode()}
        r = self._client._http.put(f"/v1/sandboxes/{self.id}/put", json=body, timeout=300)
        if r.status_code >= 400:
            raise HerdsError(error_detail(r))
        return r.json()

    def _request(self, command, workdir, env, timeout, network) -> ExecRequest:
        from .mac import _build_request

        return _build_request(
            command, self._image, self._volumes, workdir, env, timeout, network,
            sandbox_id=self.id, secrets=self._secrets, inherit_home=self._inherit_home,
            app=self._app,
        )

    def exec(
        self,
        command: Union[str, list[str]],
        *,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        network: bool = True,
        stream: bool = False,
        check: bool = False,
    ) -> Result:
        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        req = self._request(command, workdir, env, timeout, network)
        result = self._client.run(self.machine_id, req, stream_to_stdout=stream)
        if check:
            result.raise_for_status()
        return result

    def stream(
        self,
        command: Union[str, list[str]],
        **kwargs,
    ) -> Iterator[tuple[str, str]]:
        req = self._request(
            command, kwargs.get("workdir"), kwargs.get("env"),
            kwargs.get("timeout"), kwargs.get("network", True),
        )
        for frame in self._client.stream(self.machine_id, req):
            if frame.type == FrameType.STDOUT:
                yield "stdout", frame.data.get("text", "")
            elif frame.type == FrameType.STDERR:
                yield "stderr", frame.data.get("text", "")

    def session(
        self,
        command: Union[str, list[str]],
        *,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        network: bool = True,
    ) -> "Session":
        """Start a RESIDENT process you feed many stdin turns into.

            with mac.sandbox() as sbx:
                s = sbx.session("cat")           # a line reader kept alive
                s.send("hello\\n")
                for stream, text in s.stream():  # echoes stream back live
                    print(text, end="")
                    s.send("world\\n"); s.close()

        Unlike ``exec`` (one-shot) the process stays live; ``send`` writes to its
        stdin from anywhere, ``stream`` yields its output until it exits, and
        ``close`` sends EOF. Because it's driven through the control plane, any
        worker that knows the session id can feed it — cross-worker input is free.
        """
        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        from .mac import _build_request

        req = _build_request(
            command, self._image, self._volumes, workdir, env, None, network,
            sandbox_id=self.id, secrets=self._secrets, inherit_home=self._inherit_home,
            app=self._app,
        )
        request_id = self._client._start_session(self.machine_id, req)
        return Session(request_id, self.machine_id, client=self._client)

    def spawn(
        self,
        command: Union[str, list[str]],
        *,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        network: bool = True,
        keep_alive: bool = False,
    ) -> str:
        """Start a long-running process in this sandbox without waiting.

        Returns immediately with a request id; the process keeps running on the
        Mac (the sandbox shows as "live") until it exits or you call ``stop()``.
        With ``keep_alive=True`` it's supervised — respawned if it exits — so it
        behaves like a service. Use ``exec`` for commands you wait on.
        """
        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        from .mac import _build_request

        req = _build_request(
            command, self._image, self._volumes, workdir, env, timeout, network,
            sandbox_id=self.id, secrets=self._secrets, inherit_home=self._inherit_home,
            keep_alive=keep_alive, app=self._app,
        )
        return self._client._start(self.machine_id, req)

    def stop(self) -> dict:
        """Stop any running processes in this sandbox (it stays on disk)."""
        return self._client.stop_sandbox(self.id)

    def expose(self, port: int, name: str = "") -> str:
        """Expose a server running in this sandbox (e.g. a web app or API on
        ``localhost:port``) as a public URL routed through the control plane."""
        return self._client.expose_port(self.id, port, name).get("url") or f"/p/{self.id}/{port}/"

    def tunnel(self, port: int, *, timeout: float = 20.0):
        """Open a RAW bidirectional byte tunnel to ``localhost:port`` in this
        sandbox — the connection ``expose()`` can't give you.

            with sbx.tunnel(9222) as t:     # a Chrome DevTools / websocket port
                t.send(b"...")
                data = t.recv()

        Where ``expose()`` is buffered HTTP request/response, this is a persistent
        pipe: bytes flow both ways untouched, so CDP, websockets, and screencasts
        survive. Returns a :class:`herds.TcpTunnel` (also a context manager)."""
        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        return self._client.open_tunnel(port, sandbox_id=self.id, timeout=timeout)

    # Modal-flavoured alias.
    connect_port = tunnel

    def tunnel_url(self, port: int) -> str:
        """The ``ws://``/``wss://`` URL for a raw tunnel to ``port`` in this
        sandbox (handy for handing a raw port to a non-Python CDP client)."""
        return self._client.tunnel_url(port, sandbox_id=self.id)

    def agent(
        self,
        goal: str,
        *,
        harness: str = "claude-code",
        proxy: Optional[str] = None,
        token: Optional[str] = None,
        command: Optional[str] = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        stream: bool = True,
    ) -> Result:
        """Run an agent inside this sandbox — keyless via proxyagent, output streamed.

            with mac.sandbox(image="xcode:26") as sbx:
                sbx.agent("build the app and fix any errors", proxy=PROXY, token="pa_…")

        The token routes through your proxy so the model key never lands here; for
        a never-on-disk token, create the sandbox with ``secrets=["proxyagent"]``
        (holding ``PROXYAGENT_TOKEN``). See :meth:`herds.Mac.agent`."""
        from .mac import _agent_argv, _agent_env, _agent_resolve

        proxy, token = _agent_resolve(proxy, token, None)
        return self.exec(
            _agent_argv(goal, harness, proxy, command),
            env={**_agent_env(proxy, token), **(env or {})},
            workdir=workdir, timeout=timeout, stream=stream,
        )

    def snapshot_filesystem(self, name: str = "") -> "Image":
        """Snapshot this sandbox's filesystem into a reusable base image.

            base = sbx.snapshot_filesystem("my-provisioned-env")
            fresh = mac.sandbox(image=base)   # starts pre-populated

        Mirrors Modal's ``Sandbox.snapshot_filesystem()``: the Mac tars the
        sandbox's workspace+home into a named base under the herds home. Returns an
        :class:`Image` bound to that base (``Image.from_id(image_id)``) — pass it
        as a new sandbox's ``image`` to restore the snapshot before anything runs.
        """
        from .client import HerdsError, error_detail

        if self._terminated:
            raise RuntimeError(f"sandbox {self.id} has been terminated")
        body = {"base": name} if name else {}
        r = self._client._http.post(f"/v1/sandboxes/{self.id}/snapshot", json=body, timeout=300)
        if r.status_code >= 400:
            raise HerdsError(error_detail(r))
        return Image.from_id(r.json()["image_id"])

    def terminate(self) -> None:
        """Destroy the sandbox: stop its processes and wipe its workspace."""
        try:
            self._client.terminate_sandbox(self.id)
        except Exception:
            pass
        self._terminated = True

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.terminate()

    def __repr__(self) -> str:
        return f"Sandbox({self.id!r} on {self.machine_id!r})"


class Session:
    """A handle to a resident, stdin-fed process on a Mac.

    Created by :meth:`Sandbox.session` / :meth:`herds.Mac.session`. ``send``
    writes a chunk to the process's stdin; ``stream`` yields ``(stream, text)``
    output live until the process exits; ``close`` sends EOF (which typically
    lets a line-reader loop finish). The process is addressed by ``id`` through
    the control plane, so any worker holding that id can feed it stdin.
    """

    def __init__(self, request_id: str, machine_id: str, *, client: Optional[HerdsClient] = None):
        self.id = request_id
        self.machine_id = machine_id
        self._client = client or default_client()
        self._log_gen = None   # the live stream_logs generator (holds the log WS)

    def send(self, data: str) -> None:
        """Write a chunk to the session's stdin."""
        self._client.send_stdin(self.id, data)

    def keepalive(self) -> None:
        """Mark this session active so the idle reaper spares it — call while the
        session is doing work with no stdin/stdout (e.g. parked awaiting a user's
        AskUserQuestion answer) so a long wait doesn't get it reaped."""
        self._client.session_keepalive(self.id)

    def stream(self) -> Iterator[tuple[str, str]]:
        """Yield ``(stream, text)`` output chunks live until the session exits.

        The underlying log WebSocket is tracked so :meth:`close` can tear it down
        even if you ``break`` out early — otherwise the socket (and its reader
        thread) would leak and block interpreter exit."""
        gen = self._client.stream_logs(self.id)
        self._log_gen = gen
        try:
            for frame in gen:
                if frame.type == FrameType.STDOUT:
                    yield "stdout", frame.data.get("text", "")
                elif frame.type == FrameType.STDERR:
                    yield "stderr", frame.data.get("text", "")
        finally:
            try:
                gen.close()   # GeneratorExit -> stream_logs' `with ws` closes the socket
            except Exception:
                pass
            if self._log_gen is gen:
                self._log_gen = None

    def close(self) -> None:
        """End the session: EOF its stdin (so a reader loop finishes) AND close
        the log stream if one is open, so nothing dangles."""
        try:
            self._client.send_stdin(self.id, "", eof=True)
        except Exception:
            pass
        gen, self._log_gen = self._log_gen, None
        if gen is not None:
            try:
                gen.close()   # closes the log WS + its reader thread
            except Exception:
                pass

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Session({self.id!r} on {self.machine_id!r})"
