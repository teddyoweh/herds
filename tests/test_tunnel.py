"""Raw bidirectional TCP tunnel tests.

The feature: a byte-for-byte pipe to a sandbox-local TCP port (unlike ``expose``,
which is buffered HTTP request/response). These tests exercise the REAL thing
in-process, with timeouts everywhere so nothing can hang:

  * ``test_daemon_raw_tunnel_echo_roundtrip`` runs an actual asyncio TCP echo
    server and drives the REAL daemon tunnel handlers against it — bytes go in a
    ``TUNNEL_DATA`` frame, get written to the socket, echoed back, and come out
    as a ``TUNNEL_DATA`` frame. This is the raw round-trip.
  * ``test_control_raw_tunnel_roundtrip_via_agent`` drives the REAL control app
    via TestClient with a fake agent socket, proving the control-plane wiring
    (agent dispatch + client<->agent byte relay) end to end.
  * the rest cover protocol framing, the offline-refusal path, and the SDK URL.
"""

import asyncio
import base64

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from herds.control import create_app
from herds.protocol import (
    Frame,
    FrameType,
    tunnel_close_frame,
    tunnel_data_frame,
    tunnel_open_frame,
    tunnel_ready_frame,
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


# --------------------------------------------------------------------------- #
# Protocol framing
# --------------------------------------------------------------------------- #


def test_tunnel_frames_roundtrip():
    o = Frame.load(tunnel_open_frame("tun_1", 9222).dump())
    assert o.type == FrameType.TUNNEL_OPEN
    assert o.data["stream_id"] == "tun_1" and o.data["port"] == 9222
    assert o.data["host"] == "127.0.0.1"

    d = Frame.load(tunnel_data_frame("tun_1", b"\x00\x01raw\xff").dump())
    assert d.type == FrameType.TUNNEL_DATA
    assert base64.b64decode(d.data["data_b64"]) == b"\x00\x01raw\xff"

    r = Frame.load(tunnel_ready_frame("tun_1").dump())
    assert r.type == FrameType.TUNNEL_READY and r.data["stream_id"] == "tun_1"

    c = Frame.load(tunnel_close_frame("tun_1", error="connection refused").dump())
    assert c.type == FrameType.TUNNEL_CLOSE and c.data["error"] == "connection refused"
    # A clean close carries no error key.
    assert "error" not in Frame.load(tunnel_close_frame("tun_1").dump()).data


# --------------------------------------------------------------------------- #
# Daemon side — REAL socket round-trip against a real echo server
# --------------------------------------------------------------------------- #


class _FakeWS:
    """Captures frames the daemon ships upstream (stands in for the control WS)."""

    def __init__(self):
        self.frames: list[Frame] = []

    async def send(self, raw):
        self.frames.append(Frame.load(raw))


async def _wait_for(pred, *, timeout=5.0):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        got = pred()
        if got is not None:
            return got
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met within timeout")


@pytest.mark.asyncio
async def test_daemon_raw_tunnel_echo_roundtrip(herds_home):
    from herds.daemon import Daemon

    # A real TCP echo server on an ephemeral localhost port.
    async def handle(reader, writer):
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        finally:
            try:
                writer.close()
            except Exception:
                pass

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    daemon = Daemon("http://x", "m_test", None)
    fake = _FakeWS()
    daemon._ws = fake
    sid = "tun_echo"

    try:
        # Open the tunnel: the daemon dials the echo server and confirms READY.
        await daemon._handle(Frame(type=FrameType.TUNNEL_OPEN,
                                   data={"stream_id": sid, "port": port, "host": "127.0.0.1"}))
        await _wait_for(lambda: True if any(
            f.type == FrameType.TUNNEL_READY and f.data.get("stream_id") == sid
            for f in fake.frames) else None)

        # Byte-for-byte round-trip, twice, over the SAME live socket.
        await daemon._handle(tunnel_data_frame(sid, b"ping-raw-\x00\xff"))

        def echoed_once():
            buf = b"".join(
                base64.b64decode(f.data["data_b64"])
                for f in fake.frames
                if f.type == FrameType.TUNNEL_DATA and f.data.get("stream_id") == sid
            )
            return buf if b"ping-raw-\x00\xff" in buf else None

        assert (await _wait_for(echoed_once)) is not None
        assert sid in daemon._tunnels  # socket still live between turns

        await daemon._handle(tunnel_data_frame(sid, b"second-turn"))

        def echoed_twice():
            buf = b"".join(
                base64.b64decode(f.data["data_b64"])
                for f in fake.frames
                if f.type == FrameType.TUNNEL_DATA and f.data.get("stream_id") == sid
            )
            return buf if b"second-turn" in buf else None

        assert (await _wait_for(echoed_twice)) is not None

        # Close tears the socket down.
        await daemon._handle(Frame(type=FrameType.TUNNEL_CLOSE, data={"stream_id": sid}))
        assert sid not in daemon._tunnels
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_daemon_tunnel_dial_failure_reports_close(herds_home):
    from herds.daemon import Daemon

    daemon = Daemon("http://x", "m_test", None)
    fake = _FakeWS()
    daemon._ws = fake
    sid = "tun_dead"
    # Port 1 is (essentially) never listening → dial fails → TUNNEL_CLOSE w/ error.
    await daemon._handle(Frame(type=FrameType.TUNNEL_OPEN,
                               data={"stream_id": sid, "port": 1, "host": "127.0.0.1"}))
    closed = [f for f in fake.frames
              if f.type == FrameType.TUNNEL_CLOSE and f.data.get("stream_id") == sid]
    assert closed and closed[0].data.get("error")
    assert not any(f.type == FrameType.TUNNEL_READY for f in fake.frames)
    assert sid not in daemon._tunnels


# --------------------------------------------------------------------------- #
# Control plane — REAL app via TestClient, with a fake agent socket
# --------------------------------------------------------------------------- #


def test_control_raw_tunnel_roundtrip_via_agent():
    app = create_app(":memory:")
    c = TestClient(app)
    with c.websocket_connect("/agent/ws?machine_id=m1") as agent:
        agent.send_text(Frame(type=FrameType.REGISTERED, data={"machine": {"name": "M1"}}).dump())
        with c.websocket_connect("/v1/machines/m1/tunnel/9999") as client:
            # The control plane dispatches a TUNNEL_OPEN down the agent socket.
            opened = Frame.load(agent.receive_text())
            assert opened.type == FrameType.TUNNEL_OPEN
            assert opened.data["port"] == 9999
            sid = opened.data["stream_id"]

            # Play the daemon: confirm the dial so the client's pump starts.
            agent.send_text(tunnel_ready_frame(sid).dump())

            # client -> port: raw bytes arrive at the agent as TUNNEL_DATA.
            client.send_bytes(b"hello-raw-\x00\xff")
            data = Frame.load(agent.receive_text())
            assert data.type == FrameType.TUNNEL_DATA and data.data["stream_id"] == sid
            assert base64.b64decode(data.data["data_b64"]) == b"hello-raw-\x00\xff"

            # port -> client: bytes the agent emits reach the client verbatim.
            agent.send_text(tunnel_data_frame(sid, b"world-raw-\x01\x02").dump())
            assert client.receive_bytes() == b"world-raw-\x01\x02"


def test_tunnel_offline_machine_refused():
    app = create_app(":memory:")
    c = TestClient(app)
    # No agent online → the control plane rejects the tunnel connection cleanly.
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/v1/machines/default/tunnel/8080"):
            pass


def test_tunnel_unknown_sandbox_refused():
    app = create_app(":memory:")
    c = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/v1/sandboxes/sbx_nope/tunnel/8080"):
            pass


# --------------------------------------------------------------------------- #
# SDK surface
# --------------------------------------------------------------------------- #


def test_sdk_tunnel_url_shapes(herds_home, monkeypatch):
    from herds.sdk.client import HerdsClient, TcpTunnel

    monkeypatch.setenv("HERDS_CONTROL_PLANE", "https://you.relay.herds.run")
    client = HerdsClient(control_plane="https://you.relay.herds.run", api_key="hx_tok")
    murl = client.tunnel_url(9222, machine_id="m1")
    assert murl == "wss://you.relay.herds.run/v1/machines/m1/tunnel/9222?token=hx_tok"
    surl = client.tunnel_url(5900, sandbox_id="sbx_1")
    assert surl == "wss://you.relay.herds.run/v1/sandboxes/sbx_1/tunnel/5900?token=hx_tok"
    # No token → no query string; default machine when none given.
    plain = HerdsClient(control_plane="http://127.0.0.1:8787", api_key=None)
    assert plain.tunnel_url(3000) == "ws://127.0.0.1:8787/v1/machines/default/tunnel/3000"
    assert hasattr(TcpTunnel, "send") and hasattr(TcpTunnel, "recv")
