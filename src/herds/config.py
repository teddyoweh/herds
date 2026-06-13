"""Local on-disk state for Herds: ``~/.herds``.

This is the single source of truth for where things live and how the CLI, SDK,
and daemon find their config. Mirrors Modal's ``~/.modal.toml`` idea but as a
small JSON file plus a directory tree for volumes/sandboxes/logs.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

HERDS_HOME = Path(os.environ.get("HERDS_HOME", Path.home() / ".herds"))

CONFIG_PATH = HERDS_HOME / "config.json"
CREDENTIALS_PATH = HERDS_HOME / "credentials.json"
VOLUMES_DIR = HERDS_HOME / "volumes"
SANDBOXES_DIR = HERDS_HOME / "sandboxes"
IMAGES_DIR = HERDS_HOME / "images"
LOGS_DIR = HERDS_HOME / "logs"
RUN_DIR = HERDS_HOME / "run"

DEFAULT_CONTROL_PLANE = os.environ.get("HERDS_CONTROL_PLANE", "http://127.0.0.1:8787")

AUTH_PATH = HERDS_HOME / "auth.json"
# The relay is invisible infra — baked in, overridable only for our own testing.
DEFAULT_RELAY = os.environ.get("HERDS_RELAY", "wss://relay.herds.run")


def ensure_dirs() -> None:
    for d in (HERDS_HOME, VOLUMES_DIR, SANDBOXES_DIR, IMAGES_DIR, LOGS_DIR, RUN_DIR):
        d.mkdir(parents=True, exist_ok=True)


def now_ms() -> int:
    return int(time.time() * 1000)


# --------------------------------------------------------------------------- #
# Config (control-plane URL, active machine, profile)
# --------------------------------------------------------------------------- #


@dataclass
class Config:
    control_plane: str = DEFAULT_CONTROL_PLANE
    machine_id: Optional[str] = None        # this Mac's id, set on `herds connect`
    machine_name: Optional[str] = None
    default_machine: Optional[str] = None    # which machine the SDK targets by default
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text())
            # HERDS_CONTROL_PLANE env always wins over the saved file, so a host
            # that bumps to a free port can point its daemon at the right URL.
            control_plane = os.environ.get("HERDS_CONTROL_PLANE") or raw.get("control_plane") or DEFAULT_CONTROL_PLANE
            return cls(
                control_plane=control_plane,
                machine_id=raw.get("machine_id"),
                machine_name=raw.get("machine_name"),
                default_machine=raw.get("default_machine"),
                extra=raw.get("extra", {}),
            )
        return cls()

    def save(self) -> None:
        ensure_dirs()
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "control_plane": self.control_plane,
                    "machine_id": self.machine_id,
                    "machine_name": self.machine_name,
                    "default_machine": self.default_machine,
                    "extra": self.extra,
                },
                indent=2,
            )
        )


# --------------------------------------------------------------------------- #
# Credentials (API key for SDK, device token for daemon)
# --------------------------------------------------------------------------- #


@dataclass
class Credentials:
    api_key: Optional[str] = None         # SDK -> control plane
    device_token: Optional[str] = None    # daemon -> control plane

    @classmethod
    def load(cls) -> "Credentials":
        # Env always wins, like Modal's MODAL_TOKEN_* precedence.
        api_key = os.environ.get("HERDS_API_KEY")
        device_token = os.environ.get("HERDS_DEVICE_TOKEN")
        if CREDENTIALS_PATH.exists():
            raw = json.loads(CREDENTIALS_PATH.read_text())
            api_key = api_key or raw.get("api_key")
            device_token = device_token or raw.get("device_token")
        return cls(api_key=api_key, device_token=device_token)

    def save(self) -> None:
        ensure_dirs()
        CREDENTIALS_PATH.write_text(
            json.dumps({"api_key": self.api_key, "device_token": self.device_token}, indent=2)
        )
        # Tokens are secrets; never world-readable.
        try:
            os.chmod(CREDENTIALS_PATH, 0o600)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Auth (account token + assigned subdomain) — set by `herds auth`
# --------------------------------------------------------------------------- #


@dataclass
class Auth:
    """The user's account identity. `token` authenticates to the relay; `account`
    is their assigned name/subdomain. The relay URL is infra — never user-set."""

    token: Optional[str] = None       # hx_… account token
    account: Optional[str] = None      # assigned subdomain, e.g. "teddy" → teddy.herds.run
    url: Optional[str] = None          # the public link, e.g. https://teddy.herds.run
    relay: str = DEFAULT_RELAY

    @classmethod
    def load(cls) -> "Auth":
        token = os.environ.get("HERDS_TOKEN")
        account = os.environ.get("HERDS_ACCOUNT")
        url = None
        relay = DEFAULT_RELAY
        if AUTH_PATH.exists():
            raw = json.loads(AUTH_PATH.read_text())
            token = token or raw.get("token")
            account = account or raw.get("account")
            url = raw.get("url")
            relay = os.environ.get("HERDS_RELAY") or raw.get("relay") or DEFAULT_RELAY
        return cls(token=token, account=account, url=url, relay=relay)

    @property
    def signed_in(self) -> bool:
        return bool(self.token and self.account)

    def save(self) -> None:
        ensure_dirs()
        AUTH_PATH.write_text(
            json.dumps({"token": self.token, "account": self.account, "url": self.url, "relay": self.relay}, indent=2)
        )
        try:
            os.chmod(AUTH_PATH, 0o600)
        except OSError:
            pass
