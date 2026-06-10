# Darwin Cloud — Design

This document explains *why* Darwin is built the way it is. The product thesis:

> Connect your Mac to the internet and turn it into a programmable runtime.
> **Every Mac becomes an API.**

The developer surface deliberately mirrors Modal (`App`, `Image`, `Volume`,
`Sandbox`, `mac.run()`) because that mental model already lives in developers'
heads — but the runtime is the user's *own* Mac.

## Three components

### 1. Control plane (`darwin.control`)
A small FastAPI service. It does exactly three things:

1. Holds the persistent WebSocket from each Mac's daemon.
2. Accepts `exec` requests from the SDK (REST) and pushes them down the right
   agent socket.
3. Fans streamed stdout/stderr/exit frames back to the listening SDK client,
   correlated by `request_id`.

Durable facts — machines, API keys, device tokens, job history — live in SQLite
(`darwin.control.store`). Live connection state and the log fan-out are
in-memory. **It never stores volumes, sandboxes, images, or caches.** Those stay
on the Mac. The Mac is the cloud.

### 2. Daemon / agent (`darwin.daemon`)
Runs on the Mac. Holds **one persistent outbound WebSocket** to the control
plane and services commands pushed down it, streaming results back up.

Why outbound WebSocket? The Mac is behind NAT/firewall — nothing on the internet
can dial *in*. Every tool that solves this (GitHub Actions self-hosted runners,
Tailscale's DERP fallback, Cloudflare Tunnel, ngrok, Temporal/Modal workers)
uses the same move: the machine dials home and work comes back down the open
connection. It runs over 443, traverses corporate proxies, and needs no
port-forwarding. gRPC bidi streaming is the documented graduation path once
WebSocket framing becomes the bottleneck.

The daemon installs as a launchd **LaunchAgent** (runs as the user, with their
toolchains and keychain — not root), with `KeepAlive` for auto-restart and
reconnect-with-backoff in the loop.

### 3. SDK + CLI (`darwin.sdk`, `darwin.cli`)
The SDK is synchronous (user code is ordinary blocking Python): httpx to start a
job, the `websockets` sync client to stream logs back into a `Result`. The CLI
is Typer + Rich.

## The execution model (`darwin.daemon.executor`)

This is where the real macOS work happens. Each **sandbox** is the unit of
isolation:

- **Own directory tree** — `~/.darwin/sandboxes/<id>/{workspace,tmp,home}`.
- **Clean environment** — rebuilt from an allowlist (`env -i` style). `HOME`,
  `TMPDIR`, and the common toolchain caches (`DERIVED_DATA_PATH`,
  `npm_config_cache`, `PIP_CACHE_DIR`, `CARGO_HOME`, `XDG_*`) are redirected
  *into* the sandbox so concurrent jobs never clobber each other's caches.
- **Own process session** — `start_new_session=True`, so a timeout or cancel
  kills the entire process tree (`killpg`), not just the parent. macOS has no
  cgroups; process-group teardown is the lifecycle primitive.
- **Write-fence** — when `sandbox-exec` is present, the command is wrapped in a
  Seatbelt profile that confines writes to the sandbox + mounted volumes and can
  cut the network. This is workspace confinement for *trusted* code (the user
  owns the Mac), not an adversarial jail.

Everything degrades gracefully: a missing tool never hard-fails a run.

### Images = environment recipes
On a Mac an `Image` isn't a container; it's a recipe resolved on the host
(`darwin.daemon.images`):

- `Image.xcode("26")` → selects `DEVELOPER_DIR` (per-process — never clobbers a
  concurrent job the way `xcode-select --switch` would), via `xcodes` if needed.
- `Image.node("22")` / `Image.python("3.13")` → pins through `mise`.

If the toolchain isn't installed, the command runs on the host and Darwin
reports what it *would* have pinned (surfaced as a `darwin:` stderr note).

### Volumes = persistent directories
A `Volume` is a named directory under `~/.darwin/volumes/<name>`. Mounted into a
run, it's symlinked under the working directory at the mount name and exposed via
`$DARWIN_VOLUME_<NAME>`. No commit/reload — a local dir is durable on write — but
the no-op `commit()`/`reload()` methods exist so Modal code ports unchanged.

## Wire protocol (`darwin.protocol`)

One module holds every message shape so the three components can't drift. Frames
carry a `type`, a `request_id` (correlation), an optional `seq` (ordering/loss
detection), and a `data` payload. The agent socket multiplexes many concurrent
commands over one connection by `request_id`. A late log subscriber misses
nothing: the control plane buffers a request's frames and replays them on
subscribe.

## Why this shape scales without a rewrite

- **In-memory fan-out → Redis pub/sub**: the moment there's more than one control
  plane process, swap the in-memory subscriber map for Redis. The boundary is
  drawn at `Hub.publish` / `Hub.subscribe`.
- **SQLite → Postgres**: `Store` is the only thing touching the DB.
- **Host-process isolation → Tart VMs**: `Sandbox` and `Image` are interfaces; a
  Tart backend resolves `Image.xcode("26")` to an OCI tag and a `Volume` to a
  virtio-fs `--dir` share, with no SDK change. (Constraint to design around:
  Apple's EULA caps macOS VMs at **2 per physical host**, so macOS-VM slots are a
  scarce per-machine resource while host-process sandboxes scale with CPU.)

## Auth (roadmap-ready, permissive by default)

The store already models API keys (SDK → control plane) and device tokens
(daemon → control plane). For local use auth is off so the magic works
instantly; set `DARWIN_REQUIRE_AUTH=1` to enforce keys and machine-ownership
ACLs. The intended `darwin connect` flow is OAuth device authorization → a
per-machine device token, exactly the IoT-style enrollment pattern.
