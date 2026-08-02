"""Pushing large payloads: fewer bytes, working symlinks, fail-fast.

Measured on a real fleet before changing anything:

    control plane on the same machine   ~24 MB/s
    through the relay                    0.23-0.75 MB/s

Parallel uploads only bought 1.4x, so the relay is throughput-limited end to
end — the only lever left on this side is sending fewer bytes.

Two correctness bugs mattered more than the speed, both of which would have hit
a 572MB .app bundle at the *end* of a 40-minute upload: the archive exceeded the
daemon's 512MB cap, and symlinks were dropped, which produces a bundle macOS
will not launch.
"""

from __future__ import annotations

import base64
import os
import tarfile
import tempfile
from pathlib import Path

import pytest

from herds.daemon import files as F
from herds.sdk.volume import WRITE_CAP, _DEFAULT_IGNORE, _check_size, _tar_dir


def _app(root: Path) -> Path:
    """A miniature .app with the framework symlink layout macOS requires."""
    app = root / "Demo.app"
    fw = app / "Contents/Frameworks/Demo.framework"
    (fw / "Versions/A").mkdir(parents=True)
    (fw / "Versions/A/Demo").write_bytes(b"MACHO" * 2000)
    os.symlink("A", fw / "Versions/Current")
    os.symlink("Versions/Current/Demo", fw / "Demo")
    (app / "Contents/Info.plist").write_text("<plist/>")
    return app


def _extract(tar: bytes, dest: Path, monkeypatch) -> dict:
    monkeypatch.setattr(F, "_resolve", lambda kind, ident, rel: (dest, dest))
    return F.extract_tar("volume", "v", "", base64.b64encode(tar).decode())


# --- fewer bytes ------------------------------------------------------------ #

def test_archive_is_gzipped():
    src = Path(tempfile.mkdtemp()).resolve()
    (src / "f.txt").write_text("x" * 100_000)
    tar = _tar_dir(src, set(_DEFAULT_IGNORE))
    assert tar[:2] == b"\x1f\x8b", "archive is not gzip — the relay is the bottleneck"


def test_compression_actually_shrinks_repetitive_payloads():
    src = Path(tempfile.mkdtemp()).resolve()
    (src / "big.bin").write_bytes(b"MACHO" * 200_000)
    assert len(_tar_dir(src, set(_DEFAULT_IGNORE))) < 200_000


def test_gzipped_archive_is_still_readable_by_an_older_daemon():
    """The daemon opens with mode='r:*', which sniffs — so this is drop-in."""
    src = Path(tempfile.mkdtemp()).resolve()
    (src / "a.txt").write_text("hello")
    with tarfile.open(fileobj=__import__("io").BytesIO(_tar_dir(src, set())), mode="r:*") as tf:
        assert "a.txt" in tf.getnames()


# --- working symlinks ------------------------------------------------------- #

def test_app_bundle_symlinks_survive_the_round_trip(monkeypatch):
    """Dropping these produces a bundle that will not launch."""
    src = Path(tempfile.mkdtemp()).resolve()
    _app(src)
    dest = Path(tempfile.mkdtemp()).resolve() / "out"
    _extract(_tar_dir(src / "Demo.app", set(_DEFAULT_IGNORE)), dest, monkeypatch)

    fw = dest / "Contents/Frameworks/Demo.framework"
    assert (fw / "Versions/Current").is_symlink()
    assert (fw / "Demo").is_symlink()
    assert (fw / "Demo").resolve().exists(), "framework binary is unreachable"
    assert (dest / "Contents/Info.plist").read_text() == "<plist/>"


def test_absolute_symlinks_are_refused(monkeypatch):
    src = Path(tempfile.mkdtemp()).resolve() / "pkg"
    src.mkdir()
    os.symlink("/etc/passwd", src / "escape")
    dest = Path(tempfile.mkdtemp()).resolve() / "out"
    _extract(_tar_dir(src, set(_DEFAULT_IGNORE)), dest, monkeypatch)
    assert not (dest / "escape").is_symlink()


def test_traversing_symlinks_are_refused(monkeypatch):
    src = Path(tempfile.mkdtemp()).resolve() / "pkg"
    src.mkdir()
    os.symlink("../../../../../../etc/hosts", src / "up")
    dest = Path(tempfile.mkdtemp()).resolve() / "out"
    _extract(_tar_dir(src, set(_DEFAULT_IGNORE)), dest, monkeypatch)
    assert not (dest / "up").is_symlink()


@pytest.mark.parametrize("linkname,ok", [
    ("A", True), ("Versions/Current/Demo", True), ("./x", True),
    ("/etc/passwd", False), ("../../../etc/hosts", False), ("", False),
])
def test_link_containment_rule(tmp_path, linkname, ok):
    dest = tmp_path.resolve()
    (dest / "sub").mkdir()
    assert F._link_stays_inside(dest, dest / "sub" / "link", linkname) is ok


# --- fail fast -------------------------------------------------------------- #

def test_oversize_payload_fails_immediately_with_guidance():
    """Failing after a 40-minute upload is the worst possible outcome."""
    from herds.sdk.client import HerdsError

    with pytest.raises(HerdsError) as e:
        _check_size(b"x" * (WRITE_CAP + 1), Path("Wispr.app"))
    msg = str(e.value)
    assert "over the 512 MB upload limit" in msg
    assert "mac.fetch" in msg, "the error must point at the fast path"
    assert "minutes" in msg


def test_within_cap_passes():
    _check_size(b"x" * 1024, Path("small.txt"))


def test_cap_matches_the_daemons():
    assert WRITE_CAP == F._WRITE_CAP, "SDK and daemon limits drifted apart"
