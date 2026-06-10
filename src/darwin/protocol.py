"""The wire protocol spoken across all three Darwin components.

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
    SANDBOX_CREATE = "sandbox_create"  # materialize a sandbox
    SANDBOX_EXEC = "sandbox_exec"      # run a command inside a sandbox
    SANDBOX_TERMINATE = "sandbox_terminate"
    CANCEL = "cancel"                  # cancel an in-flight request
    FS_LIST = "fs_list"                # list a directory (request → single result)
    FS_READ = "fs_read"                # read a file (request → single result)
    HTTP_REQUEST = "http_request"      # proxy an HTTP request to a sandbox port
    PING = "ping"

    # agent -> control-plane (results streamed back up the socket)
    REGISTERED = "registered"          # handshake ack with machine facts
    VOLUMES_REPORT = "volumes_report"  # periodic snapshot of on-disk volumes
    METRICS_REPORT = "metrics_report"  # periodic CPU/memory sample
    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT = "exit"                      # terminal frame for a request
    SANDBOX_READY = "sandbox_ready"
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
        },
    )


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
        },
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
