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
    Session,
    Secret,
    TcpTunnel,
    Volume,
    configure,
    mac,
    machines,
    fleet,
    Fleet,
)

try:  # single source of truth is pyproject; read it back off the install
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("herds")
except (ImportError, PackageNotFoundError):  # running from a source tree
    __version__ = "0.3.2"

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
    "Session",
    "Secret",
    "TcpTunnel",
    "Volume",
    "configure",
    "mac",
    "machines",
    "fleet",
    "Fleet",
    "__version__",
]
