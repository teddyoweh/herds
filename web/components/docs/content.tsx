"use client";

import type { ReactNode } from "react";
import { A, Callout, Card, CardGrid, Co, Code, Divider, Endpoints, H2, H3, Lead, LI, P, Params, UL } from "./ui";

/* ------------------------------------------------------------------ *
 * Docs content. Each page is a small component built from the docs
 * primitives. Accurate to the implemented Herds SDK / CLI / API.
 * ------------------------------------------------------------------ */

export type Go = (id: string) => void;
export type DocPage = { id: string; group: string; title: string; description: string; Body: (p: { go: Go }) => ReactNode };

export const GROUPS = ["Getting started", "Core concepts", "Python SDK", "Command line", "Self-hosting", "Reference"];

/* ============================ Getting started ============================= */

const Introduction = ({ go }: { go: Go }) => (
  <>
    <Lead>
      Herds turns any Mac you own into a programmable cloud runtime — a real machine your code, agents, SDKs, and CLIs can drive
      from anywhere. Think Modal, but the sandbox is macOS: Xcode builds, iOS simulators, codesigning, AppleScript, and native
      app testing, exposed as an API.
    </Lead>

    <H2>The idea</H2>
    <P>
      Linux sandboxes can&rsquo;t build an iOS app, open a simulator, or codesign a binary. Real Apple work needs a real Mac. Herds
      takes the Mac on your desk and makes it callable: it dials home over a single outbound WebSocket (no inbound ports, no port
      forwarding), connects to a tiny control plane, and from then on you run commands on it from a Python SDK or the CLI.
    </P>

    <H2>Two commands</H2>
    <P>
      One on the machine you want to drive, one wherever you want to drive it from. No account, no signup, no inbound
      ports.
    </P>
    <Code lang="bash">{`herds child                                   # on the Mac — prints one token
herds use herds_sk_…@studio.relay.herds.run   # anywhere else — now you're driving it`}</Code>
    <P>
      Several Macs that should answer as one pool instead? That&rsquo;s{" "}
      <Co>herds host</Co> — see <A href="#" onClick={(e) => { e.preventDefault(); go("fleets"); }}>Fleets you can drive</A>.
    </P>

    <Callout type="tip" title="The mental model">
      A <Co>Mac</Co> is a machine you control. A <Co>Sandbox</Co> is an isolated, persistent workspace on it. A <Co>Volume</Co> is a
      named directory that survives across runs. You <Co>run</Co> commands, <Co>expose</Co> ports as public URLs, and ship code with{" "}
      <Co>put</Co>. If you&rsquo;ve used Modal, this will feel familiar.
    </Callout>

    <H2>What you can do</H2>
    <UL>
      <LI>Run shell commands, Xcode/Swift builds, and test suites on a real Mac — synchronously, streamed, or fanned out in parallel.</LI>
      <LI>Spin up persistent <strong className="font-semibold text-stone-800">sandboxes</strong>, ship a codebase into them, and run long-lived servers.</LI>
      <LI><strong className="font-semibold text-stone-800">Expose a port</strong> running in a sandbox as a public URL — share a preview or hit an endpoint.</LI>
      <LI>Mount durable <strong className="font-semibold text-stone-800">volumes</strong> so caches, builds, and state survive across runs.</LI>
      <LI>Run a Python function <strong className="font-semibold text-stone-800">remotely</strong> on the Mac with a decorator.</LI>
      <LI>Join several Macs into one <strong className="font-semibold text-stone-800">fleet</strong> and address them by name.</LI>
      <LI>Run a real <strong className="font-semibold text-stone-800">agent</strong> — Claude Code, Codex, or your own — <em>on</em> a Mac, keyless, with output streamed back.</LI>
    </UL>

    <H2>Start here</H2>
    <CardGrid>
      <Card title="Quickstart" desc="From pip install to your first command on a Mac, in under a minute." onClick={() => go("quickstart")} />
      <Card title="Fleets you can drive" desc="herds child, herds use, and holding several fleets at once." onClick={() => go("fleets")} />
      <Card title="How it works" desc="The daemon, the control plane, and the relay — and why there are no inbound ports." onClick={() => go("how-it-works")} />
      <Card title="Running commands" desc="run, stream, and map — the core of the Python SDK." onClick={() => go("commands")} />
      <Card title="Sandboxes" desc="Isolated, persistent workspaces with public URLs." onClick={() => go("sandboxes")} />
      <Card title="Sessions" desc="Long-lived processes you drive turn by turn — how a resident agent runs on a Mac." onClick={() => go("sessions")} />
      <Card title="Agents (keyless)" desc="Run Claude Code / Codex on a Mac — no model key on the machine." onClick={() => go("agents")} />
    </CardGrid>
  </>
);

const Quickstart = ({ go }: { go: Go }) => (
  <>
    <Lead>
      Two commands: one on the Mac you want to drive, one wherever you want to drive it from.
    </Lead>

    <H2>1 · Install</H2>
    <Code lang="bash">{`uv tool install herds    # recommended (or: pipx install herds)
pip install herds        # into a project's environment, for the SDK`}</Code>
    <P>
      Herds needs Python 3.9 or newer, and ships both the <Co>herds</Co> Python SDK and the <Co>herds</Co>{" "}
      command-line tool. See <A href="#" onClick={(e) => { e.preventDefault(); go("installation"); }}>Installation</A>{" "}
      if <Co>herds</Co> isn&rsquo;t found afterwards.
    </P>

    <H2>2 · On the Mac: make it drivable</H2>
    <Code lang="bash">{`herds child`}</Code>
    <Code lang="text">{`✓ This machine is live and drivable

  Take this anywhere and drive it
    herds use herds_sk_…@studio.relay.herds.run`}</Code>
    <P>
      No account and no signup — it provisions a link on the Herds relay, starts a local control plane, registers this
      Mac, and prints one credential that carries its own address. No inbound port is opened: the Mac dials out.
    </P>

    <H2>3 · Anywhere else: drive it</H2>
    <P>Any machine — another Mac, a Linux box, a Windows PC:</P>
    <Code lang="bash">{`herds use herds_sk_…@studio.relay.herds.run
✓ Driving studio — 1 machine, 1 online

herds run -- uname -msr
herds machines`}</Code>
    <P>
      …and from Python, with nothing further to configure:
    </P>
    <Code lang="python">{`import herds

mac = herds.mac()                       # the idlest Mac in your fleet
print(mac.run("sw_vers").stdout)
mac.run("xcodebuild -scheme App test", check=True)   # real Xcode; raises on non-zero exit`}</Code>
    <Callout type="tip" title="More than one fleet">
      <Co>herds use</Co> holds as many as you like and switches by name —{" "}
      <Co>herds contexts</Co>, <Co>herds use work</Co>. See{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("fleets"); }}>Fleets you can drive</A>.
    </Callout>

    <H2>Running a fleet instead</H2>
    <P>
      Several Macs that should answer as one pool? Sign in for a permanent, branded link, host from one Mac, and join
      the rest — they all show up in a single fleet.
    </P>
    <Code lang="bash">{`herds auth          # free account + a permanent subdomain like you.herds.run
herds host          # control plane + dashboard + public link

# on every other Mac (a fresh one installs and joins in the same line)
herds connect herds_sk_…@you.herds.run
curl -fsSL herds.run/install | sh -s -- herds_sk_…@you.herds.run`}</Code>
    <P>
      There&rsquo;s no separate &ldquo;host&rdquo; command to learn: a machine running <Co>herds child</Co> is
      already a control plane other Macs can join. <Co>herds host</Co> is the old name for it.
    </P>

    <H2>Were you handed a Mac?</H2>
    <P>
      If someone gave you a Herds token, <Co>herds use</Co> it — or point the SDK straight at it:
    </P>
    <Code lang="python">{`import herds
herds.configure(url="https://you.relay.herds.run", token="hx_…")   # or env: HERDS_CONTROL_PLANE / HERDS_API_KEY
print(herds.mac().run("uname -msr").stdout)`}</Code>

    <Callout type="tip">
      Want an agent to <em>drive</em> — or run keyless <em>on</em> — your Mac? See <A href="#" onClick={(e) => { e.preventDefault(); go("agents"); }}>Agents</A>,
      or install the agent skill with <Co>herds skill --install</Co>.
    </Callout>

    <Divider />
    <P>
      Next: <A href="#" onClick={(e) => { e.preventDefault(); go("commands"); }}>Running commands</A> covers <Co>run</Co>, <Co>stream</Co>, and{" "}
      <Co>map</Co> in depth.
    </P>
  </>
);

