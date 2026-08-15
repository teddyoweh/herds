# Changelog

What changed, and why it had to. Headlines are the release commits' own — the
full story behind any entry is `git log`, where each release explains itself.

## 0.9.8 — 2026-08-15

**The control plane's history stays bounded, and its database stops being the
bottleneck.** Found on a Mac mini whose host.db had grown to 1.4 GB: finished
jobs lived forever, the pre-0.9.7 sync path had written multi-megabyte base64
tars into job output, and metric samples accumulated every heartbeat since the
beginning of time. On top of that the connection ran SQLite's default journal
mode — readers block the writer, and eight concurrent jobs stampede into
"database is locked". The machine read as online while every run queued for
minutes; the daemon's 8-wide admission gate was never the problem. Now: WAL +
busy_timeout on every connection, and retention at each host start — finished
jobs kept a week, outputs capped at 256 KB, metrics kept to a recent window,
VACUUM when meaningful space comes back. A drowning machine heals by
restarting.

## Unreleased

**Known, not yet fixed:** `herds auth --repoint` silently no-ops when
`HERDS_CONTROL_PLANE` is set — and the daemon injects exactly that variable
into commands it runs, so the repair tool cannot repair a machine you are
driving remotely, and says nothing about why. Found while unfracturing a Mac
mini from its accidental one-machine fleet; the env override should at least
announce itself, and `--repoint` should override it or say it can't.
Related: deleting `host.json` breaks `child stop`'s ability to find the pid,
so a stop/start bounce silently becomes a no-op while the old host keeps its
old registration. Identity and process state need one story — see `doctor`.

Two more from the same field day: **the run queue is invisible and unbounded**
— a Mac reads "online" while hours of queued jobs make every `run()` take
minutes, and nothing anywhere reports depth; "online" must mean *answers
work*, not *socket connected*. And **two supervisors ran side by side** on one
Mac (`child --foreground` × 2, both under launchd, respawning duelling stacks
on ports 8788/8790) — the duplicate-host check in `run_host` guards one port,
not the machine.

## 0.9.7 — 2026-08-15

First release on PyPI since 0.9.5 — 0.9.6 was tagged but never published, so
its venv/installer work ships here. Also fixes the release workflow itself,
which never built the dashboard: a CI-published wheel would have shipped
without the UI.

**Files move between Macs at network speed — `herds cp`, `mac.pull`, `mac.send`.**
Push has been direct-first since 0.5.0, but everything coming *back* still rode
the relay at ~0.5 MB/s, Mac-to-Mac transfer didn't exist at all, and the
`expose()` the fetch docstring promised was never built. The far Mac now serves
a path itself — one archive, one unguessable token, short TTL, tailnet-first —
and the other end pulls it directly. Measured: 210 MB in 2.4 s (~86 MB/s) where
the relay path takes ~7 minutes. Every direction falls back to the relay when
there's no shared network, so it is only ever faster.

```
herds cp ./build.zip mini:~/incoming        # here → Mac
herds cp mini:~/renders/out.mov .           # Mac → here
herds cp studio:~/data.tar mini:~/data      # Mac → Mac, no middleman
```

**`herds child` announces the fork before minting a fleet of one.** On a Mac
that isn't signed in, `child` provisions a fresh anonymous account — that's the
zero-signup front door, and it stays. But it did it silently, which is how a
second Mac walks off into its own universe: signed in on the laptop, ran
`child` on the new Mac, and that Mac became its own one-machine fleet — online,
healthy, and invisible from every other machine its owner drives. Now it says
so first, and on a terminal it asks (default yes, so hello-world is still one
command and one Enter). Automation is never prompted.

## 0.9.6 — 2026-08-07

The CLI stops being a tenant of somebody's venv. `herds link` from a venv now
installs herds standalone (uv or pipx) instead of symlinking a binary that dies
with the project; the installer never installs into an active venv, and names
the stale herds sitting earlier on PATH — the failure that looks exactly like
success.

## 0.9.5 — 2026-08-06

