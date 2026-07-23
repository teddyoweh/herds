"""The wire protocol spoken across all three Herds components.

The SDK talks REST to the control plane to *start* work and WebSocket to
*stream* logs back. The Mac daemon ("agent") holds a single persistent
WebSocket to the control plane and receives pushed commands down it. Every
frame carries a ``request_id`` so concurrent commands can share one socket.

Keeping every message shape in one module means the control plane, the daemon,
and the SDK can never silently drift out of sync.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class FrameType(str, Enum):
    """Discriminator for every message on the agent <-> control-plane socket."""

    # control-plane -> agent (commands pushed down the socket)
    EXEC = "exec"                      # run a one-shot command
    SESSION_START = "session_start"    # start a RESIDENT process fed many stdin turns
    STDIN = "stdin"                    # write a chunk to a resident process's stdin
    KEEPALIVE = "keepalive"            # mark a resident session active (spare it from the idle reaper)
    SANDBOX_CREATE = "sandbox_create"  # materialize a sandbox
    SANDBOX_EXEC = "sandbox_exec"      # run a command inside a sandbox
    SANDBOX_TERMINATE = "sandbox_terminate"
    SNAPSHOT = "snapshot"              # tar a sandbox's fs into a named base image
    CANCEL = "cancel"                  # cancel an in-flight request
    FS_LIST = "fs_list"                # list a directory (request → single result)
    FS_READ = "fs_read"                # read a file preview (request → single result)
    FS_GET = "fs_get"                  # read a whole file out as base64 (request → single result)
    FS_WRITE = "fs_write"              # write a file / extract a tar into a volume or sandbox
    FS_REMOVE = "fs_remove"            # delete a file or directory from a volume or sandbox
    HTTP_REQUEST = "http_request"      # proxy an HTTP request to a sandbox port
    # WebSocket tunnelling over the relay control channel (multiplexed by stream_id):
    WS_OPEN = "ws_open"                # relay -> host: open a local WS at {path, query}
    WS_DATA = "ws_data"                # both ways: a text message on {stream_id}
    WS_CLOSE = "ws_close"              # both ways: close {stream_id}
    # RAW bidirectional TCP tunnel (multiplexed by stream_id). Unlike WS_* these
    # carry opaque bytes (base64 in ``data_b64``), so CDP / websockets / a
    # screencast — anything that can't survive buffered HTTP request/response —
    # flows unmodified to a sandbox-local TCP port.
    TUNNEL_OPEN = "tunnel_open"        # control -> agent: dial 127.0.0.1:{port} for {stream_id}
    TUNNEL_DATA = "tunnel_data"        # both ways: a chunk of raw bytes on {stream_id}
    TUNNEL_CLOSE = "tunnel_close"      # both ways: close {stream_id} (carries {error} on dial fail)
    PING = "ping"

    # agent -> control-plane (results streamed back up the socket)
    REGISTERED = "registered"          # handshake ack with machine facts
    TUNNEL_READY = "tunnel_ready"      # agent -> control: raw tunnel {stream_id} dialed OK
    SESSION_READY = "session_ready"    # agent -> control: a resident session's process is live
    VOLUMES_REPORT = "volumes_report"  # periodic snapshot of on-disk volumes
    METRICS_REPORT = "metrics_report"  # periodic CPU/memory sample
    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT = "exit"                      # terminal frame for a request
    SANDBOX_READY = "sandbox_ready"
    SNAPSHOT_RESULT = "snapshot_result"  # response to SNAPSHOT
    FS_RESULT = "fs_result"            # response to FS_LIST / FS_READ
    HTTP_RESPONSE = "http_response"    # response to HTTP_REQUEST
    ERROR = "error"
    PONG = "pong"


class JobState(str, Enum):
    QUEUED = "queued"        # accepted by control plane, not yet on a machine
    DISPATCHED = "dispatched"  # pushed to the agent socket
    RUNNING = "running"      # agent reported first output / start
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    LOST = "lost"            # machine went away mid-flight


class MachineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


# --------------------------------------------------------------------------- #
# Machine facts (sent during the agent handshake)
# --------------------------------------------------------------------------- #


class MachineInfo(BaseModel):
    """Hardware/OS facts the agent reports so the SDK can show a nice card."""

    machine_id: str
    name: str                       # e.g. "MacBook Pro"
    model: Optional[str] = None     # e.g. "Mac15,3"
    device_type: Optional[str] = None  # machine-readable form factor: macbook_pro|macbook_air|mac_mini|mac_studio|imac|mac_pro
    chip: Optional[str] = None      # e.g. "Apple M4"
    arch: str = "arm64"
    cpu_count: Optional[int] = None
    memory_gb: Optional[int] = None
    macos_version: Optional[str] = None  # e.g. "26.2"
    agent_version: str = "0.1.0"


# --------------------------------------------------------------------------- #
# Frames
# --------------------------------------------------------------------------- #


class Frame(BaseModel):
    """Base envelope. ``type`` discriminates; ``request_id`` correlates.

    ``request_id`` is absent only for connection-level frames (ping/pong,
    registered). ``seq`` orders output chunks within a single request so the
    client can detect drops.
    """

    type: FrameType
    request_id: Optional[str] = None
    seq: Optional[int] = None
    data: dict[str, Any] = Field(default_factory=dict)

    def dump(self) -> str:
        return self.model_dump_json(exclude_none=True)

    @classmethod
    def load(cls, raw: str | bytes) -> "Frame":
        return cls.model_validate_json(raw)


# Convenience constructors -- thin wrappers so call sites read clearly. ------ #


def exec_frame(
    request_id: str,
    command: list[str] | str,
    *,
    image: Optional[str] = None,
    volumes: Optional[dict[str, str]] = None,
    workdir: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
    network: bool = True,
    sandbox_id: Optional[str] = None,
    inherit_home: bool = False,
    keep_alive: bool = False,
    setup_commands: Optional[list[str]] = None,
    base: Optional[str] = None,
) -> Frame:
    return Frame(
        type=FrameType.EXEC,
        request_id=request_id,
        data={
            "command": command,
            "image": image,
            "volumes": volumes or {},
            "workdir": workdir,
            "env": env or {},
            "timeout": timeout,
            "network": network,
            "sandbox_id": sandbox_id,
            "inherit_home": inherit_home,
            "keep_alive": keep_alive,
            "setup_commands": list(setup_commands or []),
            "base": base,
        },
    )


def session_start_frame(
    request_id: str,
    command: list[str] | str,
    *,
    image: Optional[str] = None,
    volumes: Optional[dict[str, str]] = None,
    workdir: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    network: bool = True,
    sandbox_id: Optional[str] = None,
    inherit_home: bool = False,
    setup_commands: Optional[list[str]] = None,
    base: Optional[str] = None,
) -> Frame:
    """Start a resident process the backend feeds many stdin turns into.

    Mirrors :func:`exec_frame` but marks the process as a long-lived session:
    the daemon launches it with ``stdin=PIPE``, keeps it alive, and streams its
    stdout/stderr under ``request_id`` (which doubles as the session id) until it
    exits or is cancelled. Feed it with :func:`stdin_frame`.
    """
    return Frame(
        type=FrameType.SESSION_START,
        request_id=request_id,
        data={
            "command": command,
            "image": image,
            "volumes": volumes or {},
            "workdir": workdir,
            "env": env or {},
            "network": network,
            "sandbox_id": sandbox_id,
            "inherit_home": inherit_home,
            "setup_commands": list(setup_commands or []),
            "base": base,
        },
    )


def stdin_frame(request_id: str, data: str = "", *, eof: bool = False) -> Frame:
    """Deliver a chunk of stdin to a resident session (by ``request_id``).

    ``eof=True`` closes the session's stdin (EOF), which typically lets the
    resident process finish and exit. An empty ``data`` with ``eof=True`` is a
    pure close.
    """
    return Frame(
        type=FrameType.STDIN,
        request_id=request_id,
        data={"data": data, "eof": eof},
    )


def keepalive_frame(request_id: str) -> Frame:
    """Mark a resident session active so the idle reaper spares it — used to hold
    a session alive during work with no stdin/stdout (e.g. a driver parked
    awaiting a user's AskUserQuestion answer)."""
    return Frame(type=FrameType.KEEPALIVE, request_id=request_id, data={})


def sandbox_create_frame(
    request_id: str,
    sandbox_id: str,
    *,
    image: Optional[str] = None,
    volumes: Optional[dict[str, str]] = None,
    command: Optional[list[str] | str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
    network: bool = True,
    setup_commands: Optional[list[str]] = None,
    base: Optional[str] = None,
) -> Frame:
    return Frame(
        type=FrameType.SANDBOX_CREATE,
        request_id=request_id,
        data={
            "sandbox_id": sandbox_id,
            "image": image,
            "volumes": volumes or {},
            "command": command,
            "env": env or {},
            "timeout": timeout,
            "network": network,
            "setup_commands": list(setup_commands or []),
            "base": base,
        },
    )


def snapshot_frame(request_id: str, sandbox_id: str, base: str) -> Frame:
    """control -> agent: tar a sandbox's workspace+home into a named ``base``
    image under the herds home. The agent replies with a ``SNAPSHOT_RESULT``
    frame carrying ``{base, image_id, size_bytes, path}`` (or ``{error}``).

    This is the Herds analog of Modal's ``Sandbox.snapshot_filesystem()``:
    the produced ``image_id`` can seed a fresh sandbox via ``base=`` on exec
    (``Image.from_id(image_id)`` on the SDK side)."""
    return Frame(
        type=FrameType.SNAPSHOT,
        request_id=request_id,
        data={"sandbox_id": sandbox_id, "base": base},
    )


def sandbox_exec_frame(
    request_id: str,
    sandbox_id: str,
    command: list[str] | str,
    *,
    workdir: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
) -> Frame:
    return Frame(
        type=FrameType.SANDBOX_EXEC,
        request_id=request_id,
        data={
            "sandbox_id": sandbox_id,
            "command": command,
            "workdir": workdir,
            "env": env or {},
            "timeout": timeout,
        },
    )


def tunnel_open_frame(stream_id: str, port: int, *, host: str = "127.0.0.1") -> Frame:
    """control -> agent: open a raw TCP tunnel to ``host:port`` on the Mac,
    identified by ``stream_id``. The agent dials the port and pumps bytes both
    ways as :func:`tunnel_data_frame`, replying :func:`tunnel_ready_frame` once
    connected or :func:`tunnel_close_frame` (with ``error``) if the dial fails."""
    return Frame(
        type=FrameType.TUNNEL_OPEN,
        data={"stream_id": stream_id, "port": int(port), "host": host},
    )


def tunnel_ready_frame(stream_id: str) -> Frame:
    """agent -> control: the raw tunnel ``stream_id`` connected successfully."""
    return Frame(type=FrameType.TUNNEL_READY, data={"stream_id": stream_id})


def session_ready_frame(request_id: str) -> Frame:
    """agent -> control: a resident session's process is launched and live.

    Lets the control plane block ``POST /v1/machines/{id}/sessions`` until the
    process actually exists — so the returned handle is immediately usable and an
    early ``stdin`` write can't race ahead of the process (Modal's ``create``
    contract: the sandbox is running by the time you hold its handle)."""
    return Frame(type=FrameType.SESSION_READY, request_id=request_id, data={})


def tunnel_data_frame(stream_id: str, payload: bytes) -> Frame:
    """Both ways: a chunk of raw bytes on ``stream_id`` (base64 on the wire)."""
    import base64

    return Frame(
        type=FrameType.TUNNEL_DATA,
        data={"stream_id": stream_id, "data_b64": base64.b64encode(bytes(payload)).decode()},
    )


def tunnel_close_frame(stream_id: str, *, error: Optional[str] = None) -> Frame:
    """Both ways: close ``stream_id``. ``error`` is set only when the agent could
    not dial the port (so the initiating side can surface a clear failure)."""
    data: dict[str, Any] = {"stream_id": stream_id}
    if error:
        data["error"] = error
    return Frame(type=FrameType.TUNNEL_CLOSE, data=data)


def stdout_frame(request_id: str, seq: int, text: str) -> Frame:
    return Frame(type=FrameType.STDOUT, request_id=request_id, seq=seq, data={"text": text})


def stderr_frame(request_id: str, seq: int, text: str) -> Frame:
    return Frame(type=FrameType.STDERR, request_id=request_id, seq=seq, data={"text": text})


def exit_frame(request_id: str, exit_code: int, duration_ms: int) -> Frame:
    return Frame(
        type=FrameType.EXIT,
        request_id=request_id,
        data={"exit_code": exit_code, "duration_ms": duration_ms},
    )


def error_frame(request_id: Optional[str], message: str) -> Frame:
    return Frame(type=FrameType.ERROR, request_id=request_id, data={"message": message})


# --------------------------------------------------------------------------- #
# REST request/response models (SDK <-> control plane)
# --------------------------------------------------------------------------- #


class ExecRequest(BaseModel):
    command: list[str] | str
    image: Optional[str] = None
    volumes: dict[str, str] = Field(default_factory=dict)   # mount_path -> volume name
    workdir: Optional[str] = None
    env: dict[str, str] = Field(default_factory=dict)
    timeout: Optional[int] = None
    network: bool = True
    sandbox_id: Optional[str] = None   # reuse a persistent sandbox workspace
    secrets: list[str] = Field(default_factory=list)  # secret names to inject as env
    inherit_home: bool = False         # run with the user's real HOME (tools, logins)
    keep_alive: bool = False           # supervise: respawn the process if it exits
    app: Optional[str] = None          # group this run under a named App
    setup_commands: list[str] = Field(default_factory=list)  # image provisioning steps
    base: Optional[str] = None         # restore a snapshot base image into a new sandbox


class ExecAccepted(BaseModel):
    request_id: str
    machine_id: str
    state: JobState = JobState.QUEUED


class ExecResult(BaseModel):
    request_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    state: JobState


class MachineSummary(BaseModel):
    machine_id: str
    name: str
    status: MachineStatus
    info: Optional[MachineInfo] = None
    last_seen_ms: Optional[int] = None
