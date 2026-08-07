"""Many fleets on one machine, and the pair that must never come apart.

A control plane and the API key that opens it are one credential in two halves.
Keeping them in two single-valued files is what let them drift: `herds host`
wrote one, `herds connect` wrote the other, `herds auth` wrote neither, and each
time the symptom was a good key at the wrong door — "missing API key", or a bare
401 naming neither side.

contexts.json is the registry; the active entry is *projected* into
config.json + credentials.json, so everything that already reads those (the
daemon, HerdsClient, `herds host`) keeps working untouched and a switch moves
both halves or neither.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from herds import cli as cli_mod
from herds import config
from herds.cli import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", tmp_path / "credentials.json")
    monkeypatch.setattr(config, "CONTEXTS_PATH", tmp_path / "contexts.json")
    monkeypatch.setattr(config, "AUTH_PATH", tmp_path / "auth.json")
    for n in ("VOLUMES_DIR", "SANDBOXES_DIR", "IMAGES_DIR", "LOGS_DIR", "RUN_DIR"):
        monkeypatch.setattr(config, n, tmp_path / n.lower())
    for e in ("HERDS_API_KEY", "HERDS_DEVICE_TOKEN", "HERDS_CONTROL_PLANE"):
        monkeypatch.delenv(e, raising=False)
    return tmp_path


@pytest.fixture
def fleet_ok(monkeypatch):
    """`herds use` probes a fleet before adopting it; make that succeed."""
    monkeypatch.setattr(cli_mod, "_probe_fleet",
                        lambda url, key: ([{"machine_id": "mac_1", "status": "online"},
                                           {"machine_id": "mac_2", "status": "offline"}], None))


# -- the store -------------------------------------------------------------- #


def test_activate_projects_into_the_files_everything_else_reads(home):
    ctxs = config.Contexts.load()
    ctxs.add("studio", "https://studio.relay.herds.run", "herds_sk_studio")
    ctxs.activate("studio")

    assert config.Config.load().control_plane == "https://studio.relay.herds.run"
    assert config.Credentials.load().api_key == "herds_sk_studio"


def test_switching_moves_both_halves(home):
    ctxs = config.Contexts.load()
    ctxs.add("a", "https://a.relay.herds.run", "key_a")
    ctxs.add("b", "https://b.relay.herds.run", "key_b")

    ctxs.activate("a")
    assert (config.Config.load().control_plane, config.Credentials.load().api_key) == \
           ("https://a.relay.herds.run", "key_a")

    ctxs.activate("b")
    assert (config.Config.load().control_plane, config.Credentials.load().api_key) == \
           ("https://b.relay.herds.run", "key_b"), "a key was left behind at the old door"


def test_a_pre_contexts_install_is_adopted_not_ignored(home):
    """Machines set up before contexts existed still drive exactly one fleet."""
    cfg = config.Config.load()
    cfg.control_plane = "https://teddyoweh.relay.herds.run"
    cfg.save()
    creds = config.Credentials.load()
    creds.api_key = "herds_sk_old"
    creds.save()
    assert not (home / "contexts.json").exists()

    ctxs = config.Contexts.load()

    assert ctxs.current == "teddyoweh"
    assert ctxs.active.api_key == "herds_sk_old"


def test_a_bare_default_install_has_no_fleets(home):
    """Nothing configured → don't invent a context pointing at localhost."""
    assert config.Contexts.load().items == {}


def test_contexts_file_is_not_world_readable(home):
    ctxs = config.Contexts.load()
    ctxs.add("s", "https://s.relay.herds.run", "key")
    ctxs.activate("s")

    assert ((home / "contexts.json").stat().st_mode & 0o777) == 0o600, "it holds API keys"


def test_forgetting_the_active_fleet_falls_back(home):
    ctxs = config.Contexts.load()
    ctxs.add("a", "https://a.relay.herds.run", "key_a")
    ctxs.add("b", "https://b.relay.herds.run", "key_b")
    ctxs.activate("a")

    assert ctxs.remove("a")
    assert ctxs.current == "b", "removing the active fleet left nothing selected"


