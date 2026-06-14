"""``Mac`` -- a handle to one of your connected Macs. The core of the SDK.

    import herds as dc
    mac = dc.mac()
    result = mac.run("xcodebuild -scheme MyApp build")
    print(result.stdout)
"""

from __future__ import annotations

from typing import Iterator, Optional, Union

from ..protocol import ExecRequest
from .client import HerdsClient, Result, default_client
from .image import Image
from .secret import Secret
from .volume import Volume

ImageLike = Union[Image, str, None]
VolumesLike = Optional[dict[str, Union[Volume, str]]]
SecretsLike = Optional[list[Union[Secret, str]]]


def _normalize_secrets(secrets: SecretsLike) -> list[str]:
    return [s.name if isinstance(s, Secret) else str(s) for s in (secrets or [])]


def _normalize_image(image: ImageLike) -> tuple[Optional[str], dict[str, str]]:
    if image is None:
        return None, {}
    if isinstance(image, str):
        return image, {}
    return image.name, dict(image.env)


def _normalize_volumes(volumes: VolumesLike) -> dict[str, str]:
    out: dict[str, str] = {}
    for mount, vol in (volumes or {}).items():
        out[mount] = vol.name if isinstance(vol, Volume) else str(vol)
    return out


def _build_request(
    command: Union[str, list[str]],
    image: ImageLike,
    volumes: VolumesLike,
    workdir: Optional[str],
    env: Optional[dict[str, str]],
    timeout: Optional[int],
    network: bool,
    sandbox_id: Optional[str] = None,
    secrets: SecretsLike = None,
    inherit_home: bool = False,
    keep_alive: bool = False,
) -> ExecRequest:
    image_name, image_env = _normalize_image(image)
    merged_env = {**image_env, **(env or {})}
    return ExecRequest(
        command=command,
        image=image_name,
        volumes=_normalize_volumes(volumes),
        workdir=workdir,
        env=merged_env,
        timeout=timeout,
        network=network,
        sandbox_id=sandbox_id,
        secrets=_normalize_secrets(secrets),
        inherit_home=inherit_home,
        keep_alive=keep_alive,
    )


class Mac:
    """A connected Mac you can run commands on."""

    def __init__(self, machine_id: str = "default", client: Optional[HerdsClient] = None):
        self._client = client or default_client()
        self.machine_id = machine_id
        self._info: Optional[dict] = None

    # -- facts -------------------------------------------------------------- #

    @property
    def info(self) -> dict:
        if self._info is None:
            self._info = self._client.get_machine(self.machine_id)
            # Adopt the resolved id so later calls hit the same machine.
            self.machine_id = self._info.get("machine_id", self.machine_id)
        return self._info

    @property
    def name(self) -> str:
        return self.info.get("name", self.machine_id)

    @property
    def online(self) -> bool:
        try:
            return self.info.get("status") == "online"
        except Exception:
            return False

    # -- run ---------------------------------------------------------------- #

    def run(
        self,
        command: Union[str, list[str]],
        *,
        image: ImageLike = None,
        volumes: VolumesLike = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        secrets: SecretsLike = None,
        timeout: Optional[int] = None,
        network: bool = True,
        inherit_home: bool = False,
        stream: bool = False,
        check: bool = False,
    ) -> Result:
        """Run a command on this Mac and return the :class:`Result`.

        ``stream=True`` mirrors output to your terminal live as it runs.
        ``check=True`` raises :class:`CommandError` on a non-zero exit.
        ``inherit_home=True`` runs with your real HOME and tools/logins (e.g. so
        ``claude``, ``git``, ``gh`` use your credentials) — your Mac, as you.
        """
        req = _build_request(command, image, volumes, workdir, env, timeout, network,
                             secrets=secrets, inherit_home=inherit_home)
        result = self._client.run(self.machine_id, req, stream_to_stdout=stream)
        if check:
            result.raise_for_status()
        return result

    def stream(
        self,
        command: Union[str, list[str]],
        *,
        image: ImageLike = None,
        volumes: VolumesLike = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        network: bool = True,
    ) -> Iterator[tuple[str, str]]:
        """Yield ``(stream, text)`` chunks live as the command runs."""
        from ..protocol import FrameType

        req = _build_request(command, image, volumes, workdir, env, timeout, network)
        for frame in self._client.stream(self.machine_id, req):
            if frame.type == FrameType.STDOUT:
                yield "stdout", frame.data.get("text", "")
            elif frame.type == FrameType.STDERR:
                yield "stderr", frame.data.get("text", "")

    def sandbox(self, image: ImageLike = None, volumes: VolumesLike = None) -> "Sandbox":
        from .sandbox import Sandbox

        return Sandbox.create(image=image, volumes=volumes, mac=self)

    def __repr__(self) -> str:
        return f"Mac({self.machine_id!r})"


def mac(
    machine_id: str = "default",
    *,
    url: Optional[str] = None,
    token: Optional[str] = None,
    client: Optional[HerdsClient] = None,
) -> Mac:
    """Get a handle to one of your Macs. With no id, picks your online Mac.

    Pass ``url`` + ``token`` to target a remote host directly (great for agents)::

        herds.mac(url="https://you.relay.herds.run", token="hx_…").run("uname")
    """
    if client is None and (url or token):
        client = HerdsClient(control_plane=url, api_key=token)
    return Mac(machine_id, client=client)


def machines(
    *,
    url: Optional[str] = None,
    token: Optional[str] = None,
    client: Optional[HerdsClient] = None,
) -> list[Mac]:
    """List all your connected Macs as :class:`Mac` handles."""
    if client is None and (url or token):
        client = HerdsClient(control_plane=url, api_key=token)
    c = client or default_client()
    return [Mac(m["machine_id"], client=c) for m in c.list_machines()]
