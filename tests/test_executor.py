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
    assert (herds_home / "images" / "base1.tar").exists()

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
