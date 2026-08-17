"""Local displacement test for the relay fix. No prod contact.

Spins up create_relay_app on 127.0.0.1, connects a host, displaces it with a
second host connection while firing a burst of HTTP requests through subdomain
routing, and asserts: no 500 (no send-after-close RuntimeError), the displaced
socket is closed 4409, and the new host serves. Prints PASS/FAIL lines.
"""
import asyncio, base64, contextlib, io, json, os, socket, tempfile, threading, sys
from pathlib import Path

import httpx
import uvicorn
import websockets

os.environ["HERDS_RELAY_STATE"] = tempfile.mktemp(suffix=".json")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from herds.relay import create_relay_app, make_accounts  # noqa: E402
from herds.protocol import Frame, FrameType  # noqa: E402

# Provision one account into the state file the app will read.
acct = make_accounts(Path(os.environ["HERDS_RELAY_STATE"]))
prov = acct.provision("testmac")
TOKEN, SUB = prov["token"], prov["account"]

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

PORT = free_port()
app = create_relay_app(domain="herds.run")

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error"))

def run_server():
    asyncio.run(server.serve())

threading.Thread(target=run_server, daemon=True).start()

async def fake_host(label, stop_evt):
    """Connect as a host; answer HTTP_REQUEST frames with a body naming `label`.
    Returns the close code when the relay closes us (displacement)."""
    url = f"ws://127.0.0.1:{PORT}/relay/connect?token={TOKEN}"
    async with websockets.connect(url) as ws:
        stop_evt._ws = ws
        try:
            async for raw in ws:
                fr = Frame.load(raw)
                if fr.type == FrameType.HTTP_REQUEST:
                    resp = Frame(type=FrameType.HTTP_RESPONSE, request_id=fr.request_id,
                                 data={"status": 200,
                                       "body_b64": base64.b64encode(label.encode()).decode(),
                                       "headers": {}})
                    await ws.send(resp.dump())
        except websockets.ConnectionClosed as e:
            return e.code
    return None

async def get(client):
    try:
        r = await client.get(f"http://127.0.0.1:{PORT}/ping",
                             headers={"host": f"{SUB}.localhost"})
        return r.status_code, r.text
    except Exception as e:  # noqa: BLE001
        return "EXC", repr(e)

async def main():
    results = {"pass": [], "fail": []}
    # wait for server
    for _ in range(50):
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                await c.get(f"http://127.0.0.1:{PORT}/relay/whoami?token={TOKEN}")
            break
        except Exception:  # noqa: BLE001
            await asyncio.sleep(0.1)

    async with httpx.AsyncClient(timeout=10) as client:
        # host1 up
        h1_stop = asyncio.Event()
        h1 = asyncio.create_task(fake_host("HOST1", h1_stop))
        await asyncio.sleep(0.6)

        # A) baseline
        code, body = await get(client)
        (results["pass"] if code == 200 and body == "HOST1" else results["fail"]).append(
            f"A baseline: {code} {body!r} (want 200 HOST1)")

        # B) displacement + in-flight race: fire 20 concurrent GETs, connect host2 mid-burst
        h2_stop = asyncio.Event()
        async def burst():
            return await asyncio.gather(*[get(client) for _ in range(20)])
        burst_task = asyncio.create_task(burst())
        await asyncio.sleep(0.02)  # let some requests be in flight
        h2 = asyncio.create_task(fake_host("HOST2", h2_stop))
        burst_results = await burst_task
        h1_code = await asyncio.wait_for(h1, timeout=5)  # host1 should be closed by displacement

        codes = [c for c, _ in burst_results]
        five_hundreds = [r for r in burst_results if r[0] == 500]
        (results["pass"] if not five_hundreds else results["fail"]).append(
            f"B race: no 500s during displacement (got codes {sorted(set(str(c) for c in codes))}); "
            f"500 count={len(five_hundreds)}")
        (results["pass"] if h1_code == 4409 else results["fail"]).append(
            f"B host1 displaced with 4409 close (got {h1_code})")

        # C) after settle, host2 serves
        await asyncio.sleep(0.4)
        code, body = await get(client)
        (results["pass"] if code == 200 and body == "HOST2" else results["fail"]).append(
            f"C post-displacement: {code} {body!r} (want 200 HOST2)")

        h2_stop.set()
        h2.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await h2

    # D) RuntimeError check is done by the caller grepping combined stderr for
    #    'Cannot call "send"' / 'RuntimeError' — see the shell wrapper.
    print("\n=== RESULTS ===")
    for p in results["pass"]:
        print("PASS:", p)
    for f in results["fail"]:
        print("FAIL:", f)
    print("\nOVERALL:", "PASS" if not results["fail"] else "FAIL")
    return 0 if not results["fail"] else 1

sys.exit(asyncio.run(main()))
