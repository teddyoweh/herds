"""Run commands on this Mac with per-sandbox isolation, and stream output.

Isolation model (MVP, no VM):
  * Each sandbox gets its own directory tree: workspace/ tmp/ home/.
  * The environment is rebuilt from an allowlist; HOME/TMPDIR and the common
    toolchain caches (DerivedData, npm, pip, cargo...) are redirected *into*
    the sandbox so concurrent jobs never clobber each other's caches.
  * Each command runs in its own process *session* (start_new_session=True) so
    a timeout or cancel can kill the entire process tree, not just the parent.
  * When `sandbox-exec` is available we wrap the command in a Seatbelt profile
    that confines writes to the sandbox dir and optionally cuts the network.

Everything degrades gracefully: missing tools never hard-fail a run.
"""

from __future__ import annotations

import asyncio
import codecs
import os
import shutil
import signal
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .. import config
from . import images

# A callback the daemon supplies to ship a chunk of output upstream.
# Signature: (stream, text) where stream is "stdout" | "stderr".
OutputSink = Callable[[str, str], Awaitable[None]]


# Environment variables we always pass through from the daemon's own env.
_ENV_ALLOWLIST = (
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SSH_AUTH_SOCK",
    "HOMEBREW_PREFIX", "HOMEBREW_CELLAR", "HOMEBREW_REPOSITORY",
)

_DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


class Sandbox:
    """A persistent, isolated workspace on disk. The unit of isolation."""

    def __init__(self, sandbox_id: str, image: Optional[str] = None):
        self.id = sandbox_id
        self.image = image
        self.root = config.SANDBOXES_DIR / sandbox_id
        self.workspace = self.root / "workspace"
        self.tmp = self.root / "tmp"
        self.home = self.root / "home"
        self._procs: dict[str, asyncio.subprocess.Process] = {}

    def materialize(self) -> None:
        for d in (self.workspace, self.tmp, self.home):
            d.mkdir(parents=True, exist_ok=True)

    def destroy(self) -> None:
        # Kill anything still running, then remove the tree.
        for proc in list(self._procs.values()):
            _kill_tree(proc)
        shutil.rmtree(self.root, ignore_errors=True)


def _volume_path(name: str) -> Path:
    p = config.VOLUMES_DIR / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _build_env(
    sandbox: Sandbox,
    resolution: images.ImageResolution,
    extra_env: dict[str, str],
    inherit_home: bool = False,
) -> dict[str, str]:
    """Construct the environment for a run.

    Default: a clean, sandbox-scoped environment built from an allowlist with
    HOME/caches redirected into the sandbox (isolation).

    ``inherit_home=True``: run *as the user* — the full real environment, real
    HOME, real logins (so tools like ``claude``, ``git``, ``gh`` that rely on
    ``~`` credentials and the keychain just work). This is the BYO-Mac promise;
    it deliberately trades isolation for "my Mac, my tools."
    """
    if inherit_home:
        env = dict(os.environ)
        env["HERDS_SANDBOX_ID"] = sandbox.id
        env.update({k: v for k, v in resolution.env.items() if v})
        env["PATH"] = resolution.merge_path(os.environ.get("PATH", _DEFAULT_PATH))
        env.update(extra_env)
        return env

    env: dict[str, str] = {}
    for key in _ENV_ALLOWLIST:
        if key in os.environ:
            env[key] = os.environ[key]

    env["HOME"] = str(sandbox.home)
    env["TMPDIR"] = str(sandbox.tmp)
    env["USER"] = os.environ.get("USER", "herds")
    env["HERDS_SANDBOX_ID"] = sandbox.id

    # Redirect toolchain caches into the sandbox so jobs don't fight over them.
    env["DERIVED_DATA_PATH"] = str(sandbox.home / "DerivedData")
    env["npm_config_cache"] = str(sandbox.home / ".npm")
    env["PIP_CACHE_DIR"] = str(sandbox.home / ".pip")
    env["CARGO_HOME"] = str(sandbox.home / ".cargo")
    env["XDG_CACHE_HOME"] = str(sandbox.home / ".cache")
    env["XDG_CONFIG_HOME"] = str(sandbox.home / ".config")

    # Image overlay (e.g. DEVELOPER_DIR), then PATH, then caller overrides.
    env.update({k: v for k, v in resolution.env.items() if v})
    env["PATH"] = resolution.merge_path(os.environ.get("PATH", _DEFAULT_PATH))
    env.update(extra_env)
    return env


