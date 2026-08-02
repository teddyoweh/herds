"""Pull bytes to the Mac directly instead of pushing them through the relay.

`push`/`Volume.put` send every byte from the caller, through the control plane
and relay, to the Mac. Measured on a real fleet: ~24 MB/s when the control plane
is local, but **0.23-0.75 MB/s through the relay** — so a 572MB app bundle takes
13-41 minutes and saturates the relay for every other machine while it runs.

The Mac has its own internet connection. For anything fetchable, downloading it
there costs the relay nothing and goes at the Mac's own speed.
"""

from __future__ import annotations

import pytest

from herds.sdk.mac import _NAME_OK, Mac


class _R:
    ok, exit_code, stderr = True, 0, ""

    def __init__(self, stdout=""):
        self.stdout = stdout


@pytest.fixture
def captured(monkeypatch):
    """Capture the shell script fetch() builds, without running anything."""
    seen = {}

    def fake_run(self, command, **kw):
        seen["script"] = command
        seen["kwargs"] = kw
        return _R('{"path":"/tmp/x","bytes":123}')

    monkeypatch.setattr(Mac, "run", fake_run)
    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: None)
    return seen


def test_fetch_returns_parsed_metadata(captured):
    out = Mac().fetch("https://example.com/a.dmg")
    assert out["bytes"] == 123
    assert out["path"] == "/tmp/x"
    assert "seconds" in out and "mb_per_s" in out


def test_volume_target_lands_in_the_volume(captured):
    Mac().fetch("https://example.com/a.bin", "model.bin", volume="weights")
    s = captured["script"]
    assert "/volumes/weights" in s
    assert "name='model.bin'" in s or 'name=model.bin' in s


def test_sandbox_target_lands_in_the_workspace(captured):
    Mac().fetch("https://example.com/a.bin", "x", sandbox="sbx1")
    assert "/sandboxes/sbx1/workspace" in captured["script"]


def test_default_target_is_cwd(captured):
    Mac().fetch("https://example.com/a.bin")
    assert 'base="$PWD"' in captured["script"]


def test_filename_is_derived_from_the_url(captured):
    Mac().fetch("https://example.com/downloads/Wispr.dmg?token=abc")
    assert "Wispr.dmg" in captured["script"]


def test_absolute_dest_is_used_verbatim(captured):
    Mac().fetch("https://example.com/a", "/tmp/here.bin")
    # The script branches on a leading slash rather than always joining to base.
    assert 'case "$name" in /*)' in captured["script"]


@pytest.mark.parametrize("bad", ["../../etc", "$(id)", "a b", "a;rm -rf /", ""])
def test_unsafe_volume_names_are_refused_not_escaped(captured, bad):
    """Refusing beats escaping: a name can never break out of the herds home."""
    with pytest.raises(ValueError):
        Mac().fetch("https://example.com/a", "x", volume=bad)


@pytest.mark.parametrize("good", ["weights", "my-vol", "a.b_c", "v1"])
def test_ordinary_names_are_accepted_intact(captured, good):
    """Regression: quoting once sliced the first and last character off names."""
    Mac().fetch("https://example.com/a", "f.bin", volume=good)
    assert f"/volumes/{good}" in captured["script"]


def test_url_is_shell_quoted(captured):
    Mac().fetch("https://example.com/a;touch /tmp/pwned")
    s = captured["script"]
    assert "'https://example.com/a;touch /tmp/pwned'" in s


def test_headers_are_quoted(captured):
    Mac().fetch("https://example.com/a", headers={"Authorization": "Bearer x y"})
    assert "-H 'Authorization: Bearer x y'" in captured["script"]


def test_resume_is_on_by_default_and_can_be_disabled(captured):
    Mac().fetch("https://example.com/a")
    assert "-C -" in captured["script"]
    Mac().fetch("https://example.com/a", resume=False)
    assert "-C -" not in captured["script"]


def test_runs_against_the_real_machine_by_default(captured):
    """A sandboxed fetch would roll back — the file has to persist."""
    Mac().fetch("https://example.com/a")
    assert captured["kwargs"]["inherit_home"] is True


def test_volume_and_sandbox_are_mutually_exclusive(captured):
    with pytest.raises(ValueError):
        Mac().fetch("https://example.com/a", volume="v", sandbox="s")


def test_failure_raises_with_stderr(monkeypatch):
    class Bad:
        ok, exit_code, stdout, stderr = False, 22, "", "curl: (22) 404"

    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(Mac, "run", lambda self, c, **k: Bad())
    from herds.sdk.client import HerdsError

    with pytest.raises(HerdsError, match="404"):
        Mac().fetch("https://example.com/missing")


def test_name_pattern_bounds_length():
    assert _NAME_OK.match("a" * 64)
    assert not _NAME_OK.match("a" * 65)
