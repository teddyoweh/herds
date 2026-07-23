"""Run a real Claude Code agent ON the Mac — keyless.

Every model call routes through your proxyagent proxy, so the model API key never
touches the Mac; it only ever holds a scoped, revocable token. Output streams back.

    python examples/keyless_agent.py

The Mac needs `proxyagent` and the agent CLI installed
(pip install proxyagent · npm i -g @anthropic-ai/claude-code).
"""

import herds

mac = herds.mac(url="https://you.herds.run", token="hx_...")   # from `herds host`

mac.agent(
    "list the files here and summarise what this project does in two sentences",
    proxy="https://proxy.you.com",   # your proxyagent proxy — the real model key stays here
    secret="proxyagent",             # a Herds Secret holding the scoped token; never on disk
    stream=True,
    app="keyless-agent",             # groups this run under an App
)
