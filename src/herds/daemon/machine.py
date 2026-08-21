"""Gather hardware/OS facts about this Mac for the registration handshake."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import uuid
from typing import Optional

from ..protocol import MachineInfo

# Resolve the macOS system tools by absolute path.
#
# `sysctl` and `system_profiler` live in /usr/sbin, which is NOT on the PATH a
# LaunchAgent inherits if the plist pins one (a plist with
# PATH=/opt/homebrew/bin:/usr/bin:/bin is enough to lose them). Looking them up
# by bare name then raised FileNotFoundError, which the handlers below swallow
# as "no data" -- so the host Mac registered itself with a null model, chip,
# cpu_count and memory_gb while `sw_vers` and `pmset` (both /usr/bin) kept
# working. Absolute paths make the probe independent of how we were launched.
_BIN_DIRS = ("/usr/sbin", "/usr/bin", "/sbin", "/bin")


def _tool(name: str) -> str:
    """Absolute path to a macOS system tool, falling back to PATH lookup."""
    for d in _BIN_DIRS:
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which(name) or name


def _run_tool(name: str, *args: str, timeout: float = 2) -> Optional[str]:
    """Run a system tool and return stripped stdout, or None if it's unavailable."""
    try:
        out = subprocess.run(
            [_tool(name), *args], capture_output=True, text=True, timeout=timeout
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _sysctl(key: str) -> Optional[str]:
    return _run_tool("sysctl", "-n", key)


def _macos_version() -> Optional[str]:
    return _run_tool("sw_vers", "-productVersion")


def _model_name() -> Optional[str]:
    """Authoritative marketing model name (e.g. 'MacBook Pro') via system_profiler.

    Apple-Silicon model identifiers (``Mac15,3``) can't be classified reliably by
    prefix, so we read the real name once. Runs a single time (gather is cached)."""
    out = _run_tool("system_profiler", "SPHardwareDataType", timeout=6)
    if not out:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Model Name:"):
            return line.split(":", 1)[1].strip() or None
    return None


_TYPE_SLUGS = (
    ("macbook pro", "macbook_pro"), ("macbookpro", "macbook_pro"),
    ("macbook air", "macbook_air"), ("macbookair", "macbook_air"),
    ("mac mini", "mac_mini"), ("macmini", "mac_mini"),
    ("mac studio", "mac_studio"), ("macstudio", "mac_studio"),
    ("mac pro", "mac_pro"), ("macpro", "mac_pro"),
    ("imac", "imac"), ("macbook", "macbook"),
)


def _device_type(model_name: Optional[str], model_id: Optional[str]) -> Optional[str]:
    """Machine-readable form factor from the model name and/or identifier."""
    hay = " ".join(x for x in (model_name, model_id) if x).lower()
    for needle, slug in _TYPE_SLUGS:
        if needle in hay:
            return slug
    return None


def _computer_name() -> Optional[str]:
    """The name the person actually gave this Mac — System Settings > General >
    About > Name, a.k.a. `scutil`'s ComputerName — not a hardware description
    nobody typed. Every OTHER Mac in a fleet reads this `name` field straight
    off the relay with no override path of its own, so whatever this function
    returns is permanently what "MacBook Pro (Apple M4 Pro)" looked like to
    everyone else — the actual bug a Universe user hit: two Macs, indistinguishable
    in their own device list, because both fell through to the generic branch
    below. `scutil` lives in /usr/sbin, hence `_run_tool` and not a bare shell out."""
    return _run_tool("scutil", "--get", "ComputerName")


def _pretty_name(
    model_name: Optional[str], model_id: Optional[str], chip: Optional[str],
    computer_name: Optional[str] = None,
) -> str:
    """The name a person set beats a marketing model name beats a bare model id."""
    if computer_name:
        return computer_name
    base = model_name
    if not base:
        slug = _device_type(None, model_id)
        base = {
            "macbook_pro": "MacBook Pro", "macbook_air": "MacBook Air", "macbook": "MacBook",
            "mac_mini": "Mac mini", "mac_studio": "Mac Studio", "mac_pro": "Mac Pro",
            "imac": "iMac",
        }.get(slug or "", platform.node().split(".")[0] or "Mac")
    return f"{base} ({chip})" if chip else base


def _agent_version() -> str:
    from .. import __version__

    return __version__


# Cache only a *complete* probe. The daemon is long-lived and re-registers on
# every reconnect, so caching a degraded read (see _tool above) would pin this
# Mac as a specless device until the process restarted.
_CACHE: dict = {}


def gather(machine_id: str, agent_version: Optional[str] = None) -> MachineInfo:
    agent_version = agent_version or _agent_version()
    key = (machine_id, agent_version)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    chip = _sysctl("machdep.cpu.brand_string")
    model = _sysctl("hw.model")
    mem_bytes = _sysctl("hw.memsize")
    cpu_count = _sysctl("hw.ncpu")
    model_name = _model_name()
    computer_name = _computer_name()
    info = MachineInfo(
        machine_id=machine_id,
        name=_pretty_name(model_name, model, chip, computer_name),
        model=model,
        device_type=_device_type(model_name, model),
        chip=chip,
        arch=platform.machine(),
        cpu_count=int(cpu_count) if cpu_count and cpu_count.isdigit() else None,
        memory_gb=round(int(mem_bytes) / (1024**3)) if mem_bytes and mem_bytes.isdigit() else None,
        macos_version=_macos_version(),
        agent_version=agent_version,
    )
    # Everything that needs a subprocess came back -> safe to memoize.
    if model and chip and cpu_count and mem_bytes:
        _CACHE[key] = info
    return info


def new_machine_id() -> str:
    """A stable-ish id for this Mac. Random suffix keeps it short and unique."""
    return "mac_" + uuid.uuid4().hex[:8]
