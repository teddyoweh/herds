"""``python -m herds`` — the entry point that always works.

`pip install herds` writes a `herds` console script into the *installing*
environment's scripts directory. For a venv that's the venv's bin (correct, and
active while the venv is). For `pip install --user` on macOS it's
``~/.local/bin`` or ``~/Library/Python/3.x/bin``, neither of which is on a
default PATH — so the install succeeds and the command still isn't found.

Nothing in a package can put a script on someone's PATH. What it can do is
guarantee a second way in: ``python -m herds`` runs from the interpreter that
did the install, so it works whenever the import works. If the console script
turns out not to be reachable, say where it is and how to fix it — the user
running this is probably here because `herds` wasn't found.
"""

from __future__ import annotations

import os
import shutil
import sys
import sysconfig
from typing import Optional


def _console_script() -> Optional[str]:
    """Path to the installed ``herds`` script, if we can find one.

    Install schemes differ by platform, packager, and Python build, so every
    lookup here is best-effort: not finding the script is an ordinary answer,
    never an error.
    """
    candidates = []
    for key in ("scripts", "purelib"):
        try:
            base = sysconfig.get_path(key)
        except (KeyError, ValueError):
            continue
        if base:
            candidates.append(os.path.dirname(base) if key == "purelib" else base)
    # `pip install --user` lands in the user scheme, not the default one.
    try:
        user = sysconfig.get_path("scripts", f"{os.name}_user")
    except (KeyError, ValueError):
        user = None
    if user:
        candidates.append(user)

    for d in candidates:
        cand = os.path.join(d, "herds")
        if os.path.isfile(cand):
            return cand
    return None


def _warn_if_not_on_path() -> None:
    if shutil.which("herds"):
        return  # reachable as `herds` — nothing to say
    script = _console_script()
    if not script:
        return
    d = os.path.dirname(script)
    print(
        f"note: `herds` is installed at {script}\n"
        f"      but {d} is not on your PATH, so the bare `herds` command won't work.\n"
        f"      Fix it once:   python3 -m herds link\n"
        f"      (links it into a directory your shell already searches)\n",
        file=sys.stderr,
    )


def main() -> None:
    try:
        _warn_if_not_on_path()
    except Exception:  # noqa: BLE001 — a hint must never be why the CLI failed
        pass
    from .cli import app

    app()


if __name__ == "__main__":
    main()