def _seatbelt_profile(sandbox: Sandbox, volume_paths: list[Path], network: bool) -> str:
    """A permissive-read / confined-write Seatbelt profile.

    Reads are open (toolchains live all over the disk); writes are fenced to the
    sandbox + mounted volumes + the system temp dirs. Network is a toggle.
    """
    writable = [str(sandbox.root), "/private/tmp", "/private/var/folders"]
    writable += [str(p) for p in volume_paths]
    write_rules = "\n".join(f'  (subpath "{p}")' for p in writable)
    net_rule = "(allow network*)" if network else "(deny network*)"
    return f"""(version 1)
(allow default)
(deny file-write*)
(allow file-write*
{write_rules}
  (regex #"^/dev/")
)
{net_rule}
"""


def _wrap_command(
    command: list[str] | str,
    sandbox: Sandbox,
    volume_paths: list[Path],
    network: bool,
) -> list[str]:
    """Return the argv to exec, wrapped in sandbox-exec when available."""
    if isinstance(command, str):
        inner = ["/bin/zsh", "-lc", command]
    else:
        inner = list(command)

    if shutil.which("sandbox-exec"):
        profile = _seatbelt_profile(sandbox, volume_paths, network)
        return ["sandbox-exec", "-p", profile, *inner]
    return inner


def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill the whole process group started with start_new_session=True."""
    if proc.returncode is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            proc.terminate()
        except ProcessLookupError:
            pass


async def _pump(stream: asyncio.StreamReader, name: str, sink: OutputSink) -> None:
    """Drain a subprocess pipe into ``sink`` chunk by chunk.

    Read fixed-size chunks, not readline(): a single line longer than the
    StreamReader limit (e.g. base64 of a screenshot — one ~1.3MB line) makes
    readline() raise LimitOverrunError, which would crash the pump and hang the
    SDK waiting for output that never arrives. An incremental UTF-8 decoder keeps
    multibyte chars intact across chunk boundaries.
    """
    dec = codecs.getincrementaldecoder("utf-8")("replace")
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            tail = dec.decode(b"", final=True)
            if tail:
                await sink(name, tail)
            break
        text = dec.decode(chunk)
        if text:
            await sink(name, text)


class ResidentSession:
    """A long-lived process the backend feeds many stdin turns into.

    Unlike :meth:`Executor.run` (one-shot: launch, drain, exit), a session stays
    resident: its stdin is an open pipe, stdout/stderr pump continuously into the
    sink for the whole lifetime, and it only ends when its stdin is closed (EOF),
    the process exits on its own, or it is cancelled.
    """

    def __init__(
        self,
        request_id: str,
        proc: asyncio.subprocess.Process,
        sandbox: "Sandbox",
        started: float,
    ) -> None:
        self.request_id = request_id
        self.proc = proc
        self.sandbox = sandbox
        self.started = started
        self._pumps: Optional[asyncio.Future] = None
        self._stdin_closed = False

    async def send(self, data: str) -> None:
        """Write a chunk to the process's stdin and flush it."""
        stdin = self.proc.stdin
        if stdin is None or self._stdin_closed:
            return
        try:
            stdin.write(data.encode() if isinstance(data, str) else bytes(data))
            await stdin.drain()
        except (BrokenPipeError, ConnectionResetError, RuntimeError, OSError):
            # The child closed its stdin or died — nothing more to feed.
            pass

    async def close_stdin(self) -> None:
        """Send EOF on stdin so a line-reader loop can finish cleanly."""
        stdin = self.proc.stdin
        if stdin is None or self._stdin_closed:
            return
        self._stdin_closed = True
        try:
            stdin.write_eof()
        except (OSError, RuntimeError):
            pass

    def kill(self) -> None:
        _kill_tree(self.proc)

    async def wait(self) -> int:
        """Block until the resident process exits; return its exit code."""
        await self.proc.wait()
        if self._pumps is not None:
            await self._pumps
        return self.proc.returncode if self.proc.returncode is not None else -1


