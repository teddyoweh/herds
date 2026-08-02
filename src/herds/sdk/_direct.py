"""Direct transfer: the Mac pulls the bytes from you, not through the relay.

The relay is a control channel. Measured on a real fleet it sustains ~0.5 MB/s
end to end, and parallel uploads only bought 1.4x, so it is throughput-limited
and no amount of chunking makes a big push fast. It is also shared: a long push
degrades every other machine in the fleet while it runs.

But the two machines can usually talk to each other directly. So serve the
payload from here on an ephemeral port and have the Mac ``curl`` it. On a LAN
that is ~100 MB/s instead of ~0.5, and the relay carries only the command.

Addresses are tried Tailscale-first: a tailnet address works across networks and
through the client-isolated Wi-Fi that makes plain LAN discovery fail, which is
exactly the case where people reach for a relay copy in the first place.

Falls back to the relay path whenever no address is reachable, so this is an
optimisation, never a new way to fail.
"""

from __future__ import annotations

import contextlib
import secrets
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _primary_ip() -> str:
    """The address of the interface that carries default-route traffic."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def _tailscale_ip() -> str:
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True,
                           text=True, timeout=3)
        return (r.stdout or "").strip().splitlines()[0].strip() if r.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def candidate_hosts() -> list:
    """Addresses this machine might be reachable on, best bet first."""
    hosts, seen = [], set()
    for ip in (_tailscale_ip(), _primary_ip()):
        if ip and ip not in seen:
            seen.add(ip)
            hosts.append(ip)
    return hosts


class _OneShot(BaseHTTPRequestHandler):
    payload = b""
    token = ""
    served = threading.Event()

    def do_GET(self):  # noqa: N802
        if self.path != "/" + self.token:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)
        self.served.set()

    def log_message(self, *a):  # keep the SDK quiet
        pass


@contextlib.contextmanager
def serve(payload: bytes, port: int = 0):
    """Serve ``payload`` at a single unguessable path for the life of the block.

    Yields ``(urls, served_event)``. The path is a 32-byte random token and the
    server stops when the block exits, so the exposure is one object, to whoever
    already knows the token, for the duration of one transfer.
    """
    token = secrets.token_urlsafe(24)
    handler = type("H", (_OneShot,), {"payload": payload, "token": token,
                                      "served": threading.Event()})
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    bound = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield [f"http://{h}:{bound}/{token}" for h in candidate_hosts()], handler.served
    finally:
        httpd.shutdown()
        httpd.server_close()


# Runs on the Mac with /usr/bin/python3 (3.9 on a stock system, so keep it 3.9
# clean). Self-contained so it works regardless of how herds was installed
# there, and it re-implements the same containment rules the daemon uses rather
# than shelling out to tar, which would happily extract a traversing member.
PULL_SCRIPT = r'''
import io, json, os, sys, tarfile, urllib.request

dest = os.path.abspath(sys.argv[1])
urls = sys.argv[2:]

raw = None
err = []
for u in urls:
    try:
        with urllib.request.urlopen(u, timeout=8) as r:
            raw = r.read()
        break
    except Exception as e:
        err.append("%s: %s" % (u.rsplit("/", 1)[0], e.__class__.__name__))
if raw is None:
    sys.stderr.write("unreachable: " + "; ".join(err) + "\n")
    sys.exit(3)

if not os.path.isdir(dest):
    os.makedirs(dest)

def inside(base, p):
    b, p = os.path.realpath(base), os.path.realpath(p)
    return p == b or p.startswith(b + os.sep)

n = 0
with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
    for m in tf.getmembers():
        mp = os.path.join(dest, m.name)
        if not inside(dest, mp):
            continue
        if m.isfile() or m.isdir():
            tf.extract(m, path=dest); n += 1
        elif m.issym() or m.islnk():
            ln = m.linkname
            if not ln or os.path.isabs(ln):
                continue
            if not inside(dest, os.path.join(os.path.dirname(mp), ln)):
                continue
            tf.extract(m, path=dest); n += 1

print(json.dumps({"members": n, "bytes": len(raw), "dest": dest}))
'''


def pull_command(dest: str, urls: list) -> list:
    """argv for the Mac: download from the first reachable URL and extract."""
    return ["/usr/bin/python3", "-c", PULL_SCRIPT, dest, *urls]
