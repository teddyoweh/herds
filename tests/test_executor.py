"""Executor tests: these run real subprocesses inside a temp HERDS_HOME."""

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
