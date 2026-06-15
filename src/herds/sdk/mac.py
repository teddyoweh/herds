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

    def map(self, command, items, *, max_workers: int = 8, **run_kwargs) -> list["Result"]:
        """Run a command across many inputs in parallel (Modal-style fan-out)::

            mac.map("pytest {}", ["tests/a", "tests/b", "tests/c"])     # format string
            mac.map(lambda v: f"swift build -c {v}", ["debug", "release"])  # callable

        `command` is a format string (``{}`` ← item) or a callable (item → command).
        Returns one ``Result`` per item, in input order.
        """
        import concurrent.futures as cf

        def _one(item):
            cmd = command(item) if callable(command) else command.format(item)
            return self.run(cmd, **run_kwargs)

        items = list(items)
        with cf.ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(items)))) as ex:
            return list(ex.map(_one, items))

    def sandbox(self, image: ImageLike = None, volumes: VolumesLike = None) -> "Sandbox":
        from .sandbox import Sandbox

        return Sandbox.create(image=image, volumes=volumes, mac=self)

    def push(self, local: str, volume: str, remote: str = "", *, clean: bool = False, ignore=None) -> dict:
        """Push a local file/dir to a named volume on this Mac (sugar over Volume.put)::

            mac.push("./my-project", "repo")
            mac.run("python3 app/main.py", volumes={"app": herds.Volume.from_name("repo")})
        """
        from .volume import Volume

        return Volume.from_name(volume).put(
            local, remote, client=self._client, machine=self.machine_id, clean=clean, ignore=ignore,
        )

    # -- Mac-native primitives: the stuff only a real Mac can do ------------- #

    def screenshot(self, path: Optional[str] = None, *, timeout: int = 60):
        """Capture the Mac's screen — returns PNG bytes, or writes to ``path``::

            mac.screenshot("home.png")

        Needs Screen Recording permission for whatever runs ``herds host``
        (System Settings → Privacy & Security → Screen Recording)."""
        import base64
        r = self.run(
            ["/bin/zsh", "-lc",
             'f=$(mktemp /tmp/herds_shot_XXXXXX).png && screencapture -x "$f" && base64 < "$f" && rm -f "$f"'],
            timeout=timeout,
        )
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(
                f"screenshot failed ({r.stderr.strip() or 'no output'}) — grant Screen Recording "
                "to whatever runs `herds host` (System Settings → Privacy & Security → Screen Recording).")
        data = base64.b64decode(r.stdout)
        if path:
            with open(path, "wb") as fh:
                fh.write(data)
            return path
        return data

    def read_bytes(self, remote_path: str, *, timeout: int = 60) -> bytes:
        """Read a file off the Mac as bytes."""
        import base64
        r = self.run(["base64", "-i", remote_path], timeout=timeout)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"read {remote_path}: {r.stderr.strip()}")
        return base64.b64decode(r.stdout)

    def read_text(self, remote_path: str, encoding: str = "utf-8", *, timeout: int = 60) -> str:
        """Read a text file off the Mac."""
        return self.read_bytes(remote_path, timeout=timeout).decode(encoding, errors="replace")

    def write(self, remote_path: str, data, *, timeout: int = 60) -> None:
        """Write text/bytes to a file on the Mac (creates parent dirs). For whole
        trees use ``mac.push`` / ``Volume.put`` instead."""
        import base64
        raw = data.encode() if isinstance(data, str) else bytes(data)
        r = self.run(
            ["python3", "-c",
             "import sys,base64,os\np=sys.argv[1]\nos.makedirs(os.path.dirname(p) or '.',exist_ok=True)\n"
             "open(p,'wb').write(base64.b64decode(sys.argv[2]))",
             remote_path, base64.b64encode(raw).decode()],
            timeout=timeout,
        )
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"write {remote_path}: {r.stderr.strip()}")

    def ls(self, path: str = ".", *, timeout: int = 30) -> list:
        """List a directory on the Mac → ``[{name, dir, size, mtime_ms}]``."""
        import json
        r = self.run(["python3", "-c", _LS_SRC, path], timeout=timeout)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"ls {path}: {r.stderr.strip()}")
        return json.loads(r.stdout or "[]")

    def clipboard(self, *, timeout: int = 15) -> str:
        """Read the Mac's clipboard (text)."""
        return self.run(["pbpaste"], timeout=timeout).stdout

    def copy(self, text: str, *, timeout: int = 15) -> None:
        """Set the Mac's clipboard."""
        self.run(["osascript", "-e", f"set the clipboard to {_as(text)}"], timeout=timeout)

    def notify(self, message: str, title: str = "Herds", *, timeout: int = 15) -> None:
        """Post a macOS notification banner."""
        self.run(["osascript", "-e",
                  f"display notification {_as(message)} with title {_as(title)}"], timeout=timeout)

    @property
    def ui(self) -> "_UI":
        """Keyboard/GUI control (needs Accessibility permission): ``mac.ui.type(...)``."""
        return _UI(self)

    def __repr__(self) -> str:
        return f"Mac({self.machine_id!r})"


