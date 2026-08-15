"""Direct transfer, both directions, exercised for real on this machine.

SERVE_SCRIPT is what runs on the far Mac. These tests run it exactly the way
`run()` would — as a /usr/bin/python3 subprocess — so what passes here is the
literal artifact that ships, not a re-implementation of it. The network in the
middle is this machine's loopback, which is the same code path as a LAN.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from herds.cli import app
from herds.sdk import _direct

runner = CliRunner()


@pytest.fixture
def payload_dir(tmp_path):
    src = tmp_path / "bundle"
    (src / "nested").mkdir(parents=True)
    (src / "a.txt").write_text("alpha")
    (src / "nested" / "b.bin").write_bytes(b"\x00\x01\x02" * 1000)
    return src


def _serve(path: Path, ttl: int = 30) -> dict:
    """Launch SERVE_SCRIPT the way the far Mac would, return its offer."""
    out = subprocess.run(
        [sys.executable, "-c", _direct.SERVE_SCRIPT, str(path), str(ttl)],
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    line = [l for l in out.stdout.splitlines() if l.startswith("{")][-1]
    return json.loads(line)


def test_serve_script_offers_and_serves(payload_dir, tmp_path):
    offer = _serve(payload_dir)
    assert offer["urls"] and offer["bytes"] > 0

    # The launcher has EXITED (returncode 0 above) while the server lives on —
    # that is the detach that keeps run() from blocking for the TTL.
    raw = _direct.download(offer["urls"], timeout=10)
    assert len(raw) == offer["bytes"]

    dest = tmp_path / "out"
    n = _direct.extract(raw, str(dest))
    assert n >= 3
    assert (dest / "bundle" / "a.txt").read_text() == "alpha"
    assert (dest / "bundle" / "nested" / "b.bin").read_bytes() == b"\x00\x01\x02" * 1000


def test_serve_is_one_shot(payload_dir):
    offer = _serve(payload_dir)
    _direct.download(offer["urls"], timeout=10)
    # The first complete download closes the doors (grace ~1s).
    time.sleep(2.5)
    with pytest.raises(OSError):
        _direct.download(offer["urls"], timeout=5)


def test_serve_refuses_a_wrong_token(payload_dir):
    offer = _serve(payload_dir)
    url = offer["urls"][0]
    wrong = url.rsplit("/", 1)[0] + "/not-the-token"
    with pytest.raises(OSError):
        _direct.download([wrong], timeout=5)
    # ...and the real token still works: a guess must not burn the payload.
    assert len(_direct.download(offer["urls"], timeout=10)) == offer["bytes"]


def test_download_skips_dead_addresses(payload_dir):
    offer = _serve(payload_dir)
    # A dead candidate first — the LAN address that isn't routable — must cost
    # seconds, not the transfer.
    urls = ["http://192.0.2.1:9/never"] + offer["urls"]
    raw = _direct.download(urls, timeout=8)
    assert len(raw) == offer["bytes"]


def test_extract_refuses_traversal(tmp_path):
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo("../escape.txt")
        data = b"out"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    dest = tmp_path / "safe"
    n = _direct.extract(buf.getvalue(), str(dest))
    assert n == 0
    assert not (tmp_path / "escape.txt").exists()


# ── the CLI spec parser ─────────────────────────────────────────────────────

def test_cp_spec_rules():
    from herds.cli import _cp_spec

    assert _cp_spec("mini:~/x") == ("mini", "~/x")
    assert _cp_spec("mini:") == ("mini", ".")
    assert _cp_spec("./file:with:colons") == (None, "./file:with:colons")
    assert _cp_spec("/abs/path") == (None, "/abs/path")
    assert _cp_spec("studio:relative/dir") == ("studio", "relative/dir")


def test_cp_both_local_is_refused():
    result = runner.invoke(app, ["cp", "./a", "./b"])
    assert result.exit_code == 2
    assert "local" in result.output


# ── the orchestration, with the "Mac" as a local subprocess ─────────────────
#
# A Mac in these tests is this machine: run() executes the argv locally. That
# makes pull/send/_push_to_path run their REAL direct paths — real serve, real
# HTTP, real extract — with loopback standing in for the LAN.

class _LocalResult:
    def __init__(self, p):
        self.ok = p.returncode == 0
        self.exit_code = p.returncode
        self.stdout = p.stdout
        self.stderr = p.stderr


class _LocalMac:
    machine_id = "local-test"
    _client = None

    def __init__(self):
        # Borrow the REAL orchestration off Mac — plain functions in Python —
        # so pull/send here run the shipped code, only run() is local.
        from herds.sdk.mac import Mac

        self._serve_from = Mac._serve_from.__get__(self)
        self.pull = Mac.pull.__get__(self)
        self.send = Mac.send.__get__(self)

    def run(self, command, **kw):
        if isinstance(command, list):
            p = subprocess.run(command, capture_output=True, text=True, timeout=60)
        else:
            p = subprocess.run(["/bin/sh", "-c", command], capture_output=True,
                               text=True, timeout=60)
        return _LocalResult(p)


def test_pull_direct_end_to_end(payload_dir, tmp_path):
    from herds.sdk.mac import Mac

    mac = _LocalMac()
    out = mac.pull(str(payload_dir), str(tmp_path / "pulled"))
    assert out["via"] == "direct", out
    assert out["bytes"] > 0
    assert (tmp_path / "pulled" / "bundle" / "a.txt").read_text() == "alpha"


def test_push_to_path_direct_end_to_end(payload_dir, tmp_path):
    from herds.sdk.mac import _push_to_path

    out = _push_to_path(_LocalMac(), str(payload_dir), str(tmp_path / "landed"))
    assert out["via"] == "direct", out
    assert (tmp_path / "landed" / "bundle" / "a.txt").read_text() == "alpha"


def test_send_mac_to_mac_direct(payload_dir, tmp_path):
    from herds.sdk.mac import Mac

    src_mac, dst_mac = _LocalMac(), _LocalMac()
    out = src_mac.send(str(payload_dir), dst_mac, str(tmp_path / "arrived"))
    assert out["via"] == "direct", out
    assert (tmp_path / "arrived" / "bundle" / "a.txt").read_text() == "alpha"
