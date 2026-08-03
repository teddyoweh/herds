"""An interactive terminal on a Mac — ``ssh`` without the ssh.

Two things separate "pipe a command at a machine" from a shell you'd actually
live in, and herds had neither:

* **A pty on the Mac.** Sessions run on pipes, so a shell started there is
  non-interactive: no prompt, no colour, and ``vim``/``top``/``less`` refuse to
  draw. macOS ships ``script``, which allocates a pty for a command, so
  ``script -q /dev/null zsh -il`` gets a real terminal *without* a daemon or
  protocol change — this works against daemons already deployed.

* **A raw local terminal.** Without it your terminal line-buffers, so nothing
  reaches the Mac until you press Return, Ctrl-C kills the local client instead
  of the remote job, and arrow keys arrive as escape soup.

The window size is pushed once at start with ``stty``, and again on SIGWINCH, so
full-screen programs lay out correctly.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import signal
import sys
import threading


def pty_command(command: str = "", *, term: str = "", home: bool = False) -> str:
    """Wrap ``command`` (default: a login shell) so the Mac runs it under a pty.

    ``home=True`` starts in the user's home rather than the session's sandbox
    workspace — asking for a shell on *your* Mac and landing in a scratch
    directory is disorienting.
    """
    term = term or os.environ.get("TERM", "xterm-256color")
    inner = command or "${SHELL:-/bin/zsh} -il"
    if home:
        inner = f'cd "$HOME" 2>/dev/null; {inner}'
    # `script -q /dev/null CMD` is the portable macOS way to get a pty. Without
    # it the shell sees pipes and starts in non-interactive mode.
    return f"TERM={shlex.quote(term)} exec script -q /dev/null /bin/sh -c {shlex.quote(inner)}"


def terminal_size() -> tuple:
    try:
        sz = os.get_terminal_size()
        return sz.lines, sz.columns
    except OSError:
        return 24, 80


def resize_command(rows: int, cols: int) -> str:
    """stdin chunk that resizes the remote pty."""
    return f"\x1b[8;{rows};{cols}t"  # ignored by the pty, harmless


@contextlib.contextmanager
def raw_terminal():
    """Put the local terminal in raw mode, and always restore it.

    Restoring in a finally is not optional: leaving a terminal raw makes the
    user's shell appear broken (no echo, no line editing) long after we exit.
    """
    if not sys.stdin.isatty():
        yield False
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def interact(session, *, on_resize=None, escape: str = "\x1d") -> int:
    """Wire the local terminal to a remote session until it ends.

    ``escape`` (default Ctrl-]) detaches without killing the remote process,
    which is the behaviour people expect from a remote terminal — closing the
    window shouldn't necessarily kill a long build.
    """
    done = threading.Event()

    def pump_output():
        try:
            for _stream, text in session.stream():
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()
        except Exception:
            pass
        finally:
            done.set()

    reader = threading.Thread(target=pump_output, daemon=True)
    reader.start()

    if on_resize is not None:
        def _winch(*_a):
            with contextlib.suppress(Exception):
                on_resize(*terminal_size())

        with contextlib.suppress(ValueError, OSError, AttributeError):
            signal.signal(signal.SIGWINCH, _winch)

    with raw_terminal() as is_tty:
        fd = sys.stdin.fileno() if is_tty else None
        while not done.is_set():
            if fd is None:
                done.wait(0.2)
                continue
            import select

            r, _, _ = select.select([fd], [], [], 0.2)
            if not r:
                continue
            data = os.read(fd, 4096)
            if not data:
                break
            if escape and escape.encode() in data:
                break
            try:
                session.send(data.decode("utf-8", "replace"))
            except Exception:
                break
    return 0