def _as(s: str) -> str:
    """Render a Python string as an AppleScript string literal."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


_LS_SRC = (
    "import os,sys,json\n"
    "p=sys.argv[1]\n"
    "print(json.dumps([{'name':n,"
    "'dir':os.path.isdir(os.path.join(p,n)),"
    "'size':(os.path.getsize(os.path.join(p,n)) if os.path.isfile(os.path.join(p,n)) else 0),"
    "'mtime_ms':int(os.path.getmtime(os.path.join(p,n))*1000)} "
    "for n in sorted(os.listdir(p))]))"
)

_KEYCODES = {"return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
             "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125, "up": 126}

_MODIFIERS = {"cmd": "command down", "command": "command down", "option": "option down",
              "alt": "option down", "control": "control down", "ctrl": "control down",
              "shift": "shift down"}


class _UI:
    """Drive the Mac's keyboard/GUI via System Events (Accessibility permission)."""

    def __init__(self, mac: "Mac"):
        self._m = mac

    def _osa(self, script: str, *, timeout: int = 30) -> str:
        r = self._m.run(["osascript", "-e", script], timeout=timeout)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"ui action failed: {r.stderr.strip() or 'grant Accessibility permission?'}")
        return r.stdout.strip()

    def type(self, text: str) -> None:
        """Type text into the focused field."""
        self._osa(f'tell application "System Events" to keystroke {_as(text)}')

    def key(self, name: str) -> None:
        """Press a named key — return, tab, escape, space, up/down/left/right."""
        code = _KEYCODES.get(name.lower())
        if code is None:
            self._osa(f'tell application "System Events" to keystroke {_as(name)}')
        else:
            self._osa(f'tell application "System Events" to key code {code}')

    def hotkey(self, *keys: str) -> None:
        """Press a chord, e.g. ``mac.ui.hotkey("cmd", "s")`` (mods: cmd/option/control/shift)."""
        if not keys:
            return
        *mods, final = keys
        using = ", ".join(_MODIFIERS[m.lower()] for m in mods)
        clause = f" using {{{using}}}" if using else ""
        self._osa(f'tell application "System Events" to keystroke {_as(final)}{clause}')


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


class Fleet:
    """Your whole pool of connected Macs — run work spread across all of them."""

    def __init__(self, *, url: Optional[str] = None, token: Optional[str] = None,
                 client: Optional[HerdsClient] = None):
        if client is None and (url or token):
            client = HerdsClient(control_plane=url, api_key=token)
        self._client = client or default_client()

    def macs(self) -> list[Mac]:
        """Online Macs in the pool."""
        return [Mac(m["machine_id"], client=self._client)
                for m in self._client.list_machines() if m.get("status") == "online"]

    def map(self, command, items, *, per_mac: int = 4, **run_kwargs) -> list["Result"]:
        """Run a command across many inputs, **distributed over every online Mac**::

            herds.fleet().map("pytest {}", ALL_TEST_DIRS)   # N Macs → N× throughput

        Work-stealing, not fixed round-robin: each Mac runs up to ``per_mac`` tasks
        at a time and pulls the next item the moment it's free — so faster/idler
        Macs naturally do more, and none gets overloaded. Returns one ``Result``
        per item, in input order; raises on the first task that fails.
        """
        import queue
        import threading

        macs = self.macs()
        if not macs:
            from .client import HerdsError
            raise HerdsError("No Macs are connected — run `herds host` on at least one Mac.")

        items = list(items)
        work: "queue.Queue[tuple[int, object]]" = queue.Queue()
        for pair in enumerate(items):
            work.put(pair)
        results: list = [None] * len(items)
        errors: list = []

        def _worker(mc: "Mac") -> None:
            while not errors:
                try:
                    i, item = work.get_nowait()
                except queue.Empty:
                    return
                cmd = command(item) if callable(command) else command.format(item)
                try:
                    results[i] = mc.run(cmd, **run_kwargs)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        # per_mac workers per Mac, all pulling from one shared queue (work-stealing).
        threads = [threading.Thread(target=_worker, args=(mc,), daemon=True)
                   for mc in macs for _ in range(max(1, per_mac))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:
            raise errors[0]
        return results


def fleet(*, url: Optional[str] = None, token: Optional[str] = None,
          client: Optional[HerdsClient] = None) -> Fleet:
    """Your pool of Macs — ``herds.fleet().map("pytest {}", dirs)``."""
    return Fleet(url=url, token=token, client=client)
