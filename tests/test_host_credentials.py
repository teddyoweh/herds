"""`herds host` must leave this Mac able to talk to the control plane it serves.

The host token was written to host.json (so the dashboard link carries it) and
registered in the store's api_keys — but never into credentials.json, which is
the only place the SDK and CLI look. So on the very Mac serving the control
plane, `herds tags` answered "missing API key" while the working credential sat
on disk two files away.
"""

from __future__ import annotations

import json

import pytest

from herds import config, host


@pytest.fixture
def herds_home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(config, "CREDENTIALS_PATH", tmp_path / "credentials.json")
    for name in ("VOLUMES_DIR", "SANDBOXES_DIR", "IMAGES_DIR", "LOGS_DIR", "RUN_DIR"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    monkeypatch.delenv("HERDS_API_KEY", raising=False)
    monkeypatch.delenv("HERDS_DEVICE_TOKEN", raising=False)
    return tmp_path


# The real function `herds host` calls at startup — not a copy of its logic.
_adopt = host._adopt_api_key


def test_host_token_becomes_the_sdk_api_key(herds_home):
    assert config.Credentials.load().api_key is None

    token = host._persistent_token()
    _adopt(token)

    assert config.Credentials.load().api_key == token, "SDK still has no key"


def test_adoption_is_idempotent_across_restarts(herds_home):
    """The token is stable, so a restart must not churn the credential."""
    first = host._persistent_token()
    _adopt(first)
    _adopt(host._persistent_token())

    assert config.Credentials.load().api_key == first


def test_an_existing_key_is_never_clobbered(herds_home):
    """A key set by hand or by `herds auth` elsewhere is not ours to replace."""
    creds = config.Credentials.load()
    creds.api_key = "herds_sk_set_by_the_user"
    creds.save()

    _adopt(host._persistent_token())

    assert config.Credentials.load().api_key == "herds_sk_set_by_the_user"


def test_device_token_is_left_alone(herds_home):
    """Adopting the API key must not disturb the daemon's separate credential."""
    creds = config.Credentials.load()
    creds.device_token = "hd_daemon"
    creds.save()

    _adopt(host._persistent_token())

    after = config.Credentials.load()
    assert after.device_token == "hd_daemon"
    assert after.api_key


def test_credentials_file_is_not_world_readable(herds_home):
    """It holds a token that unlocks the whole Mac."""
    _adopt(host._persistent_token())

    mode = (herds_home / "credentials.json").stat().st_mode & 0o777
    assert mode == 0o600, f"credentials.json is {oct(mode)}"


def test_written_key_matches_the_host_token_file(herds_home):
    """The two must agree, or the dashboard link and the SDK disagree."""
    token = host._persistent_token()
    _adopt(token)

    on_disk = json.loads((herds_home / "credentials.json").read_text())["api_key"]
    assert on_disk == (herds_home / "host_token").read_text().strip()
