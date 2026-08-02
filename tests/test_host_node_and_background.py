"""The host Mac must register as a real node, and `herds host` must background.

Two regressions this pins down:

1. ``sysctl`` and ``system_profiler`` live in /usr/sbin. A LaunchAgent plist
   that pins PATH (older herds installs shipped
   ``/opt/homebrew/bin:/usr/bin:/bin``) drops that directory, the probes raise
   FileNotFoundError, and the handlers swallow it as "no data" -- so the host
   registered itself with a null model/chip/cpu/memory while `sw_vers` and
   `pmset` (both /usr/bin) kept working, which made it look like a partial
   outage rather than a PATH bug.

2. ``herds host`` must detach for humans but stay in the foreground under
   launchd, whose KeepAlive would otherwise respawn an instantly-exiting
   process forever.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from herds.daemon import machine
from herds.host import _system_path, should_detach

# The PATH an older herds LaunchAgent pinned -- no /usr/sbin.
BROKEN_PATH = "/opt/homebrew/bin:/usr/bin:/bin"

macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="macOS system tools")


# --- 1. hardware probes must not depend on PATH ---------------------------- #

@macos_only
def test_tool_resolves_usr_sbin_absolutely():
    """sysctl/system_profiler resolve even when /usr/sbin isn't on PATH."""
    assert machine._tool("sysctl") == "/usr/sbin/sysctl"
    assert machine._tool("system_profiler") == "/usr/sbin/system_profiler"


@macos_only
def test_sysctl_works_without_usr_sbin_on_path(monkeypatch):
    """The exact failure mode: a pinned PATH must not blank out the hardware."""
    monkeypatch.setenv("PATH", BROKEN_PATH)
    # Bare-name lookup is genuinely broken in this environment ...
    with pytest.raises(FileNotFoundError):
        subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True)
    # ... but ours still works.
    assert machine._sysctl("hw.model")


@macos_only
def test_gather_is_fully_populated_under_a_pinned_path(monkeypatch):
    """The regression itself: a host Mac must not register as a specless device."""
    monkeypatch.setenv("PATH", BROKEN_PATH)
    machine._CACHE.clear()
    info = machine.gather("mac_test")

    assert info.model, "model came back empty (sysctl unreachable)"
    assert info.chip, "chip came back empty (sysctl unreachable)"
    assert info.cpu_count and info.cpu_count > 0
    assert info.memory_gb and info.memory_gb > 0
    assert info.device_type, "device_type empty — shows as an unknown device in the UI"
    assert info.macos_version


def test_agent_version_is_the_real_version():
    """It was hardcoded to 0.1.0, so every Mac under-reported its agent."""
    from herds import __version__

    machine._CACHE.clear()
    assert machine.gather("mac_test").agent_version == __version__


def test_degraded_probe_is_not_cached(monkeypatch):
    """A bad read must not pin this Mac as specless for the daemon's lifetime."""
    machine._CACHE.clear()
    monkeypatch.setattr(machine, "_sysctl", lambda key: None)
    monkeypatch.setattr(machine, "_model_name", lambda: None)

    degraded = machine.gather("mac_test")
    assert degraded.chip is None
    assert not machine._CACHE, "a degraded probe was memoized"

    # Once the tools are reachable again, the next call re-probes.
    monkeypatch.undo()
    machine._CACHE.clear()
    if sys.platform == "darwin":
        assert machine.gather("mac_test").chip


# --- 2. PATH hardening for spawned children -------------------------------- #

def test_system_path_restores_usr_sbin(monkeypatch):
    monkeypatch.setenv("PATH", BROKEN_PATH)
    parts = _system_path().split(os.pathsep)
    for d in ("/usr/sbin", "/sbin", "/usr/bin", "/bin"):
        assert d in parts
    # Existing entries are preserved, not replaced.
    assert "/opt/homebrew/bin" in parts


def test_system_path_does_not_duplicate(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    parts = _system_path().split(os.pathsep)
    assert len(parts) == len(set(parts))


# --- 3. foreground/background decision ------------------------------------- #

@pytest.mark.parametrize(
    "foreground,background,isatty,expected,why",
    [
        (False, False, True,  True,  "interactive terminal -> detach"),
        (False, False, False, False, "launchd/CI -> stay foreground"),
        (True,  False, True,  False, "--foreground wins over a tty"),
        (False, True,  False, True,  "--background wins over a pipe"),
    ],
)
def test_should_detach(foreground, background, isatty, expected, why):
    assert should_detach(foreground, background, isatty) is expected, why


def test_launchd_plist_runs_in_foreground_with_usr_sbin():
    """The generated plist must not fight its own supervisor, and must keep PATH."""
    from herds.cli import _plist_contents

    plist = _plist_contents("/usr/local/bin/herds")
    assert "<string>--foreground</string>" in plist, (
        "a backgrounding host under KeepAlive would respawn in a tight loop"
    )
    assert "/usr/sbin" in plist, "plist PATH must keep sysctl/system_profiler reachable"


def test_relaunch_cmd_uses_the_running_interpreter():
    """Never hand the background host off to a different herds on PATH."""
    from herds.host import _relaunch_cmd

    cmd = _relaunch_cmd(["--port", "9000"])
    assert cmd[0] == sys.executable
    assert "--foreground" in cmd
    assert cmd[-2:] == ["--port", "9000"]
