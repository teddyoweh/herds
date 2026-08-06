"""`herds child` must never talk about hosting.

child and host are the same machinery — that's the point — but they answer
different questions. host: "be the hub a fleet joins". child: "how do I drive
this machine?". Sharing the implementation is fine; sharing the *output* is not,
because the whole reason `child` exists is that `host` framed it as
infrastructure.

The first version got this wrong in the way that mattered most: the child panel
was only written into `run_host`, which is the FOREGROUND path. Detaching is the
default, so on a real `herds child` that panel went into the log file and the
user saw the host panel instead — plus "Starting the host in the background…"
and, on a machine already live, "This Mac is already hosting".
"""

from __future__ import annotations

import pytest

from herds import host

STATE = {"pid": 4242, "port": 8787, "public_url": "https://studio.relay.herds.run",
         "token": "herds_sk_demo", "provider": "Herds", "permanent": True}

# Every panel a user can actually be shown, and how it's reached.
PANELS = [
    ("already-live", host._already_hosting_panel),
    ("background", host._running_panel),
]


@pytest.mark.parametrize("label,fn", PANELS, ids=[p[0] for p in PANELS])
def test_child_panels_never_say_host(label, fn, capsys):
    fn(STATE, child=True)
    out = capsys.readouterr().out.lower()

    assert "hosting" not in out, f"{label} panel tells a child it's hosting"
    assert "herds child" in out, f"{label} panel isn't titled as child"


@pytest.mark.parametrize("label,fn", PANELS, ids=[p[0] for p in PANELS])
def test_child_panels_lead_with_how_to_drive_it(label, fn, capsys):
    """The one question `herds child` answers."""
    fn(STATE, child=True)
    out = capsys.readouterr().out

    assert "herds use herds_sk_demo@studio.relay.herds.run" in out, \
        f"{label} panel doesn't show the command that drives this machine"


@pytest.mark.parametrize("label,fn", PANELS, ids=[p[0] for p in PANELS])
def test_host_panels_are_unchanged(label, fn, capsys):
    """child is additive: `herds host` still reads exactly as it did."""
    fn(STATE, child=False)
    out = capsys.readouterr().out

    assert "herds host" in out
    assert "drivable" not in out.lower()


def test_child_restart_hint_names_child(capsys):
    """Telling someone to run `herds host --restart` after `herds child` sends
    them to a different command than the one they ran."""
    host._already_hosting_panel(STATE, child=True)
    out = capsys.readouterr().out

    assert "herds child --restart" in out
    assert "herds host --restart" not in out


def test_the_detached_path_is_the_one_users_see():
    """Guard the actual bug: detaching is the default, so the background panel
    must take `child` — a child flag that only reaches the foreground panel is
    invisible in normal use."""
    import inspect

    for fn in (host._running_panel, host._already_hosting_panel,
               host.start_host_background, host.run_host):
        assert "child" in inspect.signature(fn).parameters, \
            f"{fn.__name__} can't be told it's a child"


# -- the wiring, not the panels -------------------------------------------- #
#
# The panels above are easy to get right in isolation and were: the bug was that
# nothing PASSED child= to them on the path users take. Testing a helper you fed
# the flag by hand proves nothing about that, so these drive the real entry
# points and read what a user would actually see.


@pytest.fixture
def already_live(monkeypatch, tmp_path):
    from herds import config
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(host, "_existing_host", lambda: STATE)
    return STATE


def test_detached_child_on_a_live_machine_is_child_framed(already_live, capsys):
    """Exactly what happens when you run `herds child` twice — and the first
    thing this got wrong: it answered "This Mac is already hosting"."""
    host.start_host_background(child=True)

    out = capsys.readouterr().out
    assert "herds child" in out
    assert "hosting" not in out.lower()
    assert "herds use herds_sk_demo@studio.relay.herds.run" in out


def test_detached_host_on_a_live_machine_is_still_host_framed(already_live, capsys):
    host.start_host_background(child=False)

    out = capsys.readouterr().out
    assert "already hosting" in out.lower()


def test_foreground_child_on_a_live_machine_is_child_framed(already_live, capsys):
    """`herds child --foreground` goes through run_host, a different early return."""
    host.run_host(child=True)

    out = capsys.readouterr().out
    assert "herds child" in out
    assert "hosting" not in out.lower()


def test_the_background_relaunch_reinvokes_child(monkeypatch):
    """The detached process re-execs the CLI; if it re-execs `host`, the real
    panel written to the log is the host one and the framing is lost for good."""
    assert host._relaunch_cmd([], verb="child")[-2:] == ["child", "--foreground"]
    assert host._relaunch_cmd([], verb="host")[-2:] == ["host", "--foreground"]
