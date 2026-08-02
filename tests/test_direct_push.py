"""Direct transfer: the Mac pulls from you instead of via the relay.

The relay sustains ~0.5 MB/s end to end and parallel uploads only bought 1.4x,
so it is throughput-limited — chunking can't fix a big push. But the two
machines can usually reach each other, so serve the payload here and let the Mac
curl it. Measured 11x on the same payload (41MB source / 10.6MB gzipped).

It must degrade to the relay rather than fail: an optimisation that can break a
push is worse than a slow push.
"""

from __future__ import annotations

import os
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from herds.sdk import _direct


def test_candidate_hosts_are_plausible_addresses():
    hosts = _direct.candidate_hosts()
    for h in hosts:
        assert h.count(".") == 3, h
        assert not h.startswith("127."), "loopback is useless to another machine"


def test_serve_delivers_payload_at_the_token_path():
    with _direct.serve(b"hello-bytes") as (urls, served):
        assert urls
        url = urls[0].replace(urls[0].split("//")[1].split(":")[0], "127.0.0.1")
        assert urllib.request.urlopen(url, timeout=5).read() == b"hello-bytes"
        assert served.is_set()


def test_serve_refuses_any_other_path():
    """The token is the only thing guarding a one-shot exposure."""
    with _direct.serve(b"secret") as (urls, _):
        base = urls[0].rsplit("/", 1)[0].replace(
            urls[0].split("//")[1].split(":")[0], "127.0.0.1")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/wrong-token", timeout=5)
        assert e.value.code == 404


def test_server_stops_when_the_block_exits():
    with _direct.serve(b"x") as (urls, _):
        host_port = urls[0].split("//")[1].rsplit("/", 1)[0]
    port = int(host_port.split(":")[1])
    with pytest.raises(Exception):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/anything", timeout=2)


def test_pull_command_uses_the_stock_interpreter():
    cmd = _direct.pull_command("/tmp/d", ["http://a/1", "http://b/1"])
    assert cmd[0] == "/usr/bin/python3"   # 3.9 on a stock Mac
    assert cmd[3] == "/tmp/d"
    assert cmd[4:] == ["http://a/1", "http://b/1"]


def test_pull_script_tries_every_url_before_failing():
    assert "for u in urls" in _direct.PULL_SCRIPT
    assert "sys.exit(3)" in _direct.PULL_SCRIPT


def _run_pull(tar: bytes, dest: Path):
    """Execute the real pull script against a locally served archive."""
    import json
    import subprocess

    with _direct.serve(tar) as (urls, _):
        port = urls[0].split("//")[1].split(":")[1].split("/")[0]
        token = urls[0].rsplit("/", 1)[1]
        local = [f"http://127.0.0.1:{port}/{token}"]
        r = subprocess.run(_direct.pull_command(str(dest), local),
                           capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _tar(build) -> bytes:
    import io

    src = Path(tempfile.mkdtemp()).resolve() / "pkg"
    src.mkdir()
    build(src)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=1) as tf:
        for p in sorted(src.rglob("*")):
            tf.add(str(p), arcname=str(p.relative_to(src)), recursive=False)
    return buf.getvalue()


def test_pull_extracts_files_and_safe_symlinks():
    def build(src):
        (src / "bin").write_bytes(b"MACHO" * 100)
        os.symlink("bin", src / "current")

    dest = Path(tempfile.mkdtemp()).resolve() / "out"
    out = _run_pull(_tar(build), dest)
    assert out["members"] == 2
    assert (dest / "current").is_symlink()
    assert (dest / "current").resolve() == (dest / "bin").resolve()


def test_pull_refuses_absolute_and_traversing_symlinks():
    """Same containment rules as the daemon — not a looser second path."""
    def build(src):
        (src / "ok").write_text("fine")
        os.symlink("/etc/passwd", src / "abs")
        os.symlink("../../../../etc/hosts", src / "up")

    dest = Path(tempfile.mkdtemp()).resolve() / "out"
    out = _run_pull(_tar(build), dest)
    assert (dest / "ok").exists()
    assert not (dest / "abs").is_symlink()
    assert not (dest / "up").is_symlink()
    assert out["members"] == 1


# --- fallback behaviour ----------------------------------------------------- #

def test_push_falls_back_when_no_address_is_reachable(monkeypatch):
    from herds.sdk.mac import Mac

    monkeypatch.setattr(_direct, "candidate_hosts", lambda: [])
    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: setattr(self, "_client", None)
                        or setattr(self, "machine_id", "m"))
    called = {}

    class FakeVol:
        @staticmethod
        def from_name(n):
            class V:
                @staticmethod
                def put(*a, **k):
                    called["relay"] = True
                    return {"via": "relay"}
            return V

    import herds.sdk.volume as volmod

    monkeypatch.setattr(volmod, "Volume", FakeVol)
    src = Path(tempfile.mkdtemp())
    (src / "f.txt").write_text("x")
    assert Mac().push(str(src), "v")["via"] == "relay"
    assert called["relay"]


def test_push_falls_back_when_the_mac_cannot_reach_us(monkeypatch, tmp_path):
    """A blocked network must slow the push down, never break it."""
    from herds.sdk.mac import Mac

    monkeypatch.setattr(_direct, "candidate_hosts", lambda: ["10.0.0.1"])
    monkeypatch.setattr(Mac, "__init__", lambda self, *a, **k: setattr(self, "_client", None)
                        or setattr(self, "machine_id", "m"))

    class Failed:
        ok, exit_code, stdout, stderr = False, 3, "", "unreachable"

    monkeypatch.setattr(Mac, "run", lambda self, c, **k: Failed())
    (tmp_path / "f.txt").write_text("x")

    import herds.sdk.volume as volmod

    class FakeVol:
        @staticmethod
        def from_name(n):
            return type("V", (), {"put": staticmethod(lambda *a, **k: {"via": "relay"})})

    monkeypatch.setattr(volmod, "Volume", FakeVol)
    assert Mac().push(str(tmp_path), "v")["via"] == "relay"