const Agents = ({ go }: { go: Go }) => (
  <>
    <Lead>
      Run a real coding agent — Claude Code, Codex, or your own — <em>on</em> a Mac, a sandbox, or the whole fleet, with{" "}
      <strong className="font-semibold text-stone-800">no model API key on the machine</strong>. Output streams back live.
    </Lead>

    <H2>How it&rsquo;s keyless</H2>
    <P>
      Herds pairs with <A href="https://pypi.org/project/proxyagent/">proxyagent</A>: you run one proxy that holds the real model key, and the Mac
      only ever holds a scoped, revocable <Co>pa_</Co> token. Every model call the agent makes routes through your proxy — authenticated, scoped,
      and logged — and the real key never leaves it.
    </P>
    <Callout type="tip" title="Keep the token off disk">
      Store the <Co>pa_</Co> token as a Herds{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("secrets"); }}>Secret</A> and pass <Co>secret=&quot;proxyagent&quot;</Co> — it&rsquo;s injected
      into the agent&rsquo;s environment at run time and never written to the Mac&rsquo;s disk.
    </Callout>

    <H2>One Mac</H2>
    <Code lang="python">{`import herds
mac = herds.mac()

mac.agent("fix the failing tests and open a PR",
          proxy="https://proxy.you.com", secret="proxyagent")   # keyless, streamed`}</Code>

    <H2>A sandbox</H2>
    <Code lang="python">{`with mac.sandbox(image="xcode:26") as sbx:
    sbx.agent("build the app and fix any errors", proxy=PROXY, token="pa_…")`}</Code>

    <H2>The whole fleet</H2>
    <Code lang="python">{`results = herds.fleet().agent("upgrade dependencies", proxy=PROXY, secret="proxyagent")
for name, r in results.items():
    print(name, r.exit_code)   # {machine: Result}, run in parallel`}</Code>

    <H2>From the CLI</H2>
    <Code lang="bash">{`herds agent "summarise today's PRs" --proxy https://proxy.you.com --secret proxyagent
herds agent "upgrade deps" --all                       # every online Mac, in parallel
herds agent "build the app" --sandbox -m mac-studio    # in an isolated sandbox
herds agent "ship it" --harness codex                  # Codex instead of Claude Code`}</Code>

    <H2>Options</H2>
    <Params
      rows={[
        { name: "harness", type: "str", default: '"claude-code"', desc: <><Co>claude-code</Co>, <Co>codex</Co>, or <Co>custom</Co> (with <Co>command=&quot;my-agent {"{goal}"}&quot;</Co>).</> },
        { name: "proxy", type: "str", desc: <>Your proxyagent URL. Falls back to <Co>PROXYAGENT_PROXY</Co>.</> },
        { name: "secret", type: "str", desc: <>A Herds Secret holding <Co>PROXYAGENT_TOKEN</Co> — injected at run time, never on disk. Preferred over <Co>token</Co>.</> },
        { name: "token", type: "str", desc: <>A <Co>pa_</Co> token passed directly. Falls back to <Co>PROXYAGENT_TOKEN</Co>.</> },
        { name: "stream", type: "bool", default: "True", desc: <>Mirror the agent&rsquo;s output live as it works.</> },
      ]}
    />

    <H2>Setup on the Mac</H2>
    <P>The Mac needs <Co>proxyagent</Co> and the agent CLI installed; mint a token on your proxy with <Co>proxyagent token new &lt;label&gt;</Co>:</P>
    <Code lang="bash">{`pip install proxyagent
npm i -g @anthropic-ai/claude-code     # or @openai/codex`}</Code>

    <Divider />
    <P>
      Related: <A href="#" onClick={(e) => { e.preventDefault(); go("secrets"); }}>Secrets</A> ·{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("sandboxes"); }}>Sandboxes</A>.
    </P>
  </>
);

const Installation = () => (
  <>
    <Lead>Herds is a single pip package: the Python SDK and the CLI ship together.</Lead>

    <H2>Requirements</H2>
    <UL>
      <LI><strong className="font-semibold text-stone-800">Python 3.9+</strong> (every release is tested on 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14).</LI>
      <LI>To host a Mac: <strong className="font-semibold text-stone-800">macOS</strong>. To drive one from the SDK: any OS.</LI>
      <LI>The optional MCP server (<Co>herds[mcp]</Co>) needs <strong className="font-semibold text-stone-800">Python 3.10+</strong> — everything else runs on 3.9.</LI>
    </UL>

    <H2>Install</H2>
    <P>
      For the <strong className="font-semibold text-stone-800">CLI</strong> — hosting a Mac, joining a fleet, running
      commands — install it as a standalone tool. That puts <Co>herds</Co> on your PATH no matter which Python you have:
    </P>
    <Code lang="bash">{`uv tool install herds                # recommended (or: pipx install herds)
curl -fsSL herds.run/install | sh    # does the above, and joins a fleet if you pass a token`}</Code>
    <P>
      For the <strong className="font-semibold text-stone-800">SDK</strong> — importing <Co>herds</Co> in your own
      project — install it into that project&rsquo;s environment:
    </P>
    <Code lang="bash">{`pip install herds        # into the current venv / environment`}</Code>

    <Callout type="note" title="`herds: command not found` after pip install">
      <Co>pip install</Co> puts the <Co>herds</Co> script in the environment that did the install. In a venv that&rsquo;s
      the venv (and it works while that venv is active); with <Co>pip install --user</Co> on macOS it&rsquo;s{" "}
      <Co>~/.local/bin</Co> or <Co>~/Library/Python/3.x/bin</Co>, which aren&rsquo;t on a default PATH — so the install
      succeeds and the command still isn&rsquo;t found. One command fixes it for good:
      <Code lang="bash">{`python3 -m herds link      # symlinks herds into a directory your shell already searches
herds link --remove        # undo it`}</Code>
      <Co>python3 -m herds</Co> works whenever the import does, which is how you reach <Co>link</Co> when the bare
      command isn&rsquo;t found yet. It&rsquo;s a symlink, so upgrading the package upgrades what it points at.
    </Callout>
    <H2>Staying current</H2>
    <P>
      <Co>herds update</Co> works out how this copy was installed — uv tool, pipx, or pip — and upgrades with that
      tool. It matters: <Co>pip install -U</Co> into a uv-managed install leaves the binary on your PATH untouched, so
      it looks like it worked and nothing changed. <Co>--check</Co> reports without changing anything.
    </P>
    <Code lang="bash">{`herds update
  installed  0.9.0
  latest     0.9.2
  updating via pip (venv)…
  ✓ updated to 0.9.2`}</Code>

    <Callout type="warn" title="Why pip can't just do this">
      Wheels have no post-install hook — pip removed arbitrary install-time code execution deliberately, and only runs
      setup.py hooks when it can&rsquo;t get a wheel. So no package can put itself on your PATH at install time.{" "}
      <Co>uv tool install</Co> and <Co>pipx</Co> sidestep it by owning a directory that&rsquo;s already there;{" "}
      <Co>herds link</Co> is the equivalent for a plain <Co>pip install</Co>.
    </Callout>

    <H2>Verify</H2>
    <Code lang="bash">{`herds version
herds status        # show local config (control plane, account, machine)`}</Code>

    <H2>Run on login</H2>
    <P>
      To keep a Mac connected automatically, install a launchd agent. It reconnects the daemon whenever you log in.
    </P>
    <Code lang="bash">{`herds install         # install the LaunchAgent (auto-reconnect on login)
herds uninstall       # remove it`}</Code>

    <Callout type="note">
      Configuration lives under <Co>~/.herds</Co> (override with <Co>HERDS_HOME</Co>): <Co>config.json</Co>, credentials, your account
      token, volumes, and sandbox workspaces.
    </Callout>
  </>
);

/* ============================ Core concepts ============================== */

const HowItWorks = () => (
  <>
    <Lead>Three small pieces: a daemon on the Mac, a control plane that brokers requests, and an optional relay for public links.</Lead>

    <H2>No inbound ports</H2>
    <P>
      The Mac never listens for incoming connections. Instead, its daemon opens a single <strong className="font-semibold text-stone-800">outbound
      WebSocket</strong> to the control plane and keeps it alive. Commands are pushed down that socket; output streams back up. This is
      NAT- and firewall-friendly — nothing to forward, nothing to expose.
    </P>

    <H3>The daemon</H3>
    <P>
      Runs on the Mac (foreground via <Co>herds host</Co>, or as a LaunchAgent). It receives <Co>EXEC</Co> frames, runs them, and streams{" "}
      <Co>STDOUT</Co> / <Co>STDERR</Co> / <Co>EXIT</Co> frames back. It also reports CPU/memory metrics and the list of on-disk volumes
      periodically, and proxies HTTP to exposed sandbox ports.
    </P>

    <H3>The control plane</H3>
    <P>
      A tiny FastAPI service (<Co>herds serve</Co>, started for you by <Co>herds host</Co>). It holds the live agent connections, exposes the{" "}
      <A href="#rest-api">REST API</A> the SDK calls, and fans job output out to SDK clients over WebSocket. Durable facts — the machine
      registry, job history, volumes, secrets — live in SQLite.
    </P>

    <H3>The relay</H3>
    <P>
      Optional and hosted. It gives you a branded subdomain (<Co>you.relay.herds.run</Co>) without DNS or TLS work. Your host dials the
      relay over an outbound WebSocket; public requests to your subdomain are routed by <Co>Host</Co> header down that socket to your
      control plane. You can also self-host the relay with <Co>herds relay</Co>.
    </P>

    <Callout type="tip" title="Concurrency">
      One Mac handles many commands at once, so a fleet of agents can share a single machine. Jobs move through states{" "}
      <Co>queued → dispatched → running → succeeded/failed</Co>.
    </Callout>
  </>
);

