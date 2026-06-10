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
        env["DARWIN_SANDBOX_ID"] = sandbox.id
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
    env["USER"] = os.environ.get("USER", "darwin")
    env["DARWIN_SANDBOX_ID"] = sandbox.id

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


class Executor:
    """Owns the set of live sandboxes and runs commands inside them."""

    def __init__(self) -> None:
        config.ensure_dirs()
        self.sandboxes: dict[str, Sandbox] = {}
        # An implicit, shared sandbox for one-shot `mac.run()` calls.
        self._ephemeral_counter = 0
        # request_ids explicitly stopped — keep-alive must not respawn them.
        self._canceled: set[str] = set()

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
        sandbox = self.get_or_create(sandbox_id, image)
        resolution = images.resolve(image or sandbox.image)

        # Surface image resolution notes as stderr so users see what got pinned.
        for note in resolution.notes:
            await sink("stderr", f"darwin: {note}\n")

        # Mount volumes. Without a container there is no real "/workspace", so a
        # volume is symlinked under the sandbox working dir at the mount's
        # basename, AND exposed as an absolute path via $DARWIN_VOLUME_<NAME>.
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
            env_key = "DARWIN_VOLUME_" + "".join(
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

        async def pump(stream: asyncio.StreamReader, name: str) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                await sink(name, line.decode(errors="replace"))

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
                )
            except (OSError, ValueError) as exc:
                await sink("stderr", f"darwin: failed to launch: {exc}\n")
                self._canceled.discard(request_id)
                return 127, int((time.monotonic() - started) * 1000)

            sandbox._procs[request_id] = proc
            pumps = asyncio.gather(pump(proc.stdout, "stdout"), pump(proc.stderr, "stderr"))
            try:
                if timeout:
                    await asyncio.wait_for(proc.wait(), timeout=timeout)
                else:
                    await proc.wait()
            except asyncio.TimeoutError:
                _kill_tree(proc)
                await sink("stderr", f"darwin: timed out after {timeout}s\n")
            finally:
                await pumps
                sandbox._procs.pop(request_id, None)

            code = proc.returncode if proc.returncode is not None else -1

            if not keep_alive or request_id in self._canceled:
                break
            # Supervised restart with capped backoff.
            await sink("stderr", f"darwin: process exited ({code}); restarting (#{attempt})\n")
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
