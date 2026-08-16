"""`herds child`/`install` must ENABLE the agent before bootstrapping it.

macOS `launchctl disable` is sticky and survives bootout/bootstrap — so a Mac
whose agent was ever disabled could never get KeepAlive back, and its host
would start, die, and stay dead. The fix: always `enable` first. This pins the
call order so the enable can't be dropped again.
"""
from __future__ import annotations
import sys
import pytest
from herds.cli import _ensure_launchagent, _PLIST_LABEL


@pytest.mark.skipif(sys.platform != "darwin", reason="launchd is macOS-only")
def test_enable_precedes_bootstrap(monkeypatch, tmp_path):
    import herds.cli as cli
    calls = []
    monkeypatch.setattr(cli, "_PLIST_PATH", tmp_path / "a.plist")
    monkeypatch.setattr(cli, "_plist_contents", lambda b: "<plist/>")

    real = cli.subprocess.run
    def fake_run(argv, **kw):
        if argv and argv[0] == "launchctl":
            calls.append(argv[1])
        class R: returncode = 0; stdout = "1000"; stderr = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert _ensure_launchagent() is True
    # enable must come before bootstrap, and bootout between them
    assert "enable" in calls and "bootstrap" in calls
    assert calls.index("enable") < calls.index("bootstrap"), calls
    assert calls.index("bootout") < calls.index("bootstrap"), calls


@pytest.mark.skipif(sys.platform == "darwin", reason="non-mac no-op path")
def test_noop_off_mac():
    assert _ensure_launchagent() is False