const Authentication = () => (
  <>
    <Lead>Herds uses a few token types — each for a different boundary. The link is the address; the token is the key.</Lead>

    <H2>Token types</H2>
    <Params
      rows={[
        { name: "Account token", type: "hx_…", desc: <>Created by <Co>herds auth</Co>. Identifies your account to the relay and assigns your subdomain. Stored in <Co>~/.herds/auth.json</Co>.</> },
        { name: "Host token", type: "herds_sk_…", desc: <>Admin token for a host. Used to join another Mac to it with <Co>herds connect</Co>. Stored in <Co>~/.herds/host_token</Co>.</> },
        { name: "API key", type: "scoped", desc: <>What the SDK sends to the control plane. Scoped <Co>read</Co> / <Co>run</Co> / <Co>admin</Co>. Mint with <Co>herds token new</Co>.</> },
        { name: "Device token", type: "daemon", desc: <>Authenticates the daemon&rsquo;s WebSocket to the control plane. Managed for you.</> },
      ]}
    />

    <H2>Scopes</H2>
    <P>API keys carry one of three scopes, enforced by the control plane:</P>
    <UL>
      <LI><Co>read</Co> — list machines, read metrics, view job output.</LI>
      <LI><Co>run</Co> — everything in <Co>read</Co>, plus execute commands, manage sandboxes, and push volumes.</LI>
      <LI><Co>admin</Co> — everything in <Co>run</Co>, plus mint/revoke keys and manage secrets.</LI>
    </UL>
    <Code lang="bash">{`herds token new ci --scope run     # mint a scoped key
herds token ls                     # list keys (masked)
herds token revoke <prefix>        # revoke by visible prefix`}</Code>

    <Callout type="warn">
      Treat the API key and host token like passwords. Anyone with a <Co>run</Co>-scoped key can execute commands on your Mac. The public
      link by itself is just an address — it&rsquo;s the token that grants access.
    </Callout>
  </>
);

/* ============================ Python SDK ================================= */

const Commands = ({ go }: { go: Go }) => (
  <>
    <Lead>The core of the SDK: get a handle to a Mac, then run commands on it — synchronously, streamed, or fanned out.</Lead>

    <H2>Get a Mac</H2>
    <Code lang="python">{`import herds

mac = herds.mac()                       # your online Mac
mac = herds.mac("studio")               # a specific machine by id/name
macs = herds.machines()                 # every connected Mac

# Target a remote host directly — great for agents:
mac = herds.mac(url="https://you.relay.herds.run", token="hx_…")`}</Code>

    <H2>run()</H2>
    <P>Run a command and wait for it. Returns a <A href="#" onClick={(e) => { e.preventDefault(); go("results"); }}>Result</A>.</P>
    <Code lang="python">{`r = mac.run("sw_vers")
print(r.stdout, r.exit_code, r.ok)

mac.run("xcodebuild -scheme App test", check=True)   # raise on failure
mac.run("npm ci", workdir="app", env={"CI": "1"}, timeout=600)`}</Code>
    <Params
      rows={[
        { name: "command", type: "str | list[str]", required: true, desc: "The command to run. A string is run through the shell; a list is executed directly." },
        { name: "image", type: "Image | str", default: "None", desc: <>A toolchain to select first, e.g. <Co>&quot;xcode:26&quot;</Co>. See <A href="#" onClick={(e) => { e.preventDefault(); go("images"); }}>Images</A>.</> },
        { name: "volumes", type: "dict", default: "None", desc: <>Mounts: <Co>{`{mount_name: Volume | name}`}</Co>.</> },
        { name: "workdir", type: "str", default: "None", desc: "Working directory on the Mac." },
        { name: "env", type: "dict[str, str]", default: "None", desc: "Environment variables for the command." },
        { name: "secrets", type: "list", default: "None", desc: <>Named secrets to inject as env. See <A href="#" onClick={(e) => { e.preventDefault(); go("secrets"); }}>Secrets</A>.</> },
        { name: "timeout", type: "int", default: "None", desc: "Seconds before the command (and its children) are killed." },
        { name: "network", type: "bool", default: "True", desc: "Allow network access." },
        { name: "inherit_home", type: "bool", default: "False", desc: "Use the real $HOME — the Mac's installed tools, logins, and caches." },
        { name: "stream", type: "bool", default: "False", desc: "Stream output to your stdout/stderr live while collecting it." },
        { name: "check", type: "bool", default: "False", desc: <>Raise <Co>CommandError</Co> on a non-zero exit.</> },
      ]}
    />

    <H2>stream()</H2>
    <P>Yield <Co>(stream, text)</Co> chunks live as the command runs — <Co>stream</Co> is <Co>&quot;stdout&quot;</Co> or <Co>&quot;stderr&quot;</Co>.</P>
    <Code lang="python">{`for stream, text in mac.stream("swift build"):
    print(text, end="")`}</Code>

    <H2>map()</H2>
    <P>
      Run one command across many inputs in parallel <strong className="font-semibold text-stone-800">on this Mac</strong> —
      Modal-style fan-out. Up to <Co>max_workers</Co> at a time (8 by default). Returns a list of Results, in input order.
    </P>
    <Code lang="python">{`mac.map("pytest {}", ["tests/unit", "tests/e2e"])        # {} is the format slot
mac.map(lambda v: f"swift build -c {v}", ["debug", "release"])
mac.map("./bench {}", inputs, max_workers=8)`}</Code>
    <Callout type="note" title="One Mac, not the fleet">
      <Co>mac.map()</Co> parallelises across <em>inputs</em> on a single machine. To spread the same work across every
      Mac you own, use <Co>herds.fleet().map()</Co> — see <A href="#" onClick={(e) => { e.preventDefault(); go("fleet"); }}>the fleet</A>.
    </Callout>

    <Callout type="tip">
      Pushing a whole codebase before you run it? Use <A href="#" onClick={(e) => { e.preventDefault(); go("volumes"); }}>volumes</A> or a{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("sandboxes"); }}>sandbox</A>.
    </Callout>
  </>
);

const FleetPage = ({ go }: { go: Go }) => (
  <>
    <Lead>
      <Co>herds.fleet()</Co> is every online Mac you own, addressed as one. Where <Co>mac.map()</Co> parallelises across
      inputs on a single machine, the fleet spreads the same work over all of them.
    </Lead>

    <H2>map()</H2>
    <P>
      Run one command across many inputs, distributed over every online Mac. Returns a list of Results in input order,
      and raises on the first task that fails.
    </P>
    <Code lang="python">{`import herds

results = herds.fleet().map("pytest {}", ALL_TEST_DIRS)   # N Macs → N× throughput`}</Code>
    <P>
      Scheduling is <strong className="font-semibold text-stone-800">work-stealing</strong>, not fixed round-robin. Each
      Mac runs up to <Co>per_mac</Co> tasks at a time (4 by default) and pulls the next item the moment it&rsquo;s free,
      so idler or faster Macs naturally do more and none gets overloaded.
    </P>
    <Params
      rows={[
        { name: "command", type: "str | callable", required: true, desc: <>A format string (<Co>{"{}"}</Co> ← item) or a callable (item → command).</> },
        { name: "items", type: "iterable", required: true, desc: "One task per item." },
        { name: "per_mac", type: "int", desc: "Concurrent tasks per Mac. Default 4." },
      ]}
    />

    <H2>macs()</H2>
    <P>The online Macs in the pool, as <Co>Mac</Co> objects — handy when you want to address them individually.</P>
    <Code lang="python">{`for mac in herds.fleet().macs():
    print(mac.name, mac.run("sw_vers -productVersion").stdout.strip())`}</Code>

    <H2>agent()</H2>
    <P>
      Run the <em>same</em> agent task on every online Mac in parallel, keyless. Returns{" "}
      <Co>{"{machine_name: Result}"}</Co>. Pass <Co>on_output=fn(name, stream, text)</Co> for live output tagged by
      machine.
    </P>
    <Code lang="python">{`results = herds.fleet().agent("upgrade dependencies", proxy=PROXY, secret="proxyagent")`}</Code>
    <Callout type="note" title="Online only">
      A fleet call targets Macs that are connected right now. If none are, it raises rather than silently doing
      nothing — run <Co>herds host</Co> on at least one Mac. See{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("agents"); }}>agents</A> for the keyless proxy setup.
    </Callout>
  </>
);

