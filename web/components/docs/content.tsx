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
    </UL>

    <H2>Start here</H2>
    <CardGrid>
      <Card title="Quickstart" desc="From pip install to your first command on a Mac, in under a minute." onClick={() => go("quickstart")} />
      <Card title="How it works" desc="The daemon, the control plane, and the relay — and why there are no inbound ports." onClick={() => go("how-it-works")} />
      <Card title="Running commands" desc="run, stream, and map — the core of the Python SDK." onClick={() => go("commands")} />
      <Card title="Sandboxes" desc="Isolated, persistent workspaces with public URLs." onClick={() => go("sandboxes")} />
    </CardGrid>
  </>
);

const Quickstart = ({ go }: { go: Go }) => (
  <>
    <Lead>Two paths: you were handed a Mac (a URL + token), or you want to connect your own. Both take about a minute.</Lead>

    <H2>Install</H2>
    <Code lang="bash">{`pip install herds        # or:  uv tool install herds`}</Code>
    <P>
      Herds needs Python 3.11+. The package ships both the <Co>herds</Co> Python SDK and the <Co>herds</Co> command-line tool.
    </P>

    <H2>Path A — you were given a Mac</H2>
    <P>
      If someone handed you a Herds <strong className="font-semibold text-stone-800">URL + token</strong>, that&rsquo;s all you need. Point the SDK at it
      and run:
    </P>
    <Code lang="python">{`import herds

herds.configure(url="https://you.relay.herds.run", token="hx_…")
print(herds.mac().run("uname -msr").stdout)   # runs on that Mac, from anywhere`}</Code>
    <Callout type="note">
      <Co>configure()</Co> is identical to setting the <Co>HERDS_CONTROL_PLANE</Co> and <Co>HERDS_API_KEY</Co> environment variables.
      See <A href="#env-vars">Environment variables</A>.
    </Callout>

    <H2>Path B — connect your own Mac</H2>
    <P>On the Mac you want to make callable:</P>
    <Code lang="bash">{`pip install herds
herds auth          # sign in — creates a free account + a permanent link
herds host          # control plane + dashboard + public link, in one command`}</Code>
    <P>
      <Co>herds auth</Co> mints your account token and assigns a subdomain like <Co>you.relay.herds.run</Co>. <Co>herds host</Co> starts a
      local control plane, registers this Mac, and brings up a public link — without opening a single inbound port.
    </P>

    <H2>Run your first command</H2>
    <Code lang="python">{`import herds

mac = herds.mac()                       # your online Mac
r = mac.run("sw_vers")
print(r.stdout, r.exit_code)

mac.run("xcodebuild -scheme App test", check=True)   # raises on non-zero exit`}</Code>

    <Callout type="tip">
      Driving this from an agent? Install the agent skill with <Co>herds skill --install</Co>, or read it at <A href="/skill">herds.run/skill</A>.
    </Callout>

    <Divider />
    <P>
      Next: <A href="#" onClick={(e) => { e.preventDefault(); go("commands"); }}>Running commands</A> covers <Co>run</Co>, <Co>stream</Co>, and{" "}
      <Co>map</Co> in depth.
    </P>
  </>
);

