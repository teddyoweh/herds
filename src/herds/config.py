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
CONTEXTS_PATH = HERDS_HOME / "contexts.json"
# The relay is invisible infra — baked in, overridable only for our own testing.
# Use a *.relay.herds.run subdomain (not the apex): fresh subdomains always resolve
# straight to the relay box; the apex can get stale-cached to the wildcard.
DEFAULT_RELAY = os.environ.get("HERDS_RELAY", "wss://api.relay.herds.run")


# --------------------------------------------------------------------------- #
# Self-describing connect tokens
# --------------------------------------------------------------------------- #
#
# Joining a Mac used to need two things pasted in the right order — a link and a
# token — which is two chances to get it wrong and one more thing to carry
# around. The endpoint isn't a second secret; it's just where the token is
# valid. So carry it *in* the token:
#
#     herds_sk_mqoa56xOPbW1WUex9EC2rBMFv0CMyEwA@teddyoweh.relay.herds.run
#
# Deliberately readable rather than an opaque blob: pasting a token that
# silently points your Mac at someone else's relay is a real risk, and you can
# read this one. Shaped like user@host so it's obvious what it means.


def join_token(token: str, url: str) -> str:
    """Pack a token and its control plane into one paste-able credential."""
    host = url.split("://", 1)[-1].rstrip("/")
    return f"{token}@{host}"


def split_token(value: str):
    """Return ``(token, control_plane_url_or_None)`` for a connect credential.

    Accepts the packed ``secret@host`` form, or a bare token (returns None for
    the URL, so the caller falls back to config/env as before).
    """
    value = (value or "").strip()
    if "@" not in value:
        return value, None
    token, _, host = value.rpartition("@")
    token, host = token.strip(), host.strip().rstrip("/")
    if not token or not host:
        return value, None
    if "://" in host:
        return token, host
    # Loopback and bare host:port are plain HTTP; anything else is a real
    # deployment and must not be downgraded off TLS.
    local = host.split(":", 1)[0] in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
    return token, f"{'http' if local else 'https'}://{host}"


def ensure_dirs() -> None:
    for d in (HERDS_HOME, VOLUMES_DIR, SANDBOXES_DIR, IMAGES_DIR, LOGS_DIR, RUN_DIR):
        d.mkdir(parents=True, exist_ok=True)


def now_ms() -> int:
    return int(time.time() * 1000)


# --------------------------------------------------------------------------- #
# Fleet hardening (admission control, idle reap, sandbox GC)
# --------------------------------------------------------------------------- #
# A Mac has no cpu/mem partition — a Sandbox's cpu/mem args are advisory only.
# So instead of partitioning a machine we *bound* it: cap how many sandboxes run
# at once (with a small waiting queue), reap resident sessions that have gone
# idle (Modal's warm-idle analog), and garbage-collect stale sandbox trees so a
# long-lived daemon doesn't slowly fill the disk. All knobs are env-overridable.


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Admission: max sandboxes/sessions running concurrently on this Mac, plus the
# depth of the queue that holds callers when the cap is hit. Past the queue,
# new work is rejected (EX_TEMPFAIL) rather than piling up unbounded.
MAX_LIVE_SANDBOXES = _int_env("HERDS_MAX_LIVE_SANDBOXES", 8)
ADMISSION_QUEUE_MAX = _int_env("HERDS_ADMISSION_QUEUE_MAX", 32)
# Optional cpu backpressure: if >0 and the machine's live cpu% is at/above this,
# treat the Mac as full (queue new work) even below the count cap. 0 disables it.
ADMISSION_CPU_HIGH_WATER = _float_env("HERDS_ADMISSION_CPU_HIGH_WATER", 0.0)

# Idle-session reap: a resident (stdin-fed) session with no input for this long
# is terminated. Default 30 min.
SESSION_IDLE_TIMEOUT_MS = _int_env("HERDS_SESSION_IDLE_TIMEOUT_MS", 30 * 60 * 1000)

# Sandbox-dir GC: a sandbox tree on disk untouched for this long (and with no
# live process) is removed. Default 24 h.
SANDBOX_TTL_MS = _int_env("HERDS_SANDBOX_TTL_MS", 24 * 60 * 60 * 1000)

# How often the background reaper wakes to run idle-reap + GC. Default 60 s.
REAP_INTERVAL_MS = _int_env("HERDS_REAP_INTERVAL_MS", 60 * 1000)