const Fleets = ({ go }: { go: Go }) => (
  <>
    <Lead>
      One command makes a machine drivable. One token drives it from anywhere. If you can reach more than one
      fleet — your Macs, a colleague&rsquo;s, a CI pool — you hold them all and switch by name.
    </Lead>

    <H2>Make a machine drivable</H2>
    <P>
      On the machine you want to drive, <Co>herds child</Co>. No account, no signup: it provisions a link on the
      Herds relay, goes live, and prints one credential that carries its own address.
    </P>
    <Code lang="bash">{`herds child --name studio

✓ This machine is live and drivable

  Take this anywhere and drive it
    herds use herds_sk_…@studio.relay.herds.run`}</Code>
    <Callout type="note" title="What it starts">
      Three things: a small control plane holding <em>this machine&rsquo;s</em> jobs, sandboxes and keys in{" "}
      <Co>~/.herds/host.db</Co>; the daemon that runs your commands; and one outbound link so the token works from
      anywhere. No inbound port is opened. Manage it with <Co>herds child status</Co> / <Co>stop</Co> /{" "}
      <Co>logs</Co>.
      <br /><br />
      <Co>herds host</Co> is the old name for this command and still works — they were always the same code.
    </Callout>

    <H2>Drive it from anywhere</H2>
    <Code lang="bash">{`herds use herds_sk_…@studio.relay.herds.run
✓ Driving studio — 1 machine, 1 online

herds machines
herds run -- uname -msr`}</Code>
    <P>
      <Co>use</Co> checks the fleet before it stores anything, then tells you what you got — a credential that
      doesn&rsquo;t work is never written to disk, so a fleet can&rsquo;t sit in your list quietly 401-ing.
    </P>

    <H2>Several fleets at once</H2>
    <Code lang="bash">{`herds use herds_sk_…@studio.relay.herds.run    # add
herds use herds_sk_…@work.relay.herds.run --as work

herds contexts
  →  studio   https://studio.relay.herds.run
     work     https://work.relay.herds.run

herds use work        # switch — no token needed again
herds forget work     # drop it locally (the fleet is untouched)`}</Code>
    <P>
      Names come from the link. The relay gives every account its own subdomain, so the first label is unique by
      construction — nothing to register and no collisions to resolve. <Co>--as</Co> overrides it.
    </P>

    <H2>From Python</H2>
    <Code lang="python">{`import herds

herds.use("studio")                 # for the rest of this process
herds.mac().run("xcodebuild test")

herds.contexts()                    # [{'name': 'studio', 'active': True, …}]
herds.configure(context="work")     # same thing, explicit`}</Code>
    <Callout type="tip" title="Process-local">
      <Co>herds.use()</Co> in a script points <em>that process</em> at a fleet. It doesn&rsquo;t change what the rest
      of the machine drives, so a job targeting one fleet can&rsquo;t surprise the next shell command.
    </Callout>

    <H2>Where it&rsquo;s kept</H2>
    <P>
      <Co>~/.herds/contexts.json</Co> (mode 600 — it holds API keys). The active fleet is mirrored into{" "}
      <Co>config.json</Co> and <Co>credentials.json</Co>, which is what the daemon and SDK read.
    </P>
    <Callout type="note" title="A URL and its key are one credential">
      They only mean anything together: a key is valid at the door it was issued for. Switching moves both halves or
      neither — which is what stops the &ldquo;good key, wrong door&rdquo; 401 you&rsquo;d otherwise get after
      pointing a machine somewhere new. A machine set up before contexts existed is adopted as one automatically;
      there&rsquo;s nothing to migrate.
    </Callout>
  </>
);

const Sandboxes = ({ go }: { go: Go }) => (
  <>
    <Lead>A sandbox is an isolated, persistent workspace on a Mac — its own directory, HOME, and TMPDIR. Ship code in, run servers, expose ports.</Lead>

    <H2>Create &amp; run</H2>
    <Code lang="python">{`import herds

sbx = herds.Sandbox.create()                  # or mac.sandbox()
sbx.exec("git clone https://github.com/me/app .")
sbx.exec("npm install && npm run build", check=True)`}</Code>
    <P>Or as a context manager, which terminates the sandbox on exit:</P>
    <Code lang="python">{`with herds.Sandbox.create(image="xcode:26") as sbx:
    sbx.put("./my-project")
    sbx.exec("xcodebuild -scheme App build", check=True)`}</Code>

    <H2>Ship a codebase</H2>
    <Code lang="python">{`sbx.put("./my-project")              # tar locally, extract in the sandbox (junk pruned)
sbx.put("model.bin", "weights/")    # a single file into a subpath`}</Code>

    <H2>Long-running servers</H2>
    <P>
      <Co>spawn()</Co> starts a process without waiting and returns a request id. With <Co>keep_alive=True</Co> it&rsquo;s supervised —
      respawned if it exits — so it behaves like a service.
    </P>
    <Code lang="python">{`sbx.spawn("npm run dev", keep_alive=True)    # long-running server
url = sbx.expose(3000)                        # → a public URL
print(url)
sbx.stop()                                    # stop processes (workspace stays)`}</Code>

    <H2>Expose a port</H2>
    <P>
      <Co>expose(port, name="")</Co> publishes a server running inside the sandbox as a public URL. Pass a <Co>name</Co> for a named
      subdomain when a ports domain is configured on the host.
    </P>

    <H2>Raw tunnels</H2>
    <P>
      <Co>expose()</Co> is buffered HTTP — one request, one response. A <strong className="font-semibold text-stone-800">tunnel</strong> is
      a raw, persistent, bidirectional byte pipe straight to a port on the sandbox, routed control plane → daemon → sandbox{" "}
      <Co>localhost:port</Co>. Because nothing is framed as HTTP, protocols that keep a socket open survive: CDP, WebSockets, and
      database ports all work.
    </P>
    <Code lang="python">{`# Attach an EXTERNAL Playwright to a Chromium running on the Mac:
with sbx.tunnel(9222) as t:            # alias: sbx.connect_port(9222)
    t.send(b"GET /json/version HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n")
    print(t.recv(timeout=5))           # raw bytes back

ws_url = sbx.tunnel_url(9222)          # a URL you can hand to a WS/CDP client`}</Code>
    <P>
      A <Co>TcpTunnel</Co> has <Co>send(bytes | str)</Co>, <Co>recv(timeout=None) → bytes</Co>, and <Co>close()</Co>, and works as a
      context manager. Use it to drive or watch a live browser from <em>outside</em> the Mac — an agent running <em>inside</em> the
      sandbox never needs one; it just talks to <Co>localhost</Co> directly.
    </P>

    <H2>Web automation</H2>
    <P>
      There is no browser primitive to learn: a sandbox is a whole Mac shell, so a script or agent simply installs Playwright and drives
      Chromium itself, with free reign, and takes screenshots.
    </P>
    <Code lang="python">{`with herds.Sandbox.create(volumes={"out": herds.Volume.from_name("shots")}) as sbx:
    sbx.exec("pip install playwright && playwright install chromium", check=True)
    sbx.put("scrape.py")
    sbx.exec("python scrape.py", check=True)   # writes screenshots into ./out

herds.Volume.from_name("shots").get("home.png", "./home.png")`}</Code>
    <Callout type="tip" title="Real residential IP, real fingerprint">
      Because Chromium runs on the Mac, its traffic exits the Mac&rsquo;s own connection — a real residential IP, on real hardware.
      Each sandbox gets its own <Co>HOME</Co> and profile, so many isolated browser sessions (separate cookies and logins) run in
      parallel on one Mac, all sharing that single residential IP. To drive or watch from outside the Mac, open a raw tunnel to the
      CDP port.
    </Callout>

    <H2>Snapshots</H2>
    <P>
      Provision a sandbox once — install toolchains, clone a repo, warm caches — then <Co>snapshot_filesystem()</Co> it into a reusable
      base Image. New sandboxes created from that Image start pre-populated, so you pay the setup cost once.
    </P>
    <Code lang="python">{`with herds.Sandbox.create() as sbx:
    sbx.exec("pip install playwright && playwright install chromium", check=True)
    base = sbx.snapshot_filesystem(name="pw-base")     # → an Image

# Later, anywhere — starts with Playwright already installed:
img = herds.Image.from_id(base.image_id)
with herds.Sandbox.create(image=img) as sbx:
    sbx.exec("python scrape.py", check=True)`}</Code>

    <H2>Methods</H2>
    <Params
      rows={[
        { name: "Sandbox.create(...)", type: "→ Sandbox", desc: <>Create a sandbox. Accepts <Co>image</Co>, <Co>volumes</Co>, <Co>secrets</Co>, <Co>inherit_home</Co>, and a target <Co>mac</Co> / <Co>machine_id</Co>.</> },
        { name: "sbx.put(local, remote='')", type: "→ dict", desc: "Copy a local file or directory into the workspace." },
        { name: "sbx.exec(command, ...)", type: "→ Result", desc: <>Run a command and wait. Same options as <Co>mac.run</Co> (<Co>workdir</Co>, <Co>env</Co>, <Co>timeout</Co>, <Co>network</Co>, <Co>stream</Co>, <Co>check</Co>).</> },
        { name: "sbx.stream(command, ...)", type: "→ iterator", desc: <>Yield <Co>(stream, text)</Co> chunks live.</> },
        { name: "sbx.spawn(command, ...)", type: "→ str", desc: <>Start without waiting; returns a request id. <Co>keep_alive=True</Co> supervises it.</> },
        { name: "sbx.expose(port, name='')", type: "→ str", desc: "Expose a port as a public URL (buffered HTTP)." },
        { name: "sbx.tunnel(port, timeout=20.0)", type: "→ TcpTunnel", desc: <>Open a raw bidirectional byte pipe to a port. Alias: <Co>connect_port</Co>.</> },
        { name: "sbx.tunnel_url(port)", type: "→ str", desc: "URL for the raw tunnel, for a WS/CDP client." },
        { name: "sbx.snapshot_filesystem(name='')", type: "→ Image", desc: "Snapshot the sandbox tree into a reusable base Image." },
        { name: "sbx.stop()", type: "→ dict", desc: "Stop running processes; the workspace stays on disk." },
        { name: "sbx.terminate()", type: "→ None", desc: "Stop processes and wipe the workspace." },
      ]}
    />

    <Callout type="note">
      Sandboxes are process-level isolation for code you trust, not a security boundary for untrusted code. They persist on the Mac
      until you <Co>terminate()</Co> them. Need durable shared state? Mount a <A href="#" onClick={(e) => { e.preventDefault(); go("volumes"); }}>volume</A>.
    </Callout>
  </>
);

