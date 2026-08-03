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


def _fake_mac(monkeypatch, capture: dict):
    """A Mac whose identity is already resolved, so no network is touched.

    shell() reads .name first (that's what pins the target), so the fake must
    provide it — patching only __init__ leaves the property reaching for a client.
    """
    from herds.sdk.mac import Mac

    class FakeSession:
        def send(self, d):
            capture.setdefault("sent", []).append(d)

        def close(self):
            capture["closed"] = True

    monkeypatch.setattr(Mac, "__init__",
                        lambda self, *a, **k: setattr(self, "machine_id", "mac_test"))
    monkeypatch.setattr(Mac, "name", property(lambda self: "TheMac"))
    monkeypatch.setattr(Mac, "session", lambda self, c, **kw: (
        capture.update({"command": c, "kwargs": kw}) or FakeSession()))
    return Mac()


def test_shell_returns_the_session_when_not_attached(monkeypatch):
    """Programmatic use (scripts, notebooks) must stay possible."""
    cap = {}
    out = _fake_mac(monkeypatch, cap).shell(attach=False)
    assert out is not None
    assert "script -q /dev/null" in cap["command"]
    assert cap["kwargs"]["inherit_home"] is True, "a shell without your tools is useless"


def test_shell_can_be_sandboxed_explicitly(monkeypatch):
    cap = {}
    _fake_mac(monkeypatch, cap).shell(attach=False, real=False)
    assert cap["kwargs"]["inherit_home"] is False


def test_shell_sets_term_and_size_env(monkeypatch):
    cap = {}
    _fake_mac(monkeypatch, cap).shell(attach=False)
    env = cap["kwargs"]["env"]
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


# --- which machine? --------------------------------------------------------- #
#
# `herds.mac()` resolves to the *idlest* online Mac. That's the right default for
# fanning work out with run()/map(), and the wrong one for a terminal: two
# invocations could land on two different machines with nothing on screen saying
# which. A shell must always target a named machine.

class _FakeClient:
    def __init__(self, machines):
        self._m = machines

    def list_machines(self):
        return self._m


def _mac(mid, name, status="online", chip="Apple M4"):
    return {"machine_id": mid, "name": name, "status": status, "info": {"chip": chip}}


def test_single_online_mac_needs_no_guess():
    from herds.cli import _pick_machine_for_shell

    c = _FakeClient([_mac("mac_only", "Studio"), _mac("mac_off", "Old", "offline")])
    assert _pick_machine_for_shell(c) == "mac_only"


def test_several_online_macs_refuses_to_pick(capsys):
    """Silently landing on a load-balanced Mac is how you rm -rf the wrong one."""
    import typer

    from herds.cli import _pick_machine_for_shell

    c = _FakeClient([_mac("mac_a", "MacBook"), _mac("mac_b", "Mini")])
    with pytest.raises(typer.Exit) as e:
        _pick_machine_for_shell(c)
    assert e.value.exit_code == 2
    out = capsys.readouterr()
    combined = out.out + out.err
    assert "more than one Mac" in combined
    assert "mac_a" in combined and "mac_b" in combined, "must list the candidates"


def test_no_online_mac_says_what_to_do(capsys):
    import typer

    from herds.cli import _pick_machine_for_shell

    with pytest.raises(typer.Exit) as e:
        _pick_machine_for_shell(_FakeClient([_mac("m", "X", "offline")]))
    assert e.value.exit_code == 1
    combined = "".join(capsys.readouterr())
    assert "herds host" in combined or "herds connect" in combined


def test_offline_macs_are_never_candidates():
    from herds.cli import _pick_machine_for_shell

    c = _FakeClient([_mac("on", "Up"), _mac("off1", "D1", "offline"),
                     _mac("off2", "D2", "offline")])
    assert _pick_machine_for_shell(c) == "on"


def test_attached_shell_announces_which_mac(monkeypatch, capsys):
    """The fix for 'which machine am I on?': say so before the first keystroke."""
    from herds.sdk import _shell
    from herds.sdk.mac import Mac

    cap = {}
    m = _fake_mac(monkeypatch, cap)
    monkeypatch.setattr(_shell, "interact", lambda s, **k: 0)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    m.shell()
    out = capsys.readouterr().out
    assert "TheMac" in out and "mac_test" in out, "must name the machine and its id"
    assert "Ctrl-]" in out
    assert "detached" in out, "must say when it lets go"
    assert cap.get("closed") is True