class Executor:
    """Owns the set of live sandboxes and runs commands inside them."""

    def __init__(self) -> None:
        config.ensure_dirs()
        self.sandboxes: dict[str, Sandbox] = {}
        # An implicit, shared sandbox for one-shot `mac.run()` calls.
        self._ephemeral_counter = 0
        # request_ids explicitly stopped — keep-alive must not respawn them.
        self._canceled: set[str] = set()
        # Resident stdin-fed sessions, keyed by request_id (== session id).
        self._sessions: dict[str, ResidentSession] = {}

    # -- sandbox lifecycle -------------------------------------------------- #

    def create_sandbox(self, sandbox_id: str, image: Optional[str] = None) -> Sandbox:
        sb = Sandbox(sandbox_id, image=image)
        sb.materialize()
        self.sandboxes[sandbox_id] = sb
        return sb

    def get_or_create(self, sandbox_id: Optional[str], image: Optional[str]) -> Sandbox:
        if sandbox_id and sandbox_id in self.sandboxes:
            return self.sandboxes[sandbox_id]
        sid = sandbox_id or f"sbx_eph_{uuid.uuid4().hex[:8]}"
        return self.create_sandbox(sid, image=image)

    def terminate_sandbox(self, sandbox_id: str) -> bool:
        sb = self.sandboxes.pop(sandbox_id, None)
        if sb is None:
            return False
        sb.destroy()
        return True

    # -- execution ---------------------------------------------------------- #

    async def _prepare_launch(
        self,
        request_id: str,
        command: list[str] | str,
        *,
        sink: OutputSink,
        image: Optional[str],
        sandbox_id: Optional[str],
        volumes: Optional[dict[str, str]],
        workdir: Optional[str],
        env: Optional[dict[str, str]],
        network: bool,
        inherit_home: bool,
    ) -> tuple[Sandbox, list[str], str, dict[str, str]]:
        """Resolve the sandbox, image, volumes and environment for a launch and
        return ``(sandbox, argv, cwd, full_env)``. Shared by one-shot ``run`` and
        resident ``start_session`` so both isolate identically."""
        sandbox = self.get_or_create(sandbox_id, image)
        resolution = images.resolve(image or sandbox.image)

        # Surface image resolution notes as stderr so users see what got pinned.
        for note in resolution.notes:
            await sink("stderr", f"herds: {note}\n")

        # Mount volumes. Without a container there is no real "/workspace", so a
        # volume is symlinked under the sandbox working dir at the mount's
        # basename, AND exposed as an absolute path via $HERDS_VOLUME_<NAME>.
        # Commands reach it as a relative path or through the env var -- both
        # unambiguous on a bare Mac.
        volume_paths: list[Path] = []
        volume_env: dict[str, str] = {}
        for mount, vol_name in (volumes or {}).items():
            real = _volume_path(vol_name)
            volume_paths.append(real)
            link = sandbox.workspace / mount.strip("/")
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                pass
            else:
                try:
                    link.symlink_to(real)
                except OSError:
                    pass
            env_key = "HERDS_VOLUME_" + "".join(
                c.upper() if c.isalnum() else "_" for c in vol_name
            )
            volume_env[env_key] = str(real)

        full_env = _build_env(sandbox, resolution, {**volume_env, **(env or {})}, inherit_home)
        cwd = workdir or str(sandbox.workspace)
        # inherit_home means "run as me" — no Seatbelt write-fence (full host access).
        if inherit_home:
            argv = ["/bin/zsh", "-lc", command] if isinstance(command, str) else list(command)
        else:
            argv = _wrap_command(command, sandbox, volume_paths, network)
        return sandbox, argv, cwd, full_env

    async def start_session(
        self,
        request_id: str,
        command: list[str] | str,
        *,
        sink: OutputSink,
        image: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        volumes: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        network: bool = True,
        inherit_home: bool = False,
    ) -> ResidentSession:
        """Launch a RESIDENT process with an open stdin pipe and return a handle.

        The process keeps running after its first output (unlike :meth:`run`);
        stdout/stderr pump into ``sink`` for its whole lifetime. Feed it via
        :meth:`session_send` and end it via :meth:`session_send` with ``eof=True``
        or :meth:`cancel`. Await completion with :meth:`session_wait`.
        """
        started = time.monotonic()
        sandbox, argv, cwd, full_env = await self._prepare_launch(
            request_id, command, sink=sink, image=image, sandbox_id=sandbox_id,
            volumes=volumes, workdir=workdir, env=env, network=network,
            inherit_home=inherit_home,
        )
        self._canceled.discard(request_id)
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env,
                start_new_session=True,  # own process group -> killable tree
                limit=4 * 1024 * 1024,
            )
        except (OSError, ValueError) as exc:
            await sink("stderr", f"herds: failed to launch session: {exc}\n")
            raise
        sandbox._procs[request_id] = proc
        session = ResidentSession(request_id, proc, sandbox, started)
        session._pumps = asyncio.gather(
            _pump(proc.stdout, "stdout", sink), _pump(proc.stderr, "stderr", sink)
        )
        self._sessions[request_id] = session
        return session

    async def session_send(self, request_id: str, data: str = "", *, eof: bool = False) -> bool:
        """Deliver a stdin chunk (and/or EOF) to a resident session. Returns
        False if no such live session exists on this machine."""
        session = self._sessions.get(request_id)
        if session is None:
            return False
        if data:
            await session.send(data)
        if eof:
            await session.close_stdin()
        return True

    async def session_wait(self, request_id: str) -> tuple[int, int]:
        """Block until the resident session exits; return ``(exit_code, ms)`` and
        drop it from the live set. Safe to call once per session."""
        session = self._sessions.get(request_id)
        if session is None:
            return -1, 0
        try:
            code = await session.wait()
        finally:
            self._sessions.pop(request_id, None)
            session.sandbox._procs.pop(request_id, None)
            self._canceled.discard(request_id)
        return code, int((time.monotonic() - session.started) * 1000)

    async def run(
        self,
        request_id: str,
        command: list[str] | str,
        *,
        sink: OutputSink,
        image: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        volumes: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        network: bool = True,
        inherit_home: bool = False,
        keep_alive: bool = False,
    ) -> tuple[int, int]:
        """Run a command, streaming output via ``sink``. Returns (exit_code, ms).

        ``keep_alive`` turns the command into a supervised service: when it exits
        (crash or clean), it is respawned (capped backoff) until explicitly
        stopped via :meth:`cancel`. The sandbox stays "live" across restarts.
        """
        started = time.monotonic()
        sandbox, argv, cwd, full_env = await self._prepare_launch(
            request_id, command, sink=sink, image=image, sandbox_id=sandbox_id,
            volumes=volumes, workdir=workdir, env=env, network=network,
            inherit_home=inherit_home,
        )

        code = -1
        attempt = 0
        while True:
            attempt += 1
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=full_env,
                    start_new_session=True,  # own process group -> killable tree
                    limit=4 * 1024 * 1024,   # roomy buffer so big bursts don't stall flow control
                )
            except (OSError, ValueError) as exc:
                await sink("stderr", f"herds: failed to launch: {exc}\n")
                self._canceled.discard(request_id)
                return 127, int((time.monotonic() - started) * 1000)

            sandbox._procs[request_id] = proc
            pumps = asyncio.gather(
                _pump(proc.stdout, "stdout", sink), _pump(proc.stderr, "stderr", sink)
            )
            try:
                if timeout:
                    await asyncio.wait_for(proc.wait(), timeout=timeout)
                else:
                    await proc.wait()
            except asyncio.TimeoutError:
                _kill_tree(proc)
                await sink("stderr", f"herds: timed out after {timeout}s\n")
            finally:
                await pumps
                sandbox._procs.pop(request_id, None)

            code = proc.returncode if proc.returncode is not None else -1

            if not keep_alive or request_id in self._canceled:
                break
            # Supervised restart with capped backoff.
            await sink("stderr", f"herds: process exited ({code}); restarting (#{attempt})\n")
            await asyncio.sleep(min(5.0, 0.5 * attempt))
            if request_id in self._canceled:
                break

        self._canceled.discard(request_id)
        return code, int((time.monotonic() - started) * 1000)

    def cancel(self, request_id: str) -> bool:
        # Mark first so a keep-alive supervisor won't respawn after the kill.
        self._canceled.add(request_id)
        for sb in self.sandboxes.values():
            proc = sb._procs.get(request_id)
            if proc:
                _kill_tree(proc)
                return True
        return False