A Linux child could register but never run anything: the daemon assumed
`/bin/zsh`. A Raspberry Pi came up online and failed every command.

## 0.9.4 — 2026-08-06

A pasted token survives the trip, and says why when it can't. Tokens copied
through phones arrive with U+00D7 for `x` and spaces after dots; `herds use`
now repairs what's unambiguous and names the injury when it isn't.

## 0.9.3 — 2026-08-06

`herds update`, using whatever installed it. Herds arrives four ways and each
upgrades differently — `pip install -U` against a uv-managed tool reports
success and changes nothing.

## 0.9.2 — 2026-08-06

`herds link`: one command to put herds on your PATH, wherever pip hid it.

## 0.9.1 — 2026-08-06

The last two `herds host` hints inside `child` output.

## 0.9.0 — 2026-08-06

One command, not two: `host` folds into `child`. They ran identical code and
differed only in panel text — now one Typer group mounted under both names,
`host` hidden but working, and a test asserts they're the same object rather
than trusting it.

## 0.8.x — 2026-08-06

**0.8.0** One command to be drivable, one token to drive it: `herds child`
provisions a link on our own relay with no account and no signup — Cloudflare
quick tunnels demoted to the last resort they should always have been.
**0.8.1–0.8.3** The docs, the hero, and `child`'s own output all stop talking
about "hosting".

## 0.7.x — 2026-08-02 → 08-06

**0.7.0** Select a Mac by name, prefix or tag — `herds.mac("Teddys Mac mini")`
— instead of the exact `mac_xxxxxxxx` id, which was the only handle that
actually worked. **0.7.2** Four bugs found pulling one thread ("is the Mac mini
active?"), including an error handler that raised its own failure. **0.7.3**
Hosting a fleet and joining one are two roles, not one credential slot they
fight over. **0.7.6** Sign in on any machine and drive — the account token was
already a valid API key; nothing wrote it where the client looked.

## 0.6.x — 2026-08-02

**0.6.0** `mac.shell()`: an interactive terminal on a Mac without ssh — a pty
via `script -q /dev/null`, no protocol change, works against old daemons.
**0.6.1** A shell always says which Mac it landed on, and never guesses.

## 0.5.0 — 2026-08-01

Push routes around the relay: the payload is served from an ephemeral local
port and the Mac pulls it directly. Same 41 MB payload: relay 14.87 s, direct
1.33 s. The relay is throughput-limited (~0.5 MB/s, parallelism bought 1.4×),
so the only fix was to stop using it for bulk bytes — the pattern the
Unreleased transfer work completes in the other directions.

## 0.4.x — 2026-08-01

**0.4.0** One token to join a Mac: `herds_sk_…@you.relay.herds.run` — the
endpoint travels inside the credential, shaped like user@host on purpose.
**0.4.1** `mac.fetch()`: the Mac downloads big files itself (~24 MB/s) instead
of receiving them through the relay (0.2–0.8 MB/s; a 572 MB bundle in ~24 s
instead of 13–41 min). **0.4.2** Compress pushes, keep symlinks — a macOS .app
arrived without its framework layout — and fail fast.

## 0.3.x — 2026-08-01

**0.3.0** COW snapshots, real GUI control (CGEvent/AX off AppleScript), and a
doctor that audits the Mac instead of the laptop you typed on. **0.3.1**
Keyboard off AppleScript too; credential-blind sandboxes. **0.3.2**
`herds disconnect`: a decommissioned Mac could never be removed and kept a
valid device token forever.

## 0.2.x — 2026-07-20 → 08-01

Modal-parity primitives: sessions, tunnels, provisioning, the volume API,
admin keys, device metadata. **0.2.2** Python 3.9+ (was 3.11+). **0.2.3** The
host registers with real specs instead of joining its own fleet specless.

## 0.1.x — 2026-06

The proving ground: relay, daemon, sandboxes, the first SDK. Ended at 0.1.24
with the wss certificate fix that let a stock macOS Python connect at all.
