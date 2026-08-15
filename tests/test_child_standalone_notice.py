"""`herds child` must announce the fork before minting a fleet of one.

`ensure_account` provisions a fresh anonymous account whenever the Mac is not
signed in. That is the product's zero-signup front door — and it used to happen
in silence, which is how a second Mac ended up as its own one-machine fleet
(`teddy-2`) instead of joining the account fleet its owner was already driving:
online, healthy, and invisible from every other machine. These tests pin the
announcement, the flow-through for automation, and the silence for a Mac that
is properly signed in.

The TTY confirm is deliberately NOT tested here: CliRunner's stdin is never a
tty, so the prompt cannot fire under it — which is itself the property the
automation tests below rely on.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from herds import config
from herds.cli import app

runner = CliRunner()


@pytest.fixture
def quiet_host(monkeypatch):
    """Stub the host machinery so `child` decides but never launches."""
    import herds.host as host

    calls = {"provisioned": 0, "started": 0}

    def fake_ensure(want=""):
        calls["provisioned"] += 1
        a = config.Auth()
        a.token, a.account = "herds_sk_test", "m0000test"
        return a

    monkeypatch.setattr(host, "ensure_account", fake_ensure)
    monkeypatch.setattr(host, "run_host", lambda **kw: calls.__setitem__("started", calls["started"] + 1))
    monkeypatch.setattr(host, "start_host_background", lambda **kw: calls.__setitem__("started", calls["started"] + 1))
    return calls


def _signed_out(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(config, "AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr(config.Auth, "load", classmethod(lambda cls: config.Auth()))


def _signed_in(monkeypatch):
    def load(cls):
        a = config.Auth()
        a.token, a.account = "herds_sk_real", "teddyoweh"
        return a

    monkeypatch.setattr(config.Auth, "load", classmethod(load))


def test_signed_out_child_announces_the_standalone_fleet(quiet_host, monkeypatch, tmp_path):
    _signed_out(monkeypatch, tmp_path)
    result = runner.invoke(app, ["child", "-b"])
    assert result.exit_code == 0
    said = result.output
    assert "its own" in said and "fleet" in said, said
    assert "herds auth" in said, said
    # Announced, not blocked: automation still goes live.
    assert quiet_host["provisioned"] == 1
    assert quiet_host["started"] == 1


def test_signed_out_non_tty_never_prompts(quiet_host, monkeypatch, tmp_path):
    _signed_out(monkeypatch, tmp_path)
    # No input provided: a prompt would raise/abort under CliRunner. Surviving
    # with exit 0 IS the assertion that nothing asked a question.
    result = runner.invoke(app, ["child", "-b"], input=None)
    assert result.exit_code == 0
    assert quiet_host["started"] == 1


def test_signed_in_child_says_nothing_about_fleets(quiet_host, monkeypatch):
    _signed_in(monkeypatch)
    result = runner.invoke(app, ["child", "-b"])
    assert result.exit_code == 0
    assert "its own" not in result.output
    assert quiet_host["started"] == 1
