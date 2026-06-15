"""Herds Cloud -- connect your Mac to the internet and turn it into a
programmable runtime.

    import herds as dc

    mac = dc.mac()
    result = mac.run("xcodebuild -scheme MyApp build")
    print(result.stdout)

The public surface intentionally echoes Modal so the mental model transfers:
``App``, ``Image``, ``Volume``, ``Sandbox`` -- but the runtime is *your Mac*.
"""

from __future__ import annotations

from .sdk import (
    App,
    CommandError,
    HerdsClient,
    HerdsError,
    Function,
    Image,
    Mac,
    RemoteExecutionError,
    Result,
    Sandbox,
    Secret,
    Volume,
    configure,
    mac,
    machines,
    fleet,
    Fleet,
)

__version__ = "0.1.16"

__all__ = [
    "App",
    "CommandError",
    "HerdsClient",
    "HerdsError",
    "Function",
    "Image",
    "Mac",
    "RemoteExecutionError",
    "Result",
    "Sandbox",
    "Secret",
    "Volume",
    "configure",
    "mac",
    "machines",
    "fleet",
    "Fleet",
    "__version__",
]
