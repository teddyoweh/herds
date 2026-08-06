"""The Herds agent skill (SKILL.md) — shipped with the package so `herds skill`
can print it or install it into ~/.claude/skills/herds/ for Claude Code.

Kept in sync with web/public/skill.md (the version served at herds.run/skill.md).
Every API call below is checked against the live SDK by tests/test_skill.py — an
agent acting on a wrong signature has no way to tell it was the docs that lied.
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

## Given a Mac? (a URL + token)

If you were handed a Herds **URL + token**, that's all you need — point the SDK at it:

```python
pip install herds
```
```python
import herds
herds.configure(url="https://you.relay.herds.run", token="hx_…")
herds.mac().run("uname -msr")          # runs on that Mac, from anywhere
```
(Or set `HERDS_CONTROL_PLANE` + `HERDS_API_KEY` in the env — same effect.)

To connect your OWN Mac instead: `pip install herds && herds auth && herds host`.

## Given nothing? (make a machine drivable)

On the machine you want to drive — no account, no signup:

```bash
herds child                # prints: herds use herds_sk_…@studio.relay.herds.run
```

Then from anywhere: `herds use <that token>` and you're driving it. Hold several
fleets at once and switch by name — `herds contexts`, `herds use work`. From Python:

```python
herds.use("studio")        # this process drives that fleet
herds.contexts()           # [{"name": "studio", "active": True, …}]
```

## Pick which Mac

```python
herds.mac()                      # the idlest online Mac
herds.mac("mini")                # by name, id, or a prefix of either
herds.mac(tag="xcode-26")        # idlest Mac carrying that tag (or chip)
herds.mac(url="https://you.relay.herds.run", token="hx_…")   # a specific host
```

Ambiguous names are reported, never guessed. Tags are set with `herds tag <id> <tag>`.

## Run commands

```python
mac = herds.mac()
print(mac.run("sw_vers").stdout)
mac.run("xcodebuild -scheme App test", check=True)        # real Xcode; raises on failure
for stream, line in mac.stream("swift build"):             # stream output live
    print(line)
mac.map("pytest {}", ["tests/unit", "tests/e2e"])          # parallel across inputs, ON THIS MAC
```

A `Result` has `.stdout`, `.stderr`, `.exit_code`, `.ok`. One Mac handles many
concurrent commands, so a fleet of agents can share it.

## Use every Mac at once

`mac.map` parallelises across inputs on **one** machine. To spread the same work
over **all** your Macs, use the fleet:

```python
herds.fleet().map("pytest {}", ALL_TEST_DIRS)    # N Macs → N× throughput
herds.fleet().macs()                              # the online Macs, as Mac objects
herds.fleet().agent("upgrade deps", proxy=PROXY, secret="proxyagent")  # same task, every Mac
```

Work-stealing, not round-robin: each Mac takes up to `per_mac` tasks (4 by default)
and pulls the next the moment it's free, so idler Macs do more and none is swamped.
A fleet call targets Macs connected *right now*, and raises if none are.

## Ship a codebase, then run it

```python
mac.push("./my-project", "repo")                  # → a named volume on the Mac
mac.run("python3 app/main.py", volumes={"app": herds.Volume.from_name("repo")})
```

`push` has the Mac pull the payload **directly from your machine** (LAN/tailnet)
instead of streaming every byte through the relay, which sustains only ~0.5 MB/s
and is shared by the whole fleet. Pass `direct=False` to force the relay path.
For a one-off workspace, `sbx.put("./my-project")` ships straight into a sandbox.

## Long-running processes you feed turn by turn

```python
s = mac.session("python3 -i")     # a RESIDENT process, not one command
s.send("import platform; print(platform.machine())\\n")
for stream, text in s.stream():   # output streams back live
    print(text)
s.close()
```

Use a session when you need state to persist between inputs (a REPL, a debugger,
an interactive installer). Use `mac.run` for anything that just starts and ends.

`mac.shell()` is the *human* front door — it takes over your terminal with a real
pty (Ctrl-] detaches), or from the CLI, `herds ssh <machine>`. In a script or
notebook, with no terminal to attach to, it hands back a `Session` instead.

## Mac-native control (only a real Mac can do this)

```python
mac.screenshot("home.png")           # capture the screen
mac.write("/tmp/x.json", data); mac.read_text("~/notes.md"); mac.ls("~/Projects")
mac.copy("hi"); mac.clipboard()      # clipboard
mac.notify("done")                   # notification banner
mac.ui.type("hello"); mac.ui.key("return"); mac.ui.hotkey("cmd", "s")  # keyboard/GUI
```

`screenshot` / `mac.ui.*` need Screen Recording / Accessibility granted to the
process running `herds host` (System Settings → Privacy & Security).

## Drive real apps (the moat)

`mac.run` runs in the user's REAL login session (not a sandbox), so it drives real
apps with their real logins/data. Run `herds doctor` to check macOS permissions.

```python
# Chrome — the user's real profile (cookies, logins):
c = mac.chrome("https://news.ycombinator.com")
c.js("document.querySelectorAll('.titleline a')[0].innerText")   # run JS in the tab
# (js() needs Chrome's View → Developer → Allow JavaScript from Apple Events)
# For Playwright: mac.chrome(cdp_port=9222) then attach over the DevTools Protocol.

# Xcode / Simulator — builds are headless; the Simulator needs the GUI session:
mac.run("xcodebuild -scheme App -destination 'platform=iOS Simulator,name=iPhone 16' test")
mac.run("xcrun simctl boot 'iPhone 16'; xcrun simctl launch booted com.you.App")

# iMessage — real account + history (needs Full Disk Access + Automation):
mac.run("sqlite3 ~/Library/Messages/chat.db 'select text from message order by date desc limit 5'")
mac.run(['osascript','-e','tell application "Messages" to send "hi" to buddy "+15551234567"'])
```

Driving GUI apps needs: a **logged-in GUI session** (use `herds install` → a
LaunchAgent), plus the right permissions (`herds doctor` lists what's missing).

## Sandboxes — isolated, persistent workspaces

```python
sbx = herds.Sandbox.create()
sbx.exec("git clone https://github.com/me/app .")
sbx.exec("npm install && npm run build", check=True)
sbx.spawn("npm run dev", keep_alive=True)                  # long-running server
url = sbx.expose(3000)                                      # -> a public URL
```

## Volumes & secrets

```python
vol = herds.Volume.from_name("builds")
mac.run("xcodebuild archive", volumes={"out": vol})        # persistent dir
mac.run("./deploy.sh", secrets=["appstore"])               # injected env
```

## Remote Python — run a function on the Mac

```python
app = herds.App("ci")
@app.function(image=herds.Image.python("3.13"))            # must live in a .py file
def build(target: str) -> dict:
    import platform; return {"target": target, "ran_on": platform.node()}
build.remote("release")                                     # ships source, runs on the Mac
```

## CLI

```
herds run -- <cmd>      run a command on a Mac (streams output)
herds ssh [machine]     interactive terminal on a Mac (Ctrl-] detaches)
herds machines          list your connected Macs
herds tags              list Macs with their tags, status, and live CPU
herds host              self-host control plane + dashboard + public link
herds connect <token>   join THIS Mac to a fleet (the token carries its link)
```

Every command that takes a machine accepts an id, a name, a prefix of either, or
a tag — `-m mini`, `-m ci`, `-m mac_ed74`.

## When to reach for Herds

- The task needs **real macOS** — Xcode / Swift builds, iOS Simulator, code-signing,
  AppleScript / automation, testing native Mac apps.
- You want to **run a server** in a sandbox and get a **public URL**.
- You need a **persistent workspace** that survives across steps.
- You have **several Macs** and want the work spread across all of them.

Docs: https://herds.run · Repo: https://github.com/teddyoweh/herds
'''
