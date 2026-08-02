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
import ctypes
import os
import shutil
import signal
import tarfile
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from .. import config
from . import images

# A callback the daemon supplies to ship a chunk of output upstream.
# Signature: (stream, text) where stream is "stdout" | "stderr".
OutputSink = Callable[[str, str], Awaitable[None]]

# Exit code returned when work is turned away at the admission gate. 75 is
# EX_TEMPFAIL — "try again later", which is exactly what a full Mac is saying.
EX_ADMISSION_REJECTED = 75


class AdmissionRejected(Exception):
    """The per-Mac concurrency cap *and* its waiting queue are both full."""


class _Admission:
    """A counting gate with a bounded FIFO queue.

    Up to ``capacity`` slots run concurrently. When full, callers wait in a queue
    of at most ``queue_max`` — beyond that, :meth:`acquire` raises
    :class:`AdmissionRejected` rather than letting work pile up without bound. An
    optional cpu high-water adds backpressure: when the machine is already hot we
    treat it as full even below the count cap. This is the daemon-side analog of
    Modal's scheduler refusing to overcommit a worker.
    """

    def __init__(
        self,
        capacity: int,
        queue_max: int,
        cpu_high_water: float = 0.0,
        cpu_sampler: Optional[Callable[[], float]] = None,
    ) -> None:
        self.capacity = max(1, int(capacity))
        self.queue_max = max(0, int(queue_max))
        self.cpu_high_water = float(cpu_high_water)
        self._cpu_sampler = cpu_sampler
        self.active = 0
        self._waiters: "deque[asyncio.Future]" = deque()

    def _hot(self) -> bool:
        if self.cpu_high_water <= 0 or self._cpu_sampler is None:
            return False
        try:
            return self._cpu_sampler() >= self.cpu_high_water
        except Exception:  # noqa: BLE001 — a broken sampler must never block work
            return False

    async def acquire(self) -> None:
        # A free slot only counts if the machine isn't already over its cpu line.
        if self.active < self.capacity and not self._hot():
            self.active += 1
            return
        if len(self._waiters) >= self.queue_max:
            raise AdmissionRejected(
                f"at capacity ({self.active}/{self.capacity} live, "
                f"{len(self._waiters)}/{self.queue_max} queued)"
            )
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._waiters.append(fut)
        try:
            await fut  # released() hands its slot straight to us; active unchanged
        except asyncio.CancelledError:
            # We were cancelled while queued — leave the queue cleanly. If we had
            # already been handed a slot, pass it on so it isn't leaked.
            try:
                self._waiters.remove(fut)
            except ValueError:
                if fut.done() and not fut.cancelled():
                    self.release()
            raise

    def release(self) -> None:
        # Hand the freed slot to the next waiter (active stays the same) or, if
        # nobody is waiting, actually give it back to the pool.
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.done():
                fut.set_result(None)
                return
        self.active = max(0, self.active - 1)

    def stats(self) -> dict:
        return {
            "active": self.active,
            "capacity": self.capacity,
            "queued": len(self._waiters),
            "queue_max": self.queue_max,
        }


def _live_cpu_sample() -> float:
    """This Mac's current cpu%, the same signal the control plane uses to pick the
    idlest machine. Best-effort: any failure reads as 0 (never adds backpressure)."""
    try:
        from . import metrics
        return float(metrics.sample().get("cpu", 0.0))
    except Exception:  # noqa: BLE001
        return 0.0


def _newest_mtime(path: Path) -> float:
    """The most recent mtime anywhere in a tree — our 'last touched' signal for
    GC. Cheap for a sandbox (small trees); errors on individual files are
    ignored so a transient stat failure never wedges the reaper."""
    newest = 0.0
    try:
        newest = path.stat().st_mtime
    except OSError:
        return newest
    for p in path.rglob("*"):
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    return newest


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


# --------------------------------------------------------------------------- #
# Snapshot -> base images (Modal snapshot_filesystem / Image.from_id analog)
# --------------------------------------------------------------------------- #

# A base image is just a local tarball of a sandbox's workspace+home, stored
# under the herds home. Cheap to make, cheap to restore -- no VM, no registry.
_SNAPSHOT_DIRS = ("workspace", "home")


