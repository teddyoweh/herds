"""`herds update` — upgrade with the tool that did the install.

Herds arrives four ways and each upgrades differently. `pip install -U` into a
uv-managed tool doesn't touch what's on PATH, so the command appears to succeed
and the old binary keeps running; inside a pipx venv it fights pipx's own
bookkeeping. So the method has to be detected, not assumed.

The version comparison is its own hazard: string ordering puts "0.9.10" before
"0.9.2", which would report an upgrade as a downgrade and refuse it.
"""

from __future__ import annotations

import sys

import pytest
from typer.testing import CliRunner

from herds import update as up
from herds.cli import app

runner = CliRunner()


# -- ordering releases ------------------------------------------------------ #


@pytest.mark.parametrize("lo,hi", [
    ("0.9.2", "0.9.10"),      # the one string comparison gets wrong
    ("0.9.2", "0.10.0"),
    ("0.9.9", "1.0.0"),
    ("0.8.3", "0.9.0"),
    ("1.0.0-rc1", "1.0.0"),   # a prerelease precedes its release
])
def test_version_ordering(lo, hi):
    assert up.parse_version(lo) < up.parse_version(hi), f"{lo} should sort before {hi}"


def test_equal_versions_are_equal():
    assert up.parse_version("0.9.2") == up.parse_version("0.9.2")


def test_short_versions_are_padded():
    assert up.parse_version("1.0") == up.parse_version("1.0.0")


def test_garbage_does_not_raise():
    for v in ("", "not-a-version", "1", "..", "v2.0.0"):
        assert isinstance(up.parse_version(v), tuple)


# -- picking the right upgrade command -------------------------------------- #


def test_uv_tool_install_uses_uv(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/Users/x/.local/share/uv/tools/herds")
    method, argv, note = up.install_method()

    assert method == "uv"
    assert argv[1:3] == ["tool", "install"]
    # uv caches the package index; without this a release published minutes ago
    # resolves to the previous one and the upgrade looks like a no-op.
    assert "--no-cache" in argv
    assert "uv" in note


def test_pipx_install_uses_pipx(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/Users/x/.local/pipx/venvs/herds")
    method, argv, note = up.install_method()

    assert method == "pipx"
    assert argv[1:] == ["upgrade", "herds"]


def test_venv_uses_this_interpreters_pip(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/tmp/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    method, argv, note = up.install_method()

    assert method == "pip"
    assert argv[0] == sys.executable, "must upgrade THIS environment, not whichever pip is on PATH"
    assert "--upgrade" in argv and "herds" in argv


def test_pip_upgrade_bypasses_the_wheel_cache(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/tmp/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert "--no-cache-dir" in up.install_method()[1]


# -- the command ------------------------------------------------------------ #


def test_reports_up_to_date_and_changes_nothing(monkeypatch):
    monkeypatch.setattr(up, "installed_version", lambda: "0.9.2")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    ran = []
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: ran.append(a) or (True, ""))

    r = runner.invoke(app, ["update"])

    assert r.exit_code == 0
    assert "up to date" in r.output
    assert ran == [], "ran an upgrade when there was nothing to upgrade"


def test_newer_local_build_is_not_downgraded(monkeypatch):
    """Running a build newer than PyPI (a dev install) must not 'upgrade' back."""
    monkeypatch.setattr(up, "installed_version", lambda: "0.10.0")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    ran = []
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: ran.append(a) or (True, ""))

    runner.invoke(app, ["update"])

    assert ran == [], "downgraded a newer local build"


def test_check_never_runs_anything(monkeypatch):
    monkeypatch.setattr(up, "installed_version", lambda: "0.8.0")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    ran = []
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: ran.append(a) or (True, ""))

    r = runner.invoke(app, ["update", "--check"])

    assert r.exit_code == 0
    assert "0.8.0" in r.output and "0.9.2" in r.output
    assert ran == [], "--check modified the system"


def test_offline_fails_loudly(monkeypatch):
    monkeypatch.setattr(up, "installed_version", lambda: "0.9.2")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: None)

    r = runner.invoke(app, ["update"])

    assert r.exit_code == 1
    assert "PyPI" in r.output


def test_a_failed_upgrade_exits_nonzero_and_shows_the_command(monkeypatch):
    monkeypatch.setattr(up, "installed_version", lambda: "0.8.0")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: (False, "boom"))

    r = runner.invoke(app, ["update"])

    assert r.exit_code == 1
    assert "herds" in r.output, "didn't show the command to run by hand"


def test_success_reports_the_version_from_a_fresh_interpreter(monkeypatch):
    """This process imported herds before upgrading, so its in-memory
    __version__ is the old one — reporting that would claim failure."""
    monkeypatch.setattr(up, "installed_version", lambda: "0.8.0")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: (True, ""))
    monkeypatch.setattr(up, "installed_after_upgrade", lambda: "0.9.2")

    r = runner.invoke(app, ["update"])

    assert r.exit_code == 0
    assert "0.9.2" in r.output


def test_an_upgrade_that_did_not_take_is_reported(monkeypatch):
    """Index caches can serve a stale version — say so instead of claiming success."""
    monkeypatch.setattr(up, "installed_version", lambda: "0.8.0")
    monkeypatch.setattr(up, "latest_version", lambda *a, **k: "0.9.2")
    monkeypatch.setattr(up, "run_upgrade", lambda *a, **k: (True, ""))
    monkeypatch.setattr(up, "installed_after_upgrade", lambda: "0.8.0")

    r = runner.invoke(app, ["update"])

    assert "Still on 0.8.0" in r.output
