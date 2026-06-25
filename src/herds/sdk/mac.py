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
        # Native screen/GUI access must run in your real login session — no Seatbelt
        # sandbox, real $HOME — or macOS TCC won't honour the Screen Recording grant.
        r = self.run(
            ["/bin/zsh", "-lc",
             'f=$(mktemp /tmp/herds_shot_XXXXXX).png && screencapture -x "$f" && base64 < "$f" && rm -f "$f"'],
            timeout=timeout, inherit_home=True,
        )
        screen_hint = ("grant Screen Recording to whatever runs `herds host` "
                       "(System Settings → Privacy & Security → Screen Recording), then restart it")
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"screenshot failed ({r.stderr.strip() or 'no output'}) — {screen_hint}.")
        data = base64.b64decode(r.stdout)
        # A TCC denial frequently still exits 0 but yields a tiny/empty capture.
        if len(data) < 1024:
            from .client import HerdsError
            raise HerdsError(f"screenshot came back empty — {screen_hint}.")
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
            raise HerdsError(f"write {remote_path}: {_clean_err(r.stderr)}")

    def ls(self, path: str = ".", *, timeout: int = 30) -> list:
        """List a directory on the Mac → ``[{name, dir, size, mtime_ms}]``."""
        import json
        r = self.run(["python3", "-c", _LS_SRC, path], timeout=timeout)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"ls {path}: {_clean_err(r.stderr)}")
        return json.loads(r.stdout or "[]")

    def clipboard(self, *, timeout: int = 15) -> str:
        """Read the Mac's clipboard (text)."""
        return self.run(["pbpaste"], timeout=timeout, inherit_home=True).stdout

    def copy(self, text: str, *, timeout: int = 15) -> None:
        """Set the Mac's clipboard."""
        self.run(["osascript", "-e", f"set the clipboard to {_as(text)}"], timeout=timeout, inherit_home=True)

    def notify(self, message: str, title: str = "Herds", *, timeout: int = 15) -> None:
        """Post a macOS notification banner."""
        self.run(["osascript", "-e",
                  f"display notification {_as(message)} with title {_as(title)}"], timeout=timeout, inherit_home=True)

    @property
    def ui(self) -> "_UI":
        """Keyboard/GUI control (needs Accessibility permission): ``mac.ui.type(...)``."""
        return _UI(self)

    def chrome(self, url: Optional[str] = None, *, cdp_port: Optional[int] = None) -> "_Chrome":
        """Launch & drive Chrome in the Mac's real session (your profile/logins)::

            c = mac.chrome("https://news.ycombinator.com")
            c.js("document.title")              # run JS in the active tab
            c.open("https://example.com")

        Pass ``cdp_port`` to also enable the DevTools Protocol (drive with Playwright
        over the exposed port). ``js()`` needs Chrome's *View → Developer → Allow
        JavaScript from Apple Events*, plus Automation permission for the host."""
        args = []
        if cdp_port:
            args += [f"--remote-debugging-port={cdp_port}", "--remote-allow-origins=*"]
        self.run(["/bin/zsh", "-lc", f'open -na "Google Chrome" --args {" ".join(args)}'], timeout=30, inherit_home=True)
        c = _Chrome(self, cdp_port)
        if url:
            import time
            time.sleep(1.5)  # let Chrome come up before the first AppleScript
            c.open(url)
        return c

    # -- agents: run a real agent on this Mac, keyless --------------------- #

    def agent(
        self,
        goal: str,
        *,
        harness: str = "claude-code",
        proxy: Optional[str] = None,
        token: Optional[str] = None,
        secret: Optional[str] = None,
        command: Optional[str] = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        volumes: VolumesLike = None,
        timeout: Optional[int] = None,
        stream: bool = True,
        inherit_home: bool = True,
    ) -> Result:
        """Run an agent — Claude Code, Codex, or a custom CLI — on this Mac, keyless.

        It routes every model call through your `proxyagent <https://pypi.org/project/proxyagent/>`_
        proxy, so the model API key never touches this Mac — it only ever holds a
        scoped, revocable token. Pass that token as a Herds **Secret** (best) so
        it's injected at run time and never written to disk; output streams live::

            mac.agent("fix the failing tests", proxy="https://proxy.you.com", secret="proxyagent")
            mac.agent("summarise today's PRs", harness="codex", proxy=PROXY, token="pa_…")
            mac.agent("ship it", harness="custom", command="my-agent {goal}", proxy=PROXY)

        The Mac needs ``proxyagent`` and the chosen agent CLI installed
        (``pip install proxyagent`` · ``npm i -g @anthropic-ai/claude-code``).
        ``inherit_home=True`` (default) runs as you, so the agent uses your real
        tools, logins and PATH. Returns the :class:`Result` (exit code + output).
        """
        proxy, token = _agent_resolve(proxy, token, secret)
        return self.run(
            _agent_argv(goal, harness, proxy, command),
            env={**_agent_env(proxy, token), **(env or {})},
            secrets=[secret] if secret else None,
            workdir=workdir, volumes=volumes, timeout=timeout,
            stream=stream, inherit_home=inherit_home,
        )

    def __repr__(self) -> str:
        return f"Mac({self.machine_id!r})"