# How long start_session blocks waiting for the agent to confirm the resident
# process is live (SESSION_READY) before returning best-effort. Generous, because
# a session may provision a toolchain (setup_commands) before it comes up.
SESSION_START_TIMEOUT_S = _float_env("HERDS_SESSION_START_TIMEOUT_S", 120.0)


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
            if relay in ("wss://relay.herds.run", "ws://relay.herds.run"):
                relay = DEFAULT_RELAY  # migrate off the apex
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


# --------------------------------------------------------------------------- #
# Contexts (many fleets, one active) — set by `herds use`
# --------------------------------------------------------------------------- #
#
# A machine can reach more than one fleet: your own Macs, a colleague's, a CI
# pool. The control-plane URL and the API key that opens it are *one pair* — a
# key is only meaningful at the door it was issued for. Keeping them in two
# single-valued files is what let them drift apart, which surfaced as a good key
# at the wrong door: "missing API key", or a bare 401 naming neither.
#
# So contexts.json is the registry, and the *active* entry is projected into
# config.json + credentials.json. Everything that already reads those — the
# daemon, HerdsClient, `herds host` — keeps working untouched, and switching
# fleets moves both halves or neither.


@dataclass
class Context:
    """One fleet you can drive: where it is, and the key that opens it."""

    name: str
    control_plane: str
    api_key: Optional[str] = None
    added_ms: int = 0

    def to_json(self) -> dict:
        return {"control_plane": self.control_plane, "api_key": self.api_key,
                "added_ms": self.added_ms}


@dataclass
class Contexts:
    current: Optional[str] = None
    items: dict = field(default_factory=dict)   # name -> Context

    # -- load / save -------------------------------------------------------- #

    @classmethod
    def load(cls) -> "Contexts":
        if not CONTEXTS_PATH.exists():
            return cls._adopt_existing()
        try:
            raw = json.loads(CONTEXTS_PATH.read_text())
        except (OSError, ValueError):
            return cls._adopt_existing()
        items = {
            name: Context(name=name, control_plane=v.get("control_plane", ""),
                          api_key=v.get("api_key"), added_ms=v.get("added_ms", 0))
            for name, v in (raw.get("contexts") or {}).items()
            if v.get("control_plane")
        }
        return cls(current=raw.get("current"), items=items)

    @classmethod
    def _adopt_existing(cls) -> "Contexts":
        """A machine set up before contexts existed still has exactly one fleet.

        Treat its config.json + credentials.json as an unnamed context rather
        than pretending it has none — otherwise `herds contexts` would report
        nothing on a machine that is very much driving something.
        """
        cfg = Config.load()
        if not cfg.control_plane or cfg.control_plane == DEFAULT_CONTROL_PLANE:
            return cls()
        name = context_name_for(cfg.control_plane)
        creds = Credentials.load()
        return cls(current=name, items={
            name: Context(name=name, control_plane=cfg.control_plane, api_key=creds.api_key)
        })

    def save(self) -> None:
        ensure_dirs()
        CONTEXTS_PATH.write_text(json.dumps(
            {"current": self.current,
             "contexts": {n: c.to_json() for n, c in self.items.items()}},
            indent=2,
        ))
        try:
            os.chmod(CONTEXTS_PATH, 0o600)   # holds API keys
        except OSError:
            pass

    # -- registry ----------------------------------------------------------- #

    @property
    def active(self) -> Optional[Context]:
        return self.items.get(self.current or "")

    def add(self, name: str, control_plane: str, api_key: Optional[str]) -> Context:
        ctx = Context(name=name, control_plane=control_plane.rstrip("/"),
                      api_key=api_key, added_ms=now_ms())
        self.items[name] = ctx
        return ctx

    def remove(self, name: str) -> bool:
        if name not in self.items:
            return False
        del self.items[name]
        if self.current == name:
            self.current = next(iter(self.items), None)
        return True

    def activate(self, name: str) -> Context:
        """Select a fleet and project it into the files everything else reads."""
        ctx = self.items[name]
        self.current = name
        self.save()
        cfg = Config.load()
        cfg.control_plane = ctx.control_plane
        cfg.save()
        creds = Credentials.load()
        creds.api_key = ctx.api_key      # the pair moves together, always
        creds.save()
        return ctx


def context_name_for(url: str) -> str:
    """A short, stable name for a fleet, derived from its URL.

    The relay already hands every account a unique subdomain, so the first label
    is unique by construction — no registry, no collisions to resolve.
    """
    host = (url or "").split("://")[-1].split("/")[0].split(":")[0]
    if not host:
        return "default"
    if host in ("127.0.0.1", "localhost", "::1"):
        return "local"
    label = host.split(".")[0]
    return label or host
