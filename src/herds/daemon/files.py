"""Filesystem inspection for sandboxes and volumes, scoped and safe.

The dashboard browses files that live on the Mac. These helpers resolve a
``kind`` ("sandbox"/"volume") + relative path to a real directory under
``~/.herds``, refusing any path that escapes the root, then list directories
or read (capped) file contents.
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import tarfile
from pathlib import Path

from .. import config

_READ_CAP = 256 * 1024  # 256 KB (preview reads)
_GET_CAP = 64 * 1024 * 1024  # 64 MB (full file read-out)
_WRITE_CAP = 512 * 1024 * 1024  # 512 MB per upload


def _root(kind: str, ident: str) -> Path:
    if kind == "sandbox":
        # The sandbox's working dir is workspace/ — what exec sees and put should target.
        return (config.SANDBOXES_DIR / ident / "workspace").resolve()
    if kind == "volume":
        return (config.VOLUMES_DIR / ident).resolve()
    raise ValueError(f"unknown fs kind: {kind}")


def _resolve(kind: str, ident: str, rel: str) -> tuple[Path, Path]:
    root = _root(kind, ident)
    target = (root / rel.lstrip("/")).resolve()
    # Refuse traversal outside the root.
    if root != target and root not in target.parents:
        raise PermissionError("path escapes root")
    return root, target


def list_dir(kind: str, ident: str, rel: str = "") -> dict:
    root, target = _resolve(kind, ident, rel)
    if not target.exists():
        return {"error": "not found", "path": rel}
    if not target.is_dir():
        return {"error": "not a directory", "path": rel}

    entries = []
    for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        try:
            st = p.stat()
            is_dir = p.is_dir()
            entries.append({
                "name": p.name,
                "dir": is_dir,
                "size": 0 if is_dir else st.st_size,
                "mtime_ms": int(st.st_mtime * 1000),
            })
        except OSError:
            continue
    return {"path": rel, "entries": entries}


def read_file(kind: str, ident: str, rel: str) -> dict:
    root, target = _resolve(kind, ident, rel)
    if not target.exists() or not target.is_file():
        return {"error": "not a file", "path": rel}
    st = target.stat()
    raw = target.read_bytes()[: _READ_CAP]
    truncated = st.st_size > _READ_CAP
    # Heuristic binary detection.
    if b"\x00" in raw[:4096]:
        return {
            "path": rel, "size": st.st_size, "binary": True, "truncated": truncated,
            "content_b64": base64.b64encode(raw[:8192]).decode(),
        }
    return {
        "path": rel,
        "size": st.st_size,
        "binary": False,
        "truncated": truncated,
        "content": raw.decode("utf-8", errors="replace"),
        "mtime_ms": int(st.st_mtime * 1000),
    }


def get_file(kind: str, ident: str, rel: str) -> dict:
    """Read a whole file *out* of a volume/sandbox as base64 (the read-out path).

    Unlike :func:`read_file` (a capped, text-friendly preview for the browser),
    this returns the complete bytes so the SDK can reconstruct the file locally.
    Refuses anything larger than ``_GET_CAP`` so one frame stays bounded. Path
    traversal is rejected by :func:`_resolve`, same as the write side."""
    _root, target = _resolve(kind, ident, rel)
    if not target.exists() or not target.is_file():
        return {"error": "not a file", "path": rel}
    st = target.stat()
    if st.st_size > _GET_CAP:
        return {"error": f"file exceeds {_GET_CAP} byte read-out limit", "path": rel, "size": st.st_size}
    return {
        "path": rel,
        "size": st.st_size,
        "content_b64": base64.b64encode(target.read_bytes()).decode(),
        "mtime_ms": int(st.st_mtime * 1000),
        "ok": True,
    }


def remove(kind: str, ident: str, rel: str, recursive: bool = True) -> dict:
    """Delete a file or directory from a volume/sandbox.

    Refuses to delete the root itself and refuses any path that escapes the
    root (traversal / symlink escape), exactly like :func:`extract_tar`. A
    directory is removed recursively when ``recursive`` (the default)."""
    root, target = _resolve(kind, ident, rel)
    if target == root:
        raise PermissionError("cannot remove the root itself")
    if not target.exists():
        return {"error": "not found", "path": rel}
    if target.is_dir() and not target.is_symlink():
        if not recursive and any(target.iterdir()):
            raise ValueError("directory not empty")
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"path": rel, "removed": True, "ok": True}


def write_file(kind: str, ident: str, rel: str, content_b64: str) -> dict:
    """Write a single file into a volume/sandbox at ``rel`` (parents created)."""
    _root, target = _resolve(kind, ident, rel)
    data = base64.b64decode(content_b64 or "")
    if len(data) > _WRITE_CAP:
        raise ValueError("file exceeds size limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "size": len(data), "ok": True}


def extract_tar(kind: str, ident: str, rel: str, tar_b64: str, clean: bool = False) -> dict:
    """Extract a tarball into a volume/sandbox dir — the codebase-push path.

    Safe: every member is resolved and rejected if it escapes the destination,
    and symlinks/hardlinks/devices are skipped."""
    _root, dest = _resolve(kind, ident, rel)
    raw = base64.b64decode(tar_b64 or "")
    if len(raw) > _WRITE_CAP:
        raise ValueError("archive exceeds size limit")
    if clean and dest.exists() and dest.is_dir():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
        for m in tf.getmembers():
            mp = (dest / m.name).resolve()
            if dest != mp and dest not in mp.parents:
                continue  # refuse traversal outside dest

            if m.isfile() or m.isdir():
                tf.extract(m, path=dest)
                n += 1
            elif m.issym() or m.islnk():
                # Symlinks used to be dropped wholesale. That's safe but wrong
                # for the main use case: a macOS .app bundle's frameworks are
                # Versions/Current symlinks, and a copy without them produces a
                # bundle that will not launch. Keep the link only when its
                # target stays inside the destination.
                if not _link_stays_inside(dest, mp, m.linkname):
                    continue
                tf.extract(m, path=dest)
                n += 1
            # devices/fifos are still skipped entirely
    return {"path": rel, "members": n, "ok": True}


def _link_stays_inside(dest: Path, link_path: Path, linkname: str) -> bool:
    """True when a symlink resolves within ``dest`` (absolute links always fail).

    Checked against the link's own directory, which is how the OS resolves it.
    """
    if not linkname or os.path.isabs(linkname):
        return False
    target = (link_path.parent / linkname).resolve()
    return target == dest or dest in target.parents