def _agent_argv(goal: str, harness: str, proxy: Optional[str], command: Optional[str]) -> list[str]:
    """Build the ``proxyagent run`` argv that launches a real agent CLI, keyless."""
    argv = ["proxyagent", "run", harness, "--goal", goal]
    if proxy:
        argv += ["--proxy", proxy]
    if command:
        argv += ["--command", command]
    return argv


def _agent_resolve(proxy: Optional[str], token: Optional[str], secret: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve the proxy URL and token to forward to the Mac. Both fall back to
    the caller's ``PROXYAGENT_PROXY`` / ``PROXYAGENT_TOKEN`` env (proxyagent's CLI
    doesn't read them itself). A Herds ``secret`` means send no plaintext token —
    it's injected from the secret store instead."""
    import os as _os
    proxy = proxy or _os.environ.get("PROXYAGENT_PROXY")
    token = token if (token or secret) else _os.environ.get("PROXYAGENT_TOKEN")
    return proxy, token


def _agent_env(proxy: Optional[str], token: Optional[str]) -> dict[str, str]:
    import os as _os
    env: dict[str, str] = {}
    proxy = proxy or _os.environ.get("PROXYAGENT_PROXY")
    if proxy:
        env["PROXYAGENT_PROXY"] = proxy
    if token:  # best practice is a Herds Secret instead, so it's never on the wire as plain env
        env["PROXYAGENT_TOKEN"] = token
    return env


def _as(s: str) -> str:
    """Render a Python string as an AppleScript string literal."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _clean_err(stderr: str) -> str:
    """The helpers shell out to ``python3 -c`` snippets; on failure stderr is a
    full traceback. Surface just the final, meaningful line (the actual error)."""
    lines = [ln for ln in (stderr or "").strip().splitlines() if ln.strip()]
    if not lines:
        return "failed"
    last = lines[-1].strip()
    # Drop the "OSError: " / "PermissionError: " prefix for a cleaner message.
    return last.split(": ", 1)[1] if ": " in last and "Error" in last.split(": ", 1)[0] else last


def _tcc_hint(stderr: str, default_perm: str) -> str:
    """Turn an osascript failure into an actionable permission hint. macOS reports
    a TCC denial with distinct AppleEvent error codes, and the permission to grant
    differs (Accessibility for keystrokes vs Automation for app control)."""
    err = (stderr or "").strip()
    low = err.lower()
    perm = default_perm
    if "-1743" in err or "1002" in err or "not authorized to send apple events" in low or "not allowed assistive" in low:
        perm = "Automation" if "apple events" in low else "Accessibility"
    pane = {"Accessibility": "Accessibility", "Automation": "Automation",
            "Screen Recording": "Screen Recording"}.get(perm, perm)
    return (f"{err or 'permission denied'} — grant {pane} to whatever runs `herds host` "
            f"(System Settings → Privacy & Security → {pane}), then restart it")


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
        r = self._m.run(["osascript", "-e", script], timeout=timeout, inherit_home=True)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"ui action failed: {_tcc_hint(r.stderr, 'Accessibility')}")
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


class _Chrome:
    """Drive Google Chrome in the Mac's real session via AppleScript."""

    def __init__(self, mac: "Mac", cdp_port: Optional[int] = None):
        self._m = mac
        self.cdp_port = cdp_port  # set if launched with the DevTools Protocol

    def _osa(self, body: str) -> str:
        r = self._m.run(["osascript", "-e", f'tell application "Google Chrome" to {body}'], timeout=30, inherit_home=True)
        if not r.ok:
            from .client import HerdsError
            raise HerdsError(f"chrome: {_tcc_hint(r.stderr, 'Automation')}")
        return r.stdout.strip()

    def open(self, url: str) -> None:
        """Open a URL in the front window."""
        self._osa(f"open location {_as(url)}")

    def js(self, code: str) -> str:
        """Run JavaScript in the active tab and return the result. Needs Chrome's
        'View → Developer → Allow JavaScript from Apple Events'."""
        return self._osa(f"execute active tab of front window javascript {_as(code)}")

    def url(self) -> str:
        """URL of the active tab."""
        return self._osa("return URL of active tab of front window")

    def title(self) -> str:
        """Title of the active tab."""
        return self._osa("return title of active tab of front window")

    def tabs(self) -> list:
        """[(title, url)] of every tab in the front window."""
        titles = self._osa("return title of every tab of front window")
        urls = self._osa("return URL of every tab of front window")
        ts = [t.strip() for t in titles.split(",")]
        us = [u.strip() for u in urls.split(",")]
        return list(zip(ts, us))


def _matches_tag(m: dict, tag: str) -> bool:
    """A machine matches a tag by an explicit label or its chip (e.g. 'apple-m4-pro')."""
    t = tag.strip().lower()
    if t in (x.lower() for x in (m.get("tags") or [])):
        return True
    chip = ((m.get("info") or {}).get("chip") or "").lower().replace(" ", "-")
    return bool(chip) and t in chip


def _route_to_tag(c: HerdsClient, tag: str) -> str:
    """Pick the idlest ONLINE Mac matching a tag (smart routing by live CPU)."""
    cands = [m for m in c.list_machines() if m.get("status") == "online" and _matches_tag(m, tag)]
    if not cands:
        from .client import HerdsError
        raise HerdsError(f"no online Mac matches tag {tag!r} — tag one with `herds tag <id> {tag}`.")
    cands.sort(key=lambda m: m["live_cpu"] if m.get("live_cpu") is not None else 0.0)
    return cands[0]["machine_id"]


def mac(
    machine_id: str = "default",
    *,
    tag: Optional[str] = None,
    url: Optional[str] = None,
    token: Optional[str] = None,
    client: Optional[HerdsClient] = None,
) -> Mac:
    """Get a handle to one of your Macs. With no id, picks your online Mac.

    Pass ``tag`` to smart-route to the **idlest online Mac** with that label or chip::

        herds.mac(tag="xcode-26").run("xcodebuild …")   # least-loaded matching Mac

    Pass ``url`` + ``token`` to target a remote host directly (great for agents)::

        herds.mac(url="https://you.relay.herds.run", token="hx_…").run("uname")
    """
    if client is None and (url or token):
        client = HerdsClient(control_plane=url, api_key=token)
    c = client or default_client()
    if tag:
        machine_id = _route_to_tag(c, tag)
    return Mac(machine_id, client=c)


def machines(
    *,
    tag: Optional[str] = None,
    url: Optional[str] = None,
    token: Optional[str] = None,
    client: Optional[HerdsClient] = None,
) -> list[Mac]:
    """List your connected Macs as :class:`Mac` handles, optionally filtered by ``tag``."""
    if client is None and (url or token):
        client = HerdsClient(control_plane=url, api_key=token)
    c = client or default_client()
    rows = c.list_machines()
    if tag:
        rows = [m for m in rows if _matches_tag(m, tag)]
    return [Mac(m["machine_id"], client=c) for m in rows]


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

    def agent(
        self,
        goal: str,
        *,
        harness: str = "claude-code",
        proxy: Optional[str] = None,
        token: Optional[str] = None,
        secret: Optional[str] = None,
        command: Optional[str] = None,
        on_output=None,
        **kwargs,
    ) -> dict[str, "Result"]:
        """Run the **same** agent task on **every** online Mac, in parallel — keyless.

            herds.fleet().agent("upgrade deps and run tests", proxy=PROXY, secret="proxyagent")

        Returns ``{machine_name: Result}``. Pass ``on_output=fn(name, stream, text)``
        to receive live output tagged by machine (otherwise each run is captured).
        See :meth:`Mac.agent` for the keyless proxyagent setup.
        """
        import threading

        proxy, token = _agent_resolve(proxy, token, secret)
        macs = self.macs()
        if not macs:
            from .client import HerdsError
            raise HerdsError("No Macs are connected — run `herds host` on at least one Mac.")

        out: dict[str, "Result"] = {}
        errs: dict[str, Exception] = {}
        lock = threading.Lock()

        def _one(mc: "Mac") -> None:
            nm = mc.name
            try:
                if on_output is not None:
                    last = None
                    for s, t in mc.stream(_agent_argv(goal, harness, proxy, command),
                                          env={**_agent_env(proxy, token), **kwargs.get("env", {})}):
                        on_output(nm, s, t)
                    res = Result(exit_code=0, duration_ms=0, stdout="", stderr="")
                else:
                    res = mc.agent(goal, harness=harness, proxy=proxy, token=token,
                                   secret=secret, command=command, stream=False, **kwargs)
                with lock:
                    out[nm] = res
            except Exception as exc:  # noqa: BLE001 — collect per-Mac, don't kill the fleet
                with lock:
                    errs[nm] = exc

        threads = [threading.Thread(target=_one, args=(mc,), daemon=True) for mc in macs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for nm, exc in errs.items():
            out[nm] = exc  # surface the failure per machine rather than aborting the rest
        return out


def fleet(*, url: Optional[str] = None, token: Optional[str] = None,
          client: Optional[HerdsClient] = None) -> Fleet:
    """Your pool of Macs — ``herds.fleet().map("pytest {}", dirs)``."""
    return Fleet(url=url, token=token, client=client)
