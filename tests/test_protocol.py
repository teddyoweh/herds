from darwin.protocol import (
    Frame,
    FrameType,
    ExecRequest,
    exec_frame,
    exit_frame,
    stdout_frame,
)


def test_frame_roundtrip():
    f = stdout_frame("req_1", 3, "hello\n")
    raw = f.dump()
    back = Frame.load(raw)
    assert back.type == FrameType.STDOUT
    assert back.request_id == "req_1"
    assert back.seq == 3
    assert back.data["text"] == "hello\n"


def test_exec_frame_carries_fields():
    f = exec_frame("req_2", "echo hi", image="xcode:26", timeout=30, sandbox_id="sbx_1")
    assert f.type == FrameType.EXEC
    assert f.data["command"] == "echo hi"
    assert f.data["image"] == "xcode:26"
    assert f.data["timeout"] == 30
    assert f.data["sandbox_id"] == "sbx_1"


def test_exit_frame():
    f = exit_frame("req_3", 0, 1234)
    assert f.data["exit_code"] == 0
    assert f.data["duration_ms"] == 1234


def test_exec_request_defaults():
    r = ExecRequest(command="ls")
    assert r.network is True
    assert r.volumes == {}
    assert r.sandbox_id is None
