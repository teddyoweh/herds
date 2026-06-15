<div align="center">

# Herds

**Connect your Mac to the internet and turn it into a programmable runtime.**

*Modal, for Macs.*

[![PyPI](https://img.shields.io/pypi/v/herds?color=34d39e&label=pip%20install%20herds)](https://pypi.org/project/herds/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

<br/>

![Herds dashboard](https://raw.githubusercontent.com/teddyoweh/herds/main/assets/dashboard.png)

</div>

---

Herds makes any Mac you own into a runtime that agents, SDKs, CLIs, cron jobs,
and applications can execute against from anywhere. Install the daemon, sign in,
and your Mac becomes an API.

```python
import herds

mac = herds.mac()
result = mac.run("xcodebuild -scheme MyApp build")
print(result.stdout)
```

Nobody cares about SSH. Nobody cares about Tailscale. Nobody cares about machine
management. **They just have a Mac.**

## The mental model

It's not "rent Macs." It's not "manage servers." It's not "a CI system."

> **Every Mac becomes an API.**

The developer surface intentionally echoes Modal, so the mental model transfers
directly — `App`, `Image`, `Volume`, `Sandbox` — except the runtime is *your
Mac*, and Apple's licensing makes that something Modal/AWS structurally can't
offer as dense rented cloud. Your Mac, already licensed, is the cloud.

## Architecture

Three small pieces. Your Mac never opens an inbound port; the daemon dials home
over a persistent WebSocket (the same NAT-traversal pattern as GitHub Actions
runners, Tailscale, and Cloudflare Tunnel), and commands are pushed back down
that socket.

```
┌─────────────┐   REST: start a job    ┌──────────────┐   WS (agent dials home)  ┌─────────────┐
│  Python SDK │ ───────────────────►   │ Control Plane│ ◄──────────────────────  │ Mac Daemon  │
│   + CLI     │ ◄═══ WS: stream logs ══ │  (FastAPI)   │  ═══ exec / stdout ════► │ (executor)  │
└─────────────┘                        └──────────────┘                          └─────────────┘
   herds.mac().run()                    sqlite + fan-out                            your real Mac
```

The control plane is deliberately tiny — it remembers *who owns what* and job
status. **Volumes, sandboxes, images, and caches never leave the Mac.** The Mac
is the cloud.

## Quickstart

```bash
pip install herds      # or: uv tool install herds
herds auth             # sign in (free) — gives you a stable, branded link
herds host             # your Mac goes live
```

```
✓ Herds host is live
  Dashboard   https://you.relay.herds.run        ← permanent, zero setup
  Host token  herds_sk_…
→ Open your dashboard (opens already signed in)
  https://you.relay.herds.run/?token=…
```

`herds auth` gives you a free account and a **permanent, branded link** —
no Cloudflare, no Tailscale, no port forwarding. Click the magic link and the
dashboard opens already signed in. Other Macs join the pool with
`herds connect <link> <token>`. (No account? `herds host` still works with a
temporary tunnel.)

Prefer the web? Sign up at **[herds.run](https://herds.run)** (email + password)
and manage everything from the platform dashboard.

### Drive it from Python

```python
import herds

mac = herds.mac()
print(mac.run("sw_vers").stdout)
print(mac.run("xcodebuild -version").stdout)
```

## Give an agent a real Mac

This is the point. Hand an AI agent the Herds **skill** + a **token** + your
**URL**, and it can run anything on your Mac — from anywhere, over the public link:

```bash
herds skill --install      # installs SKILL.md so Claude Code can drive your Mac
```

```python
import herds

# hand the agent just a URL + token — no SSH, no setup:
mac = herds.mac(url="https://you.relay.herds.run", token="hx_…")
mac.run("uname -msr")                    # → Darwin 25.2.0 arm64
mac.run("xcodebuild -scheme App test")   # real Xcode, real macOS

# or set it once for the whole process:
herds.configure(url="https://you.relay.herds.run", token="hx_…")
# (env works too: HERDS_CONTROL_PLANE, HERDS_API_KEY)
```

Commands **and live log streams** tunnel through the relay — control plane → your
Mac → back — so the agent needs no SSH, no VPN, and no inbound ports.

Don't hand an agent your full token — mint a **scoped, revocable** one:

```bash
herds token new my-agent --scope run    # can run commands, can't mint keys or read secrets
herds token ls                          # read | run | admin
herds token revoke herds_sk_…           # kill it anytime, without locking yourself out
```

## The SDK

### Run commands

```python
mac = herds.mac()

# blocking, returns a Result(exit_code, stdout, stderr, duration_ms)
r = mac.run("swift build", check=True)

# stream output live to your terminal
mac.run("npm test", stream=True)

# iterate output yourself
for stream, line in mac.stream("xcodebuild build"):
    handle(line)

# fan out across inputs, in parallel (Modal-style .map):
results = mac.map("pytest {}", ["tests/unit", "tests/integration", "tests/e2e"])
results = mac.map(lambda v: f"swift build -c {v}", ["debug", "release"])

# spread across EVERY connected Mac (more Macs → more throughput):
herds.fleet().map("pytest {}", ALL_TEST_DIRS)
```

One Mac handles many concurrent commands — verified at 10 parallel runs — so a
fleet of agents can share it.

### Images — environment recipes resolved on the Mac

```python
mac.run("xcodebuild build", image=herds.Image.xcode("26"))   # selects DEVELOPER_DIR
mac.run("node --version",   image=herds.Image.node("22"))     # pins via mise
mac.run("python script.py", image=herds.Image.python("3.13"))
```

On a Mac an Image isn't a container — it's a recipe that selects the right Xcode
(`DEVELOPER_DIR`, never clobbering concurrent jobs) or runtime (`mise`). If a
toolchain isn't installed, the command still runs against the host and Herds
tells you what it would have pinned.

### Volumes — persistent directories on the Mac

```python
vol = herds.Volume.from_name("ios-builds")
# Reachable as ./builds (relative to the working dir) and via the env var.
mac.run("xcodebuild archive -archivePath $HERDS_VOLUME_IOS_BUILDS/App.xcarchive",
        volumes={"builds": vol})

# Push an entire local codebase onto the Mac (tarred + extracted, junk pruned) —
# the way you'd ship a repo to a long-running agent. Like `modal volume put`:
herds.Volume.from_name("repo").put("./my-project")        # dir → volume root
herds.Volume.from_name("data").put("model.bin", "weights/")  # one file
mac.run("python3 app/main.py", volumes={"app": herds.Volume.from_name("repo")})
```

…or from the CLI: `herds volume put repo ./my-project --url https://you.relay.herds.run --token hx_…`

On a bare Mac there's no container, so a volume is mounted under the working
directory at the mount name *and* exposed as an absolute path through
`$HERDS_VOLUME_<NAME>` — both unambiguous. (Absolute `/workspace`-style mounts
arrive with the Tart VM backend.)

### Sandboxes — isolated, persistent workspaces

```python
with herds.Sandbox.create(image="xcode:26") as sbx:
    sbx.put("./my-project")                       # push your local codebase in
    sbx.exec("xcodebuild -scheme App build", check=True)
```

`sbx.put()` (and `mac.push("./dir", "volume")`) tar a local directory and extract it
on the Mac — the same one-liner whether you target a sandbox or a volume.

Each sandbox is its own directory tree with redirected `HOME`/`TMPDIR` and
toolchain caches, its own process session (so timeouts kill the whole tree), and
an optional `sandbox-exec` write-fence. Files persist between `exec` calls.

### Expose a server — a sandbox becomes a URL

```python
sbx.spawn("python -m http.server 8000", keep_alive=True)
url = sbx.expose(8000)            # → https://you.relay.herds.run/p/<sbx>/8000/
```

Run a web app or API inside a sandbox and get a hittable public link. Requests
tunnel through the agent WebSocket — control plane → daemon → the sandbox's
`localhost:port` — so it works behind NAT with no inbound ports. With a wildcard
domain you get named subdomains (`https://myapi--teddy.herds.run`).

### Apps & functions — run real Python on your Mac

```python
app = herds.App("builds")

@app.function(image=herds.Image.python("3.13"))
def inspect(target: str) -> dict:
    import platform
    return {"target": target, "ran_on": platform.node()}

@app.local_entrypoint()
def main():
    print(inspect.remote("release"))   # ships source, runs on the Mac
```

## The dashboard

`herds host` serves a full web dashboard — bundled into the package as a static
build, served by the control plane (no Node.js at runtime). Live metrics, a
sandbox explorer with exposed ports, a deep file browser for volumes, secrets,
run history — all polling the same API the SDK and CLI use.

| | |
|:--:|:--:|
| ![Machine](https://raw.githubusercontent.com/teddyoweh/herds/main/assets/machine.png) | ![Sandbox](https://raw.githubusercontent.com/teddyoweh/herds/main/assets/sandbox.png) |
| *Per-Mac live gauges* | *Sandboxes — activity + exposed ports* |
| ![Volumes](https://raw.githubusercontent.com/teddyoweh/herds/main/assets/volumes.png) | |
| *Volumes — a real file explorer* | |

## The CLI

```
herds auth               sign in (free) — get a stable, branded link
herds host               self-host: control plane + dashboard + public link
herds skill [--install]  print/install the agent skill (SKILL.md) for Claude Code
herds open               open your live dashboard in the browser
herds token new|ls|revoke   scoped, revocable tokens (read|run|admin) for agents/CI
herds connect <link> <token>   join another Mac to a host
herds serve              run a bare control plane locally
herds machines           list your connected Macs
herds run -- <cmd>       run a command on a Mac (streams output)
herds shell -c <cmd>     one-off command (SSH-equivalent)
herds logs               recent jobs
herds status             local configuration
herds volume ls|create|rm
herds image ls           toolchain images available on this Mac
herds install            launchd LaunchAgent — stay online on login
herds uninstall
```

## Isolation, honestly

The MVP isolates with per-sandbox directories, a clean allowlisted environment,
process-group teardown, and (when available) a `sandbox-exec` write-fence. This
is the right model for *trusted* code — the user owns the Mac and runs their own
builds — and it starts instantly.

The documented next tier is **Tart** VMs (Apple's Virtualization.framework, OCI
images, near-instant APFS copy-on-write clones) for true OS-level isolation, and
Apple's native `container` for Linux jobs on macOS 26. The `Image`/`Volume`/
`Sandbox` API is drawn so those become a backend swap, not an API change. See
[`DESIGN.md`](DESIGN.md) and [`ROADMAP.md`](ROADMAP.md).

## Apple licensing — the moat

Apple's macOS SLA limits virtualization to **2 VMs per physical Mac** and forbids
"service bureau / time-sharing." The BYO-Mac model sidesteps this: the Mac and
its macOS license belong to *you*, so Herds runs as personal/dev use on hardware
you own — which is exactly what the license permits and what makes "Modal for
Macs" both accurate and hard to copy as a rented-fleet cloud.

## Build from source

```bash
git clone https://github.com/teddyoweh/herds
cd herds
uv venv && uv pip install -e ".[dev]"
uv run pytest                      # backend tests
./scripts/build_release.sh         # build the dashboard + wheel (with UI bundled)
```

The dashboard lives in `web/` (Next.js, static-exported). `scripts/build_release.sh`
exports it and bundles it into the wheel, so `pip install` ships the whole UI.

## Status

Live today, end-to-end:

- **`pip install herds`** — on [PyPI](https://pypi.org/project/herds/), dashboard bundled in.
- **`herds auth` + `herds host`** — a free account and a permanent, branded link
  (`you.relay.herds.run`) over our hosted relay — no Cloudflare/Tailscale needed.
- **Agents over the relay** — a remote agent with a token runs `mac.run()` and
  streams logs from anywhere; HTTP *and* WebSocket tunnel through the relay.
- **The platform** — sign up at [herds.run](https://herds.run) (email + password)
  → manage your Macs from the web dashboard.
- Connect Macs, run/stream commands, mount volumes, drive sandboxes, expose ports
  as URLs, run remote Python.

See [`ROADMAP.md`](ROADMAP.md) for what's next (Tart VM backend, per-token scopes,
code-shipping for functions).

## License

Apache-2.0
