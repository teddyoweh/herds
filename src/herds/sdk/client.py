"""The SDK transport: a synchronous client over the control plane's HTTP+WS API.

User code is ordinary blocking Python (``mac.run(...)``), so the client uses
httpx's sync client to start a job and the ``websockets`` sync client to stream
logs back. The async machinery stays inside the control plane and daemon.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

import httpx
from websockets.sync.client import connect as ws_connect

from .. import config
from ..protocol import ExecRequest, Frame, FrameType


@dataclass
class Result:
    """The outcome of a command run on a Mac."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    request_id: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def raise_for_status(self) -> "Result":
        if not self.ok:
            raise CommandError(self)
        return self

    def __repr__(self) -> str:
        return (f"Result(exit_code={self.exit_code}, duration_ms={self.duration_ms}, "
                f"stdout={self.stdout[:40]!r}...)")


class CommandError(RuntimeError):
    def __init__(self, result: Result):
        self.result = result
        super().__init__(
            f"command failed with exit code {result.exit_code}\n{result.stderr.strip()}"
        )


class HerdsError(RuntimeError):
    pass


def _raise_http(r) -> None:
    """Raise a clear HerdsError from a failed response — never crash on a
    non-JSON body (e.g. the relay's plain-text 502 when no Mac is connected)."""
    try:
        data = r.json()
        detail = data.get("detail") if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 — body wasn't JSON
        detail = None
    text = detail or (r.text or "").strip() or f"HTTP {r.status_code}"
    if r.status_code in (502, 503, 504) or "no herds host" in text.lower():
        raise HerdsError("No Mac is connected to this account — run `herds host` on your Mac.")
    if r.status_code in (401, 403):
        raise HerdsError(f"Authentication failed ({r.status_code}): {text}. Check your token.")
    raise HerdsError(text)


class HerdsClient:
    """Talks to the control plane. One per process is plenty."""

    def __init__(self, control_plane: Optional[str] = None, api_key: Optional[str] = None):
        cfg = config.Config.load()
        creds = config.Credentials.load()
        self.control_plane = (control_plane or cfg.control_plane).rstrip("/")
        self.api_key = api_key or creds.api_key
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        self._http = httpx.Client(base_url=self.control_plane, headers=headers, timeout=30.0)

    # -- introspection ------------------------------------------------------ #

    def list_machines(self) -> list[dict]:
        r = self._http.get("/v1/machines")
        if r.status_code >= 400:
            _raise_http(r)
        return r.json().get("machines", [])

    def get_machine(self, machine_id: str) -> dict:
        r = self._http.get(f"/v1/machines/{machine_id}")
        if r.status_code == 404:
            raise HerdsError(f"no such machine: {machine_id}")
        if r.status_code >= 400:
            _raise_http(r)
        return r.json()

    # -- execution ---------------------------------------------------------- #

    def _start(self, machine_id: str, req: ExecRequest) -> str:
        r = self._http.post(f"/v1/machines/{machine_id}/exec", json=req.model_dump())
        if r.status_code >= 400:
            _raise_http(r)
        return r.json()["request_id"]

    def stop_sandbox(self, sandbox_id: str) -> dict:
        r = self._http.post(f"/v1/sandboxes/{sandbox_id}/stop")
        if r.status_code >= 400:
            _raise_http(r)
        return r.json()

    def terminate_sandbox(self, sandbox_id: str) -> dict:
        r = self._http.delete(f"/v1/sandboxes/{sandbox_id}")
        if r.status_code >= 400:
            _raise_http(r)
        return r.json()

    def expose_port(self, sandbox_id: str, port: int, name: str = "") -> dict:
        r = self._http.post(f"/v1/sandboxes/{sandbox_id}/ports", json={"port": port, "name": name})
        if r.status_code >= 400:
            _raise_http(r)
        return r.json()

    def stream(
        self,
        machine_id: str,
        req: ExecRequest,
        on_output: Optional[Callable[[str, str], None]] = None,
    ) -> Iterator[Frame]:
        """Start a job and yield every frame as it arrives, until EXIT."""
        request_id = self._start(machine_id, req)
        ws_url = self.control_plane.replace("http://", "ws://").replace("https://", "wss://")
        # The control plane authenticates the log stream via a ?token= query param
        # when auth is enforced (it can't read an Authorization header on a WS upgrade).
        q = f"?token={self.api_key}" if self.api_key else ""
        from ..relay import _wss_ssl_context

        log_url = f"{ws_url}/v1/jobs/{request_id}/logs{q}"
        with ws_connect(log_url, max_size=None, ssl=_wss_ssl_context(log_url)) as ws:
            for raw in ws:
                frame = Frame.load(raw)
                if on_output and frame.type in (FrameType.STDOUT, FrameType.STDERR):
                    on_output(frame.type.value, frame.data.get("text", ""))
                yield frame
                if frame.type == FrameType.EXIT:
                    return

    def run(
        self,
        machine_id: str,
        req: ExecRequest,
        *,
        stream_to_stdout: bool = False,
    ) -> Result:
        """Run a command to completion, collecting output into a :class:`Result`."""
        out: list[str] = []
        err: list[str] = []
        request_id = ""
        exit_code = -1
        duration_ms = 0

        def emit(stream: str, text: str) -> None:
            if stream_to_stdout:
                target = sys.stdout if stream == "stdout" else sys.stderr
                target.write(text)
                target.flush()

        for frame in self.stream(machine_id, req, on_output=emit):
            request_id = frame.request_id or request_id
            if frame.type == FrameType.STDOUT:
                out.append(frame.data.get("text", ""))
            elif frame.type == FrameType.STDERR:
                err.append(frame.data.get("text", ""))
            elif frame.type == FrameType.EXIT:
                exit_code = frame.data.get("exit_code", -1)
                duration_ms = frame.data.get("duration_ms", 0)

        return Result(
            exit_code=exit_code,
            stdout="".join(out),
            stderr="".join(err),
            duration_ms=duration_ms,
            request_id=request_id,
        )

    def close(self) -> None:
        self._http.close()


# A lazily-created process-wide default client, so `dc.mac()` needs no setup.
_default_client: Optional[HerdsClient] = None


def default_client() -> HerdsClient:
    global _default_client
    if _default_client is None:
        _default_client = HerdsClient()
    return _default_client


def configure(url: Optional[str] = None, token: Optional[str] = None) -> HerdsClient:
    """Point the SDK at a Mac for this process — the agent-friendly one-liner::

        import herds
        herds.configure(url="https://you.relay.herds.run", token="hx_…")
        herds.mac().run("uname -msr")

    Equivalent to setting ``HERDS_CONTROL_PLANE`` / ``HERDS_API_KEY``. Either
    argument may be omitted to keep the env/credentials default.
    """
    global _default_client
    _default_client = HerdsClient(control_plane=url, api_key=token)
    return _default_client
