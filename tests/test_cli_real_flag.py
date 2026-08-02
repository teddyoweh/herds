"""`herds run` / `herds shell` must be able to target the real Mac.

Everything runs in a throwaway sandbox by default: $HOME is redirected into
~/.herds/sandboxes/sbx_eph_*/home and a Seatbelt profile rolls back writes. The
SDK has always been able to opt out via ``mac.run(..., inherit_home=True)``, but
the CLI exposed no equivalent -- so anyone driving a Mac through `herds shell`
or `herds run` hit "directories are not writable" / "read-only file system" with
no way out, and the natural conclusion was that herds simply couldn't reach the
real machine. --real is that escape hatch; these tests pin the wiring.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from herds.cli import app

runner = CliRunner()


class _FakeResult:
    exit_code = 0
    stdout = ""
    stderr = ""


@pytest.fixture
def captured(monkeypatch):
    """Capture the kwargs the CLI hands to Mac.run, without touching a network."""
    calls = []

    class FakeMac:
        def __init__(self, *a, **kw):
            pass

        def run(self, cmd, **kwargs):
            calls.append({"cmd": cmd, **kwargs})
            return _FakeResult()

    # `herds.sdk.mac` the attribute is the mac() factory, which shadows the
    # submodule — go through sys.modules to reach the real module object.
    import sys

    mac_mod = sys.modules["herds.sdk.mac"]
    monkeypatch.setattr(mac_mod, "Mac", FakeMac)
    monkeypatch.setattr("herds.cli._client", lambda *a, **kw: object())
    return calls


@pytest.mark.parametrize("argv,expected", [
    (["shell", "-c", "ls"], False),
    (["shell", "--real", "-c", "ls"], True),
    (["shell", "--inherit-home", "-c", "ls"], True),
])
def test_shell_passes_inherit_home(captured, argv, expected):
    runner.invoke(app, argv)
    assert captured, "Mac.run was never called"
    assert captured[0]["inherit_home"] is expected


@pytest.mark.parametrize("argv,expected", [
    (["run", "--", "ls"], False),
    (["run", "--real", "--", "ls"], True),
    (["run", "--inherit-home", "--", "ls"], True),
])
def test_run_passes_inherit_home(captured, argv, expected):
    runner.invoke(app, argv)
    assert captured, "Mac.run was never called"
    assert captured[0]["inherit_home"] is expected


def test_sandboxed_remains_the_default(captured):
    """--real must be opt-in; isolation is the safe default."""
    runner.invoke(app, ["run", "--", "whoami"])
    assert captured[0]["inherit_home"] is False


def test_real_flag_is_discoverable():
    """This gap cost hours precisely because it wasn't findable in --help."""
    for cmd in ("run", "shell"):
        out = runner.invoke(app, [cmd, "--help"]).output
        assert "--real" in out, f"{cmd} --help doesn't mention --real"
        assert "sandbox" in out.lower(), f"{cmd} --help doesn't explain the default"
