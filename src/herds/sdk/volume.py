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


# The daemon refuses uploads past this. Checked here too, so a doomed transfer
# fails in a second instead of after a 40-minute push through the relay.
WRITE_CAP = 512 * 1024 * 1024


def _check_size(payload: bytes, src: Path) -> None:
    if len(payload) <= WRITE_CAP:
        return
    from .client import HerdsError

    raise HerdsError(
        f"{src.name} is {len(payload) / 1e6:.0f} MB after packing, over the "
        f"{WRITE_CAP // (1024 * 1024)} MB upload limit — the Mac would reject it.\n"
        f"Pushing this through the relay would take ~{len(payload) / 1e6 / 0.5 / 60:.0f} "
        f"minutes anyway (the relay sustains ~0.5 MB/s and is shared by the whole "
        f"fleet). Have the Mac pull it instead:\n"
        f"    mac.fetch('<url>', '{src.name}')\n"
        f"or, for Mac-to-Mac, expose() it on the source and fetch that URL."
    )


def _tar_dir(src: Path, ignore: set, compresslevel: int = 1) -> bytes:
    """Tar a directory, pruning ignored dirs (so we never walk node_modules).

    Gzipped, because the wire is the bottleneck: pushing through the relay runs
    at ~0.5 MB/s while gzip level 1 compresses at hundreds of MB/s, so
    compression is never the limiting step and real payloads shrink ~2x (a
    measured 1.9x on Chrome.app, 2.8x on Cursor.app). Level 1 rather than 6
    deliberately — it stays far faster than even a local control plane (~24
    MB/s), so this can't become the new bottleneck.

    The daemon extracts with ``mode="r:*"``, which sniffs the format, so this is
    backwards compatible with daemons that predate it.

    Symlinks are preserved: an ``.app`` bundle's framework layout is symlinks
    (``Versions/Current``), and a copy without them produces a bundle that will
    not launch.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=compresslevel) as tf:
        for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in ignore]
            # Directory symlinks show up in dirnames; os.walk won't descend them
            # with followlinks=False, so add them as links explicitly.
            for dn in list(dirnames):
                full = os.path.join(dirpath, dn)
                if os.path.islink(full):
                    dirnames.remove(dn)
                    try:
                        tf.add(full, arcname=os.path.relpath(full, src), recursive=False)
                    except OSError:
                        pass
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
            payload = _tar_dir(src, ignored)
            _check_size(payload, src)
            body = {"machine_id": mid, "path": remote,
                    "tar_b64": base64.b64encode(payload).decode(), "clean": clean}
        else:
            rel = remote.rstrip("/") + "/" + src.name if remote.endswith("/") else (remote or src.name)
            payload = src.read_bytes()
            _check_size(payload, src)
            body = {"machine_id": mid, "path": rel,
                    "content_b64": base64.b64encode(payload).decode()}

        r = c._http.put(f"/v1/volumes/{self.name}/put", json=body, timeout=300)
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
        return r.json()

    def get(
        self,
        remote: str,
        local: Optional[str] = None,
        *,
        machine: str = "default",
        url: Optional[str] = None,
        token: Optional[str] = None,
        client=None,
    ) -> bytes:
        """Read a single file back *out* of this volume on the Mac.

        Returns the raw bytes. If ``local`` is given, the bytes are also written
        to that local path (parents created)::

            data = herds.Volume.from_name("data").get("weights/model.bin")
            herds.Volume.from_name("repo").get("out/report.pdf", "./report.pdf")
        """
        from .client import HerdsClient, HerdsError, default_client

        c = client or (HerdsClient(control_plane=url, api_key=token) if (url or token) else default_client())
        mid = _resolve_machine(c, machine)
        r = c._http.get(f"/v1/volumes/{self.name}/get",
                        params={"machine_id": mid, "path": remote}, timeout=300)
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
        payload = r.json()
        if payload.get("error"):
            raise HerdsError(payload["error"])
        data = base64.b64decode(payload.get("content_b64", ""))
        if local:
            dest = Path(local).expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return data

    def listdir(
        self,
        path: str = "",
        *,
        machine: str = "default",
        url: Optional[str] = None,
        token: Optional[str] = None,
        client=None,
    ) -> list:
        """List a directory in this volume; returns the entry dicts
        (``name``/``dir``/``size``/``mtime_ms``)."""
        from .client import HerdsClient, HerdsError, default_client

        c = client or (HerdsClient(control_plane=url, api_key=token) if (url or token) else default_client())
        mid = _resolve_machine(c, machine)
        r = c._http.get(f"/v1/volumes/{self.name}/files",
                        params={"machine_id": mid, "path": path}, timeout=60)
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
        payload = r.json()
        if payload.get("error"):
            raise HerdsError(payload["error"])
        return payload.get("entries", [])

    def remove(
        self,
        path: str,
        *,
        machine: str = "default",
        url: Optional[str] = None,
        token: Optional[str] = None,
        client=None,
    ) -> dict:
        """Delete a file or directory (recursively) from this volume on the Mac."""
        from .client import HerdsClient, HerdsError, default_client

        c = client or (HerdsClient(control_plane=url, api_key=token) if (url or token) else default_client())
        mid = _resolve_machine(c, machine)
        r = c._http.request("DELETE", f"/v1/volumes/{self.name}/file",
                            params={"machine_id": mid, "path": path}, timeout=60)
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
        payload = r.json()
        if payload.get("error"):
            raise HerdsError(payload["error"])
        return payload

    # Kept for Modal API compatibility; local dirs are always consistent.
    def commit(self) -> None:  # noqa: D401
        """No-op: a local volume is durable the moment you write to it."""

    def reload(self) -> None:  # noqa: D401
        """No-op: a local volume is always current."""

    def __repr__(self) -> str:
        return f"Volume({self.name!r})"
