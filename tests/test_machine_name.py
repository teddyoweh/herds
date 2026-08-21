"""A Mac's display name should be what its owner actually named it.

`gather()` used to build `name` purely from `system_profiler`/`sysctl` — two
MacBook Pros on the same fleet showed as identical strings, with no way to
tell them apart in a device list. `scutil --get ComputerName` (System
Settings > General > About > Name) was sitting unread the whole time.
"""
from __future__ import annotations

from herds.daemon import machine


def test_pretty_name_prefers_computer_name():
    assert machine._pretty_name("MacBook Pro", "Mac16,8", "Apple M4 Pro", "Teddy's MacBook Pro") == (
        "Teddy's MacBook Pro"
    )


def test_pretty_name_falls_back_without_computer_name():
    # Unchanged behavior when ComputerName is empty/unavailable — a fresh Mac
    # (or scutil failing in some sandboxed context) still gets a real name.
    assert machine._pretty_name("MacBook Pro", "Mac16,8", "Apple M4 Pro", None) == (
        "MacBook Pro (Apple M4 Pro)"
    )
    assert machine._pretty_name("MacBook Pro", "Mac16,8", "Apple M4 Pro", "") == (
        "MacBook Pro (Apple M4 Pro)"
    )


def test_gather_calls_scutil_and_prefers_it(monkeypatch):
    monkeypatch.setattr(machine, "_sysctl", lambda key: {
        "machdep.cpu.brand_string": "Apple M4 Pro",
        "hw.model": "Mac16,8",
        "hw.memsize": str(24 * 1024**3),
        "hw.ncpu": "14",
    }.get(key))
    monkeypatch.setattr(machine, "_model_name", lambda: "MacBook Pro")
    monkeypatch.setattr(machine, "_macos_version", lambda: "26.2")

    calls = []

    def fake_run_tool(name, *args, timeout=2):
        calls.append((name, args))
        if name == "scutil":
            return "Teddy's MacBook Pro"
        return None

    monkeypatch.setattr(machine, "_run_tool", fake_run_tool)
    machine._CACHE.clear()

    info = machine.gather("mac_1a7aa9a7", agent_version="0.9.11")
    assert info.name == "Teddy's MacBook Pro"
    assert ("scutil", ("--get", "ComputerName")) in calls


def test_gather_two_identical_macbooks_get_distinct_names(monkeypatch):
    # The actual bug: two same-model Macs on one fleet, indistinguishable.
    monkeypatch.setattr(machine, "_sysctl", lambda key: {
        "machdep.cpu.brand_string": "Apple M4 Pro",
        "hw.model": "Mac16,8",
        "hw.memsize": str(24 * 1024**3),
        "hw.ncpu": "14",
    }.get(key))
    monkeypatch.setattr(machine, "_model_name", lambda: "MacBook Pro")
    monkeypatch.setattr(machine, "_macos_version", lambda: "26.2")
    machine._CACHE.clear()

    monkeypatch.setattr(machine, "_run_tool", lambda name, *a, timeout=2: (
        "Teddy's MacBook Pro" if name == "scutil" else None
    ))
    mac_a = machine.gather("mac_1a7aa9a7", agent_version="0.9.11")

    monkeypatch.setattr(machine, "_run_tool", lambda name, *a, timeout=2: (
        "Carlton's MacBook Pro" if name == "scutil" else None
    ))
    mac_b = machine.gather("mac_b124f7ce", agent_version="0.9.11")

    assert mac_a.name != mac_b.name
    assert mac_a.name == "Teddy's MacBook Pro"
    assert mac_b.name == "Carlton's MacBook Pro"
