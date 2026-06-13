# Herds — Roadmap

## ✅ Now (MVP — works end-to-end locally)

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
- CLI: `serve`, `connect`, `machines`, `run`, `shell`, `logs`, `status`,
  `volume {ls,create,rm}`, `image ls`, `install`/`uninstall` (launchd).

## 🔜 Next

- **Auth & accounts**: OAuth device-authorization flow for `herds connect`,
  per-machine device tokens, API keys, machine-ownership ACLs (the `Store`
  already models all of this; flip on `HERDS_REQUIRE_AUTH`). `herds login` /
  `herds token new`.
- **Hosted control plane**: deploy the FastAPI app; swap in-memory fan-out for
  Redis pub/sub and SQLite for Postgres (both isolated behind existing
  boundaries). Public TLS endpoint so Macs anywhere can connect.
- **Robust function shipping**: package dependencies + module context (beyond
  single-file `getsource`) so `@app.function` runs richer code remotely;
  `.spawn()` → `FunctionCall.get()`, `.map()` fan-out.
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