def _base_tar_path(base: str) -> Path:
    """Where a named base image lives on disk. The name is sanitized so it can't
    escape IMAGES_DIR; a plain ``"myenv"`` maps to ``.../images/myenv.tar``."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in base).strip("._") or "base"
    return (config.IMAGES_DIR / f"{safe}.tar").resolve()


def _base_clone_path(base: str) -> Path:
    """Where a clone-backed base image lives (a directory, not a tarball)."""
    return _base_tar_path(base).with_suffix(".clone")


def _clonefile(src: Path, dst: Path) -> bool:
    """APFS copy-on-write clone of a whole tree. True if it worked.

    ``clonefile(2)`` shares blocks instead of copying them, so this is ~constant
    time and consumes no extra space until something diverges — measured 64x
    faster than a byte copy on a 200MB tree, and the gap widens with size.
    That's what makes snapshotting a *real* home directory viable at all;
    tarring one never was. Falls back to tar when the volume isn't APFS.
    """
    if not hasattr(_clonefile, "_fn"):
        try:
            libc = ctypes.CDLL("/usr/lib/libSystem.dylib", use_errno=True)
            libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            libc.clonefile.restype = ctypes.c_int
            _clonefile._fn = libc.clonefile
        except (OSError, AttributeError):
            _clonefile._fn = None
    fn = _clonefile._fn
    if fn is None:
        return False
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # clonefile requires dst to not exist; it recreates the hierarchy itself.
    return fn(str(src).encode(), str(dst).encode(), 0) == 0


def _tree_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def snapshot_to_base(sandbox_root: Path, base: str) -> dict:
    """Snapshot a sandbox's ``workspace/`` and ``home/`` into the named base image.

    Prefers an APFS clone (instant, block-shared); falls back to a tarball on
    non-APFS volumes. Returns ``{base, image_id, size_bytes, path, mode}``.
    Idempotent by name: writing the same base again replaces it."""
    config.ensure_dirs()

    clone_root = _base_clone_path(base)
    staged = clone_root.with_suffix(".clone.tmp")
    shutil.rmtree(staged, ignore_errors=True)
    cloned = []
    for sub in _SNAPSHOT_DIRS:
        d = sandbox_root / sub
        if d.is_dir() and _clonefile(d, staged / sub):
            cloned.append(sub)
    if cloned:
        shutil.rmtree(clone_root, ignore_errors=True)
        staged.replace(clone_root)          # atomic swap; no half-written base
        _base_tar_path(base).unlink(missing_ok=True)   # drop any stale tar twin
        return {"base": base, "image_id": clone_root.stem,
                "size_bytes": _tree_size(clone_root), "path": str(clone_root),
                "mode": "clone"}

    shutil.rmtree(staged, ignore_errors=True)
    tar_path = _base_tar_path(base)
    tmp = tar_path.with_suffix(".tar.tmp")
    with tarfile.open(tmp, "w") as tf:
        for sub in _SNAPSHOT_DIRS:
            d = sandbox_root / sub
            if d.is_dir():
                tf.add(d, arcname=sub)
    tmp.replace(tar_path)  # atomic swap so a reader never sees a half tar
    size = tar_path.stat().st_size
    return {"base": base, "image_id": tar_path.stem, "size_bytes": size,
            "path": str(tar_path), "mode": "tar"}


def restore_from_base(sandbox_root: Path, base: str) -> bool:
    """Extract a named base image into a sandbox root, recreating workspace+home.

    Returns True if the base existed and was restored, False if there is no such
    base (the sandbox is then just a fresh empty tree). Path traversal in the tar
    is refused member by member."""
    # Clone-backed base: restore by cloning back, which is as cheap as taking it.
    clone_root = _base_clone_path(base)
    if clone_root.is_dir():
        ok = False
        for sub in _SNAPSHOT_DIRS:
            src = clone_root / sub
            if src.is_dir() and _clonefile(src, sandbox_root / sub):
                ok = True
        if ok:
            return True

    tar_path = _base_tar_path(base)
    if not tar_path.exists():
        return False
    root = sandbox_root.resolve()
    with tarfile.open(tar_path, "r:*") as tf:
        for m in tf.getmembers():
            if not (m.isfile() or m.isdir()):
                continue  # skip symlinks/devices/hardlinks
            mp = (root / m.name).resolve()
            if root != mp and root not in mp.parents:
                continue  # refuse traversal outside the sandbox root
            tf.extract(m, path=root)
    return True


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
    command: Union[list[str], str],
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


async def _pump(
    stream: asyncio.StreamReader,
    name: str,
    sink: OutputSink,
    on_activity: Optional[Callable[[], None]] = None,
) -> None:
    """Drain a subprocess pipe into ``sink`` chunk by chunk.

    Read fixed-size chunks, not readline(): a single line longer than the
    StreamReader limit (e.g. base64 of a screenshot — one ~1.3MB line) makes
    readline() raise LimitOverrunError, which would crash the pump and hang the
    SDK waiting for output that never arrives. An incremental UTF-8 decoder keeps
    multibyte chars intact across chunk boundaries.

    ``on_activity`` (resident sessions) is called on every non-empty chunk so a
    session that is actively PRODUCING output — including a driver heartbeating
    while it waits for a user answer — counts as alive and the idle reaper won't
    kill it mid-turn. The reaper still reclaims genuinely-silent sessions.
    """
    dec = codecs.getincrementaldecoder("utf-8")("replace")
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            tail = dec.decode(b"", final=True)
            if tail:
                await sink(name, tail)
            break
        if on_activity is not None:
            try:
                on_activity()
            except Exception:  # noqa: BLE001 — activity tracking must never break the pump
                pass
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
        # Monotonic clock of the last input turn — drives idle-session reaping.
        self.last_active = started
        self._pumps: Optional[asyncio.Future] = None
        self._stdin_closed = False

    def touch(self) -> None:
        """Mark the session active NOW so the idle reaper spares it.

        Bumped by stdin ``send`` (a turn), by stdout activity (the process is
        producing output), and by an explicit ``/v1/sessions/{id}/keepalive``
        from the backend — e.g. while a driver is parked awaiting a user answer,
        which is mid-turn work with no stdin/stdout to prove it's alive."""
        self.last_active = time.monotonic()

    async def send(self, data: str) -> None:
        """Write a chunk to the process's stdin and flush it."""
        stdin = self.proc.stdin
        if stdin is None or self._stdin_closed:
            return
        self.last_active = time.monotonic()
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

    def __init__(
        self,
        *,
        max_live: Optional[int] = None,
        queue_max: Optional[int] = None,
        cpu_high_water: Optional[float] = None,
        cpu_sampler: Optional[Callable[[], float]] = None,
    ) -> None:
        config.ensure_dirs()
        self.sandboxes: dict[str, Sandbox] = {}
        # An implicit, shared sandbox for one-shot `mac.run()` calls.
        self._ephemeral_counter = 0
        # request_ids explicitly stopped — keep-alive must not respawn them.
        self._canceled: set[str] = set()
        # Resident stdin-fed sessions, keyed by request_id (== session id).
        self._sessions: dict[str, ResidentSession] = {}
        # Fleet admission gate: bound concurrent live work on this Mac.
        self._admission = _Admission(
            capacity=config.MAX_LIVE_SANDBOXES if max_live is None else max_live,
            queue_max=config.ADMISSION_QUEUE_MAX if queue_max is None else queue_max,
            cpu_high_water=(
                config.ADMISSION_CPU_HIGH_WATER if cpu_high_water is None else cpu_high_water
            ),
            cpu_sampler=cpu_sampler if cpu_sampler is not None else _live_cpu_sample,
        )
        self._reaper: Optional[asyncio.Task] = None
        # request_ids currently holding an admission slot — so each is freed once.
        self._admitted: set[str] = set()

    def admission_stats(self) -> dict:
        """Live view of the admission gate (active/capacity/queued)."""
        return self._admission.stats()

    def _release_admission(self, request_id: str) -> None:
        """Return this request's admission slot exactly once (idempotent)."""
        if request_id in self._admitted:
            self._admitted.discard(request_id)
            self._admission.release()

    # -- sandbox lifecycle -------------------------------------------------- #

    def create_sandbox(
        self, sandbox_id: str, image: Optional[str] = None, base: Optional[str] = None
    ) -> Sandbox:
        sb = Sandbox(sandbox_id, image=image)
        sb.materialize()
        # A fresh sandbox seeded from a snapshot base restores that base's
        # workspace+home on top of the empty tree (best-effort: a missing base is
        # a no-op, so the sandbox is simply empty).
        if base:
            restore_from_base(sb.root, base)
        self.sandboxes[sandbox_id] = sb
        return sb

    def get_or_create(
        self, sandbox_id: Optional[str], image: Optional[str], base: Optional[str] = None
    ) -> Sandbox:
        if sandbox_id and sandbox_id in self.sandboxes:
            return self.sandboxes[sandbox_id]
        sid = sandbox_id or f"sbx_eph_{uuid.uuid4().hex[:8]}"
        return self.create_sandbox(sid, image=image, base=base)

    def terminate_sandbox(self, sandbox_id: str) -> bool:
        sb = self.sandboxes.pop(sandbox_id, None)
        if sb is None:
            return False
        sb.destroy()
        return True

    def snapshot(self, sandbox_id: str, base: str) -> dict:
        """Tar a sandbox's workspace+home into a named base image and return its
        facts (``base``/``image_id``/``size_bytes``/``path``). Works whether or
        not the sandbox is tracked in-memory, as long as its dir tree exists."""
        sb = self.sandboxes.get(sandbox_id)
        root = sb.root if sb is not None else (config.SANDBOXES_DIR / sandbox_id)
        if not root.exists():
            raise FileNotFoundError(f"no such sandbox on disk: {sandbox_id}")
        return snapshot_to_base(root, base)

    # -- execution ---------------------------------------------------------- #

    async def _prepare_launch(
        self,
        request_id: str,
        command: Union[list[str], str],
        *,
        sink: OutputSink,
        image: Optional[str],
        sandbox_id: Optional[str],
        volumes: Optional[dict[str, str]],
        workdir: Optional[str],
        env: Optional[dict[str, str]],
        network: bool,
        inherit_home: bool,
        setup_commands: Optional[list[str]] = None,
        base: Optional[str] = None,
    ) -> tuple[Sandbox, list[str], str, dict[str, str]]:
        """Resolve the sandbox, image, volumes and environment for a launch and
        return ``(sandbox, argv, cwd, full_env)``. Shared by one-shot ``run`` and
        resident ``start_session`` so both isolate identically.

        A new sandbox named with ``base`` first restores that snapshot image; any
        ``setup_commands`` (image provisioning) then run once, cached by content
        hash so a repeat is a cheap no-op."""
        sandbox = self.get_or_create(sandbox_id, image, base=base)
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
        # Run image provisioning (node/claude-code/python deps/chromium…) once,
        # before the user's command, cached by content hash.
        if setup_commands:
            await self._provision(
                sandbox, list(setup_commands), sink=sink, full_env=full_env,
                volume_paths=volume_paths, network=network, inherit_home=inherit_home,
            )
        # inherit_home means "run as me" — no Seatbelt write-fence (full host access).
        if inherit_home:
            argv = ["/bin/zsh", "-lc", command] if isinstance(command, str) else list(command)
        else:
            argv = _wrap_command(command, sandbox, volume_paths, network)
        return sandbox, argv, cwd, full_env

    async def _provision(
        self,
        sandbox: Sandbox,
        setup_commands: list[str],
        *,
        sink: OutputSink,
        full_env: dict[str, str],
        volume_paths: list[Path],
        network: bool,
        inherit_home: bool,
    ) -> bool:
        """Run a sandbox's image ``setup_commands`` once, idempotently.

        A content hash of the command list keys a marker on disk under the
        sandbox; if the marker exists the whole step is skipped (cheap no-op). The
        marker is written only when *every* command succeeds, so a failed
        provisioning re-runs next time instead of silently caching a broken env.
        Progress and a clear note for a missing tool (exit 127) stream via
        ``sink``. Returns True if the environment is provisioned (cached or fresh).
        """
        h = images.provision_hash(setup_commands)
        marker_dir = sandbox.root / ".herds_provision"
        marker = marker_dir / f"{h}.done"
        if marker.exists():
            await sink("stderr", f"herds: provisioning cached ({h}); "
                                 f"skipping {len(setup_commands)} step(s)\n")
            return True

        cwd = str(sandbox.workspace)
        n = len(setup_commands)
        for i, cmd in enumerate(setup_commands, 1):
            await sink("stderr", f"herds: provisioning ({i}/{n}): {cmd}\n")
            if inherit_home:
                argv = ["/bin/zsh", "-lc", cmd]
            else:
                argv = _wrap_command(cmd, sandbox, volume_paths, network)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=full_env,
                    start_new_session=True,
                    limit=4 * 1024 * 1024,
                )
            except (OSError, ValueError) as exc:
                await sink("stderr", f"herds: provisioning could not launch step {i}: {exc}\n")
                return False
            pumps = asyncio.gather(
                _pump(proc.stdout, "stdout", sink), _pump(proc.stderr, "stderr", sink)
            )
            await proc.wait()
            await pumps
            code = proc.returncode if proc.returncode is not None else -1
            if code != 0:
                if code == 127:
                    await sink("stderr", f"herds: provisioning step {i} needs a tool that "
                                         f"isn't installed (exit 127): {cmd!r} — install it or "
                                         f"add it to the image; not caching\n")
                else:
                    await sink("stderr", f"herds: provisioning step {i} failed (exit {code}); "
                                         f"not caching so it retries next run\n")
                return False

        marker_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"provisioned {n} step(s)\n")
        await sink("stderr", f"herds: provisioning complete ({h}); cached\n")
        return True

    async def start_session(
        self,
        request_id: str,
        command: Union[list[str], str],
        *,
        sink: OutputSink,
        image: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        volumes: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        network: bool = True,
        inherit_home: bool = False,
        setup_commands: Optional[list[str]] = None,
        base: Optional[str] = None,
    ) -> ResidentSession:
        """Launch a RESIDENT process with an open stdin pipe and return a handle.

        The process keeps running after its first output (unlike :meth:`run`);
        stdout/stderr pump into ``sink`` for its whole lifetime. Feed it via
        :meth:`session_send` and end it via :meth:`session_send` with ``eof=True``
        or :meth:`cancel`. Await completion with :meth:`session_wait`.
        """
        started = time.monotonic()
        # Admission first: a resident session holds a live slot for its lifetime.
        try:
            await self._admission.acquire()
        except AdmissionRejected as exc:
            await sink("stderr", f"herds: admission cap reached ({exc}); session rejected\n")
            raise
        self._admitted.add(request_id)
        try:
            sandbox, argv, cwd, full_env = await self._prepare_launch(
                request_id, command, sink=sink, image=image, sandbox_id=sandbox_id,
                volumes=volumes, workdir=workdir, env=env, network=network,
                inherit_home=inherit_home, setup_commands=setup_commands, base=base,
            )
            self._canceled.discard(request_id)
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
        except BaseException as exc:  # launch/prepare failed — free the slot we took
            self._release_admission(request_id)
            if isinstance(exc, (OSError, ValueError)):
                await sink("stderr", f"herds: failed to launch session: {exc}\n")
            raise
        sandbox._procs[request_id] = proc
        session = ResidentSession(request_id, proc, sandbox, started)
        # stdout activity keeps the session non-idle so the reaper never kills a
        # session that's actively producing output (or heartbeating during an
        # answer-wait) mid-turn. stderr is diagnostics — don't count it.
        session._pumps = asyncio.gather(
            _pump(proc.stdout, "stdout", sink, on_activity=session.touch),
            _pump(proc.stderr, "stderr", sink),
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

    def session_keepalive(self, request_id: str) -> bool:
        """Mark a resident session active so the idle reaper spares it. Returns
        False if no such live session exists on this machine. Used by the backend
        to hold a session alive during work with no stdin/stdout — e.g. a driver
        parked awaiting a user's AskUserQuestion answer."""
        session = self._sessions.get(request_id)
        if session is None:
            return False
        session.touch()
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
            self._release_admission(request_id)
        return code, int((time.monotonic() - session.started) * 1000)

    async def run(
        self,
        request_id: str,
        command: Union[list[str], str],
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
        setup_commands: Optional[list[str]] = None,
        base: Optional[str] = None,
    ) -> tuple[int, int]:
        """Run a command, streaming output via ``sink``. Returns (exit_code, ms).

        ``keep_alive`` turns the command into a supervised service: when it exits
        (crash or clean), it is respawned (capped backoff) until explicitly
        stopped via :meth:`cancel`. The sandbox stays "live" across restarts.
        """
        started = time.monotonic()
        # Admission first: hold a live slot for the whole run (incl. keep-alive
        # restarts). If the Mac is full past its queue, turn the work away cleanly
        # with EX_TEMPFAIL rather than raising into the hot path.
        try:
            await self._admission.acquire()
        except AdmissionRejected as exc:
            await sink("stderr", f"herds: admission cap reached ({exc}); rejected\n")
            return EX_ADMISSION_REJECTED, int((time.monotonic() - started) * 1000)
        self._admitted.add(request_id)
        try:
            sandbox, argv, cwd, full_env = await self._prepare_launch(
                request_id, command, sink=sink, image=image, sandbox_id=sandbox_id,
                volumes=volumes, workdir=workdir, env=env, network=network,
                inherit_home=inherit_home, setup_commands=setup_commands, base=base,
            )
        except BaseException:
            self._release_admission(request_id)
            raise

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
        self._release_admission(request_id)
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

    # -- fleet reaping: idle sessions + stale sandbox trees ----------------- #

    def reap_idle_sessions(self, idle_timeout_ms: Optional[int] = None) -> list[str]:
        """Kill resident sessions with no input for longer than the idle timeout.

        This is Modal's warm-idle analog: a session that's been sitting doing
        nothing is torn down to give its admission slot back. Killing the process
        lets the awaiting :meth:`session_wait` finish normally, which cleans up
        state and releases admission. Returns the reaped request_ids."""
        timeout = (
            config.SESSION_IDLE_TIMEOUT_MS if idle_timeout_ms is None else idle_timeout_ms
        ) / 1000.0
        now = time.monotonic()
        reaped: list[str] = []
        for request_id, session in list(self._sessions.items()):
            if now - session.last_active >= timeout:
                session.kill()
                reaped.append(request_id)
        return reaped

    def gc_sandbox_dirs(self, ttl_ms: Optional[int] = None) -> list[str]:
        """Remove sandbox trees on disk untouched for longer than the TTL.

        Nothing else cleans these up, so a long-lived daemon would slowly fill the
        disk with dead ephemeral sandboxes. A tree is GC-able only when it has no
        live process running in it (an in-memory sandbox mid-run is always kept),
        and its newest mtime is older than the TTL. Returns the removed ids."""
        ttl = (config.SANDBOX_TTL_MS if ttl_ms is None else ttl_ms) / 1000.0
        now = time.time()
        removed: list[str] = []
        base = config.SANDBOXES_DIR
        if not base.exists():
            return removed
        for d in base.iterdir():
            if not d.is_dir():
                continue
            sid = d.name
            sb = self.sandboxes.get(sid)
            if sb is not None and sb._procs:
                continue  # live work running here — never GC out from under it
            if now - _newest_mtime(d) < ttl:
                continue  # recently touched — leave it
            shutil.rmtree(d, ignore_errors=True)
            self.sandboxes.pop(sid, None)
            removed.append(sid)
        return removed

    def start_reapers(self) -> asyncio.Task:
        """Launch the background loop that periodically reaps idle sessions and
        GCs stale sandbox dirs. Idempotent: returns the existing task if already
        running. The daemon starts this once it has an event loop."""
        if self._reaper is not None and not self._reaper.done():
            return self._reaper

        async def _loop() -> None:
            interval = max(1.0, config.REAP_INTERVAL_MS / 1000.0)
            while True:
                await asyncio.sleep(interval)
                try:
                    self.reap_idle_sessions()
                except Exception:  # noqa: BLE001 — a reap error must not kill the loop
                    pass
                try:
                    self.gc_sandbox_dirs()
                except Exception:  # noqa: BLE001
                    pass

        self._reaper = asyncio.create_task(_loop())
        return self._reaper