const Installation = () => (
  <>
    <Lead>Herds is a single pip package: the Python SDK and the CLI ship together.</Lead>

    <H2>Requirements</H2>
    <UL>
      <LI><strong className="font-semibold text-stone-800">Python 3.11+</strong> (tested on 3.11, 3.12, 3.13).</LI>
      <LI>To host a Mac: <strong className="font-semibold text-stone-800">macOS</strong>. To drive one from the SDK: any OS.</LI>
    </UL>

    <H2>Install</H2>
    <Code lang="bash">{`pip install herds          # into the current environment
uv tool install herds      # or as a standalone CLI tool
curl -fsSL herds.run/install | sh   # bootstrap script`}</Code>

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
    <P>Run one command across many inputs in parallel — Modal-style fan-out. Returns a list of Results.</P>
    <Code lang="python">{`mac.map("pytest {}", ["tests/unit", "tests/e2e"])        # {} is the format slot
mac.map(lambda v: f"swift build -c {v}", ["debug", "release"])
mac.map("./bench {}", inputs, max_workers=8)`}</Code>

    <Callout type="tip">
      Pushing a whole codebase before you run it? Use <A href="#" onClick={(e) => { e.preventDefault(); go("volumes"); }}>volumes</A> or a{" "}
      <A href="#" onClick={(e) => { e.preventDefault(); go("sandboxes"); }}>sandbox</A>.
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

    <H2>Methods</H2>
    <Params
      rows={[
        { name: "Sandbox.create(...)", type: "→ Sandbox", desc: <>Create a sandbox. Accepts <Co>image</Co>, <Co>volumes</Co>, <Co>secrets</Co>, <Co>inherit_home</Co>, and a target <Co>mac</Co> / <Co>machine_id</Co>.</> },
        { name: "sbx.put(local, remote='')", type: "→ dict", desc: "Copy a local file or directory into the workspace." },
        { name: "sbx.exec(command, ...)", type: "→ Result", desc: <>Run a command and wait. Same options as <Co>mac.run</Co> (<Co>workdir</Co>, <Co>env</Co>, <Co>timeout</Co>, <Co>network</Co>, <Co>stream</Co>, <Co>check</Co>).</> },
        { name: "sbx.stream(command, ...)", type: "→ iterator", desc: <>Yield <Co>(stream, text)</Co> chunks live.</> },
        { name: "sbx.spawn(command, ...)", type: "→ str", desc: <>Start without waiting; returns a request id. <Co>keep_alive=True</Co> supervises it.</> },
        { name: "sbx.expose(port, name='')", type: "→ str", desc: "Expose a port as a public URL." },
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

    <H2>API</H2>
    <Params
      rows={[
        { name: "Volume.from_name(name)", type: "→ Volume", desc: "Reference a volume by name; created lazily on first write." },
        { name: "vol.put(local, remote='', ...)", type: "→ dict", desc: <>Copy a file/dir into the volume. Options: <Co>clean</Co>, <Co>ignore</Co>, <Co>machine</Co>.</> },
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
    .run_commands("brew install swiftlint")   # run once before your command
)
mac.run("xcodebuild -scheme App archive", image=img)`}</Code>

    <Params
      rows={[
        { name: ".env_vars(**vars)", type: "→ Image", desc: "Add or override environment variables." },
        { name: ".run_commands(*cmds)", type: "→ Image", desc: "Setup commands run once before your command (best-effort)." },
      ]}
    />
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

const CLI = () => (
  <>
    <Lead>The <Co>herds</Co> CLI covers the whole lifecycle — sign in, host a Mac, run commands, and manage volumes, images, and tokens.</Lead>

    <H2>Account &amp; hosting</H2>
    <Code lang="bash">{`herds auth [--token hx_…] [--name <subdomain>]   # sign in, get account + link
herds host [--port 8787] [--no-tunnel] [--quick] # control plane + dashboard + link
herds host setup                                  # walkthrough: Tailscale Funnel
herds connect <url> <token>                        # join THIS Mac to a host
herds open                                          # open the dashboard in a browser`}</Code>

    <H2>Running commands</H2>
    <Code lang="bash">{`herds run -- <cmd>          # run a command on a Mac (streams output)
herds shell -c "<cmd>"      # one-off command
herds machines              # list connected Macs
herds logs [-m <id>]        # recent jobs
herds status                # local config`}</Code>

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
    <Code lang="bash">{`herds connect https://you.relay.herds.run herds_sk_…`}</Code>

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

    <H2>Execution</H2>
    <Endpoints
      rows={[
        { method: "POST", path: "/v1/machines/{id}/exec", desc: "Queue a command → request_id" },
        { method: "GET", path: "/v1/jobs", desc: "Recent jobs" },
        { method: "GET", path: "/v1/jobs/{request_id}/output", desc: "Job output (even mid-run)" },
        { method: "WS", path: "/v1/jobs/{request_id}/logs", desc: "Stream job frames live" },
      ]}
    />

    <H2>Sandboxes</H2>
    <Endpoints
      rows={[
        { method: "GET", path: "/v1/sandboxes", desc: "List sandboxes" },
        { method: "GET", path: "/v1/sandboxes/{id}", desc: "One sandbox + active jobs" },
        { method: "POST", path: "/v1/sandboxes/{id}/stop", desc: "Stop running processes" },
        { method: "DELETE", path: "/v1/sandboxes/{id}", desc: "Terminate + wipe workspace" },
        { method: "POST", path: "/v1/sandboxes/{id}/ports", desc: "Expose a port → URL" },
        { method: "PUT", path: "/v1/sandboxes/{id}/put", desc: "Push a file/dir (tar)" },
      ]}
    />

    <H2>Volumes, secrets &amp; keys</H2>
    <Endpoints
      rows={[
        { method: "GET", path: "/v1/volumes", desc: "List volumes" },
        { method: "PUT", path: "/v1/volumes/{name}/put", desc: "Push a file/dir" },
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
      ]}
    />
    <Code lang="bash">{`export HERDS_CONTROL_PLANE="https://you.relay.herds.run"
export HERDS_API_KEY="hx_…"
python my_agent.py     # the SDK is now pointed at that Mac`}</Code>
  </>
);

/* ============================ registry ================================== */

export const PAGES: DocPage[] = [
  { id: "introduction", group: "Getting started", title: "Introduction", description: "What Herds is, and the mental model.", Body: Introduction },
  { id: "quickstart", group: "Getting started", title: "Quickstart", description: "From install to your first command.", Body: Quickstart },
  { id: "installation", group: "Getting started", title: "Installation", description: "Install the SDK and CLI.", Body: Installation },

  { id: "how-it-works", group: "Core concepts", title: "How it works", description: "Daemon, control plane, and relay.", Body: HowItWorks },
  { id: "authentication", group: "Core concepts", title: "Authentication", description: "Tokens, scopes, and keys.", Body: Authentication },

  { id: "commands", group: "Python SDK", title: "Running commands", description: "run, stream, and map.", Body: Commands },
  { id: "sandboxes", group: "Python SDK", title: "Sandboxes", description: "Isolated, persistent workspaces.", Body: Sandboxes },
  { id: "volumes", group: "Python SDK", title: "Volumes", description: "Durable named directories.", Body: Volumes },
  { id: "images", group: "Python SDK", title: "Images", description: "Select toolchains on the Mac.", Body: Images },
  { id: "secrets", group: "Python SDK", title: "Secrets", description: "Injected environment bundles.", Body: Secrets },
  { id: "functions", group: "Python SDK", title: "Remote functions", description: "Run a Python function on the Mac.", Body: Functions },
  { id: "results", group: "Python SDK", title: "Results & errors", description: "Result objects and exceptions.", Body: Results },

  { id: "cli", group: "Command line", title: "CLI reference", description: "Every herds subcommand.", Body: CLI },

  { id: "hosting", group: "Self-hosting", title: "Hosting a Mac", description: "herds host, end to end.", Body: Hosting },
  { id: "relay", group: "Self-hosting", title: "The relay", description: "Public links and subdomains.", Body: Relay },

  { id: "rest-api", group: "Reference", title: "REST API", description: "Control plane HTTP + WS endpoints.", Body: RestApi },
  { id: "env-vars", group: "Reference", title: "Environment variables", description: "All HERDS_* configuration.", Body: EnvVars },
];
