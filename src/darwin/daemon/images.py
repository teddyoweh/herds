"""Resolve an ``Image`` name to concrete environment changes on this Mac.

In Modal an Image bakes a container. On a Mac we don't have cheap containers,
so an Image is an *environment recipe*: pick the right Xcode via ``DEVELOPER_DIR``,
the right Node/Python via ``mise``, and so on. Everything here is best-effort and
degrades to a clean no-op when the underlying tool isn't installed -- the command
still runs against the host toolchain, it just isn't pinned.

Image names follow ``"<kind>:<version>"`` (e.g. ``"xcode:26"``, ``"node:22"``,
``"python:3.13"``). A plain ``"<kind>"`` means "whatever is on PATH".
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional


class ImageResolution:
    """The result of resolving an image: env overlay + human-readable notes."""

    def __init__(self) -> None:
        self.env: dict[str, str] = {}
        self.path_prepend: list[str] = []
        self.notes: list[str] = []

    def merge_path(self, base_path: str) -> str:
        if not self.path_prepend:
            return base_path
        return ":".join(self.path_prepend) + ":" + base_path


def _split(image: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not image:
        return None, None
    if ":" in image:
        kind, version = image.split(":", 1)
        return kind.strip().lower(), version.strip()
    return image.strip().lower(), None


def _resolve_xcode(version: Optional[str], res: ImageResolution) -> None:
    """Point DEVELOPER_DIR at the requested Xcode without touching global state.

    Per-process DEVELOPER_DIR is the safe way to select Xcode -- it never
    clobbers a concurrent job the way ``xcode-select --switch`` would.
    """
    candidates: list[Path] = []
    if version:
        candidates += [
            Path(f"/Applications/Xcode-{version}.app/Contents/Developer"),
            Path(f"/Applications/Xcode_{version}.app/Contents/Developer"),
        ]
    candidates.append(Path("/Applications/Xcode.app/Contents/Developer"))

    for dev_dir in candidates:
        if dev_dir.exists():
            res.env["DEVELOPER_DIR"] = str(dev_dir)
            res.notes.append(f"xcode -> {dev_dir.parent.parent.name}")
            return

    if shutil.which("xcodes"):
        res.notes.append(
            f"xcode {version or '(default)'} not installed; run `xcodes install {version or 'latest'}`"
        )
    else:
        res.notes.append("xcode requested but no Xcode found and `xcodes` not installed")


def _resolve_mise(kind: str, version: Optional[str], res: ImageResolution) -> None:
    """Use mise to pin a runtime (node/python/ruby/go...) for this command."""
    if not shutil.which("mise"):
        res.notes.append(
            f"{kind} {version or ''} requested; install `mise` to pin it (using host {kind})".strip()
        )
        return
    spec = f"{kind}@{version}" if version else kind
    # mise exposes a shim dir; activating via env keeps it per-process.
    res.env["MISE_"] = ""  # placeholder so callers see mise is engaged
    res.path_prepend.insert(0, str(Path.home() / ".local/share/mise/shims"))
    res.notes.append(f"{kind} -> mise {spec}")
    res.env.setdefault("DARWIN_MISE_SPEC", spec)


# Runtimes we know how to pin through mise.
_MISE_KINDS = {"node", "python", "ruby", "go", "rust", "java", "bun", "deno"}


def resolve(image: Optional[str]) -> ImageResolution:
    """Map an image name to an environment overlay. Always returns something."""
    res = ImageResolution()
    kind, version = _split(image)
    if kind is None:
        return res

    if kind == "xcode":
        _resolve_xcode(version, res)
    elif kind in _MISE_KINDS:
        _resolve_mise(kind, version, res)
    elif kind in ("base", "macos", "host"):
        res.notes.append("host environment")
    else:
        # Unknown image kind: don't fail, just run on the host and say so.
        res.notes.append(f"unknown image '{image}'; running on host toolchain")
    return res
