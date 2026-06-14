# Herds — Roadmap

## ✅ Shipped

- Daemon dials home over a persistent WebSocket; reconnects with backoff.
- Control plane: register machines, dispatch `exec`, fan out streamed logs,
  SQLite-backed machine/job/key store.
- SDK: `mac.run()` (blocking + `stream=True` + `stream()` iterator), `Result`,
  `Image` (xcode/node/python recipes), `Volume`, `Sandbox` (persistent
  workspace), `App`/`@app.function` with genuine remote-Python via source
  shipping.
- Executor: per-sandbox dir, env isolation, toolchain-cache redirection,
  process-group kill-tree, timeouts, `sandbox-exec` write-fence, graceful
  toolchain degradation.
- CLI: `auth`, `host`, `skill`, `serve`, `connect`, `machines`, `run`, `shell`,
  `logs`, `status`, `volume {ls,create,rm}`, `image ls`, `install`/`uninstall`.

### Hosted platform & agents

- **`pip install herds`** on [PyPI](https://pypi.org/project/herds/) — the full
  dashboard is bundled into the wheel (no Node.js at runtime).
- **Hosted relay**: `herds auth` + `herds host` → a permanent, branded link
  (`you.relay.herds.run`) with no inbound ports; magic-link dashboard auto-auth.
- **Accounts**: email + password (scrypt) on a Neon **Postgres** store, or
  passwordless CLI tokens; web platform dashboard at [herds.run](https://herds.run).
- **Agents anywhere**: a remote agent holding only a token runs `mac.run()` and
  streams logs over the relay — HTTP *and* WebSocket tunnelled through the host
  socket, so no SSH/VPN/inbound ports.

## 🔜 Next

- **Per-token scopes & revocation**: an agent token is full shell access today —
  add scoped, expiring tokens and a revoke list.
- **Slim SDK install**: move `fastapi`/`uvicorn` to a `[host]` extra so agents get
  a tiny `pip install herds`.
- **Scale-out**: Redis pub/sub fan-out + connection-stability hardening for many
  concurrent hosts on one relay.
- **Robust function shipping**: package dependencies + module context (beyond
  single-file `getsource`); `.spawn()` → `FunctionCall.get()`, `.map()` fan-out.
- **`herds shell`**: a true interactive PTY session, not just `-c`.
- **Scheduled jobs**: `@app.function(schedule=herds.Cron("0 9 * * *"))` driven by
  the control plane.

## 🌋 Premium isolation tier — Tart VMs

- Add a **Tart** backend (Apple Virtualization.framework): `Image.xcode("26")`
  → OCI image tag, `Volume` → virtio-fs `--dir` share, near-instant APFS
  copy-on-write clones, warm VM pool for ~1s starts.
- Respect Apple's EULA: **≤2 macOS VMs per physical host** — the scheduler
  treats macOS-VM slots as a scarce per-machine resource; host-process sandboxes
  and Linux containers scale freely.
- **Apple `container`** backend (macOS 26 Tahoe) for Linux jobs
  (`Image.node`/`Image.python`) — sub-second, OCI-native, per-container VM
  isolation. Keep Tart macOS VMs for Xcode/Apple work.

## 🔭 Later

- Throwaway/recycled local-user pool for stronger filesystem isolation without a
  VM.
- Web dashboard for machines, jobs, logs.
- Distribution: Homebrew tap (`brew install herds`) with a
  `virtualenv_install_with_resources` formula and a `service do` block; later a
  signed/notarized single binary.
- Volume snapshots & sharing; per-volume APFS quotas.
- Marketplace risk note: any "rent my idle Mac to third parties" feature must
  clear Apple's SLA "service bureau / time-sharing" clause — keep the safe core
  as "my Mac, my SDK."
