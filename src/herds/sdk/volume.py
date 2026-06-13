"""``Volume`` -- a named, persistent directory that lives on the Mac.

Mounted into a sandbox at a path; survives across runs. Mirrors
``modal.Volume.from_name(...)``. There is no commit/reload step because the
data is a real local directory -- writes are immediately durable -- but we keep
the no-op methods so Modal code ports unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Volume:
    name: str

    @staticmethod
    def from_name(name: str, *, create_if_missing: bool = True) -> "Volume":
        # The directory is created lazily on the Mac when first mounted.
        return Volume(name=name)

    # Kept for Modal API compatibility; local dirs are always consistent.
    def commit(self) -> None:  # noqa: D401
        """No-op: a local volume is durable the moment you write to it."""

    def reload(self) -> None:  # noqa: D401
        """No-op: a local volume is always current."""

    def __repr__(self) -> str:
        return f"Volume({self.name!r})"
