"""Put ``herds`` on the PATH after a ``pip install`` that didn't.

`pip install herds` writes the console script into whichever environment did the
install. In a venv that's correct. With `pip install --user` on macOS it's
`~/.local/bin` or `~/Library/Python/3.x/bin`, neither on a default PATH — so pip
reports success and the command isn't found.

**No package can fix that at install time.** Wheels have no post-install hook;
pip removed arbitrary install-time code execution on purpose, and it only runs
setup.py hooks for sdist builds it can't get a wheel for. Anything claiming
otherwise is either building from sdist by accident or shipping something that
will stop working.

What *can* be done is make it one deliberate command afterwards: find a
directory already on PATH that we're allowed to write to, and symlink the script
into it. A symlink (not a copy) so upgrading the package upgrades what the link
resolves to.

That symlink is the right answer for a `--user` or system install. It is the
*wrong* answer when herds lives inside a project virtualenv: the link would
resolve into that venv, so `herds` works from any directory right up until the
venv is deleted, rebuilt, or the project is thrown away — and then a global
command breaks for a reason nobody will connect to a venv they forgot about. A
CLI that drives your Macs shouldn't be a tenant of some project's environment.

So when we're running from a venv, "put it on PATH" means installing herds as a
standalone tool (uv or pipx: its own managed environment, its own bin, nothing
to activate) rather than linking the venv's copy. The venv keeps whatever it
has — the SDK stays importable there, which is the reason to `pip install` into
a project in the first place — and the command on your PATH stops depending
on it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Ordered by how conventional they are as a place for user-installed tools on
# the platforms Herds runs on. The first one that's on PATH and writable wins.
PREFERRED = (
    "/opt/homebrew/bin",     # Apple Silicon Homebrew
    "/usr/local/bin",        # Intel Homebrew, and the classic Unix answer
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "bin"),
)


# Tools that install a Python CLI into its own managed environment and put the
# command on PATH themselves. Either one gives a herds that outlives any venv.
STANDALONE = (
    ("uv", ["tool", "install", "--force", "herds"]),
    ("pipx", ["install", "--force", "herds"]),
)

# Also worth linking: the daemon entry point. Only `herds` gets the careful
# treatment (it's the one people type), but leaving `herdsd` behind means
# anything that shells out to it fails while `herds` works.
COMPANIONS = ("herdsd",)


def _path_dirs() -> list:
    return [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]


def install_flavor() -> str:
    """How this install got here — the thing that decides what "global" means.

    ``uv-tool``/``pipx`` are already standalone. ``venv`` is the case a symlink
    can't honestly fix. ``user``/``system`` are on-PATH-or-not problems, which a
    symlink solves exactly.
    """
    prefix = sys.prefix.replace(os.sep, "/")
    if "/uv/tools/" in prefix or os.environ.get("UV_TOOL_BIN_DIR"):
        return "uv-tool"
    if "/pipx/venvs/" in prefix:
        return "pipx"
    if sys.prefix != sys.base_prefix:
        return "venv"
    here = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if here.startswith(os.path.abspath(str(Path.home()))):
        return "user"
    return "system"


def standalone_installer() -> Optional[tuple]:
    """(tool name, argv) for a standalone install, or None if neither is here."""
    for name, args in STANDALONE:
        exe = shutil.which(name)
        if exe:
            return name, [exe] + args
    return None


def _writable(d: str) -> bool:
    return os.path.isdir(d) and os.access(d, os.W_OK)


def target_dir(explicit: Optional[str] = None) -> tuple:
    """(directory, already_on_path) to link into.

    Prefers somewhere already on PATH — linking into a directory the shell can't
    see just moves the problem. Falls back to ~/.local/bin, which we can create,
    and reports that it isn't on PATH so the caller can say so.
    """
    if explicit:
        return explicit, explicit in _path_dirs()

    on_path = _path_dirs()
    for d in PREFERRED:
        if d in on_path and _writable(d):
            return d, True
    # Any other writable PATH entry that isn't inside a virtualenv (linking into
    # the venv we're running from would be a no-op that breaks on deactivate).
    venv = os.environ.get("VIRTUAL_ENV", "")
    for d in on_path:
        if _writable(d) and not (venv and d.startswith(venv)) and "/site-packages" not in d:
            return d, True
    return str(Path.home() / ".local" / "bin"), False


def _tool_bin_dirs(tool: str) -> list:
    """Where a standalone installer puts commands, in the order it prefers.

    Asked explicitly rather than trusting ``which``: we may be running inside
    the very venv we're trying to stop depending on, and that venv's `herds` is
    earlier on PATH than the one we just installed.
    """
    dirs = []
    for var in (("UV_TOOL_BIN_DIR",) if tool == "uv" else ("PIPX_BIN_DIR",)) + ("XDG_BIN_HOME",):
        v = os.environ.get(var)
        if v:
            dirs.append(v)
    dirs.append(str(Path.home() / ".local" / "bin"))
    return dirs


def go_global(timeout: float = 600.0) -> dict:
    """Reinstall herds as a standalone tool, so the command owns its own env.

    This is a real install, not a link: after it, `herds` resolves to an
    environment that uv/pipx manages and nothing else can take away. Any venv
    that also has herds keeps it — importable as the SDK, which is what a venv
    install is for.
    """
    found = standalone_installer()
    if not found:
        return {"ok": False, "reason": "no-installer",
                "detail": "Neither `uv` nor `pipx` is installed."}
    tool, argv = found
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "reason": "no-installer", "tool": tool,
                "detail": f"{argv[0]}: not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout", "tool": tool,
                "detail": f"{tool} timed out after {int(timeout)}s"}
    except Exception as exc:  # noqa: BLE001 — the caller renders every failure
        return {"ok": False, "reason": "failed", "tool": tool, "detail": str(exc)}

    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0:
        return {"ok": False, "reason": "failed", "tool": tool,
                "detail": out or f"{tool} exited {p.returncode}"}

    if tool == "uv":  # teaches the user's shell rc about uv's bin dir
        try:
            subprocess.run([argv[0], "tool", "update-shell"],
                           capture_output=True, text=True, timeout=60)
        except Exception:  # noqa: BLE001 — a PATH nicety, never a failure
            pass

    dest, on_path = None, False
    path_dirs = _path_dirs()
    for d in _tool_bin_dirs(tool):
        cand = os.path.join(d, "herds")
        if os.path.exists(cand):
            dest, on_path = cand, d in path_dirs
            break
    if dest is None:  # installed fine, just somewhere we didn't predict
        dest = shutil.which("herds")
        on_path = bool(dest)
    return {"ok": True, "tool": tool, "dest": dest, "on_path": on_path, "output": out}


def shadowed_by(dest: str) -> Optional[str]:
    """An older `herds` the shell finds *before* the one at ``dest``.

    A stale copy from a previous install method is the one failure that looks
    like nothing happened: the install succeeded, the file is right there, and
    `herds` still runs last year's version from somewhere else on PATH.
    """
    found = shutil.which("herds")
    if not found or not dest:
        return None
    try:
        if os.path.realpath(found) == os.path.realpath(dest):
            return None
    except OSError:
        return None
    return found


def herds_script() -> Optional[str]:
    """The `herds` console script belonging to *this* interpreter."""
    from .__main__ import _console_script

    return _console_script()


def link(explicit: Optional[str] = None, force: bool = False) -> dict:
    """Symlink the console script somewhere on PATH.

    Returns a dict describing what happened; raises nothing the caller can't
    render. Idempotent: an existing link to the same script is a no-op.
    """
    script = herds_script()
    if not script:
        return {"ok": False, "reason": "no-script",
                "detail": "Couldn't find this install's `herds` script."}

    d, on_path = target_dir(explicit)
    dest = os.path.join(d, "herds")

    try:
        os.makedirs(d, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "reason": "mkdir", "detail": str(exc), "dir": d}

    if os.path.lexists(dest):
        try:
            if os.path.realpath(dest) == os.path.realpath(script):
                return {"ok": True, "already": True, "dest": dest,
                        "script": script, "on_path": on_path, "dir": d}
        except OSError:
            pass
        if not force:
            return {"ok": False, "reason": "exists", "dest": dest, "dir": d,
                    "detail": f"{dest} already exists and points elsewhere."}
        try:
            os.unlink(dest)
        except OSError as exc:
            return {"ok": False, "reason": "unlink", "detail": str(exc), "dest": dest}

    try:
        os.symlink(script, dest)
    except OSError as exc:
        return {"ok": False, "reason": "symlink", "detail": str(exc),
                "dest": dest, "dir": d}

    return {"ok": True, "already": False, "dest": dest, "script": script,
            "on_path": on_path, "dir": d, "also": _link_companions(script, d)}


def _link_companions(script: str, d: str) -> list:
    """Link the other console scripts next to `herds`, best-effort.

    Never clobbers and never fails the main link: `herds` working is the point,
    and `herdsd` following it along is a convenience for anything that shells
    out to the daemon by name.
    """
    linked = []
    src_dir = os.path.dirname(script)
    for name in COMPANIONS:
        src, dest = os.path.join(src_dir, name), os.path.join(d, name)
        if not os.path.exists(src) or os.path.lexists(dest):
            continue
        try:
            os.symlink(src, dest)
            linked.append(dest)
        except OSError:
            pass
    return linked


def resolves_to(dest: str) -> bool:
    """Does the shell now find `herds`, and is it the one we just linked?"""
    found = shutil.which("herds")
    if not found:
        return False
    try:
        return os.path.realpath(found) == os.path.realpath(dest)
    except OSError:
        return False


def shell_rc() -> Path:
    """The rc file to suggest a PATH line in, based on the running shell."""
    sh = os.path.basename(os.environ.get("SHELL", "")) or "zsh"
    return Path.home() / {"zsh": ".zshrc", "bash": ".bash_profile",
                          "fish": ".config/fish/config.fish"}.get(sh, ".profile")


def unlink(explicit: Optional[str] = None) -> dict:
    """Remove a link we created — only if it actually points at a herds script."""
    d, _ = target_dir(explicit)
    dest = os.path.join(d, "herds")
    if not os.path.lexists(dest):
        return {"ok": False, "reason": "missing", "dest": dest}
    if not os.path.islink(dest):
        return {"ok": False, "reason": "not-a-link", "dest": dest,
                "detail": f"{dest} isn't a symlink — refusing to delete it."}
    try:
        os.unlink(dest)
    except OSError as exc:
        return {"ok": False, "reason": "unlink", "detail": str(exc), "dest": dest}
    return {"ok": True, "dest": dest}


__all__ = ["link", "unlink", "target_dir", "herds_script", "resolves_to", "shell_rc",
           "install_flavor", "standalone_installer", "go_global", "shadowed_by"]
