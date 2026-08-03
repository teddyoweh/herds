"""Selecting which Mac — by name, id, prefix or tag.

Only the exact `mac_xxxxxxxx` id used to resolve, so `herds ssh "Mac mini"`
failed with "machine Mac mini is offline" — wrong twice over: the machine was
online, and the name was never the problem. People address machines by name.
"""
from __future__ import annotations

import tempfile, os
import pytest
from fastapi import HTTPException

from herds.control import Hub, _match_machine
from herds.control.store import Store
from herds.protocol import MachineStatus


@pytest.fixture
def env():
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    s = Store(db)
    s.upsert_machine("mac_1a7aa9a7", "MacBook Pro (Apple M4 Pro)", "o", {}, MachineStatus.ONLINE, 0)
    s.upsert_machine("mac_ed74b9b0", "Teddys Mac mini", "o", {}, MachineStatus.ONLINE, 0)
    s.add_tags("mac_ed74b9b0", ["ci", "builder"])
    return s, Hub(s)


@pytest.mark.parametrize("ident,expected", [
    ("mac_ed74b9b0", "mac_ed74b9b0"),               # exact id
    ("Teddys Mac mini", "mac_ed74b9b0"),            # exact name
    ("teddys mac mini", "mac_ed74b9b0"),            # name, case-insensitive
    ("mac_ed74", "mac_ed74b9b0"),                   # id prefix
    ("mini", "mac_ed74b9b0"),                       # name substring
    ("MacBook", "mac_1a7aa9a7"),                    # the other one
    ("ci", "mac_ed74b9b0"),                         # tag
    ("builder", "mac_ed74b9b0"),                    # another tag
])
def test_selectors(env, ident, expected):
    s, hub = env
    assert _match_machine(s, hub, ident, "o") == expected


def test_ambiguous_prefix_refuses_and_lists(env):
    """Guessing between two Macs is the bug this whole change removes."""
    s, hub = env
    with pytest.raises(HTTPException) as e:
        _match_machine(s, hub, "mac_", "o")
    assert e.value.status_code == 409
    assert "matches 2 machines" in e.value.detail
    assert "mac_1a7aa9a7" in e.value.detail and "mac_ed74b9b0" in e.value.detail


def test_unknown_lists_what_is_available(env):
    s, hub = env
    with pytest.raises(HTTPException) as e:
        _match_machine(s, hub, "nope", "o")
    assert e.value.status_code == 404
    assert "Known:" in e.value.detail


def test_exact_name_beats_a_substring_of_another(env):
    """Precision order matters: an exact name must never lose to a substring."""
    s, hub = env
    s.upsert_machine("mac_zzz", "mini", "o", {}, MachineStatus.ONLINE, 0)
    # "mini" is now an exact name AND a substring of "Teddys Mac mini"
    assert _match_machine(s, hub, "mini", "o") == "mac_zzz"


def test_offline_machines_still_resolve(env):
    """Resolution is a lookup; liveness is a separate, clearer error."""
    s, hub = env
    s.upsert_machine("mac_off", "Old iMac", "o", {}, MachineStatus.OFFLINE, 0)
    assert _match_machine(s, hub, "Old iMac", "o") == "mac_off"


def test_empty_registry_is_a_clear_404():
    db = os.path.join(tempfile.mkdtemp(), "e.db")
    s = Store(db)
    with pytest.raises(HTTPException) as e:
        _match_machine(s, Hub(s), "anything", "o")
    assert e.value.status_code == 404