const Sessions = ({ go }: { go: Go }) => (
  <>
    <Lead>
      A session is a <strong className="font-semibold text-stone-800">resident process</strong> on the Mac that you feed one turn at a
      time. You write to its stdin, read its stdout as it works, and the process — and all its state — stays alive between turns.
    </Lead>

    <H2>Why sessions exist</H2>
    <P>
      <Co>run</Co> and <Co>exec</Co> are one-shot: a command starts, finishes, and its process is gone. A session is the opposite — a
      long-lived process you drive turn by turn. This is exactly how you run a long-lived agent on a Mac: one resident process, one
      stdin turn per prompt, JSON events streamed back from stdout, and model calls routed through a proxy. It is the same shape spawn&rsquo;s
      persistent driver runs in on Modal.
    </P>

    <H2>Start a session</H2>
    <Code lang="python">{`import herds

mac = herds.mac()
s = mac.session("python3 -i")     # a resident REPL
s.send("print(6 * 7)\\n")
for stream, text in s.stream():   # live output until the process exits
    print(text, end="")
s.close()                          # EOF → the process finishes`}</Code>
    <P>
      <Co>send()</Co> writes one turn to stdin, <Co>stream()</Co> yields <Co>(stream, text)</Co> chunks live until the process exits,
      and <Co>close()</Co> sends EOF so it can finish. Sandboxes have the same primitive: <Co>sbx.session(command, ...)</Co>.
    </P>

    <H2>A long-lived agent (keyless)</H2>
    <P>
      Run a coding agent as a resident process and drive it across many prompts on one live session. Point it at a proxy that holds the
      real model key, so no key ever lands on the Mac (see <A href="#" onClick={(e) => { e.preventDefault(); go("agents"); }}>Agents</A>).
    </P>
    <Code lang="python">{`import json, herds

mac = herds.mac()
s = mac.session(
    "claude --print --input-format stream-json --output-format stream-json --verbose",
    env={"ANTHROPIC_BASE_URL": PROXY, "ANTHROPIC_API_KEY": TOKEN},   # keyless via proxy
)

# Turn 1 — write one user message to stdin:
s.send(json.dumps({"type": "user", "message": {"role": "user",
        "content": "clone the repo and run tests"}}) + "\\n")
for stream, text in s.stream():
    print(text, end="")

# Turn 2 — SAME live session; the agent's state persists:
s.send(json.dumps({"type": "user", "message": {"role": "user",
        "content": "now fix the first failing test"}}) + "\\n")
for stream, text in s.stream():
    print(text, end="")

s.close()`}</Code>

    <H2>Methods</H2>
    <Params
      rows={[
        { name: "mac.session(command, ...)", type: "→ Session", desc: <>Start a resident process on the Mac. Options: <Co>image</Co>, <Co>volumes</Co>, <Co>workdir</Co>, <Co>env</Co>, <Co>network</Co>, <Co>inherit_home</Co>.</> },
        { name: "sbx.session(command, ...)", type: "→ Session", desc: <>Start a resident process in a sandbox. Options: <Co>workdir</Co>, <Co>env</Co>, <Co>network</Co>.</> },
        { name: "Session.send(data)", type: "→ None", desc: "Write one turn to the process's stdin." },
        { name: "Session.stream()", type: "→ iterator", desc: <>Yield <Co>(stream, text)</Co> chunks live until the process exits.</> },
        { name: "Session.close()", type: "→ None", desc: "Send EOF so the process finishes." },
      ]}
    />

    <Callout type="note">
      Idle sessions are reaped after <Co>HERDS_SESSION_IDLE_TIMEOUT_MS</Co> (default 30 minutes). Send a turn to keep one alive, or{" "}
      <Co>close()</Co> it when you&rsquo;re done. Concurrent sessions count against{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("env-vars"); }}><Co>HERDS_MAX_LIVE_SANDBOXES</Co></A>.
    </Callout>

    <Divider />
    <P>
      Related: <A href="#" onClick={(e) => { e.preventDefault(); go("sandboxes"); }}>Sandboxes</A> ·{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("agents"); }}>Agents</A>.
    </P>
  </>
);

const Volumes = () => (
  <>
    <Lead>A volume is a named directory on the Mac that survives across runs, sandboxes, and reboots — for caches, build outputs, datasets, or a checked-out repo.</Lead>

    <H2>Push &amp; mount</H2>
    <Code lang="python">{`import herds

herds.Volume.from_name("repo").put("./my-project")     # tar + extract on the Mac
herds.Volume.from_name("data").put("model.bin", "weights/")

vol = herds.Volume.from_name("builds")
mac.run("xcodebuild archive", volumes={"out": vol})    # mounted as ./out`}</Code>
    <P>
      A mounted volume is reachable by its mount name (relative) and via <Co>$HERDS_VOLUME_&lt;NAME&gt;</Co> (absolute) inside the command.
      Writes are durable immediately — there is no commit step.
    </P>

    <H2>What gets pushed</H2>
    <P>Directories are tarred locally and extracted on the Mac. Common junk is pruned automatically:</P>
    <Code lang="text">{`.git  node_modules  __pycache__  .venv  venv  dist  build
.next  .turbo  .cache  .mypy_cache  .pytest_cache  .DS_Store  target  …`}</Code>
    <P>Add your own patterns with <Co>ignore=[...]</Co>, or wipe the destination first with <Co>clean=True</Co>.</P>

    <H2>Read &amp; manage</H2>
    <P>Read files back out, list what&rsquo;s there, and delete — without spinning up a command on the Mac.</P>
    <Code lang="python">{`vol = herds.Volume.from_name("shots")

data = vol.get("home.png")               # → bytes
vol.get("home.png", "./home.png")        # also save it locally

for entry in vol.listdir("screens"):     # name / dir / size / mtime_ms
    print(entry["name"], entry["size"])

vol.remove("screens/old.png")            # delete a file or dir (recursive)`}</Code>

    <H2>API</H2>
    <Params
      rows={[
        { name: "Volume.from_name(name)", type: "→ Volume", desc: "Reference a volume by name; created lazily on first write." },
        { name: "vol.put(local, remote='', ...)", type: "→ dict", desc: <>Copy a file/dir into the volume. Options: <Co>clean</Co>, <Co>ignore</Co>, <Co>machine</Co>.</> },
        { name: "vol.get(remote, local=None)", type: "→ bytes", desc: <>Read a file out. If <Co>local</Co> is given, also save it there.</> },
        { name: "vol.listdir(path='')", type: "→ list[dict]", desc: <>List a directory. Entries carry <Co>name</Co>, <Co>dir</Co>, <Co>size</Co>, <Co>mtime_ms</Co>.</> },
        { name: "vol.remove(path)", type: "→ dict", desc: "Delete a file or dir (recursive). Path-traversal protected." },
        { name: "mac.push(local, volume, remote='')", type: "→ dict", desc: <>Sugar for <Co>Volume.from_name(volume).put(local, remote)</Co>.</> },
      ]}
    />

    <Callout type="tip">
      From the shell: <Co>herds volume put repo ./my-project</Co>. List with <Co>herds volume ls</Co>.
    </Callout>
  </>
);

const Images = () => (
  <>
    <Lead>An Image selects a toolchain on the Mac before your command runs. It is not a container — it picks the right Xcode or language version on the real machine.</Lead>

    <H2>Built-in toolchains</H2>
    <Code lang="python">{`import herds

herds.Image.xcode("26")        # select a specific Xcode (DEVELOPER_DIR)
herds.Image.python("3.13")     # pin Python via mise
herds.Image.node("22")         # pin Node via mise
herds.Image.macos()            # the bare host environment, as-is
herds.Image.from_name("ruby:3.3")`}</Code>
    <P>Supported names resolve on the Mac: <Co>xcode:&lt;v&gt;</Co>, <Co>python:&lt;v&gt;</Co>, <Co>node:&lt;v&gt;</Co>, <Co>ruby:&lt;v&gt;</Co>, <Co>go:&lt;v&gt;</Co>, and <Co>macos</Co>.</P>

    <H2>Customize</H2>
    <P>Images are immutable — builder methods return a new Image.</P>
    <Code lang="python">{`img = (
    herds.Image.xcode("26")
    .env_vars(CONFIGURATION="Release")
    .run_commands("brew install swiftlint")   # actually runs before your command
)
mac.run("xcodebuild -scheme App archive", image=img)

# Provision a browser toolchain once, cached thereafter:
herds.Image.macos().run_commands("pip install playwright", "playwright install chromium")`}</Code>
    <P>
      <Co>run_commands</Co> genuinely executes on the Mac before your command, and is keyed by a content hash: the first run installs,
      identical repeats are a no-op. It is no longer a best-effort stub.
    </P>

    <Params
      rows={[
        { name: ".env_vars(**vars)", type: "→ Image", desc: "Add or override environment variables." },
        { name: ".run_commands(*cmds)", type: "→ Image", desc: "Setup commands that actually run on the Mac before your command. Cached by content hash — first run installs, repeats are a no-op." },
      ]}
    />

    <H2>Snapshots</H2>
    <P>
      For heavier setup, provision a sandbox once and snapshot it into a reusable base — new sandboxes from that Image start
      pre-populated.
    </P>
    <Code lang="python">{`with herds.Sandbox.create() as sbx:
    sbx.exec("pip install playwright && playwright install chromium", check=True)
    base = sbx.snapshot_filesystem(name="pw-base")   # → an Image

img = herds.Image.from_id(base.image_id)             # reference it later
herds.Sandbox.create(image=img)                       # starts pre-populated`}</Code>

    <Callout type="note">
      Selecting an Xcode never clobbers other concurrent jobs on the same Mac — each job gets its own <Co>DEVELOPER_DIR</Co>.
    </Callout>
  </>
);

