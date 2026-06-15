"""The Herds SDK: turn a connected Mac into a programmable runtime."""

from __future__ import annotations

from .app import App, Function, RemoteExecutionError
from .client import CommandError, HerdsClient, HerdsError, Result, configure
from .image import Image
from .mac import Mac, mac, machines, fleet, Fleet
from .sandbox import Sandbox
from .secret import Secret
from .volume import Volume

__all__ = [
    "App",
    "Function",
    "RemoteExecutionError",
    "CommandError",
    "HerdsClient",
    "HerdsError",
    "Result",
    "Image",
    "Mac",
    "mac",
    "machines",
    "fleet",
    "Fleet",
    "configure",
    "Sandbox",
    "Secret",
    "Volume",
]
