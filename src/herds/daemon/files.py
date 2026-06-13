"""Filesystem inspection for sandboxes and volumes, scoped and safe.

The dashboard browses files that live on the Mac. These helpers resolve a
``kind`` ("sandbox"/"volume") + relative path to a real directory under
``~/.herds``, refusing any path that escapes the root, then list directories
or read (capped) file contents.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .. import config

_READ_CAP = 256 * 1024  # 256 KB


def _root(kind: str, ident: str) -> Path:
    if kind == "sandbox":
        return (config.SANDBOXES_DIR / ident).resolve()
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
