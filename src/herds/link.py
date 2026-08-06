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
"""

from __future__ import annotations

import os
import shutil
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


def _path_dirs() -> list:
    return [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]


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
            "on_path": on_path, "dir": d}


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


__all__ = ["link", "unlink", "target_dir", "herds_script", "resolves_to", "shell_rc"]