const Secrets = () => (
  <>
    <Lead>Secrets are named bundles of environment variables. The control plane stores the values; they&rsquo;re injected into a command&rsquo;s environment at run time.</Lead>

    <H2>Create &amp; use</H2>
    <Code lang="python">{`import herds

herds.Secret.create("openai", {"OPENAI_API_KEY": "sk-…"})

mac.run("python agent.py", secrets=["openai"])          # by name
mac.run("./deploy.sh", secrets=[herds.Secret.from_name("appstore")])`}</Code>

    <H2>API</H2>
    <Params
      rows={[
        { name: "Secret.create(name, values)", type: "→ Secret", desc: <>Create a secret from a <Co>{`dict[str, str]`}</Co> of env vars.</> },
        { name: "Secret.from_name(name)", type: "→ Secret", desc: "Reference an existing secret by name." },
        { name: "Secret.list()", type: "→ list[dict]", desc: "List secrets (values masked)." },
      ]}
    />
    <Callout type="warn">
      Secret values live in the control plane, not in your code. Anyone with an <Co>admin</Co>-scoped key can manage them.
    </Callout>
  </>
);

const Functions = () => (
  <>
    <Lead>Run a Python function on the Mac. Decorate it, then call <Co>.remote()</Co> — the function&rsquo;s source ships to the Mac and runs under the target Python.</Lead>

    <H2>Example</H2>
    <Code lang="python">{`import herds

app = herds.App("ci")

@app.function(image=herds.Image.python("3.13"))
def build(target: str) -> dict:
    import platform
    return {"target": target, "ran_on": platform.node()}

result = build.remote("release")    # ships source, runs on the Mac
print(result)                        # {'target': 'release', 'ran_on': '...'}`}</Code>

    <H2>Rules</H2>
    <UL>
      <LI>The function must live at module level — its source is read with <Co>inspect.getsource()</Co>.</LI>
      <LI>Arguments and the return value must be JSON-serializable.</LI>
      <LI>Closures and non-importable globals don&rsquo;t travel. Import what you need inside the function.</LI>
    </UL>

    <Params
      rows={[
        { name: "@app.function(...)", type: "decorator", desc: <>Mark a function to run on the Mac. Options: <Co>machine</Co>, <Co>image</Co>, <Co>volumes</Co>, <Co>timeout</Co>.</> },
        { name: "fn.remote(*args)", type: "→ value", desc: <>Ship source and execute on the Mac. Raises <Co>RemoteExecutionError</Co> on failure.</> },
        { name: "fn.local(*args)", type: "→ value", desc: "Call the function in-process (no shipping)." },
        { name: "@app.local_entrypoint()", type: "decorator", desc: "Mark a local orchestration entry point." },
      ]}
    />
  </>
);

const Results = () => (
  <>
    <Lead>Every command returns a Result. Errors are explicit — opt into raising with <Co>check=True</Co> or <Co>raise_for_status()</Co>.</Lead>

    <H2>Result</H2>
    <Code lang="python">{`r = mac.run("swift test")
r.stdout         # collected standard output (str)
r.stderr         # collected standard error (str)
r.exit_code      # process exit code (int)
r.ok             # True if exit_code == 0
r.duration_ms    # elapsed time in milliseconds
r.request_id     # unique id for this run

r.raise_for_status()    # raise CommandError if it failed`}</Code>

    <H2>Exceptions</H2>
    <Params
      rows={[
        { name: "CommandError", type: "Exception", desc: <>A command exited non-zero (via <Co>check=True</Co> or <Co>raise_for_status()</Co>). Carries the <Co>.result</Co>.</> },
        { name: "RemoteExecutionError", type: "Exception", desc: <>A remote function (<Co>fn.remote()</Co>) failed.</> },
        { name: "HerdsError", type: "Exception", desc: "An API or connection error talking to the control plane." },
      ]}
    />
    <Code lang="python">{`import herds

try:
    mac.run("xcodebuild -scheme App test", check=True)
except herds.CommandError as e:
    print(e.result.exit_code)
    print(e.result.stderr)`}</Code>
  </>
);

/* ============================ CLI ======================================= */

const CLI = ({ go }: { go: Go }) => (
  <>
    <Lead>The <Co>herds</Co> CLI covers the whole lifecycle — sign in, host a Mac, run commands, and manage volumes, images, and tokens.</Lead>

    <H2>Be drivable, and drive</H2>
    <Code lang="bash">{`herds child [--name <name>]        # make THIS machine drivable; prints one token
herds child status | stop | logs   # manage it (herds host is the old name)
herds link                         # put herds on your PATH after a pip install
herds update [--check]             # upgrade, using whatever installed it
herds use <token>                  # drive that fleet from here (adds + switches)
herds use <name>                   # switch to a fleet you already have
herds contexts                     # list the fleets this machine can drive
herds forget <name>                # drop a fleet's credentials locally`}</Code>
    <P>
      See <A href="#" onClick={(e) => { e.preventDefault(); go("fleets"); }}>Fleets you can drive</A> for the whole
      flow, including holding several at once.
    </P>

    <H2>Account &amp; hosting</H2>
    <Code lang="bash">{`herds auth [--token hx_…] [--name <subdomain>]   # sign in, get account + link
herds auth --repoint                              # point this Mac's CLI back at your account
herds child setup                                 # walkthrough: Tailscale Funnel
herds connect <token>                              # join THIS Mac (token carries its link)
herds disconnect [id]                              # remove a Mac from the fleet
herds open                                          # open the dashboard in a browser`}</Code>

    <H3>Which fleet am I talking to?</H3>
    <P>
      A Mac can serve its own control plane <em>and</em> have joined someone else&rsquo;s. One machine points at one
      control plane at a time — <Co>herds status</Co> shows which, and <Co>herds connect</Co> moves it.
    </P>
    <P>
      Signing in doesn&rsquo;t move it on its own. <Co>herds auth</Co> only repoints when the control plane you&rsquo;re
      on has stopped answering, so joining a colleague&rsquo;s fleet survives a later sign-in. Use{" "}
      <Co>herds auth --repoint</Co> to switch back to your own account deliberately. <Co>HERDS_CONTROL_PLANE</Co>{" "}
      overrides both.
    </P>
    <Callout type="note" title="The connect token is also your API key">
      <Co>herds connect</Co> saves the token as this Mac&rsquo;s API key as well as its device token, so the CLI and SDK
      here can query the fleet it just joined. Because the two move together, a Mac that has hosted and then joined
      elsewhere won&rsquo;t be left holding its old key against the new control plane. If a call fails with{" "}
      <Co>401</Co>, the message names the control plane that rejected it.
    </Callout>

    <H2>Running commands</H2>
    <Code lang="bash">{`herds ssh [machine]         # interactive terminal (real pty · Ctrl-] detaches)
herds ssh mini -c htop      # run one program interactively
herds run -- <cmd>          # run a command on a Mac (streams output)
herds shell -c "<cmd>"      # one-off command
herds machines              # list connected Macs
herds logs [-m <id>]        # recent jobs
herds status                # local config`}</Code>
    <P>
      Every command that takes a machine accepts an id, a name, an id prefix, part of a name, or a tag —{" "}
      <Co>-m mini</Co>, <Co>-m ci</Co>, <Co>-m mac_ed74</Co>. Ambiguous references are listed, never guessed.
    </P>

    <Callout type="warn" title="Sandboxed by default">
      <Co>run</Co> and <Co>shell</Co> execute in a throwaway sandbox: <Co>$HOME</Co> points at{" "}
      <Co>~/.herds/sandboxes/sbx_eph_…/home</Co> and writes are rolled back. That&rsquo;s right for CI and untrusted code, but it means
      installing apps or using your keychain <em>silently won&rsquo;t stick</em>. Add <Co>--real</Co> to run as you against the real
      machine:
      <Code lang="bash">{`herds run --real -- brew install --cask cursor
herds shell --real -c 'ls ~/Library'`}</Code>
      In the SDK that&rsquo;s <Co>mac.run(cmd, inherit_home=True)</Co>. <Co>herds ssh</Co> is already real by default.
    </Callout>

    <H2>Hosting &amp; permissions</H2>
    <Code lang="bash">{`herds host                  # go live — runs in the BACKGROUND, returns your prompt
herds host status           # is this Mac hosting, and on which link
herds host stop             # stop the background host
herds host logs [-F]        # tail it
herds host --foreground     # stay attached (what the LaunchAgent uses)

herds doctor                # audit GUI/TCC permissions ON THE MAC
herds doctor --local        # audit this process instead`}</Code>

    <H2>Volumes &amp; images</H2>
    <Code lang="bash">{`herds volume ls
herds volume create <name>
herds volume put <name> <local> [remote] [--clean]
herds volume rm <name>

herds image ls              # available toolchains`}</Code>

    <H2>Tokens</H2>
    <Code lang="bash">{`herds token new [label] --scope read|run|admin
herds token ls
herds token revoke <prefix>`}</Code>

    <H2>Daemon &amp; service</H2>
    <Code lang="bash">{`herds serve [--host 127.0.0.1] [--port 8787]   # run the control plane
herds install                                   # LaunchAgent: reconnect on login
herds uninstall
herds skill [--install]                         # print/install the agent skill
herds version`}</Code>
  </>
);

