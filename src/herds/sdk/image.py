"""``Image`` -- an environment recipe, resolved on the Mac.

Mirrors Modal's chaining builder, but on a Mac an Image selects toolchains
(Xcode via DEVELOPER_DIR, runtimes via mise) rather than baking a container.
The SDK side just records intent; the daemon's ``images`` module resolves it.

An Image serializes to a single name string (``"xcode:26"``) plus an env
overlay carried alongside the request, which is all the wire protocol needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass(frozen=True)
class Image:
    name: Optional[str] = None          # e.g. "xcode:26", "node:22"
    env: dict[str, str] = field(default_factory=dict)
    setup_commands: tuple[str, ...] = ()

    # -- factories (start a chain) ----------------------------------------- #

    @staticmethod
    def xcode(version: str) -> "Image":
        return Image(name=f"xcode:{version}")

    @staticmethod
    def node(version: str = "22") -> "Image":
        return Image(name=f"node:{version}")

    @staticmethod
    def python(version: str = "3.13") -> "Image":
        return Image(name=f"python:{version}")

    @staticmethod
    def macos() -> "Image":
        """The bare host environment -- whatever is already installed."""
        return Image(name="macos")

    @staticmethod
    def from_name(name: str) -> "Image":
        return Image(name=name)

    # -- builder steps (return new Images; frozen + immutable) -------------- #

    def env_vars(self, **vars: str) -> "Image":
        merged = {**self.env, **vars}
        return replace(self, env=merged)

    def run_commands(self, *commands: str) -> "Image":
        """Setup commands run once before the user's command (best-effort)."""
        return replace(self, setup_commands=self.setup_commands + commands)

    # -- serialization ----------------------------------------------------- #

    def to_request_fields(self) -> dict:
        return {"image": self.name, "env": dict(self.env)}

    def __repr__(self) -> str:
        return f"Image({self.name or 'host'})"
