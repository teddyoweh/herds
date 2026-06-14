"""The Herds agent skill (SKILL.md) — shipped with the package so `herds skill`
can print it or install it into ~/.claude/skills/herds/ for Claude Code.

Kept in sync with web/public/skill.md (the version served at herds.run/skill.md).
"""

SKILL_MD = '''---
name: herds
description: Give your agent a real Mac. Run shell commands, Xcode/Swift builds, native app testing, and macOS automation on a Mac you own — or spin up persistent sandboxes and expose servers as public URLs. Use whenever a task needs real macOS that a Linux sandbox can't do.
homepage: https://herds.run
---

# Herds — give your agent a real Mac

Herds turns any Mac into a programmable runtime your agent controls from anywhere.
The Mac dials home over a WebSocket (no inbound ports), so an agent runs commands
on it through a tiny control plane.

## Connect a Mac (one time)

```bash
pip install herds
herds auth                 # sign in -> get an hx_... token
herds host                 # this Mac goes live at https://you.relay.herds.run
```

## Run commands (Python SDK)

```python
import herds

mac = herds.mac()
print(mac.run("sw_vers").stdout)
mac.run("xcodebuild -scheme App test", check=True)      # real Xcode
for stream, line in mac.stream("swift build"):           # stream output live
    print(line)
```

## Sandboxes — isolated, persistent workspaces

```python
sbx = herds.Sandbox.create()
sbx.exec("git clone https://github.com/me/app .")
sbx.exec("npm install && npm run build", check=True)
sbx.spawn("npm run dev", keep_alive=True)                # long-running server
url = sbx.expose(3000)                                    # -> a public URL
```

## Volumes & secrets

```python
vol = herds.Volume.from_name("builds")
mac.run("xcodebuild archive", volumes={"out": vol})      # persistent dir
mac.run("./deploy.sh", secrets=["appstore"])             # injected env
```

## CLI

```
herds run -- <cmd>      run a command on a Mac (streams output)
herds machines          list your connected Macs
herds host              self-host control plane + dashboard + public link
herds connect <link>    join another Mac to your pool
```

## When to reach for Herds

- The task needs **real macOS** — Xcode / Swift builds, iOS Simulator, code-signing,
  AppleScript / automation, testing native Mac apps.
- You want to **run a server** in a sandbox and get a **public URL**.
- You need a **persistent workspace** that survives across steps.

Docs: https://herds.run · Repo: https://github.com/teddyoweh/herds
'''
