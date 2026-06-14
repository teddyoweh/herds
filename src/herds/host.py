"""``herds host`` — turn this Mac into a self-hosted Herds control plane with a
secure public link.

It orchestrates four things and prints one link + one token:
  1. the control plane (FastAPI), auth enforced, serving the dashboard via proxy
  2. the dashboard (Next, built same-origin) on a local port
  3. a tunnel (cloudflared) that exposes the control plane publicly
  4. this Mac's own daemon, so the host is also a compute node

The single tunneled origin serves the UI, the API, and all WebSockets. Other
Macs join with ``herds connect <link> <token>``.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from . import config
from .control.store import Store

console = Console()
err = Console(stderr=True)


def _spawn(cmd, env=None, cwd=None, **kw) -> subprocess.Popen:
    return subprocess.Popen(cmd, env=env, cwd=cwd, **kw)


def _persistent_token() -> str:
    """A stable host token that survives restarts (so the link+token never change)."""
    f = config.HERDS_HOME / "host_token"
    if f.exists():
        t = f.read_text().strip()
        if t:
            return t
    t = "herds_sk_" + secrets.token_urlsafe(24)
    f.write_text(t)
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    return t


def _start_tunnel(port: int, procs: list, quick: bool = False) -> tuple[Optional[str], str, bool]:
    """Return (public_url, provider, is_permanent).

    One command, no setup: if a PERMANENT link is already available (Tailscale
    Funnel that's signed-in, or a configured Cloudflare named tunnel) use it;
    otherwise fall straight back to a zero-setup Cloudflare quick tunnel.
    """
    if not quick:
        # Tailscale Funnel — only if it's *already* set up (silently skip otherwise).
        if shutil.which("tailscale"):
            try:
                st = _ts_status()
                dns = (st.get("Self", {}).get("DNSName") or "").rstrip(".") if st else ""
                if st and st.get("BackendState") == "Running" and dns:
                    r = subprocess.run(["tailscale", "funnel", "--bg", str(port)],
                                       capture_output=True, text=True, timeout=20)
                    if r.returncode == 0:
                        return f"https://{dns}", "Tailscale Funnel", True
            except Exception:
                pass

        # Cloudflare named tunnel — only if configured (domain).
        name = os.environ.get("HERDS_TUNNEL_NAME")
        hostname = os.environ.get("HERDS_TUNNEL_HOSTNAME")
        if shutil.which("cloudflared") and name and hostname:
            procs.append(_spawn(
                ["cloudflared", "tunnel", "run", "--url", f"http://127.0.0.1:{port}", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ))
            return f"https://{hostname}", "Cloudflare (named)", True

    # Zero-setup fallback: Cloudflare quick tunnel (works with one command).
    if shutil.which("cloudflared"):
        t = _spawn(["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        procs.append(t)
        return _wait_tunnel_url(t), "Cloudflare (quick)", False

    return None, "none", False


def _verify_tunnel(url: str, timeout: float = 70) -> bool:
    """Poll the public URL until it actually serves (quick tunnels need a bit to
    propagate). Returns True once reachable, False on timeout."""
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _wait_tunnel_url(proc: subprocess.Popen, timeout: float = 40) -> Optional[str]:
    """Parse cloudflared's stderr for the public https URL."""
    pat = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stderr.readline()
        if not line:
            if proc.poll() is not None:
                return None
            continue
        m = pat.search(line)
        if m:
            return m.group(0)
    return None


def _ts_status() -> Optional[dict]:
    """Parsed `tailscale status`, or None if the daemon isn't reachable."""
    try:
        out = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=6)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


def _run(cmd: list) -> int:
    """Run a command, streaming its output straight to this terminal."""
    console.print(f"   [dim]$ {' '.join(cmd)}[/dim]")
    try:
        return subprocess.call(cmd)
    except Exception as exc:
        err.print(f"   [red]couldn't run {cmd[0]}: {exc}[/red]")
        return 1


def _confirm(prompt: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"   {prompt} {suffix} ").strip().lower()
    except EOFError:
        return False
    if not ans:
        return default_yes
    return ans in ("y", "yes")


