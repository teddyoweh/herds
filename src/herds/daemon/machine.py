"""Gather hardware/OS facts about this Mac for the registration handshake."""

from __future__ import annotations

import platform
import subprocess
import uuid
from functools import lru_cache
from typing import Optional

from ..protocol import MachineInfo


def _sysctl(key: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _macos_version() -> Optional[str]:
    try:
        out = subprocess.run(
            ["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _model_name() -> Optional[str]:
    """Authoritative marketing model name (e.g. 'MacBook Pro') via system_profiler.

    Apple-Silicon model identifiers (``Mac15,3``) can't be classified reliably by
    prefix, so we read the real name once. Runs a single time (gather is cached)."""
    try:
        out = subprocess.run(
            ["system_profiler", "SPHardwareDataType"], capture_output=True, text=True, timeout=6
        ).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Model Name:"):
                return line.split(":", 1)[1].strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
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


def _pretty_name(model_name: Optional[str], model_id: Optional[str], chip: Optional[str]) -> str:
    """Best-effort friendly name like 'MacBook Pro (Apple M4)'."""
    base = model_name
    if not base:
        slug = _device_type(None, model_id)
        base = {
            "macbook_pro": "MacBook Pro", "macbook_air": "MacBook Air", "macbook": "MacBook",
            "mac_mini": "Mac mini", "mac_studio": "Mac Studio", "mac_pro": "Mac Pro",
            "imac": "iMac",
        }.get(slug or "", platform.node().split(".")[0] or "Mac")
    return f"{base} ({chip})" if chip else base


@lru_cache(maxsize=1)
def gather(machine_id: str, agent_version: str = "0.1.0") -> MachineInfo:
    chip = _sysctl("machdep.cpu.brand_string")
    model = _sysctl("hw.model")
    mem_bytes = _sysctl("hw.memsize")
    cpu_count = _sysctl("hw.ncpu")
    model_name = _model_name()
    return MachineInfo(
        machine_id=machine_id,
        name=_pretty_name(model_name, model, chip),
        model=model,
        device_type=_device_type(model_name, model),
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
