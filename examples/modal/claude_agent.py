"""Modal — Claude Code in a sandbox. Mirror of ../claude_agent.py.

    modal run examples/modal/claude_agent.py

The difference: on Modal the model API key must live in the cloud (a modal.Secret
baked into the container). Herds runs the agent on your Mac keyless — the key
never touches the machine (see ../keyless_agent.py).
"""

import modal

app = modal.App("claude-demo")
image = modal.Image.debian_slim().apt_install("nodejs", "npm").run_commands(
    "npm i -g @anthropic-ai/claude-code"
)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic")])
def solve() -> str:
    import subprocess
    task = "Write and run a Python one-liner that prints the 12th prime. Output just the number."
    return subprocess.run(["claude", "-p", task], capture_output=True, text=True).stdout


@app.local_entrypoint()
def main():
    print(solve.remote().strip())
