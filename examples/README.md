# Examples

Paste your Mac's URL + token at the top of a file, run it, drive the Mac from anywhere.

```bash
pip install herds
# edit the url + token in the file, then:
python examples/remote_quickstart.py
```

Get the two values from your Mac: `herds host` prints the URL, `herds token new
my-agent --scope run` mints a scoped, revocable token. Every script is
self-contained — one line up top:

```python
mac = herds.mac(url="https://you.herds.run", token="hx_...")
```

| File | What it shows |
|------|---------------|
| `remote_quickstart.py` | run · stream · volume · sandbox — the whole SDK in one file |
| `ios_build.py`         | a real Apple-toolchain build on the remote Mac (Xcode + Swift) |
| `remote_function.py`   | Modal-style `@app.function` → `.remote()` runs Python on the Mac |
| `deploy_app.py`        | `herds deploy` — scheduled + triggerable + web-endpoint functions that run without your laptop |
| `claude_agent.py`      | Claude Code (its login on the Mac) writes code, then runs it |
| `keyless_agent.py`     | run an agent *on* the Mac keyless — model key never touches it |

Runs, sandboxes, and functions are grouped by **App** — see them in the dashboard
under **Apps**, or `herds app ls`.

## Modal vs Herds

Each example has a Modal mirror in [`modal/`](./modal) — nearly identical code,
because Herds echoes Modal's `App` / `Image` / `Volume` / `Sandbox` on purpose.
The difference is where it runs: Modal rents Linux; Herds is your Mac. Two of the
mirrors can't exist on Modal at all (`ios_build`, `keyless_agent`) — that's the point.
