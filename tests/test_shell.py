"""`mac.shell()` — an interactive terminal on a Mac, without ssh.

Two things were missing and both are required for a shell you'd actually use:

* Sessions run on **pipes**, so a shell started there is non-interactive — no
  prompt, no colour, and vim/top/less refuse to draw. macOS `script` allocates a
  pty for a command, so we get a real terminal with no daemon or protocol
  change, which means it works against daemons already deployed.
* The **local** terminal must go raw, or input is line-buffered (nothing reaches
  the Mac until Return), Ctrl-C kills the local client instead of the remote job,
  and arrow keys arrive as escape sequences.
"""

from __future__ import annotations

import os
import sys

import pytest

from herds.sdk import _shell


def test_command_is_wrapped_in_a_pty():
    """Without `script` the remote shell sees pipes and never goes interactive."""
    cmd = _shell.pty_command()
    assert "script -q /dev/null" in cmd


def test_default_is_a_login_shell():
    assert "-il" in _shell.pty_command()


def test_explicit_command_is_quoted_not_interpolated():
    cmd = _shell.pty_command("vim 'my notes.md'; rm -rf /")
    # The whole thing must arrive as one argument to sh -c.
    assert "rm -rf /" in cmd
    assert cmd.count("script -q /dev/null") == 1


def test_term_is_propagated(monkeypatch):
    monkeypatch.setenv("TERM", "screen-256color")
    assert "TERM=screen-256color" in _shell.pty_command()


def test_term_falls_back_when_unset(monkeypatch):
    monkeypatch.delenv("TERM", raising=False)
    assert "xterm-256color" in _shell.pty_command()


def test_home_option_starts_in_the_users_home():
    """A 'real' shell that opens in a scratch workspace is disorienting."""
    assert 'cd "$HOME"' in _shell.pty_command(home=True)
    assert 'cd "$HOME"' not in _shell.pty_command(home=False)


def test_terminal_size_is_sane():
    rows, cols = _shell.terminal_size()
    assert rows > 0 and cols > 0


def test_raw_terminal_is_a_noop_without_a_tty(monkeypatch):
    """Under pytest stdin isn't a tty; this must not blow up or hang."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with _shell.raw_terminal() as engaged:
        assert engaged is False


def test_raw_terminal_restores_settings_on_exception(monkeypatch):
    """Leaving a terminal raw makes the user's shell look broken afterwards."""
    import pty
    import termios

    master, slave = pty.openpty()
    try:
        fake = os.fdopen(slave, "rb", buffering=0)
        monkeypatch.setattr(sys, "stdin", fake)

        # Compare the flags a user would notice rather than the whole struct:
        # macOS sets an extra lflag bit when reading back from a pty slave, so
        # even a plain tcsetattr round-trip isn't byte-identical.
        usable = termios.ECHO | termios.ICANON | termios.ISIG

        def lflags():
            return termios.tcgetattr(slave)[3] & usable

        before = lflags()
        assert before & termios.ECHO, "pty should start with echo on"

        with pytest.raises(RuntimeError):
            with _shell.raw_terminal() as engaged:
                assert engaged is True
                assert lflags() != before, "never entered raw mode"
                raise RuntimeError("boom")

        assert lflags() == before, "terminal was left raw — the user's shell would look broken"
    finally:
        os.close(master)


def test_shell_returns_the_session_when_not_attached(monkeypatch):
    """Programmatic use (scripts, notebooks) must stay possible."""
    from herds.sdk.mac import Mac

    made = {}

    class FakeSession:
        pass

    def fake_session(self, command, **kw):
        made["command"] = command
        made["kwargs"] = kw
        return FakeSession()

    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(Mac, "session", fake_session)

    out = Mac().shell(attach=False)
    assert isinstance(out, FakeSession)
    assert "script -q /dev/null" in made["command"]
    assert made["kwargs"]["inherit_home"] is True, "a shell without your tools is useless"


def test_shell_can_be_sandboxed_explicitly(monkeypatch):
    from herds.sdk.mac import Mac

    seen = {}
    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(Mac, "session",
                        lambda self, c, **kw: seen.update(kw) or object())
    Mac().shell(attach=False, real=False)
    assert seen["inherit_home"] is False


def test_shell_sets_term_and_size_env(monkeypatch):
    from herds.sdk.mac import Mac

    seen = {}
    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(Mac, "session",
                        lambda self, c, **kw: seen.update(kw) or object())
    Mac().shell(attach=False)
    env = seen["env"]
    assert "TERM" in env and env["LINES"].isdigit() and env["COLUMNS"].isdigit()


def test_ssh_command_is_registered():
    from typer.testing import CliRunner

    from herds.cli import app

    out = CliRunner().invoke(app, ["ssh", "--help"]).output
    assert "interactive terminal" in out.lower()
    assert "--sandboxed" in out


def test_detach_key_is_documented():
    """Ctrl-] must leave the remote process running, and users must know it."""
    import inspect

    from herds.sdk.mac import Mac

    assert "Ctrl-]" in inspect.getdoc(Mac.shell)
    # keyword-only, so the default lives in __kwdefaults__
    assert _shell.interact.__kwdefaults__["escape"] == "\x1d"  # Ctrl-]
