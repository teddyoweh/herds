"""Modal — the mirror of ../keyless_agent.py that can't be keyless.

To run an agent on Modal, the model API key has to be inside the container —
a modal.Secret injected into the cloud you don't own. There's no "run it on a
machine that never holds the key" story, because the machine is theirs.

Herds inverts it: the agent runs on *your* Mac, and every model call routes
through your proxy — the real key stays on the proxy, the Mac holds only a
scoped, revocable token. Run ../keyless_agent.py instead.
"""

raise SystemExit("Modal has no keyless path — the key lives in their cloud. Use Herds: examples/keyless_agent.py")
