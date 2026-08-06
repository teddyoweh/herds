"""The agent skill must describe the SDK that actually exists.

SKILL.md is not prose an agent skims — it *is* the instruction set it acts on.
An agent that calls `mac.expose(3000)` because the skill said so has no way to
tell that the docs lied rather than the Mac failing, so a stale example here is
worse than a stale paragraph anywhere else in the docs. (The landing page did
carry exactly that call for months; nothing caught it.)

These tests pin two things: every symbol the skill names exists with the
keywords it passes, and the two copies of the file don't drift apart.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import herds
from herds.sdk.mac import Fleet, Mac
from herds.sdk.sandbox import Sandbox
from herds.sdk.volume import Volume
from herds.skill import SKILL_MD

REPO = Path(__file__).resolve().parent.parent
WEB_COPY = REPO / "web" / "public" / "skill.md"


# -- the two copies stay identical ------------------------------------------ #


def test_web_copy_matches_the_packaged_skill():
    """herds.run/skill.md is served from web/public; `herds skill --install`
    writes SKILL_MD. If they drift, two audiences get different instructions."""
    assert WEB_COPY.exists(), "web/public/skill.md is missing"
    assert WEB_COPY.read_text() == SKILL_MD, (
        "web/public/skill.md has drifted from herds.skill.SKILL_MD — "
        "update both (the docstring in skill.py claims they're in sync)"
    )


# -- every API call in the skill resolves ----------------------------------- #

# (object, attribute) pairs the skill demonstrates.
CALLS = [
    (herds, "mac"), (herds, "fleet"), (herds, "configure"),
    (herds, "use"), (herds, "contexts"),
    (herds, "Sandbox"), (herds, "Volume"), (herds, "App"), (herds, "Image"),
    (Mac, "run"), (Mac, "stream"), (Mac, "map"), (Mac, "push"), (Mac, "session"),
    (Mac, "shell"), (Mac, "screenshot"), (Mac, "write"), (Mac, "read_text"),
    (Mac, "ls"), (Mac, "copy"), (Mac, "clipboard"), (Mac, "notify"), (Mac, "chrome"),
    (Fleet, "map"), (Fleet, "macs"), (Fleet, "agent"),
    (Sandbox, "create"), (Sandbox, "exec"), (Sandbox, "spawn"), (Sandbox, "expose"),
    (Sandbox, "put"),
    (Volume, "from_name"),
]


@pytest.mark.parametrize("obj,attr", CALLS, ids=lambda v: getattr(v, "__name__", str(v)))
def test_symbol_exists(obj, attr):
    assert hasattr(obj, attr), f"skill references {getattr(obj,'__name__',obj)}.{attr}, which does not exist"


# Keyword arguments the skill passes by name.
KWARGS = [
    (herds.mac, "tag"), (herds.mac, "url"), (herds.mac, "token"),
    (Mac.run, "check"), (Mac.run, "volumes"), (Mac.run, "secrets"),
    (Mac.push, "direct"),
    (Fleet.map, "per_mac"), (Fleet.agent, "proxy"), (Fleet.agent, "secret"),
    (Sandbox.spawn, "keep_alive"),
]


@pytest.mark.parametrize("fn,kw", KWARGS, ids=lambda v: getattr(v, "__name__", str(v)))
def test_keyword_accepted(fn, kw):
    params = inspect.signature(fn).parameters
    assert kw in params or any(p.kind is p.VAR_KEYWORD for p in params.values()), \
        f"skill passes {kw}= to {fn.__qualname__}, which does not accept it"


# -- claims that were wrong elsewhere, pinned here -------------------------- #


def test_skill_does_not_claim_mac_can_expose():
    """`expose` is a Sandbox method. The landing page claimed otherwise for
    months; the skill must never pick that up."""
    assert not re.search(r"\bmac\.expose\(", SKILL_MD)
    assert not re.search(r"herds\.mac\(\)\.expose\(", SKILL_MD)


def test_skill_distinguishes_mac_map_from_fleet_map():
    """Mac.map is one machine; Fleet.map is all of them. Conflating the two is
    the exact confusion the docs shipped with."""
    assert "ON THIS MAC" in SKILL_MD, "mac.map example doesn't say it's one machine"
    assert "herds.fleet().map(" in SKILL_MD, "fleet-wide map isn't shown at all"


def test_shell_is_not_presented_as_an_agent_call():
    """Mac.shell attaches a pty and takes over the terminal. An agent calling it
    blind is a hang, so the skill has to mark it as the human path."""
    i = SKILL_MD.find("mac.shell()")
    assert i > 0, "shell isn't mentioned"
    assert "human" in SKILL_MD[i - 200:i + 200], "shell isn't flagged as the human front door"


# -- features that shipped and must be covered ------------------------------ #


@pytest.mark.parametrize("needle,feature", [
    ("herds.fleet().map(", "fleet-wide map"),
    ("mac.push(", "direct push"),
    ("mac.session(", "sessions"),
    ('herds.mac(tag=', "tag routing"),
    ("herds ssh", "interactive shell CLI"),
    ("herds child", "making a machine drivable"),
    ("herds use ", "driving a fleet"),
    ("herds.use(", "selecting a fleet from Python"),
])
def test_covers_shipped_feature(needle, feature):
    assert needle in SKILL_MD, f"skill doesn't mention {feature}"
