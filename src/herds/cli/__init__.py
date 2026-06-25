"""The ``herds`` CLI: connect Macs, run commands, manage volumes and images.

Mirrors the shape the product mockups call for:

    herds serve        # run a control plane locally (dev / self-host)
    herds connect      # connect THIS Mac and keep it online
    herds machines     # list your connected Macs
    herds run -- <cmd> # run a command on a Mac
    herds shell        # run a one-off command / drop a quick shell
    herds logs         # recent jobs
    herds volume ls    # list volumes
    herds image ls     # toolchain images available on this Mac
    herds install      # install the launchd LaunchAgent (stay online on login)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .. import __version__, config
from ..daemon import machine as machine_mod

app = typer.Typer(
    name="herds",
    help="Connect your Mac to the internet and turn it into a programmable runtime.",
    no_args_is_help=True,
    add_completion=False,
)
volume_app = typer.Typer(help="Manage volumes (persistent directories on the Mac).")
image_app = typer.Typer(help="Inspect toolchain images available on this Mac.")
token_app = typer.Typer(help="Mint scoped, revocable tokens (e.g. for agents/CI).")
schedule_app = typer.Typer(help="Recurring scheduled jobs (cron) that run on your Mac.")
app.add_typer(volume_app, name="volume")
app.add_typer(image_app, name="image")
app.add_typer(token_app, name="token")
app.add_typer(schedule_app, name="schedule")


def _control_http(url: Optional[str], tok: Optional[str]):
    from ..sdk.client import HerdsClient
    return HerdsClient(control_plane=url, api_key=tok)._http


@token_app.command("new")
def token_new(
    label: str = typer.Argument("agent", help="A name for this token."),
    scope: str = typer.Option("run", "--scope", help="read | run | admin."),
    url: Optional[str] = typer.Option(None, "--url", help="Control-plane / relay URL."),
    token: Optional[str] = typer.Option(None, "--token", help="An admin token."),
):
    """Mint a scoped, revocable token — give it to an agent, revoke it anytime."""
    r = _control_http(url, token).post("/v1/keys", json={"label": label, "scope": scope})
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    d = r.json()
    console.print(Panel.fit(
        f"[green]✓ New [bold]{d['scope']}[/bold] token[/green]\n\n  [yellow]{d['key']}[/yellow]\n\n"
        f"[dim]Shown once. Hand it to your agent; revoke with `herds token revoke {d['key'][:13]}`.[/dim]",
        title=f"token · {d['label']}", border_style="green",
    ))


@token_app.command("ls")
def token_ls(
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """List your tokens (masked) and their scopes."""
    r = _control_http(url, token).get("/v1/keys")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    keys = r.json().get("keys", [])
    if not keys:
        console.print("[dim]No tokens yet.[/dim]")
        return
    table = Table(title="Tokens")
    table.add_column("Token", style="cyan")
    table.add_column("Scope")
    table.add_column("Label", style="dim")
    for k in keys:
        table.add_row(k["masked"], k.get("scope", "admin"), k.get("label") or "")
    console.print(table)


@token_app.command("revoke")
def token_revoke(
    prefix: str,
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """Revoke a token by its visible prefix (from `herds token ls`)."""
    r = _control_http(url, token).delete(f"/v1/keys/{prefix.split('…')[0]}")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] revoked [cyan]{prefix}[/cyan]")


@schedule_app.command("add")
def schedule_add(
    cron: str = typer.Argument(..., help='Cron expr, e.g. "0 9 * * *" (min hour dom mon dow).'),
    command: list[str] = typer.Argument(..., help="The command (after --)."),
    machine: Optional[str] = typer.Option(None, "--machine", "-m", help="Target machine id."),
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """Schedule a recurring command. e.g. herds schedule add "0 9 * * *" -- swift test"""
    cmd = " ".join(command)
    r = _control_http(url, token).post(
        "/v1/schedules", json={"cron": cron, "command": cmd, "machine_id": machine})
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    d = r.json()
    console.print(f"[green]✓[/green] scheduled [cyan]{d['id']}[/cyan]  [dim]{d['cron']}[/dim]  {d['command']}")


@schedule_app.command("ls")
def schedule_ls(
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """List recurring schedules."""
    r = _control_http(url, token).get("/v1/schedules")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    rows = r.json().get("schedules", [])
    if not rows:
        console.print("[dim]No schedules yet.[/dim]")
        return
    table = Table(title="Schedules")
    table.add_column("ID", style="cyan")
    table.add_column("Cron")
    table.add_column("Command")
    table.add_column("Machine", style="dim")
    for s in rows:
        table.add_row(s["id"], s["cron"], (s["command"] or "")[:48], s.get("machine_id") or "default")
    console.print(table)


@schedule_app.command("rm")
def schedule_rm(
    schedule_id: str,
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """Remove a schedule by id."""
    r = _control_http(url, token).delete(f"/v1/schedules/{schedule_id}")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] removed [cyan]{schedule_id}[/cyan]")


@app.command("tag")
def tag_add(
    machine_id: str,
    tags: list[str] = typer.Argument(..., help="One or more tags, e.g. xcode-26 ci."),
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """Tag a Mac for routing — herds.mac(tag='xcode-26') picks the idlest match."""
    r = _control_http(url, token).post(f"/v1/machines/{machine_id}/tags", json={"tags": tags})
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] [cyan]{machine_id}[/cyan] tags: {', '.join(r.json()['tags']) or '—'}")


@app.command("tags")
def tags_ls(
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """List your Macs with their tags, status, and live CPU."""
    r = _control_http(url, token).get("/v1/machines")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    rows = r.json().get("machines", [])
    if not rows:
        console.print("[dim]No machines.[/dim]")
        return
    table = Table(title="Macs")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("CPU", justify="right")
    table.add_column("Tags", style="dim")
    for m in rows:
        cpu = m.get("live_cpu")
        table.add_row(m["machine_id"], m.get("status", "?"),
                      f"{cpu:.0f}%" if cpu is not None else "—",
                      ", ".join(m.get("tags") or []) or "—")
    console.print(table)


@app.command("untag")
def tag_rm(
    machine_id: str,
    tag: str,
    url: Optional[str] = typer.Option(None, "--url"),
    token: Optional[str] = typer.Option(None, "--token"),
):
    """Remove a tag from a Mac."""
    r = _control_http(url, token).delete(f"/v1/machines/{machine_id}/tags/{tag}")
    if r.status_code >= 400:
        err.print(f"[red]✗[/red] {r.json().get('detail', r.text)}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] removed [cyan]{tag}[/cyan] from {machine_id}")


console = Console()
err = Console(stderr=True)


def _client():
    from ..sdk.client import HerdsClient

    return HerdsClient()


# --------------------------------------------------------------------------- #
# Top-level commands
# --------------------------------------------------------------------------- #


@app.command()
def version():
    """Show the Herds version."""
    console.print(f"herds {__version__}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8787, help="Bind port."),
):
    """Run a Herds control plane locally (for development or self-hosting)."""
    from ..control import serve as serve_control

    console.print(
        Panel.fit(
            f"[bold]Herds control plane[/bold]\n\n"
            f"Listening on  [cyan]http://{host}:{port}[/cyan]\n"
            f"Agents dial   [cyan]ws://{host}:{port}/agent/ws[/cyan]\n\n"
            f"Point Macs here with:\n"
            f"  [dim]HERDS_CONTROL_PLANE=http://{host}:{port} herds connect[/dim]",
            title="serve",
            border_style="green",
        )
    )
    serve_control(host=host, port=port)


host_app = typer.Typer(help="Self-host Herds with a secure public link.", invoke_without_command=True)
app.add_typer(host_app, name="host")


@host_app.callback()
def _host_main(
    ctx: typer.Context,
    port: int = typer.Option(8787, help="Control plane port (auto-bumps if busy)."),
    no_tunnel: bool = typer.Option(False, "--no-tunnel", help="Serve locally only, no public link."),
    quick: bool = typer.Option(False, "--quick", help="Temporary Cloudflare quick tunnel (changes each run; less reliable)."),
    restart: bool = typer.Option(False, "--restart", "--force", help="Start a new host even if this Mac is already hosting."),
):
    """Self-host this Mac with a permanent Tailscale Funnel link.

    If this Mac is already hosting, shows the live link instead of starting a
    duplicate. Run `herds host setup` first to enable Tailscale Funnel.
    """
    if ctx.invoked_subcommand is not None:
        return
    from ..host import run_host

    run_host(port=port, tunnel=not no_tunnel, quick=quick, force=restart)


@host_app.command("setup")
def _host_setup():
    """Walkthrough: enable a permanent public link via Tailscale Funnel."""
    from ..host import host_setup

    host_setup()


def _print_signed_in(a: "config.Auth") -> None:
    console.print(Panel.fit(
        f"[green]✓ Signed in to Herds[/green]\n\n"
        f"[bold]Account[/bold]\n  {a.account}\n\n"
        f"[bold]Your link[/bold]  [dim](after `herds host`)[/dim]\n  [cyan]{a.url or f'https://{a.account}.relay.herds.run'}[/cyan]\n\n"
        f"[bold]Token[/bold]  [dim](use `herds auth --token …` on your other Macs)[/dim]\n  [yellow]{a.token}[/yellow]\n\n"
        f"[dim]Now run [bold]herds host[/bold] — your Mac goes live at the link above.[/dim]",
        title="herds auth", border_style="green",
    ))


@app.command()
def auth(
    token: Optional[str] = typer.Option(None, "--token", help="Account token (hx_…) — sign in headless, no browser."),
    name: Optional[str] = typer.Option(None, "--name", help="Preferred subdomain when provisioning."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Print the link + code instead of opening a browser."),
):
    """Sign in to Herds — opens your browser to approve, then syncs the token back."""
    import time as _t
    import webbrowser

    from ..relay import device_poll, device_start, provision_account, whoami

    config.ensure_dirs()
    a = config.Auth.load()

    if token:  # bring an existing token (e.g. to a second Mac) — no browser needed
        info = whoami(a.relay, token)
        if not info:
            console.print("[red]✗ Invalid or expired token.[/red]")
            raise typer.Exit(1)
        a.token, a.account, a.url = token, info["account"], info.get("url")
        a.save()
        _print_signed_in(a)
        return

    if a.signed_in and not name:
        console.print(f"[green]✓ Signed in[/green] as [bold]{a.account}[/bold] — run [bold]herds host[/bold].")
        console.print("[dim]Use [bold]herds auth --name <new>[/bold] to switch accounts.[/dim]")
        return

    # Browser sign-in (device-authorization flow): grab a code, open the browser,
    # the user approves on the web, and the token syncs straight back to this Mac.
    try:
        start = device_start(a.relay, name or "")
    except Exception as exc:  # noqa: BLE001 — older relay w/o device flow → passwordless fallback
        console.print(f"[dim]Browser sign-in unavailable ({exc}); provisioning a token instead…[/dim]")
        info = provision_account(a.relay, name or "")
        a.token, a.account, a.url = info["token"], info["account"], info.get("url")
        a.save()
        _print_signed_in(a)
        return

    code = start["user_code"]
    verify = start.get("verification_uri_complete") or start.get("verification_uri", "")
    interval = float(start.get("interval", 2) or 2)
    deadline = _t.time() + float(start.get("expires_in", 600) or 600)

    console.print(Panel.fit(
        f"[bold]Approve this Mac to finish signing in[/bold]\n\n"
        f"Open this link in your browser:\n  [cyan]{verify}[/cyan]\n\n"
        f"and confirm the code matches:\n  [bold yellow]{code}[/bold yellow]",
        title="herds auth", border_style="green",
    ))
    if not no_browser:
        try:
            webbrowser.open(verify)
        except Exception:  # noqa: BLE001 — headless / no browser: the link above still works
            pass

    with console.status("[dim]Waiting for you to approve in the browser…[/dim]", spinner="dots"):
        while _t.time() < deadline:
            _t.sleep(interval)
            try:
                res = device_poll(a.relay, start["device_code"])
            except Exception:  # noqa: BLE001 — transient network blip; keep polling
                continue
            status = res.get("status")
            if status == "approved":
                a.token, a.account, a.url = res["token"], res["account"], res.get("url")
                a.save()
                break
            if status == "expired":
                console.print("[red]✗ This sign-in request expired. Run [bold]herds auth[/bold] again.[/red]")
                raise typer.Exit(1)
        else:
            console.print("[red]✗ Timed out waiting for approval. Run [bold]herds auth[/bold] again.[/red]")
            raise typer.Exit(1)

    _print_signed_in(a)


@app.command("open")
def open_dashboard():
    """Open your live Herds dashboard in the browser (signed in)."""
    import webbrowser

    auth = config.Auth.load()
    if not auth.signed_in:
        err.print("[yellow]Not signed in.[/yellow] Run [bold]herds auth[/bold] first.")
        raise typer.Exit(1)
    url = auth.url or f"https://{auth.account}.relay.herds.run"
    tf = config.HERDS_HOME / "host_token"
    open_url = f"{url}/?token={tf.read_text().strip()}" if tf.exists() else url
    console.print(f"[dim]Opening[/dim] [cyan]{url}[/cyan] …")
    webbrowser.open(open_url)


@app.command("mcp")
def mcp_serve(
    machine: str = typer.Option("default", "--machine", "-m", help="Target machine id."),
    url: Optional[str] = typer.Option(None, "--url", help="Control-plane / relay URL."),
    token: Optional[str] = typer.Option(None, "--token", help="Access token."),
):
    """Expose your Mac as an MCP server (stdio) — any agent can drive it natively.

    Add to an MCP client (e.g. Claude Desktop / Code):

      "herds": { "command": "herds", "args": ["mcp"],
        "env": {"HERDS_CONTROL_PLANE": "https://you.relay.herds.run", "HERDS_API_KEY": "hx_…"} }
    """
    try:
        from mcp.server.fastmcp import FastMCP, Image
    except ImportError:
        err.print("[red]MCP support isn't installed.[/red] Run: [bold]pip install 'herds[mcp]'[/bold]")
        raise typer.Exit(1)
    import herds

    if url or token:
        herds.configure(url=url, token=token)
    m = herds.mac(machine)
    server = FastMCP("herds")

    @server.tool()
    def run(command: str, timeout: int = 300) -> str:
        """Run a shell command on the Mac. Returns exit code, stdout and stderr."""
        r = m.run(command, timeout=timeout)
        return f"exit_code: {r.exit_code}\n\n[stdout]\n{r.stdout}\n[stderr]\n{r.stderr}"

    @server.tool()
    def read_file(path: str) -> str:
        """Read a text file from the Mac."""
        return m.read_text(path)

    @server.tool()
    def write_file(path: str, content: str) -> str:
        """Write a text file on the Mac (creates parent dirs)."""
        m.write(path, content)
        return f"wrote {len(content)} chars to {path}"

    @server.tool()
    def list_dir(path: str = ".") -> list:
        """List a directory on the Mac → [{name, dir, size, mtime_ms}]."""
        return m.ls(path)

    @server.tool()
    def screenshot():
        """Capture the Mac's screen as a PNG (needs Screen Recording permission)."""
        # No return annotation: `Image` is a local import, so FastMCP's
        # get_type_hints() can't resolve it — it detects the Image value at runtime.
        return Image(data=m.screenshot(), format="png")

    @server.tool()
    def notify(message: str, title: str = "Herds") -> str:
        """Show a macOS notification banner on the Mac."""
        m.notify(message, title)
        return "ok"

    @server.tool()
    def list_macs() -> list:
        """List the connected Macs you can target (machine ids)."""
        return [x.machine_id for x in herds.machines()]

    server.run()  # stdio MCP transport


