"""Executor tests: these run real subprocesses inside a temp HERDS_HOME."""

import asyncio
import os
from pathlib import Path

import pytest


@pytest.fixture()
def herds_home(tmp_path, monkeypatch):
    home = tmp_path / "herds"
    monkeypatch.setenv("HERDS_HOME", str(home))
    # Reimport config so it picks up the patched env.
    import importlib

    import herds.config as cfg

    importlib.reload(cfg)
    import herds.daemon.executor as ex

    importlib.reload(ex)
    return home


async def _collect(executor, request_id, command, **kw):
    chunks: list[tuple[str, str]] = []

    async def sink(stream, text):
        chunks.append((stream, text))

    code, ms = await executor.run(request_id, command, sink=sink, **kw)
    out = "".join(t for s, t in chunks if s == "stdout")
    err = "".join(t for s, t in chunks if s == "stderr")
    return code, out, err


@pytest.mark.asyncio
async def test_basic_command(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    code, out, err = await _collect(ex, "r1", "echo hello-herds")
    assert code == 0
    assert "hello-herds" in out


@pytest.mark.asyncio
async def test_nonzero_exit(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    code, out, err = await _collect(ex, "r2", "exit 7")
    assert code == 7


@pytest.mark.asyncio
async def test_sandbox_workspace_persists(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_test")
    await _collect(ex, "r3", "echo persisted > f.txt", sandbox_id="sbx_test")
    code, out, _ = await _collect(ex, "r4", "cat f.txt", sandbox_id="sbx_test")
    assert code == 0
    assert "persisted" in out


@pytest.mark.asyncio
async def test_env_is_isolated_to_sandbox(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    # HOME should be redirected into the sandbox tree, not the real home.
    code, out, _ = await _collect(ex, "r5", "echo $HOME", sandbox_id="sbx_env")
    assert "sandboxes/sbx_env" in out


@pytest.mark.asyncio
async def test_timeout_kills_command(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    code, out, err = await _collect(ex, "r6", "sleep 10", timeout=1)
    assert code != 0
    assert "timed out" in err


@pytest.mark.asyncio
async def test_volume_env_var_exposed(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    code, out, _ = await _collect(
        ex, "r7", "echo $HERDS_VOLUME_MYVOL", volumes={"data": "myvol"}
    )
    assert "volumes/myvol" in out


# -- provisioning (Image.run_commands / setup_commands) --------------------- #


@pytest.mark.asyncio
async def test_provisioning_runs_and_hash_cache_skips_rerun(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_prov")
    setup = ["echo ran >> counter.txt"]

    # First run: provisioning executes the setup command once.
    code, out, err = await asyncio.wait_for(
        _collect(ex, "p1", "cat counter.txt", sandbox_id="sbx_prov", setup_commands=setup),
        timeout=30,
    )
    assert code == 0
    assert out.count("ran") == 1
    assert "provisioning (1/1)" in err
    assert "provisioning complete" in err

    # Second run, same commands: cached by content hash → does NOT re-run, so the
    # counter is unchanged (still one line).
    code, out, err = await asyncio.wait_for(
        _collect(ex, "p2", "cat counter.txt", sandbox_id="sbx_prov", setup_commands=setup),
        timeout=30,
    )
    assert code == 0
    assert out.count("ran") == 1
    assert "provisioning cached" in err


@pytest.mark.asyncio
async def test_provisioning_missing_tool_note_and_no_cache(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_missing")
    setup = ["herds-nonexistent-tool-xyz --version"]

    code, out, err = await asyncio.wait_for(
        _collect(ex, "m1", "echo after", sandbox_id="sbx_missing", setup_commands=setup),
        timeout=30,
    )
    # A missing tool gets a clear note and provisioning is NOT cached (so it can
    # be fixed and retried). The failed step marks no marker on disk.
    assert "isn't installed" in err
    marker_dir = herds_home / "sandboxes" / "sbx_missing" / ".herds_provision"
    assert not marker_dir.exists() or not any(marker_dir.iterdir())


# -- snapshot -> base -> restore -------------------------------------------- #


@pytest.mark.asyncio
async def test_snapshot_then_restore_reproduces_file(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_src")
    await asyncio.wait_for(
        _collect(ex, "s1", "echo hello-snap > snap.txt", sandbox_id="sbx_src"),
        timeout=30,
    )

    info = ex.snapshot("sbx_src", "base1")
    assert info["image_id"] == "base1"
    assert info["size_bytes"] > 0
    # Backed by an APFS clone where available, a tarball otherwise — assert the
    # artifact exists rather than pinning which form it took.
    assert info["mode"] in ("clone", "tar")
    assert Path(info["path"]).exists()
    assert Path(info["path"]).parent == herds_home / "images"

    # A brand-new sandbox seeded from the base restores the file.
    ex.create_sandbox("sbx_dst", base="base1")
    code, out, _ = await asyncio.wait_for(
        _collect(ex, "s2", "cat snap.txt", sandbox_id="sbx_dst"),
        timeout=30,
    )
    assert code == 0
    assert "hello-snap" in out


@pytest.mark.asyncio
async def test_restore_missing_base_is_noop(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    # No such base — the sandbox is simply an empty fresh tree, no crash.
    ex.create_sandbox("sbx_empty", base="does-not-exist")
    code, out, _ = await asyncio.wait_for(
        _collect(ex, "e1", "ls | wc -l", sandbox_id="sbx_empty"),
        timeout=30,
    )
    assert code == 0


# -- fleet: admission control, idle reap, sandbox GC ------------------------ #


async def _wait_active(ex, target, timeout=5.0):
    """Spin until the admission gate reports ``target`` live slots (or give up)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if ex.admission_stats()["active"] >= target:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"admission never reached {target}: {ex.admission_stats()}")


@pytest.mark.asyncio
async def test_admission_cap_rejects_when_full(herds_home):
    from herds.daemon.executor import EX_ADMISSION_REJECTED, Executor

    # Cap of 1 with no queue: the second concurrent run must be turned away.
    ex = Executor(max_live=1, queue_max=0)
    task1 = asyncio.create_task(_collect(ex, "a1", "sleep 5"))
    await _wait_active(ex, 1)

    code, out, err = await asyncio.wait_for(_collect(ex, "a2", "echo nope"), timeout=10)
    assert code == EX_ADMISSION_REJECTED
    assert "admission cap reached" in err
    assert "nope" not in out  # it never launched

    # Free the slot and let the long run wind down.
    ex.cancel("a1")
    await asyncio.wait_for(task1, timeout=10)
    assert ex.admission_stats()["active"] == 0


@pytest.mark.asyncio
async def test_admission_queue_runs_after_slot_frees(herds_home):
    from herds.daemon.executor import Executor

    # Cap of 1 but a real queue: the second run waits, then runs — never rejected.
    ex = Executor(max_live=1, queue_max=5)
    task1 = asyncio.create_task(_collect(ex, "q1", "sleep 0.3"))
    await _wait_active(ex, 1)

    # Queued while q1 holds the only slot; completes once q1 exits.
    task2 = asyncio.create_task(_collect(ex, "q2", "echo queued-hi"))
    code1, _, _ = await asyncio.wait_for(task1, timeout=10)
    code2, out2, _ = await asyncio.wait_for(task2, timeout=10)
    assert code1 == 0
    assert code2 == 0
    assert "queued-hi" in out2
    assert ex.admission_stats()["active"] == 0


@pytest.mark.asyncio
async def test_reap_idle_session_kills_it_and_frees_slot(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    chunks: list[tuple[str, str]] = []

    async def sink(stream, text):
        chunks.append((stream, text))

    # `cat` stays resident reading stdin — a perfectly idle session.
    await ex.start_session("sess1", "cat", sink=sink)
    assert ex.admission_stats()["active"] == 1

    # Zero idle budget → reaped immediately.
    reaped = ex.reap_idle_sessions(idle_timeout_ms=0)
    assert "sess1" in reaped

    code, ms = await asyncio.wait_for(ex.session_wait("sess1"), timeout=10)
    assert code != 0  # terminated, not a clean exit
    assert ex.admission_stats()["active"] == 0  # slot handed back


@pytest.mark.asyncio
async def test_keepalive_spares_idle_session_from_reaper(herds_home):
    """A session with no stdin would be reaped — but touch()/keepalive marks it
    active so the reaper spares it. This is the AskUserQuestion-wait case."""
    from herds.daemon.executor import Executor

    ex = Executor()

    async def sink(stream, text):
        pass

    await ex.start_session("sessk", "cat", sink=sink)
    # Keepalive marks it active NOW; a tiny idle budget must not reap it.
    assert ex.session_keepalive("sessk") is True
    reaped = ex.reap_idle_sessions(idle_timeout_ms=50_000)
    assert "sessk" not in reaped
    # Unknown session → False (no crash).
    assert ex.session_keepalive("nope") is False
    ex.terminate_sandbox("sessk")


@pytest.mark.asyncio
async def test_stdout_activity_keeps_session_alive(herds_home):
    """A session actively PRODUCING output (e.g. a driver heartbeating during an
    answer-wait) bumps last_active via the stdout pump, so it isn't reaped."""
    from herds.daemon.executor import Executor

    ex = Executor()

    async def sink(stream, text):
        pass

    # Emit a line every 50ms for a while, then sleep — proves stdout bumps activity.
    prog = "import time,sys\nfor _ in range(6):\n print('tick',flush=True); time.sleep(0.05)\ntime.sleep(30)"
    await ex.start_session("sesso", ["python3", "-u", "-c", prog], sink=sink)
    await asyncio.sleep(0.25)  # let a few ticks pump through
    # Despite a short idle budget, recent stdout keeps last_active fresh.
    reaped = ex.reap_idle_sessions(idle_timeout_ms=1_000)
    assert "sesso" not in reaped
    ex.terminate_sandbox("sesso")


@pytest.mark.asyncio
async def test_gc_removes_stale_sandbox_dir_but_keeps_fresh(herds_home):
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_old")
    old = herds_home / "sandboxes" / "sbx_old"
    assert old.exists()

    # Backdate the whole tree so it looks untouched for ~100s.
    import time as _time
    past = _time.time() - 100
    for p in [old, *old.rglob("*")]:
        os.utime(p, (past, past))

    # A brand-new sandbox is fresh and must survive the same GC pass.
    ex.create_sandbox("sbx_new")

    removed = ex.gc_sandbox_dirs(ttl_ms=5000)  # 5s TTL
    assert "sbx_old" in removed
    assert not old.exists()
    assert "sbx_new" not in removed
    assert (herds_home / "sandboxes" / "sbx_new").exists()
    # In-memory tracking for the GC'd sandbox is dropped too.
    assert "sbx_old" not in ex.sandboxes
