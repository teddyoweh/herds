"""Two hosts must not start at once — the claim that stops `child -b` racing itself.

The bug this covers is not hypothetical and was not found by reading. On a real
Mac mini, `herds child -b` armed the KeepAlive agent and then started a host
itself, launchd's `RunAtLoad` started one at the same instant, and both bound
127.0.0.1:8787. The loser retried five times and printed "control plane keeps
crashing — shutting down the host". What was left behind was seven herds
processes, two control planes (8787 and 8788, the second from the port
auto-bump), five API keys in `host.db` because every restart minted another,
and `herds child status` reporting "Not hosting" the entire time.

The two liveness guards in `run_host` cannot catch it: both ask "is a host
SERVING?", and a host that is still negotiating its tunnel is not serving yet.
Startup is the window, so startup is what has to be serialized.
"""

from __future__ import annotations

import multiprocessing as mp
import os

import pytest

from herds import host as H


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Point HERDS_HOME at a scratch dir so a real fleet is never touched."""
    monkeypatch.setattr(H.config, "HERDS_HOME", tmp_path)
    monkeypatch.setattr(H.config, "ensure_dirs", lambda: tmp_path.mkdir(exist_ok=True))
    yield


def test_second_claim_is_refused_while_the_first_is_held():
    assert H.acquire_start_lock() == os.getpid()
    # The refusal is the whole feature: without it both callers proceed to bind
    # the same port and one of them dies.
    assert H.acquire_start_lock(timeout=0.0) is None
    H.release_start_lock()
    assert H.acquire_start_lock() == os.getpid()
    H.release_start_lock()


def test_release_lets_the_next_starter_through():
    assert H.acquire_start_lock() is not None
    H.release_start_lock()
    assert H.acquire_start_lock(timeout=0.0) is not None
    H.release_start_lock()


def test_a_dead_holders_lock_is_reclaimed(tmp_path):
    """A Mac must never be left unhostable by a starter that died mid-start.

    A lock nobody can break is worse than the race it prevents: the machine
    stops being able to host at all, and the only fix is deleting a file the
    owner has never heard of.
    """
    # A pid that cannot be alive: written by hand, never reaped.
    lock = H._start_lock_file()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("999999")
    assert H.acquire_start_lock(timeout=0.0) == os.getpid()
    H.release_start_lock()


def test_a_corrupt_lock_is_reclaimed():
    """Empty or garbage contents must not wedge the Mac either."""
    lock = H._start_lock_file()
    lock.parent.mkdir(parents=True, exist_ok=True)
    for junk in ("", "   ", "not-a-pid"):
        lock.write_text(junk)
        assert H.acquire_start_lock(timeout=0.0) == os.getpid()
        H.release_start_lock()


def _claim(home_str, q):
    """Claim in a genuinely separate process — the real shape of the bug."""
    from pathlib import Path

    from herds import host as h

    h.config.HERDS_HOME = Path(home_str)
    h.config.ensure_dirs = lambda: None
    q.put(h.acquire_start_lock(timeout=0.0) is not None)


def test_only_one_of_two_processes_wins(tmp_path):
    """The mutual exclusion has to hold ACROSS processes, not within one.

    `child -b` and launchd's `RunAtLoad` are unrelated processes, which is why
    this is an `O_CREAT | O_EXCL` file and not a lock object: nothing in one
    interpreter can exclude the other.
    """
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    procs = [ctx.Process(target=_claim, args=(str(tmp_path), q)) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = [q.get(timeout=5) for _ in range(2)]
    assert sorted(results) == [False, True], f"expected exactly one winner, got {results}"
