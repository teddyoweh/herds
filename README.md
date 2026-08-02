<div align="center">

# Herds

**Connect your Mac to the internet and turn it into a programmable runtime.**

*Modal, for Macs.*

[![PyPI](https://img.shields.io/pypi/v/herds?color=34d39e&label=pip%20install%20herds)](https://pypi.org/project/herds/)
[![Python](https://img.shields.io/pypi/pyversions/herds?color=34d39e)](https://pypi.org/project/herds/)
[![CI](https://github.com/teddyoweh/herds/actions/workflows/ci.yml/badge.svg)](https://github.com/teddyoweh/herds/actions/workflows/ci.yml)
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

**Three commands — from nothing to a Mac you can drive from anywhere:**

```bash
pip install herds      # 1 · install        (or: uv tool install herds)
herds auth             # 2 · sign in        — opens your browser, syncs a token back
herds host             # 3 · go live        — your Mac is now an API
```

```
✓ Herds host is live (background · pid 64265)
  Dashboard      https://you.herds.run       ← permanent, branded link · zero setup
  Connect token  herds_sk_…@you.herds.run    ← one paste adds another Mac

  It keeps running after you close this terminal.
    status  herds host status   ·   stop  herds host stop
→ opening your dashboard, already signed in …
```

That's it. Your Mac is online at a **permanent, branded link** — no Cloudflare,
no Tailscale, no port forwarding. `herds auth` opens your browser to approve and
syncs the token back; the dashboard opens already signed in. (No account?
`herds host` still works with a temporary tunnel.)

`herds host` **returns your prompt** and keeps serving after you close the
terminal — check on it with `herds host status`, tail it with `herds host logs`,
and stop it with `herds host stop`. Use `--foreground` to stay attached instead
(that's what the `herds install` LaunchAgent uses). The Mac you host from
**joins its own fleet as a node**, so `herds.mac()` can target it like any other.

### Requirements

| | |
|---|---|
| **Python** | **3.9 – 3.14.** Every release is tested on all six. |
| **The Mac you host** | macOS (Apple Silicon or Intel) — this is the runtime. |
| **The machine you drive from** | Anything that runs Python. The SDK is a thin HTTP/WebSocket client, so your CI, your Linux box, or another Mac all work. |

The SDK deliberately holds the floor at 3.9 so it drops into older CI images and
system Pythons without a version bump. One caveat: the optional MCP server
(`pip install 'herds[mcp]'`, `herds mcp`) needs **3.10+**, because upstream `mcp`
does — everything else in herds runs on 3.9.

**Add more Macs** — one line each:

```bash
curl -fsSL herds.run/install | sh -s -- hx_…@you.herds.run   # a fresh Mac: installs + joins
herds connect hx_…@you.herds.run                             # already has herds? just connect
```

**Drive it** — from Python, the CLI, or the web dashboard:

```python
import herds

mac = herds.mac()                              # the idlest Mac in your fleet
print(mac.run("xcodebuild -version").stdout)   # real Xcode, real macOS
url = mac.expose(3000)                          # any local port → a public URL
```

Prefer the web? Sign up at **[herds.run](https://herds.run)** and manage
everything from the dashboard. New here? Full walkthrough at **[herds.run/setup](https://herds.run/setup)**.

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

**Or skip the SDK entirely — plug the Mac into any MCP client:**

```bash
pip install 'herds[mcp]'   # needs Python 3.10+ (upstream `mcp` does)
herds mcp        # serves run / read_file / write_file / list_dir / screenshot / notify
```
```jsonc
// Claude Desktop / Code / Cursor — mcpServers:
"herds": { "command": "herds", "args": ["mcp"],
  "env": { "HERDS_CONTROL_PLANE": "https://you.relay.herds.run", "HERDS_API_KEY": "hx_…" } }
```

Don't hand an agent your full token — mint a **scoped, revocable** one:

```bash
herds token new my-agent --scope run    # can run commands, can't mint keys or read secrets
herds token ls                          # read | run | admin
herds token revoke herds_sk_…           # kill it anytime, without locking yourself out
```

## Run an agent *on* your Mac — keyless

The other direction: run a real coding agent (Claude Code, Codex, or your own)
**on** a Mac and stream its output back — with **no model API key on the Mac**.
Herds pairs with [`proxyagent`](https://pypi.org/project/proxyagent/): the real key
stays on your proxy, and the Mac only ever holds a scoped, revocable token — best
of all a Herds **Secret**, so it's injected at run time and never written to disk.

```bash
herds agent "fix the failing tests" --proxy https://proxy.you.com --secret proxyagent
herds agent "upgrade deps" --all                       # every online Mac, in parallel
herds agent "build the app" --sandbox -m mac-studio    # in an isolated sandbox
herds agent "summarise today's PRs" --harness codex    # Codex instead of Claude Code
```

```python
import herds
mac = herds.mac()

mac.agent("fix the failing tests", proxy=PROXY, secret="proxyagent")    # keyless, streamed
mac.sandbox().agent("run the suite", proxy=PROXY, token="pa_…")         # isolated
herds.fleet().agent("upgrade deps", proxy=PROXY, secret="proxyagent")   # → {mac: Result}
```

Every model call the agent makes routes through your proxy — authenticated,
scoped, and logged — and the real key never leaves it. The Mac just needs
`proxyagent` and the agent CLI installed (`pip install proxyagent` ·
`npm i -g @anthropic-ai/claude-code`).

## Keep the agent alive — drive it turn by turn

`herds agent` above is one-shot. A **Session** is the other thing: a resident
process you start *once* and feed **turn after turn**, streaming its output the
whole time. Run a long-lived agent (or any stdin-driven driver) on a live
sandbox and keep prompting it — state persists between turns, and because the
session is addressed through the control plane, **any worker can send the next
turn** (cross-worker input is free).

```python
import json, herds
mac = herds.mac()

# a long-lived agent in stream-json mode — it stays alive across prompts:
s = mac.session(
    "claude --print --input-format stream-json --output-format stream-json --verbose",
    env={"ANTHROPIC_BASE_URL": PROXY, "ANTHROPIC_API_KEY": TOKEN},   # keyless: no real key on the Mac
)

def turn(text):
    s.send(json.dumps({"type": "user",
        "message": {"role": "user", "content": text}}) + "\n")

turn("clone the repo and run the tests")
for stream, text in s.stream():        # JSON events stream back as it drives
    print(text, end="")
turn("now fix the failing ones")        # SAME live session — it kept its state
s.close()                               # EOF → the agent finishes and exits
```

This is the **exact shape Modal runs a persistent agent driver in**: one resident
process, one stdin turn per prompt, JSON events streamed from stdout, model calls
routed through a proxy. Point the session's command at your *own* driver script
and it drops straight in. `mac.session(cmd)` and `sandbox.session(cmd)` return a
`Session` with `send(text)` · `stream()` · `close()`. Idle sessions are reaped
automatically (see [Bounding a Mac](#bounding-a-mac)).

## Browse the web — on a real Mac, real residential IP

A Sandbox is a whole Mac shell, so browser automation needs **no special API**:
the agent (or your script) installs Playwright, drives Chromium, and reads the
screenshots back — full, dynamic, free-reign control.

```python
shots = herds.Volume.from_name("shots")
with herds.Sandbox.create(volumes={"out": shots}) as sbx:
    sbx.exec("pip install playwright && playwright install chromium", check=True)
    sbx.put("scrape.py")                          # your Playwright script → writes ./out/*.png
    sbx.exec("python scrape.py", check=True)      # runs ON the Mac
shots.get("home.png", "./home.png")               # pull a screenshot back out
```

Because the browser runs *on the Mac*, its traffic exits the Mac's own
connection — a **real residential IP**, real consumer hardware, a real browser
fingerprint. And each Sandbox has its own `HOME`/profile, so you can run **many
isolated browser sessions in parallel on one Mac** (separate cookies/logins) —
all sharing that one residential IP. To *watch* or drive the browser from off the
Mac (a live view, or an external Playwright over CDP), open a
[raw tunnel](#raw-tunnels--any-port-as-a-live-byte-stream) to its DevTools port.

## The SDK

### Run commands

> **Sandboxed by default — `inherit_home=True` / `--real` to run as *you*.**
> A plain `mac.run(...)` gets a throwaway `HOME`
> (`~/.herds/sandboxes/sbx_eph_…/home`) and a Seatbelt profile that rolls writes
> back **and denies reads of credential stores** — `~/.ssh`, `~/.aws`,
> `~/.config/gh`, Keychains, browser cookies — so a sandboxed run can't read your
> keys and post them somewhere. That's the right default for
> CI and untrusted code — but it means installing apps, writing outside the
> sandbox, or using your keychain/logins **silently won't stick** (you'll see
> "directories are not writable" or a read-only filesystem). Opt out when you
> mean "my Mac, my tools":
>
> ```python
> mac.run("brew install --cask cursor", inherit_home=True)   # real $HOME, real disk
> ```
> ```bash
> herds run --real -- brew install --cask cursor            # same, from the CLI
> herds shell --real -c 'ls ~/Library'
> ```
>
> `mac.agent(...)`, `screenshot()`, `clipboard`, `notify()` and the AppleScript
> helpers already default to the real session — they'd be useless sandboxed.

```python
mac = herds.mac()

# blocking, returns a Result(exit_code, stdout, stderr, duration_ms)
r = mac.run("swift build", check=True)

# run against the REAL Mac — your $HOME, logins, keychain, /Applications
mac.run("brew install --cask warp", inherit_home=True)

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

# smart routing — the IDLEST online Mac with a capability (tag or chip):
herds.mac(tag="xcode-26").run("xcodebuild …")
herds.machines(tag="m4-max")          # filter the fleet by label/chip
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

**Provisioning that actually runs.** `run_commands(...)` executes on the Mac
*before* your command and is **cached by a content hash** — the first run
installs, every repeat is a no-op:

```python
img = herds.Image.macos().run_commands(
    "pip install playwright", "playwright install chromium",
)
mac.run("python scrape.py", image=img)   # installs once; cached thereafter
```

### Moving big files — pull, don't push

```python
# The MAC downloads it, over its own connection. Zero relay bytes.
mac.fetch("https://example.com/App.dmg", "App.dmg")
mac.fetch(url, "model.safetensors", volume="weights", headers={"Authorization": "Bearer …"})
```

`push`/`Volume.put` send every byte from *you*, through the control plane and the
relay, to the Mac. Measured on a real fleet:

| path | throughput | a 572 MB app bundle |
|---|---|---|
| control plane on the same machine | ~24 MB/s | ~24 s |
| **through the relay** | **0.2–0.8 MB/s** | **13–41 min** |

The relay is a control channel, not a pipe — pushing a large artifact through it
is slow *and* saturates it for every other machine in the fleet meanwhile.
Parallel uploads only bought 1.4x, so it's throughput-limited end to end. If the
thing is fetchable, `mac.fetch()` has the Mac pull it directly and the relay
carries nothing but the command.

`push`/`put` do compress now (gzip, ~1.9x on Chrome.app, ~2.8x on Cursor.app)
and preserve the framework symlinks a `.app` needs to launch. There's still a
**512 MB** cap per upload — you'll be told immediately rather than at the end of
a long push.

Mac-to-Mac is the same trick: `expose()` the file on one and `fetch()` that URL
from the other, so the bytes go direct instead of hairpinning through the relay.
Keep `push`/`put` for what it's good at — source trees and small artifacts.

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

Read files back **out** of a volume, list it, or delete from it — no mount needed:

```python
data = herds.Volume.from_name("data").get("weights/model.bin")    # → bytes
herds.Volume.from_name("shots").get("home.png", "./home.png")     # → save locally
herds.Volume.from_name("repo").listdir("src")                     # → [{name,dir,size,mtime_ms}]
herds.Volume.from_name("tmp").remove("scratch")                   # delete (recursive)
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

**Snapshot a provisioned sandbox into a reusable base** (Modal's
`snapshot_filesystem`) so the next one starts pre-populated:

```python
with herds.Sandbox.create() as sbx:
    sbx.exec("pip install playwright && playwright install chromium", check=True)
    base = sbx.snapshot_filesystem("browser-env")     # tar workspace+home → named base

fresh = herds.Sandbox.create(image=base)              # starts already provisioned
```

### Expose a server — a sandbox becomes a URL

```python
sbx.spawn("python -m http.server 8000", keep_alive=True)
url = sbx.expose(8000)            # → https://you.relay.herds.run/p/<sbx>/8000/
```

Run a web app or API inside a sandbox and get a hittable public link. Requests
tunnel through the agent WebSocket — control plane → daemon → the sandbox's
`localhost:port` — so it works behind NAT with no inbound ports. With a wildcard
domain you get named subdomains (`https://myapi--teddy.herds.run`).

### Raw tunnels — any port as a live byte stream

`expose()` is buffered HTTP request/response. When you need a **persistent,
bidirectional** connection — a websocket, a database port, or Chrome DevTools
(CDP) — open a raw tunnel instead. Bytes flow both ways, untouched:

```python
with sbx.tunnel(9222) as t:        # raw pipe to localhost:9222 in the sandbox
    t.send(b"…"); data = t.recv()

url = sbx.tunnel_url(9222)          # or hand the ws:// URL to a CDP/websocket client
```

This is what lets you attach an **external** Playwright to a Chromium running on
the Mac, or stream a live browser view — control plane → daemon → the sandbox's
`localhost:port`, over the same NAT-friendly socket, no inbound ports. (An agent
running *inside* the sandbox never needs this — it drives Chromium over its own
localhost.)

### Driving the GUI — semantic, not pixels

```python
# pointer + keyboard, all real HID-level CGEvents
mac.ui.click(400, 300);  mac.ui.right_click(400, 300)
mac.ui.drag(100, 100, 400, 300)         # interpolated, so drop targets accept it
mac.ui.scroll(-250)
mac.ui.type("hello ünicode 🎉")          # layout-independent
mac.ui.hotkey("cmd", "s")

# windows: enumerate, move, resize, raise, focus/launch
mac.ui.focus("Preview")
for w in mac.ui.windows("Preview"):
    print(w["index"], w["title"], w["x"], w["y"], w["width"], w["height"])
mac.ui.move_window("Preview", 0, 0); mac.ui.resize_window("Preview", 1200, 800)

# Best: target the accessibility tree — survives windows moving.
save = mac.ui.find("Preview", role="AXButton", name="Save")
save.click()                            # clicks its centre
mac.ui.press_element("Preview", "Save") # or AXPress it — works even if occluded
mac.ui.menu("Finder", "New Window")

for el in mac.ui.tree("Finder", "menubar", depth=3):
    print(el.role, el.name, el.center)
```

Built on CGEvent and the AX C API rather than AppleScript. That's not a style
choice: AppleScript needs an **Automation** TCC grant, the consent prompt can
only be shown to a foreground app, and a launchd daemon therefore *hangs until
timeout* instead of failing. The C APIs need only **Accessibility**.

> **Check permissions on the Mac, not on your laptop.** TCC grants are
> per-process, so `herds doctor` audits the daemon:
> ```bash
> herds doctor            # probes the Mac's daemon (use --local for this process)
> ```
> If Accessibility is missing, synthetic events are **silently dropped** —
> `mac.ui.click()` returns success and nothing moves. `herds doctor` names the
> binary to grant.

### Mac-native control — the stuff only a real Mac can do

```python
mac.screenshot("home.png")           # capture the screen (needs Screen Recording perm)
mac.write("/tmp/config.json", data)  # write a file on the Mac
text = mac.read_text("~/notes.md")   # read one back
mac.ls("~/Projects")                 # → [{name, dir, size, mtime_ms}]
mac.copy("hello"); mac.clipboard()   # the Mac's clipboard
mac.notify("build done")             # a notification banner
mac.ui.type("hello"); mac.ui.key("return")        # keyboard control
mac.ui.hotkey("cmd", "s")            # chords (needs Accessibility perm)
```

Real macOS GUI + system control — native app testing, screenshots, automation —
the things a Linux sandbox can't do. `screenshot`/`ui.*` need Screen Recording /
Accessibility granted to whatever runs `herds host` (System Settings → Privacy).

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

### Bounding a Mac

A Mac isn't partitioned like a rented container, so Herds *bounds* it instead: a
cap on concurrent sandboxes with a small waiting queue, idle-session reaping, and
garbage-collection of stale sandbox trees so disk never silently fills. All
configurable, with safe defaults:

| env | default | what it does |
|---|---|---|
| `HERDS_MAX_LIVE_SANDBOXES` | `8` | max concurrent sandboxes/sessions before new work queues |
| `HERDS_ADMISSION_QUEUE_MAX` | `32` | queue depth once the cap is hit (past it, work is rejected, not piled up) |
| `HERDS_SESSION_IDLE_TIMEOUT_MS` | `30 min` | a resident session with no input this long is reaped |
| `HERDS_SANDBOX_TTL_MS` | `24 h` | a sandbox tree untouched this long (no live process) is garbage-collected |

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
                         (runs in the background; the Mac joins its own fleet)
herds host status|stop|logs  manage the background host  ·  --foreground to attach
herds skill [--install]  print/install the agent skill (SKILL.md) for Claude Code
herds mcp                MCP server — expose this Mac as tools for ANY agent
herds doctor             check macOS permissions for driving real apps
herds open               open your live dashboard in the browser
herds token new|ls|revoke   scoped, revocable tokens (read|run|admin) for agents/CI
herds schedule add|ls|rm    recurring cron jobs that run on your Mac
herds connect <token>    join another Mac (the token carries its own link)
herds disconnect [id]    remove a Mac from the fleet (revokes its token so it
                         can't rejoin) · no id = this Mac, and stops it locally
herds serve              run a bare control plane locally
herds machines           list your connected Macs
herds tag <id> <tags…>   label a Mac for routing  ·  herds tags  ·  herds untag <id> <tag>
herds run -- <cmd>       run a command on a Mac (streams output)
herds shell -c <cmd>     one-off command (SSH-equivalent)
  └ add --real to either  run as YOU on the real Mac (real $HOME, disk, logins)
                          — without it, writes land in a throwaway sandbox
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
- **Resident sessions** — feed a live process turn-by-turn (long-lived agents,
  the way spawn drives a Modal driver) — plus **raw port tunnels**
  (CDP/websockets), **image provisioning** (cached `run_commands`), **filesystem
  snapshots**, a full **volume read API** (get/listdir/remove), and per-Mac
  **admission control + idle/GC reaping**.

See [`ROADMAP.md`](ROADMAP.md) for what's next (Tart VM backend, per-token scopes,
code-shipping for functions).

## License

Apache-2.0
