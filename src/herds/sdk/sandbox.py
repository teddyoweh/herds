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
    ):
        self.id = sandbox_id
        self.machine_id = machine_id
        self._client = client or default_client()
        self._image = image
        self._volumes = volumes
        self._secrets = secrets
        self._inherit_home = inherit_home
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
    ) -> "Sandbox":
        sid = "sbx_" + uuid.uuid4().hex[:10]
        mid = mac.machine_id if mac is not None else machine_id
        return Sandbox(
            sid, mid, image=image, volumes=volumes, secrets=secrets, inherit_home=inherit_home,
            client=client or (mac._client if mac else default_client()),
        )

    def put(self, local: str, remote: str = "", *, clean: bool = False, ignore=None) -> dict:
        """Copy a local file or directory into this sandbox's workspace.

            sbx = herds.Sandbox.create()
            sbx.put("./my-project")          # whole codebase → workspace root
            sbx.exec("python3 main.py")
        """
        import base64
        from pathlib import Path
        from .client import HerdsError
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
            raise HerdsError(r.json().get("detail", r.text)
                             if r.headers.get("content-type", "").startswith("application/json") else r.text)
        return r.json()

    def _request(self, command, workdir, env, timeout, network) -> ExecRequest:
        from .mac import _build_request

        return _build_request(
            command, self._image, self._volumes, workdir, env, timeout, network,
            sandbox_id=self.id, secrets=self._secrets, inherit_home=self._inherit_home,
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
            keep_alive=keep_alive,
        )
        return self._client._start(self.machine_id, req)

    def stop(self) -> dict:
        """Stop any running processes in this sandbox (it stays on disk)."""
        return self._client.stop_sandbox(self.id)

    def expose(self, port: int, name: str = "") -> str:
        """Expose a server running in this sandbox (e.g. a web app or API on
        ``localhost:port``) as a public URL routed through the control plane."""
        return self._client.expose_port(self.id, port, name).get("url") or f"/p/{self.id}/{port}/"

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
