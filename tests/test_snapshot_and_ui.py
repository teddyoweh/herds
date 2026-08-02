"""Copy-on-write snapshots, and UI control that works from a daemon.

Two structural fixes:

1. Snapshots tarred the sandbox, which is O(size) in both time and disk. APFS
   ``clonefile(2)`` shares blocks instead: measured 187x faster on 150MB, and
   zero new blocks. That is the difference between snapshotting a toy workspace
   and snapshotting a real home directory.

2. UI control was built on AppleScript/System Events, which needs an Automation
   TCC grant. A launchd daemon can't be shown a consent prompt, so those calls
   *block until timeout* instead of failing (measured: plain osascript 72ms,
   the same call wrapped in `tell application "System Events"` hangs). Mouse and
   accessibility now go through CGEvent and the AX C API via ctypes — gated on
   Accessibility only, no AppleEvents.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from herds.daemon import executor as ex
from herds.sdk import _input

macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


# --- snapshots -------------------------------------------------------------- #

def _sandbox(payload: bytes = b"x" * 4096) -> Path:
    root = Path(tempfile.mkdtemp()) / "sbx"
    (root / "workspace").mkdir(parents=True)
    (root / "home").mkdir()
    (root / "workspace" / "data.bin").write_bytes(payload)
    (root / "home" / "note.txt").write_text("hello")
    return root


@macos_only
def test_snapshot_uses_clone_on_apfs(tmp_path, monkeypatch):
    monkeypatch.setattr(ex.config, "IMAGES_DIR", tmp_path)
    meta = ex.snapshot_to_base(_sandbox(), "b1")
    assert meta["mode"] == "clone", "APFS should snapshot by cloning, not tarring"


@macos_only
def test_snapshot_roundtrip_preserves_content(tmp_path, monkeypatch):
    monkeypatch.setattr(ex.config, "IMAGES_DIR", tmp_path)
    ex.snapshot_to_base(_sandbox(b"payload-42" * 100), "b2")

    dst = Path(tempfile.mkdtemp()) / "restored"
    assert ex.restore_from_base(dst, "b2") is True
    assert (dst / "home" / "note.txt").read_text() == "hello"
    assert (dst / "workspace" / "data.bin").read_bytes() == b"payload-42" * 100


def test_restore_missing_base_is_false(tmp_path, monkeypatch):
    monkeypatch.setattr(ex.config, "IMAGES_DIR", tmp_path)
    assert ex.restore_from_base(Path(tempfile.mkdtemp()), "nope") is False


@macos_only
def test_snapshot_is_idempotent_by_name(tmp_path, monkeypatch):
    """Re-snapshotting a name replaces it rather than accumulating."""
    monkeypatch.setattr(ex.config, "IMAGES_DIR", tmp_path)
    root = _sandbox()
    ex.snapshot_to_base(root, "b3")
    (root / "home" / "note.txt").write_text("second")
    ex.snapshot_to_base(root, "b3")

    dst = Path(tempfile.mkdtemp()) / "r"
    ex.restore_from_base(dst, "b3")
    assert (dst / "home" / "note.txt").read_text() == "second"


@macos_only
def test_tar_fallback_still_restores(tmp_path, monkeypatch):
    """Non-APFS volumes must keep working."""
    monkeypatch.setattr(ex.config, "IMAGES_DIR", tmp_path)
    monkeypatch.setattr(ex, "_clonefile", lambda src, dst: False)

    meta = ex.snapshot_to_base(_sandbox(), "b4")
    assert meta["mode"] == "tar"

    dst = Path(tempfile.mkdtemp()) / "r"
    assert ex.restore_from_base(dst, "b4") is True
    assert (dst / "home" / "note.txt").read_text() == "hello"


# --- UI control ------------------------------------------------------------- #

def test_input_payloads_avoid_appleevents():
    """The whole point: no `tell application` on any control path."""
    for script in (_input.SCRIPT, _input.AX_SCRIPT):
        assert "tell application" not in script, "an AppleEvent here would hang a daemon"

    # The doctor is the one exception: it deliberately *sends* an AppleEvent to
    # detect a missing Automation grant. It must stay bounded, since the failure
    # mode being probed for is a hang rather than an error.
    assert "tell application" in _input.DOCTOR_SCRIPT
    assert "timeout=5" in _input.DOCTOR_SCRIPT

    # ...and they must run on the stock system interpreter, which is 3.9.
    for cmd in (_input.command("cursor"), _input.ax_command("trusted"),
                _input.doctor_command()):
        assert cmd[0] == "/usr/bin/python3"


@macos_only
def test_mouse_payload_reports_geometry():
    """Read-only ops must work without moving anything."""
    r = subprocess.run(_input.command("screen"), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    w, h = (int(v) for v in r.stdout.split())
    assert w > 0 and h > 0

    r = subprocess.run(_input.command("cursor"), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert len(r.stdout.split()) == 2


def test_mouse_payload_rejects_unknown_op():
    r = subprocess.run(_input.command("frobnicate"), capture_output=True, text=True, timeout=30)
    assert r.returncode == 2


@macos_only
def test_ax_payload_reports_trust_without_hanging():
    """AXIsProcessTrusted is the per-process truth doctor must report."""
    r = subprocess.run(_input.ax_command("trusted"), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert r.stdout.strip() in ("0", "1")


@macos_only
def test_doctor_payload_returns_json_with_trust_and_binary():
    import json

    r = subprocess.run(_input.doctor_command(), capture_output=True, text=True, timeout=90)
    assert r.returncode == 0
    d = json.loads(r.stdout.strip().splitlines()[-1])
    for key in ("accessibility", "screen_recording", "full_disk_access",
                "gui_session", "automation", "responsible_binary"):
        assert key in d
    assert isinstance(d["accessibility"], bool)
    assert os.path.isabs(d["responsible_binary"])


def test_element_click_targets_its_centre():
    """Semantic targeting: an element clicks its own centre, not a guessed pixel."""
    from herds.sdk.mac import Element

    clicks = []

    class FakeUI:
        def click(self, x, y, **kw):
            clicks.append((x, y))

    Element(FakeUI(), "App", "AXButton", "Save", 100, 200, 60, 40).click()
    assert clicks == [(130, 220)]


# --- sandbox is credential-blind ------------------------------------------- #

@macos_only
def test_sandbox_cannot_read_credentials(tmp_path):
    """A sandbox that can read ~/.ssh and reach the network isn't isolation.

    Reads stay broadly open because toolchains live everywhere, but credential
    stores are denied — otherwise "sandboxed" only means "can't corrupt".
    """
    class S:
        root = tmp_path
    prof = ex._seatbelt_profile(S(), [], network=True)
    home = os.path.expanduser("~")

    def readable(path: str) -> bool:
        r = subprocess.run(
            ["sandbox-exec", "-p", prof, "/bin/sh", "-c", f"cat {path} >/dev/null 2>&1"],
            capture_output=True,
        )
        return r.returncode == 0

    assert not readable(f"{home}/.ssh/*"), "sandbox could read SSH private keys"
    assert not readable(f"{home}/.aws/credentials")
    assert readable("/usr/bin/git"), "toolchain reads must keep working"
    assert readable("/etc/hosts")


def test_mounted_volume_overrides_a_secret_deny(tmp_path, monkeypatch):
    """An explicitly mounted volume wins — the user asked for that path."""
    monkeypatch.setattr(ex.Path, "home", staticmethod(lambda: tmp_path))
    vol = tmp_path / ".ssh"
    prof = ex._seatbelt_profile(type("S", (), {"root": tmp_path})(), [vol], network=False)
    assert f'(subpath "{vol}")' not in prof.split("(deny file-read*")[1].split(")")[0] + ")"


def test_inherit_home_skips_the_profile_entirely():
    """--real is the documented opt-out; it must not be silently fenced."""
    src = (Path(ex.__file__)).read_text()
    assert "no Seatbelt write-fence" in src


# --- keyboard is CGEvent, not AppleScript ---------------------------------- #

def test_keyboard_ops_exist_in_the_payload():
    for op in ("type", "press"):
        assert f'op == "{op}"' in _input.SCRIPT
    assert "CGEventCreateKeyboardEvent" in _input.SCRIPT
    assert "CGEventKeyboardSetUnicodeString" in _input.SCRIPT, "typing must be layout-independent"


@macos_only
def test_press_rejects_unknown_key_instead_of_guessing():
    r = subprocess.run(_input.command("press", "nosuchkey"), capture_output=True, text=True, timeout=30)
    assert r.returncode != 0
    assert "unknown key" in r.stderr


def test_window_ops_exist():
    for op in ("move", "resize", "raise", "press_element"):
        assert f'op == "{op}"' in _input.AX_SCRIPT
