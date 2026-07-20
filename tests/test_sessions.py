"""Persistent-stdin-session tests.

The keystone is a RESIDENT process the backend starts once and feeds many stdin
turns into. These tests exercise the real thing in-process (no sockets that can
hang): the Executor drives an actual resident subprocess, and the control app is
driven via TestClient for the REST wiring. Every wait has a timeout.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from herds.control import create_app
from herds.protocol import (
    Frame,
    FrameType,
    session_ready_frame,
    session_start_frame,
    stdin_frame,
)


@pytest.fixture()
def herds_home(tmp_path, monkeypatch):
    home = tmp_path / "herds"
    monkeypatch.setenv("HERDS_HOME", str(home))
    import importlib

    import herds.config as cfg

    importlib.reload(cfg)
    import herds.daemon.executor as ex

    importlib.reload(ex)
    return home


# A resident line reader: echoes "got:<line>" for each stdin line, flushing so
# output arrives turn-by-turn. It only exits when stdin hits EOF.
_READER = (
    "import sys\n"
    "for line in sys.stdin:\n"
    "    sys.stdout.write('got:' + line)\n"
    "    sys.stdout.flush()\n"
    "sys.stdout.write('done\\n'); sys.stdout.flush()\n"
)


async def _await_text(chunks, needle, *, timeout=5.0):
    """Give the event loop time to run the output pumps, then assert we saw
    ``needle`` in the accumulated stdout within ``timeout`` seconds."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if needle in "".join(t for s, t in chunks if s == "stdout"):
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"never saw {needle!r}; got: {chunks!r}")


@pytest.mark.asyncio
async def test_resident_session_multi_turn_stdin(herds_home):
    """Drive a resident line reader: send 2+ stdin chunks, each echoes back on
    the stream while the SAME process stays alive; EOF ends it cleanly."""
    from herds.daemon.executor import Executor

    ex = Executor()
    chunks: list[tuple[str, str]] = []

    async def sink(stream, text):
        chunks.append((stream, text))

    session = await ex.start_session(
        "sess1", ["python3", "-u", "-c", _READER], sink=sink
    )
    pid = session.proc.pid

    # Turn 1
    assert await ex.session_send("sess1", "hello\n") is True
    await _await_text(chunks, "got:hello")

    # Turn 2 — the process must still be the same resident one (not respawned).
    assert session.proc.pid == pid
    assert await ex.session_send("sess1", "world\n") is True
    await _await_text(chunks, "got:world")

    # Close stdin → the reader loop ends → process exits 0.
    assert await ex.session_send("sess1", eof=True) is True
    code, ms = await asyncio.wait_for(ex.session_wait("sess1"), timeout=10)
    assert code == 0
    assert ms >= 0

    out = "".join(t for s, t in chunks if s == "stdout")
    assert "got:hello" in out and "got:world" in out and "done" in out
    # Session is gone from the live set after it exits.
    assert await ex.session_send("sess1", "late\n") is False


@pytest.mark.asyncio
async def test_session_shares_sandbox_workspace(herds_home):
    """A session runs in the sandbox workspace and its writes persist there."""
    from herds.daemon.executor import Executor

    ex = Executor()
    ex.create_sandbox("sbx_s")
    chunks: list[tuple[str, str]] = []

    async def sink(stream, text):
        chunks.append((stream, text))

    writer = (
        "import sys\n"
        "for line in sys.stdin:\n"
        "    open('note.txt','a').write(line)\n"
        "    sys.stdout.write('wrote\\n'); sys.stdout.flush()\n"
    )
    await ex.start_session("sess2", ["python3", "-u", "-c", writer],
                           sink=sink, sandbox_id="sbx_s")
    await ex.session_send("sess2", "persisted-line\n")
    await _await_text(chunks, "wrote")
    await ex.session_send("sess2", eof=True)
    code, _ = await asyncio.wait_for(ex.session_wait("sess2"), timeout=10)
    assert code == 0

    # A later one-shot in the same sandbox sees the file the session wrote.
    read_chunks: list[tuple[str, str]] = []

    async def rsink(stream, text):
        read_chunks.append((stream, text))

    code, _ = await ex.run("r_read", "cat note.txt", sink=rsink, sandbox_id="sbx_s")
    assert code == 0
    assert "persisted-line" in "".join(t for s, t in read_chunks if s == "stdout")


