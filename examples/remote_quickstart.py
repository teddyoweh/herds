"""Paste a token, run this, drive a Mac from anywhere — the whole pitch.

    python examples/remote_quickstart.py

No SSH, no VPN. Commands and live logs tunnel through the relay to your Mac.
"""

import herds

mac = herds.mac(url="https://you.herds.run", token="hx_...")   # from `herds host`

APP = "quickstart"   # groups every run + sandbox below under one App in the dashboard

# Run a command — blocking, returns Result(exit_code, stdout, stderr, ...).
print(mac.run("sw_vers -productVersion", app=APP).stdout.strip())

# Stream output live, as it happens.
mac.run("for i in 1 2 3; do echo line $i; sleep 0.2; done", stream=True, app=APP)

# Volumes — data that persists across runs, on the Mac.
vol = herds.Volume.from_name("demo-cache")
mac.run("echo 1.2.3 > $HERDS_VOLUME_DEMO_CACHE/version.txt", volumes={"cache": vol}, app=APP)
print(mac.run("cat $HERDS_VOLUME_DEMO_CACHE/version.txt", volumes={"cache": vol}, app=APP).stdout.strip())

# Sandboxes — an isolated workspace; files persist between exec calls.
with herds.Sandbox.create(mac=mac, app=APP) as sbx:
    sbx.exec("echo 'build output' > artifact.txt")
    print(sbx.exec("cat artifact.txt").stdout.strip())