@app.command()
def doctor():
    """Check macOS permissions + readiness for driving real apps (Chrome/Xcode/iMessage)."""
    import os
    import subprocess
    import tempfile

    def _run(args, timeout=10):
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except Exception:  # noqa: BLE001
            return None

    # Screen Recording — a real capture is sizable; a denied one errors or is tiny.
    shot = os.path.join(tempfile.gettempdir(), "herds_doctor.png")
    r = _run(["screencapture", "-x", shot])
    screen = bool(r and r.returncode == 0 and os.path.exists(shot) and os.path.getsize(shot) > 5000)
    if os.path.exists(shot):
        try:
            os.remove(shot)
        except OSError:
            pass

    # Accessibility — System Events reports it directly.
    r = _run(["osascript", "-e", 'tell application "System Events" to get UI elements enabled'])
    access = bool(r and r.stdout.strip() == "true")

    # Full Disk Access — reading a TCC-protected file only works when granted.
    try:
        with open(os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db"), "rb") as fh:
            fh.read(16)
        fda = True
    except Exception:  # noqa: BLE001
        fda = False

    r = _run(["launchctl", "managername"])
    gui = bool(r and "Aqua" in (r.stdout or ""))
    chrome = os.path.exists("/Applications/Google Chrome.app")
    r = _run(["xcode-select", "-p"])
    xcode = bool(r and r.returncode == 0 and (r.stdout or "").strip())

    table = Table(title="herds doctor — macOS readiness")
    table.add_column("Capability")
    table.add_column("Status")
    table.add_column("Unlocks", style="dim")

    def row(name, ok, unlocks):
        table.add_row(name, "[green]✓ granted[/green]" if ok else "[red]✗ missing[/red]", unlocks)

    row("GUI login session", gui, "driving GUI apps at all")
    row("Screen Recording", screen, "mac.screenshot()")
    row("Accessibility", access, "mac.ui.type / clicks")
    row("Full Disk Access", fda, "read iMessage chat.db, app data")
    table.add_row("Automation", "[yellow]— per-app[/yellow]", "control Chrome/Messages (prompts on first use)")
    row("Chrome installed", chrome, "mac.chrome()")
    row("Xcode tools", xcode, "xcodebuild / simctl")
    console.print(table)

    panes = {"Screen Recording": "Privacy_ScreenCapture", "Accessibility": "Privacy_Accessibility",
             "Full Disk Access": "Privacy_AllFiles"}
    missing = [n for n, ok in [("Screen Recording", screen), ("Accessibility", access),
                               ("Full Disk Access", fda)] if not ok]
    if missing:
        console.print("\n[bold]Grant the missing ones[/bold] (to whatever runs `herds host`):")
        for n in missing:
            console.print(f"  • {n}: [cyan]open 'x-apple.systempreferences:com.apple.preference.security?{panes[n]}'[/cyan]")
        console.print("[dim]Then restart `herds host`. (TCC is per-app, so grant the app you run it from.)[/dim]")
    else:
        console.print("\n[green]✓ All set — your Mac can drive real apps.[/green]")


@app.command()
def relay(
    port: int = typer.Option(8888, help="Relay port."),
    domain: str = typer.Option("herds.run", help="Wildcard domain for host subdomains."),
):
    """Run a Herds relay server (our infra — routes you.<domain> → connected hosts)."""
    from ..relay import serve_relay

    console.print(f"[green]herds relay[/green] on :{port} routing [cyan]*.{domain}[/cyan] → hosts")
    serve_relay(port=port, domain=domain)


@app.command()
def skill(
    install: bool = typer.Option(False, "--install", help="Install to ~/.claude/skills/herds/ so Claude Code picks it up."),
    dir: Optional[str] = typer.Option(None, "--dir", help="Skills directory (default: ~/.claude/skills)."),
):
    """Print the Herds agent skill (SKILL.md), or --install it for Claude Code."""
    from ..skill import SKILL_MD

    if not install:
        print(SKILL_MD)  # plain print so it's pipeable: `herds skill > SKILL.md`
        return

    dest = (Path(dir) if dir else Path.home() / ".claude" / "skills") / "herds" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(SKILL_MD)
    console.print(Panel.fit(
        f"[green]✓ Installed the Herds skill[/green]\n\n  [cyan]{dest}[/cyan]\n\n"
        f"[dim]Claude Code will pick it up — your agent can now drive a real Mac.[/dim]",
        title="herds skill", border_style="green",
    ))


@app.command()
def connect(
    url: Optional[str] = typer.Argument(None, help="Host link, e.g. https://….trycloudflare.com"),
    token: Optional[str] = typer.Argument(None, help="Host token from `herds host`."),
    control_plane: Optional[str] = typer.Option(
        None, "--control-plane", help="Control plane URL (overrides positional)."
    ),
    name: Optional[str] = typer.Option(None, help="Override this machine's name."),
):
    """Connect THIS Mac to a host and keep it online (runs in the foreground)."""
    import asyncio

    from ..daemon import Daemon

    config.ensure_dirs()
    cfg = config.Config.load()
    target = control_plane or url
    if target:
        cfg.control_plane = target
    if token:
        creds0 = config.Credentials.load()
        creds0.device_token = token
        creds0.save()
    if not cfg.machine_id:
        cfg.machine_id = machine_mod.new_machine_id()
    info = machine_mod.gather(cfg.machine_id)
    cfg.machine_name = name or info.name
    cfg.save()

    mem = f"{info.memory_gb}GB RAM" if info.memory_gb else "RAM ?"
    console.print(
        Panel.fit(
            f"[green]✓ Connecting[/green]\n\n"
            f"[bold]Machine[/bold]\n  {cfg.machine_name}\n  {mem}\n  macOS {info.macos_version}\n\n"
            f"[bold]ID[/bold]\n  {cfg.machine_id}\n\n"
            f"[bold]Control plane[/bold]\n  {cfg.control_plane}",
            title="herds connect",
            border_style="green",
        )
    )
    console.print("[dim]Keeping this Mac online. Press Ctrl-C to disconnect.[/dim]\n")

    creds = config.Credentials.load()
    daemon = Daemon(cfg.control_plane, cfg.machine_id, creds.device_token)
    try:
        asyncio.run(daemon.run_forever())
    except KeyboardInterrupt:
        console.print("\n[yellow]Disconnected.[/yellow]")


@app.command()
def machines():
    """List your connected Macs."""
    try:
        rows = _client().list_machines()
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Could not reach control plane:[/red] {exc}")
        raise typer.Exit(1)
    if not rows:
        console.print("[dim]No machines yet. Run `herds connect` on a Mac.[/dim]")
        return
    table = Table(title="Machines", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Chip", style="dim")
    table.add_column("Status")
    for m in rows:
        info = m.get("info") or {}
        status = m["status"]
        color = "green" if status == "online" else "dim"
        table.add_row(
            m["machine_id"],
            m.get("name", "?"),
            info.get("chip", "—"),
            f"[{color}]{status}[/{color}]",
        )
    console.print(table)


@app.command()
def run(
    command: list[str] = typer.Argument(..., help="Command to run (after `--`)."),
    machine: str = typer.Option("default", "--machine", "-m", help="Target machine id."),
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Image, e.g. xcode:26."),
    timeout: Optional[int] = typer.Option(None, help="Timeout in seconds."),
):
    """Run a command on a Mac, streaming output live."""
    from ..sdk.mac import Mac

    m = Mac(machine, client=_client())
    cmd = " ".join(command)
    try:
        result = m.run(cmd, image=image, timeout=timeout, stream=True)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    raise typer.Exit(result.exit_code)


@app.command()
def shell(
    cmd: str = typer.Option(..., "--cmd", "-c", help="Command to run."),
    machine: str = typer.Option("default", "--machine", "-m"),
    image: Optional[str] = typer.Option(None, "--image", "-i"),
):
    """Run a one-off command on a Mac (an SSH-equivalent for quick checks)."""
    from ..sdk.mac import Mac

    m = Mac(machine, client=_client())
    result = m.run(cmd, image=image, stream=True)
    raise typer.Exit(result.exit_code)


@app.command()
def agent(
    goal: list[str] = typer.Argument(..., help="What the agent should do."),
    machine: str = typer.Option("default", "--machine", "-m", help="Target Mac (default: the idlest)."),
    all_macs: bool = typer.Option(False, "--all", help="Run the same task on every online Mac."),
    sandbox: bool = typer.Option(False, "--sandbox", help="Run inside a fresh, isolated sandbox."),
    harness: str = typer.Option("claude-code", "--harness", help="claude-code | codex | custom."),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="proxyagent URL (or $PROXYAGENT_PROXY)."),
    token: Optional[str] = typer.Option(None, "--token", help="pa_ token (or $PROXYAGENT_TOKEN)."),
    secret: Optional[str] = typer.Option(None, "--secret", help="Herds Secret holding PROXYAGENT_TOKEN — never on disk."),
    command: Optional[str] = typer.Option(None, "--command", help="Custom-harness command, e.g. 'my-agent {goal}'."),
):
    """Run an agent on your Mac(s) — keyless via proxyagent, streamed live.

    One Mac, an isolated sandbox, or the whole fleet. The model key stays on your
    proxy; the Mac only ever holds the scoped token (use --secret to keep it off disk).

        herds agent "fix the failing tests" --proxy https://proxy.you.com --secret proxyagent
        herds agent "summarise today's PRs" --harness codex --all
        herds agent "build the app" --sandbox -m mac-studio
    """
    from ..sdk.mac import Fleet, Mac
    from ..sdk.sandbox import Sandbox

    cl = _client()
    g = " ".join(goal)
    try:
        if all_macs:
            out = Fleet(client=cl).agent(g, harness=harness, proxy=proxy, token=token, secret=secret, command=command)
            for nm, r in out.items():
                ec = getattr(r, "exit_code", None)
                console.print(f"[bold]{nm}[/bold]: " + (f"exit {ec}" if ec is not None else f"[red]{r}[/red]"))
            raise typer.Exit(0)
        m = Mac(machine, client=cl)
        if sandbox:
            sbx = Sandbox.create(secrets=[secret] if secret else None, mac=m, client=cl)
            try:
                res = sbx.agent(g, harness=harness, proxy=proxy, token=token, command=command, stream=True)
            finally:
                sbx.terminate()
        else:
            res = m.agent(g, harness=harness, proxy=proxy, token=token, secret=secret, command=command, stream=True)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    raise typer.Exit(getattr(res, "exit_code", 0) or 0)


@app.command()
def logs(machine: Optional[str] = typer.Option(None, "--machine", "-m")):
    """Show recent jobs."""
    try:
        params = {"machine_id": machine} if machine else {}
        # Use the SDK client so the API key is sent (the host enforces auth).
        r = _client()._http.get("/v1/jobs", params=params, timeout=10)
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
            raise RuntimeError(detail)
        jobs = r.json().get("jobs", [])
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Could not reach control plane:[/red] {exc}")
        raise typer.Exit(1)
    if not jobs:
        console.print("[dim]No jobs yet.[/dim]")
        return
    table = Table(title="Recent jobs")
    table.add_column("Request", style="cyan")
    table.add_column("Machine", style="dim")
    table.add_column("Command")
    table.add_column("State")
    table.add_column("Exit", justify="right")
    for j in jobs:
        st = j["state"]
        color = {"succeeded": "green", "failed": "red"}.get(st, "yellow")
        table.add_row(
            j["request_id"], j["machine_id"], (j.get("command") or "")[:40],
            f"[{color}]{st}[/{color}]",
            "" if j.get("exit_code") is None else str(j["exit_code"]),
        )
    console.print(table)


@app.command()
def status():
    """Show local Herds configuration."""
    cfg = config.Config.load()
    creds = config.Credentials.load()
    table = Table(show_header=False)
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Herds home", str(config.HERDS_HOME))
    table.add_row("Control plane", cfg.control_plane)
    table.add_row("This machine", f"{cfg.machine_name or '—'} ({cfg.machine_id or 'not connected'})")
    table.add_row("API key", "set" if creds.api_key else "[dim]none[/dim]")
    table.add_row("Device token", "set" if creds.device_token else "[dim]none[/dim]")
    console.print(table)


# --------------------------------------------------------------------------- #
# volume subcommands
# --------------------------------------------------------------------------- #


@volume_app.command("ls")
def volume_ls():
    """List volumes on this Mac."""
    config.ensure_dirs()
    vols = sorted(p for p in config.VOLUMES_DIR.iterdir() if p.is_dir()) if config.VOLUMES_DIR.exists() else []
    if not vols:
        console.print("[dim]No volumes yet.[/dim]")
        return
    table = Table(title="Volumes")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Size", justify="right")
    for v in vols:
        size = sum(f.stat().st_size for f in v.rglob("*") if f.is_file())
        table.add_row(v.name, str(v), _human(size))
    console.print(table)


@volume_app.command("create")
def volume_create(name: str):
    """Create a volume (a persistent directory)."""
    config.ensure_dirs()
    (config.VOLUMES_DIR / name).mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓[/green] created volume [cyan]{name}[/cyan]")


@volume_app.command("put")
def volume_put(
    name: str,
    local: str,
    remote: str = typer.Argument("", help="Destination path inside the volume."),
    clean: bool = typer.Option(False, "--clean", help="Wipe the destination dir first."),
    url: Optional[str] = typer.Option(None, "--url", help="Control-plane / relay URL (default: local / $HERDS_CONTROL_PLANE)."),
    token: Optional[str] = typer.Option(None, "--token", help="API token (default: $HERDS_API_KEY / saved creds)."),
):
    """Copy a local file or directory into a volume on a Mac (like `modal volume put`)."""
    from pathlib import Path
    from ..sdk import Volume

    src = Path(local).expanduser()
    if not src.exists():
        err.print(f"[red]No such path:[/red] {local}")
        raise typer.Exit(1)
    kind = "directory" if src.is_dir() else "file"
    with console.status(f"Pushing {kind} [cyan]{src.name}[/cyan] → volume [cyan]{name}[/cyan]…"):
        try:
            res = Volume.from_name(name).put(str(src), remote, clean=clean, url=url, token=token)
        except Exception as exc:  # noqa: BLE001
            err.print(f"[red]✗[/red] {exc}")
            raise typer.Exit(1)
    dest = f"{name}/{remote}" if remote else name
    if res.get("members") is not None:
        console.print(f"[green]✓[/green] pushed [bold]{res['members']}[/bold] files → volume [cyan]{dest}[/cyan]")
    else:
        console.print(f"[green]✓[/green] pushed [bold]{_human(res.get('size', 0))}[/bold] → volume [cyan]{res.get('path', dest)}[/cyan]")


@volume_app.command("rm")
def volume_rm(name: str, yes: bool = typer.Option(False, "--yes", "-y")):
    """Delete a volume."""
    path = config.VOLUMES_DIR / name
    if not path.exists():
        err.print(f"[red]No such volume:[/red] {name}")
        raise typer.Exit(1)
    if not yes:
        typer.confirm(f"Delete volume {name} and all its data?", abort=True)
    shutil.rmtree(path)
    console.print(f"[green]✓[/green] deleted volume [cyan]{name}[/cyan]")


# --------------------------------------------------------------------------- #
# image subcommands
# --------------------------------------------------------------------------- #


@image_app.command("ls")
def image_ls():
    """Show toolchain images and what's actually installed on this Mac."""
    table = Table(title="Images")
    table.add_column("Image", style="cyan")
    table.add_column("Backed by", style="dim")
    table.add_column("Available")

    xcodes = list(Path("/Applications").glob("Xcode*.app"))
    table.add_row(
        "xcode:<version>",
        "DEVELOPER_DIR / xcodes",
        f"[green]{len(xcodes)} installed[/green]" if xcodes else "[yellow]none[/yellow]",
    )
    has_mise = shutil.which("mise") is not None
    for kind in ("node", "python", "ruby", "go"):
        table.add_row(
            f"{kind}:<version>",
            "mise",
            "[green]mise ready[/green]" if has_mise else "[yellow]install mise[/yellow]",
        )
    table.add_row("macos", "host environment", "[green]always[/green]")
    console.print(table)


# --------------------------------------------------------------------------- #
# launchd install / uninstall
# --------------------------------------------------------------------------- #

_PLIST_LABEL = "ai.spawnlabs.herds"
_PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{_PLIST_LABEL}.plist"


def _plist_contents(herds_bin: str) -> str:
    config.ensure_dirs()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{_PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{herds_bin}</string>
    <string>host</string>
  </array>
  <key>RunAtLoad</key><true/>
  <!-- Only load inside a real GUI (Aqua) session: screenshots, AppleScript and
       UI control need a window server. Without this the agent can load at the
       login window with no display and silently fail every screen/UI action. -->
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <!-- Always keep the host running; it handles network drops itself (in-process
       reconnect), so we don't gate on NetworkState (which would kill it on a blip). -->
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{config.LOGS_DIR / 'host.out.log'}</string>
  <key>StandardErrorPath</key><string>{config.LOGS_DIR / 'host.err.log'}</string>
</dict>
</plist>
"""


@app.command()
def install():
    """Install a launchd LaunchAgent so this Mac stays online across logins."""
    herds_bin = shutil.which("herds") or "herds"
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(_plist_contents(herds_bin))
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(_PLIST_PATH)],
                   capture_output=True)
    res = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(_PLIST_PATH)],
                         capture_output=True, text=True)
    if res.returncode == 0:
        console.print(f"[green]✓[/green] installed LaunchAgent at [dim]{_PLIST_PATH}[/dim]")
        console.print("This Mac will reconnect automatically on login and after crashes.")
    else:
        err.print(f"[red]launchctl bootstrap failed:[/red] {res.stderr.strip()}")
        raise typer.Exit(1)


@app.command()
def uninstall():
    """Remove the launchd LaunchAgent."""
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(_PLIST_PATH)],
                   capture_output=True)
    if _PLIST_PATH.exists():
        _PLIST_PATH.unlink()
    console.print("[green]✓[/green] removed LaunchAgent")


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


if __name__ == "__main__":
    app()