def test_session_frames_roundtrip():
    f = session_start_frame("sess_x", "cat", sandbox_id="sbx_1", inherit_home=True)
    back = Frame.load(f.dump())
    assert back.type == FrameType.SESSION_START
    assert back.data["command"] == "cat"
    assert back.data["sandbox_id"] == "sbx_1"
    assert back.data["inherit_home"] is True

    s = stdin_frame("sess_x", "hi\n")
    back = Frame.load(s.dump())
    assert back.type == FrameType.STDIN
    assert back.request_id == "sess_x"
    assert back.data["data"] == "hi\n"
    assert back.data["eof"] is False

    eof = stdin_frame("sess_x", eof=True)
    assert eof.data["eof"] is True and eof.data["data"] == ""


def test_stdin_to_unknown_session_404():
    app = create_app(":memory:")
    c = TestClient(app)
    r = c.post("/v1/sessions/req_nope/stdin", json={"data": "hi\n"})
    assert r.status_code == 404


def test_start_session_no_machine_409():
    # No agent connected: starting a session fails cleanly (no hang).
    app = create_app(":memory:")
    c = TestClient(app)
    r = c.post("/v1/machines/default/sessions", json={"command": "cat"})
    assert r.status_code == 409


def test_session_ready_frame_roundtrip():
    f = session_ready_frame("sess_x")
    back = Frame.load(f.dump())
    assert back.type == FrameType.SESSION_READY
    assert back.request_id == "sess_x"


@pytest.mark.asyncio
async def test_session_streams_incrementally(herds_home):
    """Output must arrive turn-by-turn as it's produced — NOT batched at exit.
    A process prints A, sleeps, prints B; the two chunks must land ~the sleep
    apart. If streaming were buffered until exit, the gap would be ~0."""
    import time as _t
    from herds.daemon.executor import Executor

    ex = Executor()
    stamps: list[tuple[float, str]] = []

    async def sink(stream, text):
        if stream == "stdout":
            stamps.append((_t.monotonic(), text))

    prog = (
        "import sys, time\n"
        "sys.stdout.write('AAA\\n'); sys.stdout.flush()\n"
        "time.sleep(0.5)\n"
        "sys.stdout.write('BBB\\n'); sys.stdout.flush()\n"
    )
    await ex.start_session("strm", ["python3", "-u", "-c", prog], sink=sink)

    async def when(needle, timeout=8.0):
        loop = asyncio.get_event_loop()
        dl = loop.time() + timeout
        while loop.time() < dl:
            for ts, t in stamps:
                if needle in t:
                    return ts
            await asyncio.sleep(0.02)
        raise AssertionError(f"never saw {needle!r}; got {stamps!r}")

    t_a = await when("AAA")
    t_b = await when("BBB")
    assert t_b - t_a >= 0.3, f"chunks arrived batched, not streamed (gap {t_b - t_a:.3f}s)"
    await asyncio.wait_for(ex.session_wait("strm"), timeout=10)


@pytest.mark.asyncio
async def test_daemon_emits_session_ready_before_exit(herds_home):
    """The daemon must emit SESSION_READY once the process is live (and before
    EXIT). That ack is what lets the control plane block start_session until the
    handle is usable — killing the stdin-before-launch race."""
    from herds.daemon import Daemon

    d = Daemon("http://x", "m1", None)
    sent: list = []

    class FakeWS:
        async def send(self, text):
            sent.append(Frame.load(text))

    d._ws = FakeWS()
    frame = session_start_frame("sready", ["python3", "-c", "import sys; sys.stdout.write('hi\\n')"])
    await asyncio.wait_for(d._handle_session_start(frame), timeout=15)

    types = [f.type for f in sent]
    assert FrameType.SESSION_READY in types, f"no SESSION_READY in {types}"
    assert FrameType.EXIT in types, f"no EXIT in {types}"
    assert types.index(FrameType.SESSION_READY) < types.index(FrameType.EXIT), \
        f"SESSION_READY must precede EXIT: {types}"
    ready = next(f for f in sent if f.type == FrameType.SESSION_READY)
    assert ready.request_id == "sready"