/* ============================ Self-hosting ============================== */

const Hosting = () => (
  <>
    <Lead>One command turns the Mac on your desk into a cloud runtime: control plane, bundled dashboard, daemon, and a public link.</Lead>

    <H2>herds host</H2>
    <Code lang="bash">{`herds host`}</Code>
    <P>This brings up, in order:</P>
    <UL>
      <LI>a local <strong className="font-semibold text-stone-800">control plane</strong> (auto-picks a free port if 8787 is taken);</LI>
      <LI>the bundled <strong className="font-semibold text-stone-800">dashboard</strong>, served by the control plane;</LI>
      <LI>this Mac&rsquo;s <strong className="font-semibold text-stone-800">daemon</strong>, connected to the local control plane;</LI>
      <LI>a <strong className="font-semibold text-stone-800">public link</strong> — via the hosted relay if you&rsquo;re signed in, otherwise a quick tunnel.</LI>
    </UL>
    <Code lang="bash">{`herds host --port 9000     # pin a port
herds host --no-tunnel     # local only, no public link
herds host --quick         # force a quick tunnel instead of the relay`}</Code>

    <H2>A second Mac</H2>
    <P>Join another machine to the same host with its host token:</P>
    <Code lang="bash">{`herds connect herds_sk_…@you.relay.herds.run`}</Code>

    <H2>Tailscale Funnel</H2>
    <P>For a stable self-managed tunnel, the setup walkthrough wires up Tailscale Funnel and the system daemon:</P>
    <Code lang="bash">{`herds host setup`}</Code>

    <Callout type="tip">
      Signed in with <Co>herds auth</Co>? <Co>herds host</Co> uses the hosted relay automatically and you get a clean{" "}
      <Co>you.relay.herds.run</Co> link — no tunnel software required.
    </Callout>
  </>
);

const Relay = () => (
  <>
    <Lead>The relay is the hosted rendezvous that turns an outbound WebSocket into a public, branded subdomain. You can run your own.</Lead>

    <H2>How routing works</H2>
    <P>
      Your host dials the relay over an outbound WebSocket. A public request to <Co>you.relay.herds.run</Co> is matched by its{" "}
      <Co>Host</Co> header, routed down your host&rsquo;s socket, and proxied to your control plane — the same HTTP-over-WebSocket framing the
      daemon uses. No inbound ports on your machine, ever.
    </P>

    <H2>Run your own</H2>
    <Code lang="bash">{`herds relay --port 8888 --domain herds.run`}</Code>
    <P>
      The relay handles the <Co>herds auth</Co> flow (provision / register / login), issues account tokens, and allocates subdomains. For
      production it can back accounts with Postgres via <Co>HERDS_DATABASE_URL</Co>; otherwise it keeps a local JSON store.
    </P>
    <Callout type="note">
      The default hosted relay is <Co>wss://api.relay.herds.run</Co> and is user-invisible — the CLI handles it. Point elsewhere with{" "}
      <Co>HERDS_RELAY</Co>.
    </Callout>
  </>
);

/* ============================ Reference ================================= */

const RestApi = () => (
  <>
    <Lead>The control plane exposes a small REST + WebSocket API. Authenticate with a Bearer token (<Co>Authorization: Bearer &lt;key&gt;</Co>), or <Co>?token=</Co> for WebSocket endpoints.</Lead>

    <H2 id="rest-api">Machines</H2>
    <Endpoints
      rows={[
        { method: "GET", path: "/v1/machines", desc: "List connected Macs (with live CPU/mem)" },
        { method: "GET", path: "/v1/machines/{id}", desc: "Get one machine (resolves 'default')" },
      ]}
    />

    <H2>Execution &amp; sessions</H2>
    <Endpoints
      rows={[
        { method: "POST", path: "/v1/machines/{id}/exec", desc: "Queue a command → request_id" },
        { method: "GET", path: "/v1/jobs", desc: "Recent jobs" },
        { method: "GET", path: "/v1/jobs/{request_id}/output", desc: "Job output (even mid-run)" },
        { method: "WS", path: "/v1/jobs/{request_id}/logs", desc: "Stream job frames live" },
        { method: "POST", path: "/v1/machines/{id}/sessions", desc: "Start a resident session → request_id" },
        { method: "POST", path: "/v1/sessions/{request_id}/stdin", desc: "Feed a stdin chunk to a running session" },
      ]}
    />

    <H2>Sandboxes &amp; tunnels</H2>
    <Endpoints
      rows={[
        { method: "GET", path: "/v1/sandboxes", desc: "List sandboxes" },
        { method: "GET", path: "/v1/sandboxes/{id}", desc: "One sandbox + active jobs" },
        { method: "POST", path: "/v1/sandboxes/{id}/stop", desc: "Stop running processes" },
        { method: "DELETE", path: "/v1/sandboxes/{id}", desc: "Terminate + wipe workspace" },
        { method: "POST", path: "/v1/sandboxes/{id}/ports", desc: "Expose a port → URL" },
        { method: "PUT", path: "/v1/sandboxes/{id}/put", desc: "Push a file/dir (tar)" },
        { method: "POST", path: "/v1/sandboxes/{id}/snapshot", desc: "Snapshot filesystem → image_id" },
        { method: "WS", path: "/v1/machines/{machine_id}/tunnel/{port}", desc: "Raw bidirectional byte tunnel to a port" },
        { method: "WS", path: "/v1/sandboxes/{sandbox_id}/tunnel/{port}", desc: "Raw bidirectional byte tunnel to a sandbox port" },
      ]}
    />

    <H2>Volumes, secrets &amp; keys</H2>
    <Endpoints
      rows={[
        { method: "GET", path: "/v1/volumes", desc: "List volumes" },
        { method: "PUT", path: "/v1/volumes/{name}/put", desc: "Push a file/dir" },
        { method: "GET", path: "/v1/volumes/{name}/get", desc: "Read a file out" },
        { method: "GET", path: "/v1/volumes/{name}/files", desc: "List a directory" },
        { method: "DELETE", path: "/v1/volumes/{name}/file", desc: "Delete a file/dir" },
        { method: "GET", path: "/v1/secrets", desc: "List secrets (masked)" },
        { method: "POST", path: "/v1/secrets", desc: "Create a secret" },
        { method: "GET", path: "/v1/keys", desc: "List API keys (masked)" },
        { method: "POST", path: "/v1/keys", desc: "Mint a scoped key" },
        { method: "GET", path: "/v1/metrics", desc: "Aggregate stats + timeseries" },
      ]}
    />

    <H2>ExecRequest body</H2>
    <Code lang="python">{`{
  "command": "xcodebuild -scheme App test",  # str | list[str]
  "image": "xcode:26",                        # optional
  "volumes": {"out": "builds"},               # mount -> volume name
  "workdir": "app",
  "env": {"CI": "1"},
  "secrets": ["appstore"],
  "timeout": 600,
  "network": true,
  "sandbox_id": "sbx_…",                      # reuse a workspace
  "inherit_home": false,
  "keep_alive": false
}`}</Code>
  </>
);

const EnvVars = () => (
  <>
    <Lead>Configuration is environment-first: every variable below overrides the matching value in <Co>~/.herds</Co>.</Lead>

    <H2 id="env-vars">Variables</H2>
    <Params
      rows={[
        { name: "HERDS_CONTROL_PLANE", type: "url", default: "http://127.0.0.1:8787", desc: "Control plane the SDK/daemon talk to." },
        { name: "HERDS_API_KEY", type: "str", desc: "SDK → control plane auth token." },
        { name: "HERDS_TOKEN", type: "hx_…", desc: "Account token for the relay." },
        { name: "HERDS_ACCOUNT", type: "str", desc: "Your assigned subdomain." },
        { name: "HERDS_RELAY", type: "wss url", default: "wss://api.relay.herds.run", desc: "Relay WebSocket endpoint." },
        { name: "HERDS_HOME", type: "path", default: "~/.herds", desc: "Config + data directory." },
        { name: "HERDS_DEVICE_TOKEN", type: "str", desc: "Daemon → control plane auth token." },
        { name: "HERDS_DATABASE_URL", type: "dsn", desc: "Postgres for the relay account store (relay only)." },
        { name: "HERDS_REQUIRE_AUTH", type: "0 | 1", default: "0", desc: "Enforce auth in the control plane." },
        { name: "HERDS_MAX_LIVE_SANDBOXES", type: "int", default: "8", desc: "Max concurrent sandboxes/sessions before new ones queue." },
        { name: "HERDS_ADMISSION_QUEUE_MAX", type: "int", default: "32", desc: "Queue depth once the cap is hit; past it, requests are rejected." },
        { name: "HERDS_SESSION_IDLE_TIMEOUT_MS", type: "ms", default: "1800000", desc: "Idle resident session → reaped (30 min)." },
        { name: "HERDS_SANDBOX_TTL_MS", type: "ms", default: "86400000", desc: "Untouched sandbox tree → garbage-collected (24 h)." },
      ]}
    />
    <Code lang="bash">{`export HERDS_CONTROL_PLANE="https://you.relay.herds.run"
export HERDS_API_KEY="hx_…"
python my_agent.py     # the SDK is now pointed at that Mac`}</Code>
  </>
);

/* ============================ registry ================================== */


