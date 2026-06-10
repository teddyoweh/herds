"""Gather hardware/OS facts about this Mac for the registration handshake."""

from __future__ import annotations

import platform
import subprocess
import uuid
from functools import lru_cache

from ..protocol import MachineInfo


def _sysctl(key: str) -> str | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _macos_version() -> str | None:
    try:
        out = subprocess.run(
            ["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _pretty_name(model: str | None, chip: str | None) -> str:
    """Best-effort friendly name like 'MacBook Pro (Apple M4)'."""
    if model and model.startswith("MacBook"):
        base = "MacBook Pro" if "Pro" in model else "MacBook"
    elif model and "Macmini" in model:
        base = "Mac mini"
    elif model and "MacStudio" in model:
        base = "Mac Studio"
    elif model and "iMac" in model:
        base = "iMac"
    else:
        base = platform.node().split(".")[0] or "Mac"
    return f"{base} ({chip})" if chip else base


@lru_cache(maxsize=1)
def gather(machine_id: str, agent_version: str = "0.1.0") -> MachineInfo:
    chip = _sysctl("machdep.cpu.brand_string")
    model = _sysctl("hw.model")
    mem_bytes = _sysctl("hw.memsize")
    cpu_count = _sysctl("hw.ncpu")
    return MachineInfo(
        machine_id=machine_id,
        name=_pretty_name(model, chip),
        model=model,
        chip=chip,
        arch=platform.machine(),
        cpu_count=int(cpu_count) if cpu_count and cpu_count.isdigit() else None,
        memory_gb=round(int(mem_bytes) / (1024**3)) if mem_bytes and mem_bytes.isdigit() else None,
        macos_version=_macos_version(),
        agent_version=agent_version,
    )


def new_machine_id() -> str:
    """A stable-ish id for this Mac. Random suffix keeps it short and unique."""
    return "mac_" + uuid.uuid4().hex[:8]
