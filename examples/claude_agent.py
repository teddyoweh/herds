"""Run Claude on your Mac, through Herds — the whole thesis in one file.

A Claude Code agent executes inside a Herds sandbox: an isolated working
directory on your Mac, but with your *real* Claude login (inherit_home=True).
The SDK orchestrates a small agent loop — ask Claude to write code, drop it in
the sandbox, run it — all on a Mac that could be anywhere on the internet.

    herds serve        # terminal A
    herds connect      # terminal B
    python examples/claude_agent.py

Requires Claude Code (`brew install claude` / logged in) on the connected Mac.
"""

import base64
import re
import herds


def extract_code(text: str) -> str:
    """Pull the first fenced code block from Claude's reply; else use it whole."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def main() -> None:
    mac = herds.mac()
    print(f"Mac: {mac.name}\n")

    # An isolated workspace, but with your real tools + Claude login.
    sbx = herds.Sandbox.create(mac=mac, inherit_home=True)
    print(f"sandbox: {sbx.id}\n")

    v = sbx.exec("claude --version", timeout=60)
    print(f"claude: {v.stdout.strip()}\n")

    # 1. Ask Claude (running on the Mac) to write a program.
    task = (
        "Write a Python program that prints the 12th prime number. "
        "Put the code in a single ```python fenced block."
    )
    gen = sbx.exec(f'claude -p {task!r}', timeout=180)
    code = extract_code(gen.stdout)
    print("Claude wrote:\n" + "\n".join("  " + l for l in code.splitlines()) + "\n")

    # 2. Drop it into the sandbox workspace (base64 avoids any quoting drama).
    b64 = base64.b64encode(code.encode()).decode()
    sbx.exec(f"echo {b64} | base64 -d > solution.py")

    # 3. Run what the agent produced.
    out = sbx.exec("python3 solution.py", timeout=30)
    print(f"Program output: {out.stdout.strip()}  (exit {out.exit_code})")

    print(f"\nInspect this whole session in the dashboard → Sandboxes → {sbx.id}")


if __name__ == "__main__":
    main()