/* ============================ Terminal & GUI ============================== */

const Terminal = ({ go }: { go: Go }) => (
  <>
    <Lead>
      An interactive terminal on a Mac, and real keyboard/mouse control of its GUI — no ssh, no VNC, no inbound ports.
    </Lead>

    <H2>A shell</H2>
    <Code lang="python">{`herds.mac().shell()                  # a real login shell
herds.mac().shell("vim notes.md")    # straight into a program`}</Code>
    <Code lang="bash">{`herds ssh                  # one Mac online? it just connects
herds ssh mini             # or name the one you want
herds ssh mini -c htop`}</Code>
    <P>
      The Mac runs it under a <strong className="font-semibold text-stone-800">pty</strong>, so you get your prompt, colours, and
      full-screen programs like <Co>vim</Co> and <Co>top</Co>. Your local terminal goes raw, so keystrokes and Ctrl-C reach the Mac
      instead of being line-buffered or killing the client. <Co>Ctrl-]</Co> detaches and leaves the remote process running.
    </P>
    <Callout type="tip" title="It always tells you which Mac">
      <Co>herds.mac()</Co> resolves to the <em>idlest</em> Mac — right for fanning work out, wrong for a terminal. A shell pins its
      target first and prints it, and <Co>herds ssh</Co> with several Macs online lists them and stops rather than guessing.
    </Callout>
    <P>
      It runs as <em>you</em> — real <Co>$HOME</Co>, real logins — and opens in your home directory. Pass <Co>--sandboxed</Co> (CLI) or{" "}
      <Co>real=False</Co> (SDK) for an isolated workspace instead. With no terminal attached (a script, a notebook) it returns the{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("sessions"); }}>Session</A> instead of taking over.
    </P>

    <H2>Picking a Mac</H2>
    <P>Any command that takes a machine accepts whatever you&rsquo;d naturally type — id, name, id prefix, part of the name, or a tag:</P>
    <Code lang="bash">{`herds ssh mac_ed74b9b0        # exact id
herds ssh "Teddys Mac mini"   # name (case-insensitive)
herds ssh mini                # part of the name
herds ssh ci                  # a tag:  herds tag mac_ed74b9b0 ci
herds run -m mini -- uname -a`}</Code>
    <P>If a reference matches more than one Mac, herds lists the candidates and stops instead of guessing.</P>

    <H2>Driving the GUI</H2>
    <Code lang="python">{`mac.ui.click(400, 300);  mac.ui.right_click(400, 300)
mac.ui.drag(100, 100, 400, 300)      # interpolated, so drop targets accept it
mac.ui.scroll(-250)
mac.ui.type("hello unicode")          # layout-independent
mac.ui.hotkey("cmd", "s")

mac.ui.focus("Preview")               # launches or fronts the app
mac.ui.move_window("Preview", 0, 0)
mac.ui.resize_window("Preview", 1200, 800)`}</Code>

    <H3>Target elements, not pixels</H3>
    <Code lang="python">{`save = mac.ui.find("Preview", role="AXButton", name="Save")
save.click()                              # clicks its centre
mac.ui.press_element("Preview", "Save")   # or AXPress it — works if occluded
mac.ui.menu("Finder", "New Window")

for el in mac.ui.tree("Finder", "menubar", depth=3):
    print(el.role, el.name, el.center)`}</Code>
    <P>
      Coordinates break the moment a window moves; accessibility elements don&rsquo;t. Built on CGEvent and the AX C API rather than
      AppleScript — AppleScript needs an <strong className="font-semibold text-stone-800">Automation</strong> grant whose prompt can
      only be shown to a foreground app, so from a launchd daemon those calls hang until timeout instead of failing.
    </P>

    <Callout type="warn" title="Check permissions on the Mac, not on your laptop">
      TCC grants are per-process. If <strong className="font-semibold text-stone-800">Accessibility</strong> isn&rsquo;t granted to the
      daemon, macOS <em>silently drops</em> synthetic events — <Co>mac.ui.click()</Co> returns success and nothing moves.
      <Code lang="bash">{`herds doctor          # audits the daemon on the Mac
herds doctor --local  # audit this process instead`}</Code>
      It names the exact binary to grant. After granting: <Co>herds host stop &amp;&amp; herds host</Co>.
    </Callout>
  </>
);

/* ============================ Moving files ================================ */

const Transfers = () => (
  <>
    <Lead>Getting bytes onto a Mac quickly — and why the obvious way is the slow way.</Lead>

    <H2>The shape of the problem</H2>
    <P>The relay is a control channel, not a pipe. Measured on a real fleet:</P>
    <Code lang="text">{`control plane on the same machine   ~24 MB/s     572MB in ~24s
through the relay                    0.2-0.8 MB/s 572MB in 13-41 min`}</Code>
    <P>
      Parallel uploads only bought 1.4x, so it&rsquo;s throughput-limited end to end — chunking can&rsquo;t fix it. Worse, a large push
      saturates the relay for every other machine in the fleet while it runs.
    </P>

    <H2>Let the Mac pull</H2>
    <Code lang="python">{`mac.fetch("https://example.com/App.dmg", "App.dmg")
mac.fetch(url, "model.safetensors", volume="weights",
          headers={"Authorization": "Bearer …"})`}</Code>
    <P>
      The Mac downloads over its own connection and the relay carries only the command. Mac-to-Mac is the same trick:{" "}
      <Co>expose()</Co> the file on one and <Co>fetch()</Co> that URL from the other.
    </P>

    <H2>push goes direct too</H2>
    <Code lang="python">{`mac.push("./Big.app", "apps")                 # direct if reachable, relay if not
mac.push("./Big.app", "apps", direct=False)   # force the relay`}</Code>
    <P>
      By default the payload is served from your machine and the Mac pulls it over the LAN or your tailnet — measured{" "}
      <strong className="font-semibold text-stone-800">11x</strong> on the same payload. Tailscale addresses are tried first, so it
      works across networks and through client-isolated Wi-Fi. If nothing is reachable it falls back to the relay silently.
    </P>
    <Callout type="tip" title="App bundles">
      Archives are gzipped (~1.9x on Chrome.app, ~2.8x on Cursor.app) and <strong className="font-semibold text-stone-800">keep
      symlinks</strong> — a <Co>.app</Co>&rsquo;s frameworks are <Co>Versions/Current</Co> links, and a copy without them will not
      launch. The relay path caps at 512 MB and tells you before the upload, not after.
    </Callout>
  </>
);


export const PAGES: DocPage[] = [
  { id: "introduction", group: "Getting started", title: "Introduction", description: "What Herds is, and the mental model.", Body: Introduction },
  { id: "quickstart", group: "Getting started", title: "Quickstart", description: "From install to your first command.", Body: Quickstart },
  { id: "installation", group: "Getting started", title: "Installation", description: "Install the SDK and CLI.", Body: Installation },

  { id: "how-it-works", group: "Core concepts", title: "How it works", description: "Daemon, control plane, and relay.", Body: HowItWorks },
  { id: "authentication", group: "Core concepts", title: "Authentication", description: "Tokens, scopes, and keys.", Body: Authentication },

  { id: "commands", group: "Python SDK", title: "Running commands", description: "run, stream, and map.", Body: Commands },
  { id: "fleet", group: "Python SDK", title: "The fleet", description: "Every Mac you own, addressed as one.", Body: FleetPage },
  { id: "fleets", group: "Getting started", title: "Fleets you can drive", description: "herds child, herds use, and holding several at once.", Body: Fleets },
  { id: "sandboxes", group: "Python SDK", title: "Sandboxes", description: "Isolated, persistent workspaces.", Body: Sandboxes },
  { id: "sessions", group: "Python SDK", title: "Sessions", description: "Long-lived processes you drive turn by turn.", Body: Sessions },
  { id: "agents", group: "Python SDK", title: "Agents (keyless)", description: "Run Claude Code / Codex on a Mac — no key on the machine.", Body: Agents },
  { id: "volumes", group: "Python SDK", title: "Volumes", description: "Durable named directories.", Body: Volumes },
  { id: "images", group: "Python SDK", title: "Images", description: "Select toolchains on the Mac.", Body: Images },
  { id: "secrets", group: "Python SDK", title: "Secrets", description: "Injected environment bundles.", Body: Secrets },
  { id: "functions", group: "Python SDK", title: "Remote functions", description: "Run a Python function on the Mac.", Body: Functions },
  { id: "results", group: "Python SDK", title: "Results & errors", description: "Result objects and exceptions.", Body: Results },

  { id: "terminal", group: "Python SDK", title: "Terminal & GUI", description: "Interactive shell, and keyboard/mouse control.", Body: Terminal },
  { id: "transfers", group: "Python SDK", title: "Moving files", description: "fetch, direct push, and why the relay is slow.", Body: Transfers },

  { id: "cli", group: "Command line", title: "CLI reference", description: "Every herds subcommand.", Body: CLI },

  { id: "hosting", group: "Self-hosting", title: "Hosting a Mac", description: "herds host, end to end.", Body: Hosting },
  { id: "relay", group: "Self-hosting", title: "The relay", description: "Public links and subdomains.", Body: Relay },

  { id: "rest-api", group: "Reference", title: "REST API", description: "Control plane HTTP + WS endpoints.", Body: RestApi },
  { id: "env-vars", group: "Reference", title: "Environment variables", description: "All HERDS_* configuration.", Body: EnvVars },
];
