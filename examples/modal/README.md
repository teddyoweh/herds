# The same code, Modal vs Herds

Herds echoes Modal on purpose — `App`, `Image`, `Volume`, `Sandbox` — so the
mental model transfers directly. The only real difference is *where it runs*:
Modal rents you Linux; Herds is **your Mac**, already licensed, on the internet.

| File | Modal | Herds (`../`) |
|------|-------|---------------|
| `remote_function.py` | `@app.function` → `.remote()` on rented Linux | identical API, runs on your Mac |
| `remote_quickstart.py` | App · Volume · Sandbox on Linux | identical API, on your Mac |
| `deploy_app.py` | `modal deploy` — scheduled + web functions in their cloud | `herds deploy` — same, running on your Mac |
| `claude_agent.py` | Claude in a sandbox — **key lives in their cloud** | Claude on your Mac, its own login |
| `ios_build.py` | ✗ **impossible** — no macOS/Xcode on Modal | real Xcode + Swift build |
| `keyless_agent.py` | ✗ **impossible** — key must be in their cloud | keyless, key never touches the Mac |

```bash
pip install modal && modal setup
modal run examples/modal/remote_function.py
```

The last two rows are the point: the moment you need macOS, or you don't want
your model key sitting in someone else's cloud, only your own Mac will do.
