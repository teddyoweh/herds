#!/usr/bin/env python3
"""End-to-end smoke test for a live Herds host (over the relay or locally).

Exercises the whole SDK surface against a *connected* Mac, so you can verify a
deployment in one command. Point it at a host and run:

    HERDS_URL=https://you.relay.herds.run HERDS_TOKEN=hx_… python scripts/smoke.py

Requires a Mac already online (`herds auth` + `herds host`). Exits non-zero on
the first failure so it's CI/staging friendly.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request

import herds


def main() -> int:
    url = os.environ.get("HERDS_URL") or os.environ.get("HERDS_CONTROL_PLANE")
    token = os.environ.get("HERDS_TOKEN") or os.environ.get("HERDS_API_KEY")
    if not url or not token:
        print("set HERDS_URL and HERDS_TOKEN (of a connected host)", file=sys.stderr)
        return 2
    herds.configure(url=url, token=token)
    mac = herds.mac()
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok))
        print(f"  {'✓' if ok else '✗'} {name}{(' — ' + detail) if detail else ''}")

    # 1. run + exit code + stderr
    r = mac.run("echo hi; echo oops >&2; exit 0")
    check("run", r.exit_code == 0 and r.stdout.strip() == "hi" and "oops" in r.stderr)

    # 2. failure surfaces
    check("run failure", mac.run("exit 7").exit_code == 7)

    # 3. parallel map
    rs = mac.map("echo {}", ["a", "b", "c", "d"])
    check("map", [x.stdout.strip() for x in rs] == ["a", "b", "c", "d"])

    # 4. push a dir to a sandbox, run it
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "main.py").write_text("print('pushed-and-ran')")
    sbx = herds.Sandbox.create()
    sbx.put(str(d))
    check("sandbox put+exec", sbx.exec("python3 main.py").stdout.strip() == "pushed-and-ran")

    # 5. expose a server through the relay
    sbx.exec("echo '<h1>smoke-ok</h1>' > index.html")
    sbx.spawn("python3 -m http.server 8000", keep_alive=True)
    time.sleep(3)
    expose_url = sbx.expose(8000)
    served = False
    for _ in range(5):
        try:
            served = "smoke-ok" in urllib.request.urlopen(expose_url, timeout=15).read().decode()
            if served:
                break
        except Exception:
            time.sleep(4)
    check("expose port", served, expose_url)
    sbx.terminate()

    ok = all(v for _, v in checks)
    print(f"\n{'PASS' if ok else 'FAIL'} — {sum(v for _, v in checks)}/{len(checks)} checks")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