def host_setup() -> None:
    """Walkthrough that *runs* the steps to enable a permanent Tailscale Funnel link."""
    from rich.text import Text

    console.print(Panel.fit(
        "Set up a [bold]permanent[/bold] public link for your host with [bold]Tailscale Funnel[/bold].\n"
        "[dim]Free, secure, stable — your link becomes https://<your-mac>.<tailnet>.ts.net[/dim]",
        title="herds host setup", border_style="green",
    ))

    def step(n, title):
        console.print(f"\n[bold]{n})[/bold] {title}")

    # 1 — installed? Auto-install via Homebrew if possible.
    step(1, "Tailscale installed")
    if not shutil.which("tailscale"):
        if shutil.which("brew") and _confirm("Not found. Install Tailscale with Homebrew now?"):
            _run(["brew", "install", "tailscale"])
        if not shutil.which("tailscale"):
            console.print("   [yellow]Still not installed.[/yellow] Install it and re-run [bold]herds host setup[/bold]:")
            console.print("     [cyan]brew install tailscale[/cyan]  [dim]or the Mac app → https://tailscale.com/download/macos[/dim]")
            return
    console.print("   [green]✓ installed[/green]")

    # 2 — background service running? Start it (needs sudo) if not.
    step(2, "Tailscale service running")
    st = _ts_status()
    if st is None:
        console.print("   [yellow]The Tailscale background service isn't running.[/yellow]")
        if _confirm("Start it now? (installs the system service — needs your password)"):
            _run(["sudo", "tailscaled", "install-system-daemon"])
            time.sleep(2)
            st = _ts_status()
        if st is None:
            console.print("   [yellow]Service still not reachable.[/yellow] Start it manually, then re-run setup:")
            console.print("     [cyan]sudo tailscaled install-system-daemon[/cyan]  [dim]or open the Tailscale Mac app[/dim]")
            return
    console.print("   [green]✓ service running[/green]")

    # 3 — signed in? Run `tailscale up` (opens the browser) if not.
    step(3, "Signed in to your tailnet")
    if st.get("BackendState") != "Running":
        if _confirm("Not signed in. Sign in now? (opens your browser)"):
            if _run(["tailscale", "up"]) != 0:
                _run(["sudo", "tailscale", "up"])
            st = _ts_status() or {}
        if st.get("BackendState") != "Running":
            console.print("   [yellow]Not signed in yet.[/yellow] Run [cyan]tailscale up[/cyan], approve in the browser, then re-run setup.")
            return
    dns = (st.get("Self", {}).get("DNSName") or "").rstrip(".")
    console.print(f"   [green]✓ signed in[/green] [dim]as {dns or 'this machine'}[/dim]")

    # 4 — Funnel enabled? (needs two one-time admin-console toggles).
    step(4, "Funnel enabled for this Mac")
    self_node = st.get("Self", {})
    caps = list(self_node.get("CapMap", {}).keys()) or list(self_node.get("Capabilities", []))
    if not any("funnel" in c for c in caps):
        console.print("   [yellow]Funnel needs two one-time toggles in the Tailscale admin console:[/yellow]")
        console.print("     a. Enable HTTPS  →  [cyan]https://login.tailscale.com/admin/dns[/cyan]")
        console.print("     b. Allow Funnel  →  [cyan]https://login.tailscale.com/admin/acls[/cyan]  add:")
        console.print(Text('        "nodeAttrs": [{ "target": ["autogroup:member"], "attr": ["funnel"] }]', style="cyan"))
        if shutil.which("open") and _confirm("Open both admin pages in your browser now?"):
            _run(["open", "https://login.tailscale.com/admin/dns"])
            _run(["open", "https://login.tailscale.com/admin/acls"])
        console.print("   Then re-run [bold]herds host setup[/bold] to confirm.")
        return
    console.print("   [green]✓ Funnel enabled[/green]")

    # Done
    url = f"https://{dns}" if dns else "https://<your-mac>.<tailnet>.ts.net"
    console.print(Panel.fit(
        f"[green]✓ Tailscale Funnel is ready[/green]\n\n"
        f"[bold]Your permanent link[/bold]\n  [cyan]{url}[/cyan]\n\n"
        f"[dim]Now run [bold]herds host[/bold] — it'll use Funnel automatically and this link\n"
        f"(and your saved host token) will stay the same every time.[/dim]",
        title="all set", border_style="green",
    ))


