"""Sample CPU and memory on macOS using only the stdlib (no psutil).

CPU is derived from the 1-minute load average normalized by core count; memory
from parsing ``vm_stat``. Both are real, lightweight, and good enough to drive
the dashboard's live charts.
"""

from __future__ import annotations

import os
import re
import subprocess


def _cpu_percent() -> float:
    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):
        return 0.0
    ncpu = os.cpu_count() or 1
    return round(min(100.0, load1 / ncpu * 100.0), 1)


def _mem_percent() -> float:
    """Parse ``vm_stat`` into a used-memory percentage."""
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return 0.0
    page = 4096
    m = re.search(r"page size of (\d+) bytes", out)
    if m:
        page = int(m.group(1))

    def pages(label: str) -> int:
        mm = re.search(rf"{label}:\s+(\d+)\.", out)
        return int(mm.group(1)) if mm else 0

    free = pages("Pages free") + pages("Pages speculative")
    active = pages("Pages active")
    inactive = pages("Pages inactive")
    wired = pages("Pages wired down")
    compressed = pages("Pages occupied by compressor")
    used = (active + wired + compressed) * page
    total = (free + active + inactive + wired + compressed) * page
    if total <= 0:
        return 0.0
    return round(used / total * 100.0, 1)


def sample() -> dict:
    """A single CPU/memory sample."""
    return {
        "cpu": _cpu_percent(),
        "mem": _mem_percent(),
        "load1": round(os.getloadavg()[0], 2) if hasattr(os, "getloadavg") else 0.0,
    }
