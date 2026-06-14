"""``Volume`` -- a named, persistent directory that lives on the Mac.

Mounted into a sandbox at a path; survives across runs. Mirrors
``modal.Volume.from_name(...)``. There is no commit/reload step because the
data is a real local directory -- writes are immediately durable -- but we keep
the no-op methods so Modal code ports unchanged.
"""

from __future__ import annotations

import base64
import io
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Junk never worth shipping with a codebase (Modal's add_local_dir skips similar).
_DEFAULT_IGNORE = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".DS_Store", "dist", "build",
    ".next", ".turbo", ".cache", ".idea", ".vscode", "target",
}


def _resolve_machine(client, machine: str) -> str:
    if machine and machine != "default":
        return machine
    ms = client.list_machines()
    online = [m for m in ms if m.get("status") == "online"] or ms
    if not online:
        raise RuntimeError("no Mac is connected — run `herds host` on a Mac first")
    return online[0]["machine_id"]


def _tar_dir(src: Path, ignore: set) -> bytes:
    """Tar a directory, pruning ignored dirs (so we never walk node_modules)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for dirpath, dirnames, filenames in os.walk(src):
            dirnames[:] = [d for d in dirnames if d not in ignore]
            for fn in filenames:
                if fn in ignore:
                    continue
                full = os.path.join(dirpath, fn)
                arc = os.path.relpath(full, src)
                try:
                    tf.add(full, arcname=arc, recursive=False)
                except OSError:
                    continue
    return buf.getvalue()


@dataclass(frozen=True)
class Volume:
    name: str

    @staticmethod
    def from_name(name: str, *, create_if_missing: bool = True) -> "Volume":
        # The directory is created lazily on the Mac when first mounted.
        return Volume(name=name)

    def put(
        self,
        local: str,
        remote: str = "",
        *,
        machine: str = "default",
        url: Optional[str] = None,
        token: Optional[str] = None,
        client=None,
        clean: bool = False,
        ignore: Optional[list] = None,
    ) -> dict:
        """Copy a local file or **entire directory** into this volume on the Mac.

        A directory is tarred locally and extracted on the Mac — the way you'd
        ship a whole codebase to a long-running agent::

            herds.Volume.from_name("repo").put("./my-project")          # → volume root
            herds.Volume.from_name("data").put("model.bin", "weights/") # one file
        """
        from .client import HerdsClient, HerdsError, default_client

        c = client or (HerdsClient(control_plane=url, api_key=token) if (url or token) else default_client())
        mid = _resolve_machine(c, machine)
        src = Path(local).expanduser()
        if not src.exists():
            raise FileNotFoundError(f"no such path: {src}")

        if src.is_dir():
            ignored = set(_DEFAULT_IGNORE) | set(ignore or [])
            body = {"machine_id": mid, "path": remote,
                    "tar_b64": base64.b64encode(_tar_dir(src, ignored)).decode(), "clean": clean}
        else:
            rel = remote.rstrip("/") + "/" + src.name if remote.endswith("/") else (remote or src.name)
            body = {"machine_id": mid, "path": rel,
                    "content_b64": base64.b64encode(src.read_bytes()).decode()}

        r = c._http.put(f"/v1/volumes/{self.name}/put", json=body, timeout=300)
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
        return r.json()

    # Kept for Modal API compatibility; local dirs are always consistent.
    def commit(self) -> None:  # noqa: D401
        """No-op: a local volume is durable the moment you write to it."""

    def reload(self) -> None:  # noqa: D401
        """No-op: a local volume is always current."""

    def __repr__(self) -> str:
        return f"Volume({self.name!r})"