def _free_port(start: int, tries: int = 64) -> int:
    """First bindable port at or after ``start`` (so the host just works)."""
    import socket

    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def run_host(port: int = 8787, dashboard_port: int = 3939, tunnel: bool = True, quick: bool = False) -> None:
    config.ensure_dirs()
    chosen = _free_port(port)
    if chosen != port:
        console.print(f"[dim]Port {port} is in use — using [bold]{chosen}[/bold] instead.[/dim]")
        port = chosen
    db_path = str(config.HERDS_HOME / "host.db")

    # 1. Stable host token (persisted) usable by dashboard + SDK + daemons.
    token = _persistent_token()
    store = Store(db_path)
    store.put_api_key(token, "host", "host")
    store.db.close()

    procs: list[subprocess.Popen] = []
    base_env = {**os.environ, "HERDS_HOME": str(config.HERDS_HOME)}

    # 2. Dashboard: the control plane serves the bundled static export
    #    (src/herds/web_dist) directly — no Node.js needed at runtime.
    web_dist = Path(__file__).resolve().parent / "web_dist"
    has_dashboard = web_dist.is_dir()
    if not has_dashboard:
        err.print("[yellow]No bundled dashboard found; serving API only.[/yellow]")

    # 3. Public link. Signed in → our relay (stable, branded, invisible). Else
    #    fall back to a Cloudflare/Tailscale tunnel.
    auth = config.Auth.load()
    use_relay = tunnel and not quick and auth.signed_in
    public_url, provider, permanent = f"http://127.0.0.1:{port}", "local", True
    if use_relay:
        public_url = auth.url or f"https://{auth.account}.herds.run"
        provider, permanent = "Herds", True
    elif tunnel:
        console.print("[dim]Opening secure tunnel…[/dim]")
        url, provider, permanent = _start_tunnel(port, procs, quick=quick)
        if url:
            public_url = url
        else:
            provider, permanent = "local", True
            err.print("[yellow]Not signed in and no tunnel available. Run [bold]herds auth[/bold] "
                      "for a stable link, or install cloudflared. Serving locally.[/yellow]")

    # 4. Control plane: auth on, serves the dashboard, knows its public URL + token.
    cp_env = {
        **base_env,
        "HERDS_REQUIRE_AUTH": "1",
        "HERDS_PUBLIC_URL": public_url,
        "HERDS_HOST_TOKEN": token,
    }
    procs.append(_spawn(
        [sys.executable, "-c",
         f"from herds.control import serve; serve(port={port}, db_path={db_path!r})"],
        env=cp_env,
    ))
    time.sleep(3)

    # 5. This Mac's own daemon (local, authed with the host token).
    procs.append(_spawn(
        [sys.executable, "-m", "herds.daemon"],
        env={**base_env, "HERDS_CONTROL_PLANE": f"http://127.0.0.1:{port}", "HERDS_DEVICE_TOKEN": token},
    ))

    # 6. Connect the public link. Relay = our infra (dial out, expose this control
    #    plane at your account's subdomain). Tunnel = verify it actually serves.
    if use_relay:
        procs.append(_spawn(
            [sys.executable, "-m", "herds.relay", "client", auth.relay, auth.token, f"http://127.0.0.1:{port}"],
            env=base_env,
        ))
        time.sleep(1.5)
    elif provider != "local":
        console.print("[dim]Verifying the link is live (quick tunnels take a few seconds)…[/dim]")
        if not _verify_tunnel(public_url):
            err.print("[yellow]The tunnel didn't come up in time.[/yellow] "
                      "It may still appear in a few seconds — reload the link, or re-run [bold]herds host[/bold].")

    link_note = (
        f"[dim]via {provider} · permanent[/dim]" if permanent
        else f"[dim]via {provider} · temporary link (changes each run) — "
             f"run [bold]herds host setup[/bold] once for a permanent Tailscale link.[/dim]"
    )
    open_url = f"{public_url}/?token={token}"
    console.print(Panel.fit(
        f"[green]✓ Herds host is live[/green]\n\n"
        f"[bold]Dashboard[/bold]\n  [cyan]{public_url}[/cyan]\n  {link_note}\n\n"
        f"[bold]Host token[/bold]\n  [yellow]{token}[/yellow] [dim](stable)[/dim]\n\n"
        f"[bold]Add another Mac[/bold]\n  [dim]herds connect {public_url} {token}[/dim]",
        title="herds host", border_style="green",
    ))
    # The magic link signs the dashboard in on open. Printed outside the panel so it
    # never gets truncated, and as an OSC-8 hyperlink so it's clickable where supported.
    console.print("\n  [bold green]→ Open your dashboard[/bold green] [dim](opens already signed in)[/dim]")
    console.print(f"    [link={open_url}][cyan]{open_url}[/cyan][/link]\n", soft_wrap=True)

    def shutdown(*_):
        console.print("\n[yellow]Shutting down host…[/yellow]")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    while True:
        time.sleep(1)
        if all(p.poll() is not None for p in procs):
            break
