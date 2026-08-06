"""`herds link` — the closest thing to "pip install put it on my PATH".

pip writes the console script into whichever environment did the install. With
`pip install --user` on macOS that's ~/.local/bin or ~/Library/Python/3.x/bin,
neither on a default PATH, so pip reports success and `herds` isn't found.

No package can fix that at install time: wheels have no post-install hook, and
pip only runs setup.py hooks when it can't get a wheel. So this is a deliberate
second command — and it has to be reachable when the first one isn't, which is
why `python -m herds link` is the documented form.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from herds import link as linkmod


@pytest.fixture
def script(tmp_path, monkeypatch):
    """A stand-in for this install's console script."""
    s = tmp_path / "env" / "bin" / "herds"
    s.parent.mkdir(parents=True)
    s.write_text("#!/bin/sh\n")
    s.chmod(0o755)
    monkeypatch.setattr(linkmod, "herds_script", lambda: str(s))
    return s


@pytest.fixture
def on_path(tmp_path, monkeypatch):
    """A writable directory the shell already searches."""
    d = tmp_path / "bin"
    d.mkdir()
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}/usr/bin{os.pathsep}/bin")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    return d


def test_links_into_a_directory_already_on_path(script, on_path):
    r = linkmod.link()

    assert r["ok"] and r["on_path"]
    dest = Path(r["dest"])
    assert dest.is_symlink()
    assert dest.resolve() == script.resolve()


def test_it_is_a_symlink_not_a_copy(script, on_path):
    """Upgrading the package must upgrade what the link resolves to. A copy
    would pin whatever bytes existed the day you ran it."""
    r = linkmod.link()
    script.write_text("#!/bin/sh\n# upgraded\n")

    assert "upgraded" in Path(r["dest"]).read_text()


def test_running_it_twice_is_a_no_op(script, on_path):
    first = linkmod.link()
    second = linkmod.link()

    assert second["ok"] and second["already"] is True
    assert second["dest"] == first["dest"]


def test_it_will_not_clobber_someone_elses_herds(script, on_path):
    other = on_path / "herds"
    other.write_text("#!/bin/sh\n# not ours\n")

    r = linkmod.link()

    assert not r["ok"] and r["reason"] == "exists"
    assert "not ours" in other.read_text(), "overwrote a binary we didn't own"


def test_force_replaces_it(script, on_path):
    (on_path / "herds").write_text("#!/bin/sh\n# not ours\n")

    r = linkmod.link(force=True)

    assert r["ok"]
    assert Path(r["dest"]).resolve() == script.resolve()


def test_it_never_links_into_the_active_virtualenv(script, tmp_path, monkeypatch):
    """Linking into the venv you're running from is a no-op that vanishes the
    moment you deactivate — the exact situation the user is trying to escape."""
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
    monkeypatch.setenv("PATH", f"{venv}{os.pathsep}/usr/bin")

    d, on_path = linkmod.target_dir()

    assert not str(d).startswith(str(tmp_path / "venv"))


def test_falls_back_and_says_it_is_not_on_path(script, tmp_path, monkeypatch):
    """Nowhere writable on PATH: still link somewhere sensible, but the caller
    has to be told, or the user is left with a link the shell can't see."""
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(linkmod, "PREFERRED", (str(tmp_path / ".local" / "bin"),))

    r = linkmod.link()

    assert r["ok"] and r["on_path"] is False
    assert Path(r["dest"]).is_symlink()


def test_remove_undoes_it(script, on_path):
    linkmod.link()
    r = linkmod.unlink()

    assert r["ok"]
    assert not (on_path / "herds").exists()


def test_remove_refuses_to_delete_a_real_binary(script, on_path):
    real = on_path / "herds"
    real.write_text("#!/bin/sh\n# somebody's actual herds\n")

    r = linkmod.unlink()

    assert not r["ok"] and r["reason"] == "not-a-link"
    assert real.exists(), "deleted a file we didn't create"


def test_missing_script_is_reported_not_raised(monkeypatch, on_path):
    monkeypatch.setattr(linkmod, "herds_script", lambda: None)

    r = linkmod.link()

    assert not r["ok"] and r["reason"] == "no-script"


def test_the_not_found_hint_points_at_link(monkeypatch, capsys, tmp_path):
    """`python -m herds` is how you reach `link` when `herds` isn't found, so
    the hint has to name it — printing a manual export line instead leaves the
    user to do by hand the thing there's now a command for."""
    from herds import __main__ as m

    s = tmp_path / "bin" / "herds"
    s.parent.mkdir(parents=True)
    s.write_text("")
    monkeypatch.setattr(m.shutil, "which", lambda _: None)
    monkeypatch.setattr(m, "_console_script", lambda: str(s))

    m._warn_if_not_on_path()

    assert "python3 -m herds link" in capsys.readouterr().err
