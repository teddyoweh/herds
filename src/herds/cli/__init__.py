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
app.add_typer(volume_app, name="volume")
app.add_typer(image_app, name="image")

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
):
    """Self-host this Mac with a permanent Tailscale Funnel link.

    Run `herds host setup` first to enable Tailscale Funnel (free, permanent).
    """
    if ctx.invoked_subcommand is not None:
        return
    from ..host import run_host

    run_host(port=port, tunnel=not no_tunnel, quick=quick)


@host_app.command("setup")
def _host_setup():
    """Walkthrough: enable a permanent public link via Tailscale Funnel."""
    from ..host import host_setup

    host_setup()


@app.command()
def auth(
    token: Optional[str] = typer.Option(None, "--token", help="Account token (hx_…)."),
    name: Optional[str] = typer.Option(None, "--name", help="Preferred subdomain when provisioning."),
):
    """Sign in to your Herds account, so `herds host` gets you a stable link."""
    from ..relay import provision_account, whoami

    config.ensure_dirs()
    a = config.Auth.load()

    if token:  # bring an existing token (e.g. to a second Mac)
        info = whoami(a.relay, token)
        if not info:
            console.print("[red]✗ Invalid or expired token.[/red]")
            raise typer.Exit(1)
        a.token, a.account, a.url = token, info["account"], info.get("url")
        a.save()
    elif a.signed_in and not name:
        console.print(f"[green]✓ Signed in[/green] as [bold]{a.account}[/bold] — run [bold]herds host[/bold].")
        return
    else:  # provision a fresh account
        info = provision_account(a.relay, name or "")
        a.token, a.account, a.url = info["token"], info["account"], info.get("url")
        a.save()

    console.print(Panel.fit(
        f"[green]✓ Signed in to Herds[/green]\n\n"
        f"[bold]Account[/bold]\n  {a.account}\n\n"
        f"[bold]Your link[/bold]  [dim](after `herds host`)[/dim]\n  [cyan]https://{a.account}.herds.run[/cyan]\n\n"
        f"[bold]Token[/bold]  [dim](use `herds auth --token …` on your other Macs)[/dim]\n  [yellow]{a.token}[/yellow]\n\n"
        f"[dim]Now run [bold]herds host[/bold] — your Mac goes live at the link above.[/dim]",
        title="herds auth", border_style="green",
    ))


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
def logs(machine: Optional[str] = typer.Option(None, "--machine", "-m")):
    """Show recent jobs."""
    import httpx

    cfg = config.Config.load()
    try:
        params = {"machine_id": machine} if machine else {}
        r = httpx.get(f"{cfg.control_plane}/v1/jobs", params=params, timeout=10)
        jobs = r.json()["jobs"]
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
    <string>connect</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
  <dict><key>NetworkState</key><true/><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{config.LOGS_DIR / 'daemon.out.log'}</string>
  <key>StandardErrorPath</key><string>{config.LOGS_DIR / 'daemon.err.log'}</string>
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
