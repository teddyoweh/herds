"""Volume read/management API (get/listdir/remove) + job-logs ownership ACL.

The filesystem round-trip runs the REAL ``daemon.files`` helpers against a temp
HERDS_HOME (in-process, no sockets). The ownership check drives the REAL control
app via ``TestClient`` and asserts a non-owner token can't tail another job's
logs.
"""

import base64
import importlib
import io
import tarfile

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from herds.control import create_app
from herds.protocol import JobState, MachineStatus


@pytest.fixture()
def files_mod(tmp_path, monkeypatch):
    """Reload config against a temp HERDS_HOME so files.py writes into tmp."""
    monkeypatch.setenv("HERDS_HOME", str(tmp_path / "herds"))
    import herds.config as cfg

    importlib.reload(cfg)
    cfg.ensure_dirs()
    import herds.daemon.files as files

    importlib.reload(files)
    return files


def test_volume_put_get_listdir_remove_roundtrip(files_mod):
    files = files_mod
    vol = "data"

    # put (single file) → get round-trip.
    payload = b"hello \x00 world"  # includes a NUL so we exercise the binary path
    files.write_file("volume", vol, "sub/a.bin", base64.b64encode(payload).decode())

    got = files.get_file("volume", vol, "sub/a.bin")
    assert got["ok"] is True
    assert base64.b64decode(got["content_b64"]) == payload
    assert got["size"] == len(payload)

    # put (tarball) → get round-trip, the codebase-push path.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        info = tarfile.TarInfo("pkg/readme.txt")
        data = b"from a tar"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    files.extract_tar("volume", vol, "", base64.b64encode(buf.getvalue()).decode())
    assert base64.b64decode(files.get_file("volume", vol, "pkg/readme.txt")["content_b64"]) == b"from a tar"

    # listdir sees both trees at the root.
    names = {e["name"] for e in files.list_dir("volume", vol, "")["entries"]}
    assert {"sub", "pkg"} <= names
    sub = files.list_dir("volume", vol, "sub")["entries"]
    assert any(e["name"] == "a.bin" and not e["dir"] for e in sub)

    # remove a file, then a whole dir.
    assert files.remove("volume", vol, "sub/a.bin")["removed"] is True
    assert files.get_file("volume", vol, "sub/a.bin").get("error")  # gone
    assert files.remove("volume", vol, "pkg")["removed"] is True
    assert "pkg" not in {e["name"] for e in files.list_dir("volume", vol, "")["entries"]}


def test_volume_traversal_is_rejected(files_mod):
    files = files_mod
    files.write_file("volume", "data", "keep.txt", base64.b64encode(b"x").decode())

    with pytest.raises(PermissionError):
        files.get_file("volume", "data", "../../../etc/passwd")
    with pytest.raises(PermissionError):
        files.remove("volume", "data", "../../keep.txt")
    with pytest.raises(PermissionError):
        files.remove("volume", "data", "")  # refuse deleting the root itself


def test_job_logs_ownership_acl(monkeypatch):
    # Enforce auth so the ACL runs (module global read at call time).
    monkeypatch.setattr("herds.control.REQUIRE_AUTH", True)

    app = create_app(":memory:")
    store = app.state.store
    store.put_api_key("key_alice", "alice", "laptop", "run")
    store.put_api_key("key_bob", "bob", "laptop", "run")
    store.upsert_machine("mac_alice", "MBP", "alice", {}, MachineStatus.ONLINE, 1)
    store.create_job("job_alice", "mac_alice", "echo hi", 1)

    c = TestClient(app)

    # A valid token that does NOT own the job's machine is rejected.
    with pytest.raises(WebSocketDisconnect) as ei:
        with c.websocket_connect("/v1/jobs/job_alice/logs?token=key_bob"):
            pass
    assert ei.value.code == 4403

    # A bogus token is rejected up front.
    with pytest.raises(WebSocketDisconnect) as ei2:
        with c.websocket_connect("/v1/jobs/job_alice/logs?token=nope"):
            pass
    assert ei2.value.code == 4401

    # The owner is accepted (connection establishes; we disconnect immediately).
    with c.websocket_connect("/v1/jobs/job_alice/logs?token=key_alice") as ws:
        ws.close()
