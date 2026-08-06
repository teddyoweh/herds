"""`python -m herds` — the way in that survives a PATH that doesn't cooperate.

`pip install herds` writes a `herds` console script into the installing
environment's scripts dir. For `pip install --user` on macOS that's
~/.local/bin or ~/Library/Python/3.x/bin — neither on a default PATH. The
install reports success and the command still isn't found, which reads as a
broken package rather than a shell config gap.

No package can put a script on someone's PATH. It can guarantee a second
entry point, and it can say where the script actually went.
"""

from __future__ import annotations

import runpy

from herds import __main__ as m


def test_module_exposes_a_main():
    assert callable(m.main)


def test_silent_when_the_command_is_reachable(monkeypatch, capsys):
    monkeypatch.setattr(m.shutil, "which", lambda _: "/usr/local/bin/herds")

    m._warn_if_not_on_path()

    assert capsys.readouterr().err == "", "nagged a user whose PATH is fine"


def test_warns_with_the_actual_directory_when_unreachable(monkeypatch, capsys, tmp_path):
    script = tmp_path / "herds"
    script.write_text("#!/bin/sh\n")
    monkeypatch.setattr(m.shutil, "which", lambda _: None)
    monkeypatch.setattr(m, "_console_script", lambda: str(script))

    m._warn_if_not_on_path()

    err = capsys.readouterr().err
    assert str(tmp_path) in err, "didn't say where the script is"
    # It used to print an export line for the user to run by hand. There's now a
    # command that does it, and `python -m herds` is how you reach it when the
    # bare command isn't found — so the hint has to name that, not homework.
    assert "python3 -m herds link" in err, "didn't offer the one-command fix"


def test_silent_when_no_script_can_be_found(monkeypatch, capsys):
    """Running from a source checkout, say — nothing useful to point at."""
    monkeypatch.setattr(m.shutil, "which", lambda _: None)
    monkeypatch.setattr(m, "_console_script", lambda: None)

    m._warn_if_not_on_path()

    assert capsys.readouterr().err == ""


def test_console_script_lookup_never_raises(monkeypatch):
    """sysconfig schemes vary by platform, packager, and Python build. A scheme
    that doesn't exist is an ordinary answer, not a crash — and this runs on
    every `python -m herds`, so raising here would break the command itself."""
    def boom(*_a, **_k):
        raise KeyError("no such scheme")

    monkeypatch.setattr(m.sysconfig, "get_path", boom)

    assert m._console_script() is None


def test_a_broken_lookup_still_runs_the_cli(monkeypatch, capsys):
    """Belt and braces: even if the diagnostic itself explodes, the CLI runs."""
    def boom(*_a, **_k):
        raise RuntimeError("sysconfig is having a day")

    monkeypatch.setattr(m, "_warn_if_not_on_path", boom)
    called = []
    monkeypatch.setattr("herds.cli.app", lambda: called.append(True))

    m.main()

    assert called == [True]


def test_the_warning_does_not_block_the_command(monkeypatch, capsys):
    """The note is advice, not a failure: the invocation still dispatches."""
    monkeypatch.setattr(m.shutil, "which", lambda _: None)
    monkeypatch.setattr(m, "_console_script", lambda: "/nowhere/bin/herds")
    called = []
    monkeypatch.setattr("herds.cli.app", lambda: called.append(True))

    m.main()

    assert called == [True], "warning short-circuited the CLI"
    assert "not on your PATH" in capsys.readouterr().err


def test_python_dash_m_runs_the_cli(monkeypatch):
    """The whole point: `python -m herds` reaches the same app object."""
    called = []
    monkeypatch.setattr("herds.cli.app", lambda: called.append(True))
    monkeypatch.setattr("herds.__main__.shutil.which", lambda _: "/usr/bin/herds")

    runpy.run_module("herds", run_name="__main__")

    assert called == [True]
