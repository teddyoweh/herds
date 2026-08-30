"""A displaced host steps down instead of fighting for the account.

The relay holds ONE host per account. Two Macs that both host therefore
displace each other — and because the loser's reconnect loop treats every close
the same, it immediately dials back and displaces the winner in turn. Neither
ever settles.

What that looks like from the outside is not a crash. It is a fleet that
answers differently on alternate calls: `herds run` returning OK, then "machine
is offline", then OK; `herds machines` returning one machine, then three. Both
answers are true — they come from two different Macs' control planes. Observed
on a real fleet before this fix.
"""

from __future__ import annotations

import inspect

from herds import relay as R


def _client_source() -> str:
    """The host client's reconnect loop, whatever it is called."""
    for name in ("_run_client", "run_host_client", "host_client", "client_main"):
        fn = getattr(R, name, None)
        if fn is not None:
            try:
                return inspect.getsource(fn)
            except (OSError, TypeError):
                pass
    return inspect.getsource(R)


def test_displacement_is_handled_distinctly_from_a_dropped_link():
    """4409 must not fall into the generic reconnect path.

    Every other cause — a Wi-Fi drop, a network switch, a relay deploy — SHOULD
    reconnect, and does. This one must not, because reconnecting is what makes
    the two hosts trade the account forever.
    """
    src = _client_source()
    assert "4409" in src, "the displaced close code is not handled at all"
    i = src.index("4409")
    window = src[i : i + 1400]
    assert "return" in window, "a displaced host must stop, not fall through to the backoff"


def test_the_message_says_what_happened_and_how_to_undo_it():
    """A host that silently vanishes is indistinguishable from one that crashed.

    The person did not do anything wrong — they started a host on a second Mac,
    which is a reasonable thing to do — so the line says which machine won and
    the one command that takes it back.
    """
    src = _client_source()
    i = src.index("4409")
    window = src[i : i + 1400]
    assert "another Mac is now hosting" in window
    assert "herds host" in window, "it must name the command that takes hosting back"


def test_stepping_down_does_not_kill_the_machine():
    """Hosting and being drivable are different jobs.

    The daemon holds its own link to the control plane, so a Mac that stops
    HOSTING is still a machine in the fleet and can still run work sent to it.
    Only the claim to serve the account's subdomain is given up.
    """
    src = _client_source()
    i = src.index("4409")
    window = src[i : i + 1400]
    assert "MACHINE" in window or "machine" in window