def test_corrupt_contexts_file_does_not_break_the_cli(home):
    (home / "contexts.json").write_text("{not json")
    assert config.Contexts.load().items == {}      # falls back, never raises


@pytest.mark.parametrize("url,expected", [
    ("https://studio.relay.herds.run", "studio"),
    ("http://127.0.0.1:8787", "local"),
    ("http://localhost:9000", "local"),
    ("https://work.example.com/", "work"),
])
def test_names_come_from_the_link(url, expected):
    """The relay already assigns a unique subdomain, so the first label is
    unique by construction — no separate registry, no collisions to resolve."""
    assert config.context_name_for(url) == expected


# -- the CLI ---------------------------------------------------------------- #


def test_use_adds_a_fleet_from_a_token_and_activates_it(home, fleet_ok):
    r = runner.invoke(app, ["use", "herds_sk_abc@studio.relay.herds.run"])

    assert r.exit_code == 0, r.output
    assert "studio" in r.output
    assert config.Config.load().control_plane == "https://studio.relay.herds.run"
    assert config.Credentials.load().api_key == "herds_sk_abc"


def test_use_reports_what_you_are_now_driving(home, fleet_ok):
    """The name matters: pasting a token must tell you where it landed."""
    out = runner.invoke(app, ["use", "herds_sk_abc@studio.relay.herds.run"]).output
    assert "studio" in out and "2 machine" in out


def test_use_switches_by_name_without_a_token(home, fleet_ok):
    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    runner.invoke(app, ["use", "herds_sk_b@b.relay.herds.run"])

    r = runner.invoke(app, ["use", "a"])

    assert r.exit_code == 0, r.output
    assert config.Config.load().control_plane == "https://a.relay.herds.run"
    assert config.Credentials.load().api_key == "herds_sk_a"


def test_use_rejects_an_unreachable_fleet(home, monkeypatch):
    """Don't store a credential that doesn't work — that's how you get a
    context that silently 401s later."""
    monkeypatch.setattr(cli_mod, "_probe_fleet", lambda url, key: (None, "missing API key"))

    r = runner.invoke(app, ["use", "herds_sk_bad@nope.relay.herds.run"])

    assert r.exit_code == 1
    assert config.Contexts.load().items == {}


def test_use_with_an_unknown_name_fails_and_lists(home, fleet_ok):
    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    r = runner.invoke(app, ["use", "typo"])
    assert r.exit_code == 1
    assert "a" in r.output


def test_as_overrides_the_derived_name(home, fleet_ok):
    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run", "--as", "carltons"])
    assert "carltons" in config.Contexts.load().items


def test_use_with_no_argument_lists(home, fleet_ok):
    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    out = runner.invoke(app, ["use"]).output
    assert "a.relay.herds.run" in out


def test_forget_removes_only_local_credentials(home, fleet_ok):
    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    r = runner.invoke(app, ["forget", "a"])
    assert r.exit_code == 0
    assert config.Contexts.load().items == {}


# -- the SDK ---------------------------------------------------------------- #


def test_sdk_use_is_process_local(home, fleet_ok):
    """`herds.use()` in a script must not repoint the whole machine — a job
    targeting one fleet shouldn't change what the next shell command drives."""
    import herds

    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    runner.invoke(app, ["use", "herds_sk_b@b.relay.herds.run"])
    runner.invoke(app, ["use", "a"])          # machine is on 'a'

    herds.use("b")                             # process points at 'b'…

    assert config.Config.load().control_plane == "https://a.relay.herds.run", \
        "SDK switch leaked into the machine's config"


def test_sdk_contexts_lists_active_first(home, fleet_ok):
    import herds

    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    runner.invoke(app, ["use", "herds_sk_b@b.relay.herds.run"])   # b is active

    names = [c["name"] for c in herds.contexts()]
    assert names[0] == "b" and herds.contexts()[0]["active"] is True


