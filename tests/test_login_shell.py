"""A string command has to run through a shell that exists on this machine.

macOS ships zsh as the login shell, so `/bin/zsh -lc` was hardcoded. On Linux
there usually is no /bin/zsh — a Raspberry Pi running `herds child` registered
fine, reported online, and then failed *every single command* with
"No such file or directory: '/bin/zsh'". The machine looked healthy and was
completely unusable.

-l is worth keeping: it sources the user's profile, which is where Homebrew,
asdf and nvm put things on PATH. So resolve the shell, don't assume it.
"""

from __future__ import annotations

import os

from herds.daemon import executor


def test_prefers_the_users_own_shell(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr(os.path, "exists", lambda p: p == "/bin/bash")
    assert executor._login_shell() == "/bin/bash"


def test_falls_back_when_zsh_is_absent(monkeypatch):
    """The Raspberry Pi case: Debian has bash and sh, no zsh."""
    monkeypatch.delenv("SHELL", raising=False)
    present = {"/bin/bash", "/bin/sh"}
    monkeypatch.setattr(os.path, "exists", lambda p: p in present)

    assert executor._login_shell() == "/bin/bash"


def test_last_resort_is_posix_sh(monkeypatch):
    """A container with neither zsh nor bash still has to run commands."""
    monkeypatch.delenv("SHELL", raising=False)
    monkeypatch.setattr(os.path, "exists", lambda p: p == "/bin/sh")

    assert executor._login_shell() == "/bin/sh"


def test_never_returns_something_that_does_not_exist(monkeypatch):
    """Even with nothing found, return the one path POSIX guarantees rather
    than a name that will fail with ENOENT at exec time."""
    monkeypatch.setenv("SHELL", "/bin/fish")
    monkeypatch.setattr(os.path, "exists", lambda p: False)

    assert executor._login_shell() == "/bin/sh"


def test_a_bogus_SHELL_is_ignored(monkeypatch):
    """$SHELL can name a shell that was uninstalled; don't exec into ENOENT."""
    monkeypatch.setenv("SHELL", "/usr/local/bin/nonexistent")
    present = {"/bin/bash", "/bin/sh"}
    monkeypatch.setattr(os.path, "exists", lambda p: p in present)

    assert executor._login_shell() == "/bin/bash"


def test_the_real_machine_has_the_shell_it_picks():
    """No mocks: whatever it chooses here must actually be executable."""
    sh = executor._login_shell()
    assert os.path.exists(sh), f"{sh} doesn't exist"
    assert os.access(sh, os.X_OK), f"{sh} isn't executable"


def test_no_call_site_still_execs_zsh_directly():
    """The bug was three separate call sites. Fixing two would have left a
    machine that works for `run` and dies on sessions — so check the pattern
    that matters (zsh in an argv), not the string (it's a fine candidate)."""
    import pathlib
    import re

    src = pathlib.Path(executor.__file__).read_text()
    bad = re.findall(r'\[\s*"/bin/(?:zsh|bash)"\s*,\s*"-l?c"', src)
    assert not bad, f"still exec'ing a hardcoded shell: {bad}"
