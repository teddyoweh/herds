"""Signing in must decide which control plane this Mac talks to — but only when
the one it has is broken.

The account lives in auth.json; the control-plane URL lives in config.json. Only
the first was written on `herds auth`, so a config left over from an earlier
account — or an old dev host — survived the sign-in. Every later command then
talked to an endpoint the user no longer had, and the relay answered with a 502
that read like an outage rather than "you are pointed at the wrong place".

Healing that unconditionally was too blunt. A Mac can serve its own control
plane *and* have joined someone else's with `herds connect`; those are separate
roles sharing one config slot. Repointing on every sign-in would pull the CLI
off a fleet the user deliberately joined while their daemon kept reporting to
it. So adoption is now conditional on the current endpoint not answering, and
`--repoint` is the deliberate override.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from herds import cli as cli_mod
from herds import config
from herds.cli import _adopt_control_plane, app

runner = CliRunner()


@pytest.fixture
def herds_home(tmp_path, monkeypatch):
    """Point every config path at a scratch dir so no real state is touched."""
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    for name in ("VOLUMES_DIR", "SANDBOXES_DIR", "IMAGES_DIR", "LOGS_DIR", "RUN_DIR"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.delenv("HERDS_CONTROL_PLANE", raising=False)
    # Never probe the real network: the answer would depend on whether the
    # developer happens to be hosting on 127.0.0.1:8787 right now.
    monkeypatch.setattr(cli_mod, "_control_plane_alive", lambda url: False)
    return tmp_path


@pytest.fixture
def alive(monkeypatch):
    """Make the currently-saved control plane look reachable."""
    monkeypatch.setattr(cli_mod, "_control_plane_alive", lambda url: True)


def _save_config(url: str) -> None:
    cfg = config.Config.load()
    cfg.control_plane = url
    cfg.save()


def test_signin_repoints_a_stale_control_plane(herds_home):
    """The observed failure: config stuck on a dev host that no longer exists."""
    _save_config("https://dev-elcruzo.relay.herds.run")

    _adopt_control_plane(config.Auth(token="hx_1", account="teddyoweh",
                                     url="https://teddyoweh.relay.herds.run"))

    assert config.Config.load().control_plane == "https://teddyoweh.relay.herds.run"


def test_signin_repoints_from_a_dead_localhost_default(herds_home):
    _save_config(config.DEFAULT_CONTROL_PLANE)

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"))

    assert config.Config.load().control_plane == "https://ada.relay.herds.run"


# -- the both-roles case: hosting and also joined to someone else ------------ #


def test_a_live_control_plane_is_left_alone(herds_home, alive):
    """You joined Bob's fleet; signing in to your own account doesn't evict you."""
    _save_config("https://bob.relay.herds.run")

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"))

    assert config.Config.load().control_plane == "https://bob.relay.herds.run"


def test_a_live_localhost_host_is_left_alone(herds_home, alive):
    """Your own `herds host` on 127.0.0.1 IS your control plane — the relay URL
    is the same thing with a public face. Don't add a network hop for nothing."""
    _save_config(config.DEFAULT_CONTROL_PLANE)

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"))

    assert config.Config.load().control_plane == config.DEFAULT_CONTROL_PLANE


def test_repoint_forces_the_switch(herds_home, alive):
    """`herds auth --repoint`: I know it's up, take me back to my account."""
    _save_config("https://bob.relay.herds.run")

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"), force=True)

    assert config.Config.load().control_plane == "https://ada.relay.herds.run"


def test_repoint_flag_reaches_the_helper(herds_home, alive, monkeypatch):
    """Wiring: `herds auth --repoint` on a signed-in Mac must actually force."""
    monkeypatch.setattr(config, "AUTH_PATH", herds_home / "auth.json")
    _save_config("https://bob.relay.herds.run")
    config.Auth(token="hx_1", account="ada",
                url="https://ada.relay.herds.run").save()

    assert runner.invoke(app, ["auth"]).exit_code == 0
    assert config.Config.load().control_plane == "https://bob.relay.herds.run"

    assert runner.invoke(app, ["auth", "--repoint"]).exit_code == 0
    assert config.Config.load().control_plane == "https://ada.relay.herds.run"


def test_account_url_is_derived_when_absent(herds_home):
    """Older relays don't return `url`; the account name still determines it."""
    _save_config("https://stale.example")

    _adopt_control_plane(config.Auth(token="hx_1", account="ada", url=None))

    assert config.Config.load().control_plane == "https://ada.relay.herds.run"


def test_env_override_wins(herds_home, monkeypatch):
    """A self-hoster who pins HERDS_CONTROL_PLANE means it."""
    monkeypatch.setenv("HERDS_CONTROL_PLANE", "http://127.0.0.1:9999")
    _save_config("http://127.0.0.1:9999")

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"))

    assert config.Config.load().control_plane == "http://127.0.0.1:9999"


def test_trailing_slash_is_not_a_difference(herds_home):
    """Must not rewrite (and log a change) over pure punctuation."""
    _save_config("https://ada.relay.herds.run")

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run/"))

    assert config.Config.load().control_plane == "https://ada.relay.herds.run"


def test_unknown_account_leaves_config_alone(herds_home):
    """Nothing to adopt → don't clobber a working endpoint."""
    _save_config("https://kept.example")

    _adopt_control_plane(config.Auth(token=None, account=None, url=None))

    assert config.Config.load().control_plane == "https://kept.example"


def test_herds_auth_heals_config_when_already_signed_in(herds_home, monkeypatch):
    """The wiring, not just the helper: `herds auth` on a signed-in Mac.

    This is the state the fleet was actually in — signed in, but talking to a
    dead endpoint. Re-running `herds auth` said "✓ Signed in" and changed
    nothing, so there was no way to recover short of editing config.json.
    """
    monkeypatch.setattr(config, "AUTH_PATH", herds_home / "auth.json")
    _save_config("https://dev-elcruzo.relay.herds.run")
    config.Auth(token="hx_1", account="teddyoweh",
                url="https://teddyoweh.relay.herds.run").save()

    result = runner.invoke(app, ["auth"])

    assert result.exit_code == 0, result.output
    assert config.Config.load().control_plane == "https://teddyoweh.relay.herds.run"


def test_other_config_fields_survive(herds_home):
    """Adopting a URL must not drop the machine identity beside it."""
    cfg = config.Config.load()
    cfg.control_plane = "https://old.example"
    cfg.machine_id = "mac_abc"
    cfg.machine_name = "Mac mini (Apple M4)"
    cfg.default_machine = "mac_abc"
    cfg.save()

    _adopt_control_plane(config.Auth(token="hx_1", account="ada",
                                     url="https://ada.relay.herds.run"))

    after = config.Config.load()
    assert after.control_plane == "https://ada.relay.herds.run"
    assert after.machine_id == "mac_abc"
    assert after.machine_name == "Mac mini (Apple M4)"
    assert after.default_machine == "mac_abc"