def test_sdk_unknown_context_names_what_it_has(home, fleet_ok):
    import herds
    from herds import HerdsError

    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])

    with pytest.raises(HerdsError) as e:
        herds.use("ghost")
    assert "ghost" in str(e.value) and "a" in str(e.value)


def test_sdk_context_selects_the_right_pair(home, fleet_ok):
    import herds

    runner.invoke(app, ["use", "herds_sk_a@a.relay.herds.run"])
    runner.invoke(app, ["use", "herds_sk_b@b.relay.herds.run"])

    c = herds.configure(context="a")

    assert c.control_plane == "https://a.relay.herds.run"
    assert c.api_key == "herds_sk_a", "picked a fleet but kept the other one's key"


# -- tokens damaged in transit ---------------------------------------------- #
#
# A token travels by copy-paste — Messages, Slack, a terminal that wrapped it
# mid-string — and arrives altered. A real one came back with × (U+00D7) where
# x should be, courtesy of a phone keyboard, plus two spaces from the panel
# wrapping the line. That failed with a UnicodeEncodeError from inside httpx,
# which names none of what actually happened.


@pytest.mark.parametrize("mangled,clean", [
    # The real one, exactly as it was pasted back.
    ("herds_sk_Fy0×BAH14QBggMIpj0or1QM×LS_rsZSg@m7d00b43. relay.herds. run",
     "herds_sk_Fy0xBAH14QBggMIpj0or1QMxLS_rsZSg@m7d00b43.relay.herds.run"),
    ("herds_sk_abc @ a.relay.herds.run", "herds_sk_abc@a.relay.herds.run"),
    ("herds_sk_a–b@a.relay.herds.run", "herds_sk_a-b@a.relay.herds.run"),
])
def test_normalize_repairs_a_pasted_token(mangled, clean):
    out, changed = config.normalize_token(mangled)
    assert out == clean
    assert changed is True, "repaired the token but didn't flag it"


def test_surrounding_whitespace_is_trimmed_quietly():
    """A trailing newline is how every paste arrives. Normalise it, but don't
    announce a repair — that would cry wolf on every single use."""
    out, changed = config.normalize_token("herds_sk_abc@a.relay.herds.run\n")
    assert out == "herds_sk_abc@a.relay.herds.run"
    assert changed is False


def test_normalize_leaves_a_good_token_alone():
    good = "herds_sk_Fy0xBAH14QBggMIpj0or1QMxLS_rsZSg@m7d00b43.relay.herds.run"
    out, changed = config.normalize_token(good)
    assert out == good and changed is False


def test_use_accepts_a_mangled_token(home, fleet_ok):
    """The whole point: paste what your phone gave you and it still works."""
    r = runner.invoke(app, ["use", "herds_sk_a×b@a.relay.herds.run"])

    assert r.exit_code == 0, r.output
    assert config.Contexts.load().items["a"].api_key == "herds_sk_axb", \
        "stored the token with the substituted character still in it"


def test_use_says_it_repaired_the_token(home, fleet_ok):
    out = runner.invoke(app, ["use", "herds_sk_a×b@a.relay.herds.run"]).output
    assert "Cleaned up" in out, "silently altered what the user pasted"


# -- unreachable fleets explain themselves ---------------------------------- #


@pytest.mark.parametrize("exc,expect", [
    (Exception("[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error (_ssl.c:1077)"),
     "isn't serving yet"),
    (Exception("[Errno 8] nodename nor servname provided"), "doesn't resolve"),
    (Exception("[Errno 61] Connection refused"), "Couldn't reach"),
])
def test_reachability_errors_are_translated(exc, expect):
    """The relay issues a cert when a machine connects, so a link whose machine
    never came up fails in the TLS handshake. Surfacing `_ssl.c:1077` to someone
    who just pasted a token explains nothing and blames the wrong thing."""
    msg = cli_mod._reachability_hint(exc, "https://m7d00b43.relay.herds.run")
    assert expect in msg
    assert "_ssl.c" not in msg
