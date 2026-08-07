"""``herds update`` — upgrade to the latest release with the right tool.

Herds gets installed four different ways and each upgrades differently. Telling
someone to "run pip install -U" is wrong for three of them: `pip install -U` into
a uv-managed tool doesn't touch what's on PATH, and inside a pipx venv it fights
pipx's own bookkeeping. So work out how *this* install got here and use its tool.

Also: both uv and PyPI's index CDN cache, so a release published seconds ago can
resolve to the previous one and look like the upgrade silently did nothing.
That bit twice while shipping today, so the check reads PyPI's JSON API directly
and the upgrade tells uv not to use its cache.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
import urllib.request
from typing import Optional

PYPI_JSON = "https://pypi.org/pypi/herds/json"


def parse_version(v: str) -> tuple:
    """Compare releases without taking a dependency on `packaging`.

    Only has to order our own versions — plain N.N.N, occasionally with a
    prerelease suffix, which sorts before the release it precedes.
    """
    main, _, rest = (v or "").partition("-")
    nums = []
    for part in main.split("."):
        digits = "".join(c for c in part if c.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    # A suffix (rc1, dev0) makes it *earlier* than the bare version.
    return (tuple(nums[:3]), 0 if rest else 1, rest)


def installed_version() -> str:
    from . import __version__

    return __version__


def latest_version(timeout: float = 8.0) -> Optional[str]:
    """The newest release on PyPI, or None if we couldn't ask.

    Deliberately the JSON API rather than the simple index: it isn't served from
    the same cache, so it reflects a just-published release sooner.
    """
    try:
        req = urllib.request.Request(PYPI_JSON, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("info", {}).get("version")
    except Exception:  # noqa: BLE001 — offline is an answer, not a crash
        return None


def install_method() -> tuple:
    """(method, argv, human_note) for upgrading *this* install."""
    prefix = sys.prefix.replace(os.sep, "/")

    if "/uv/tools/" in prefix or os.environ.get("UV_TOOL_BIN_DIR"):
        uv = shutil.which("uv") or "uv"
        # --no-cache: uv caches the package index, so a fresh release can
        # resolve to the previous one and look like nothing happened.
        return "uv", [uv, "tool", "install", "--force", "--no-cache", "herds"], "uv tool"

    if "/pipx/venvs/" in prefix:
        pipx = shutil.which("pipx") or "pipx"
        return "pipx", [pipx, "upgrade", "herds"], "pipx"

    in_venv = sys.prefix != sys.base_prefix
    argv = [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "herds"]
    if not in_venv and _user_scheme():
        argv.insert(-1, "--user")
        return "pip-user", argv, "pip (--user)"
    return "pip", argv, "pip" + (" (venv)" if in_venv else "")


def _user_scheme() -> bool:
    """Was this installed into the per-user scheme rather than system-wide?"""
    try:
        user = sysconfig.get_path("purelib", f"{os.name}_user")
    except (KeyError, ValueError):
        return False
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return bool(user) and os.path.abspath(here).startswith(os.path.abspath(user))


def run_upgrade(argv: list, timeout: float = 600.0) -> tuple:
    """(ok, output). Never raises — the caller renders the failure."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, f"{argv[0]}: not found"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {int(timeout)}s"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0, out.strip()


def installed_after_upgrade() -> Optional[str]:
    """Re-read the version from a *fresh* interpreter.

    This process imported herds before the upgrade, so ``herds.__version__`` in
    memory is the old one — reporting it back would claim the upgrade failed
    when it worked.
    """
    try:
        p = subprocess.run(
            [sys.executable, "-c",
             "from importlib.metadata import version; print(version('herds'))"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:  # noqa: BLE001
        return None
    v = (p.stdout or "").strip()
    return v or None


__all__ = ["installed_version", "latest_version", "install_method", "run_upgrade",
           "installed_after_upgrade", "parse_version"]
