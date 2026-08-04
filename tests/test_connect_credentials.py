"""Joining a fleet must leave this Mac able to *query* that fleet.

`herds connect tok@host` moved two of the three pieces of state — control_plane
and device_token — and left api_key alone. But the CLI and SDK authenticate with
api_key, so:

  * a Mac added the documented way (`curl herds.run/install | sh -s -- tok@host`)
    came up unable to run `herds tags` at all: "missing API key";
  * a Mac that had previously hosted kept its own host key while control_plane
    moved to the new fleet — a good key at the wrong door, surfacing as a bare
    401 that named neither.

The connect token is itself a valid API key on that host (`herds host` registers
the very same string via put_api_key), so the pair can and must move together.
"""

from __future__ import annotations

import pytest

from herds import config
from herds.cli import _adopt_connect_credentials


@pytest.fixture
def herds_home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", tmp_path / "credentials.json")
    for name in ("VOLUMES_DIR", "SANDBOXES_DIR", "IMAGES_DIR", "LOGS_DIR", "RUN_DIR"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    monkeypatch.delenv("HERDS_API_KEY", raising=False)
    monkeypatch.delenv("HERDS_DEVICE_TOKEN", raising=False)
    monkeypatch.delenv("HERDS_CONTROL_PLANE", raising=False)
    return tmp_path


def _connect(token: str, target: str) -> None:
    """`herds connect`'s state changes: the control-plane move it performs
    inline, plus the real credential helper the command calls."""
    cfg = config.Config.load()
    if target:
        cfg.control_plane = target
        cfg.save()
    _adopt_connect_credentials(token, target)


def test_a_freshly_joined_mac_can_query_the_fleet(herds_home):
    """The install-script case: nothing set beforehand."""
    assert config.Credentials.load().api_key is None

    _connect("herds_sk_bob", "https://bob.relay.herds.run")

    creds = config.Credentials.load()
    assert creds.api_key == "herds_sk_bob", "CLI would say 'missing API key'"
    assert creds.device_token == "herds_sk_bob"


def test_joining_replaces_a_previous_host_key(herds_home):
    """The wrong-door case: this Mac hosted, then joined someone else."""
    creds = config.Credentials.load()
    creds.api_key = "herds_sk_my_own_host"
    creds.save()

    _connect("herds_sk_bob", "https://bob.relay.herds.run")

    assert config.Credentials.load().api_key == "herds_sk_bob"


def test_key_and_control_plane_move_together(herds_home):
    """The invariant behind both bugs: they are one pair, never independent."""
    _connect("herds_sk_bob", "https://bob.relay.herds.run")
    assert config.Config.load().control_plane == "https://bob.relay.herds.run"
    assert config.Credentials.load().api_key == "herds_sk_bob"

    _connect("herds_sk_carol", "https://carol.relay.herds.run")
    assert config.Config.load().control_plane == "https://carol.relay.herds.run"
    assert config.Credentials.load().api_key == "herds_sk_carol"


def test_no_target_does_not_disturb_an_existing_key(herds_home):
    """`herds connect` with a bare token and no host: the door hasn't moved."""
    creds = config.Credentials.load()
    creds.api_key = "herds_sk_existing"
    creds.save()

    _connect("herds_sk_new_device", "")

    after = config.Credentials.load()
    assert after.api_key == "herds_sk_existing", "key moved without the door"
    assert after.device_token == "herds_sk_new_device"


def test_no_target_still_fills_a_blank_key(herds_home):
    _connect("herds_sk_only", "")
    assert config.Credentials.load().api_key == "herds_sk_only"
