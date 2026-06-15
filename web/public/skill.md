---
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

## Run commands

```python
mac = herds.mac()
print(mac.run("sw_vers").stdout)
mac.run("xcodebuild -scheme App test", check=True)        # real Xcode; raises on failure
for stream, line in mac.stream("swift build"):             # stream output live
    print(line)
mac.map("pytest {}", ["tests/unit", "tests/e2e"])          # fan out across inputs, in parallel
```

A `Result` has `.stdout`, `.stderr`, `.exit_code`, `.ok`. One Mac handles many
concurrent commands, so a fleet of agents can share it.

## Ship a codebase, then run it

```python
herds.Volume.from_name("repo").put("./my-project")         # tar + extract on the Mac (junk pruned)
mac.run("python3 app/main.py", volumes={"app": herds.Volume.from_name("repo")})

sbx = herds.Sandbox.create()
sbx.put("./my-project")                                     # …or straight into a sandbox
sbx.exec("python3 main.py")
```

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
