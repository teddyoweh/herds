"""Herds quickstart -- run commands, mount a volume, drive a sandbox.

Prereqs (in separate terminals):
    herds serve        # control plane
    herds connect      # connect this Mac

Then:
    python examples/quickstart.py
"""

import herds


def main() -> None:
    mac = herds.mac()
    print(f"Connected to: {mac.name}  (online={mac.online})\n")

    # 1. Run a command -----------------------------------------------------
    r = mac.run("echo 'hello from' $(hostname) && sw_vers -productVersion")
    print("run ->", r.stdout.strip(), f"(exit {r.exit_code}, {r.duration_ms}ms)\n")

    # 2. Stream output live ------------------------------------------------
    print("stream ->")
    mac.run("for i in 1 2 3; do echo line $i; sleep 0.2; done", stream=True)
    print()

    # 3. Volumes -- persist data across runs -------------------------------
    vol = herds.Volume.from_name("demo-cache")
    # The volume is reachable via $HERDS_VOLUME_<NAME> (and as ./<name>).
    mac.run("echo 1.2.3 > $HERDS_VOLUME_DEMO_CACHE/version.txt", volumes={"cache": vol})
    r = mac.run("cat $HERDS_VOLUME_DEMO_CACHE/version.txt", volumes={"cache": vol})
    print(f"volume readback -> {r.stdout.strip()}\n")

    # 4. Sandboxes -- isolated workspace, files persist between exec calls --
    with herds.Sandbox.create(mac=mac) as sbx:
        sbx.exec("echo 'build output' > artifact.txt")
        r = sbx.exec("cat artifact.txt && pwd")
        print(f"sandbox {sbx.id} ->")
        print("  " + r.stdout.strip().replace("\n", "\n  "))


if __name__ == "__main__":
    main()
