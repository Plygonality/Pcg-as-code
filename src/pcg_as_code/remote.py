"""Optional Unreal Python remote execution client.

This is not an MCP and not a wrap of the Unreal Python API. It sends a
pasteable apply/dump script to a running editor that already has
**Editor Preferences → Python → Enable Remote Execution** turned on.

If no editor answers, use ``pcg-as-code apply-script`` and paste the file.
"""

from __future__ import annotations

import json
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
PROTOCOL_MAGIC = "ue_py"

# Defaults match Unreal's Python Editor Script Plugin remote execution.
DEFAULT_MULTICAST_GROUP = "239.0.0.1"
DEFAULT_MULTICAST_PORT = 6766
DEFAULT_COMMAND_HOST = "127.0.0.1"
MODE_EXEC_FILE = "ExecuteFile"
MODE_EXEC_STATEMENT = "ExecuteStatement"
MODE_EVAL_STATEMENT = "EvaluateStatement"


class RemoteExecutionError(RuntimeError):
    """No running editor, or the remote command failed."""


@dataclass
class RemoteNode:
    node_id: str
    node_name: str = ""
    command_ip: str = DEFAULT_COMMAND_HOST
    command_port: int = 6776


@dataclass
class RemoteResult:
    success: bool
    result: Any = None
    output: str = ""
    command_id: str = ""

    def raise_for_status(self) -> None:
        if not self.success:
            raise RemoteExecutionError(self.output or "Remote command failed")


class RemoteExecution:
    """Discover a running Unreal Editor and run a Python command."""

    def __init__(
        self,
        *,
        multicast_group: str = DEFAULT_MULTICAST_GROUP,
        multicast_port: int = DEFAULT_MULTICAST_PORT,
        bind_address: str = "127.0.0.1",
        timeout: float = 2.0,
    ) -> None:
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.bind_address = bind_address
        self.timeout = timeout
        self._command_socket: socket.socket | None = None
        self._node: RemoteNode | None = None

    def discover(self, *, attempts: int = 8, pause: float = 0.15) -> list[RemoteNode]:
        """Ping the multicast group and collect editor pongs."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.bind_address, 0))
            sock.settimeout(self.timeout)
            ping = _encode(
                {
                    "version": PROTOCOL_VERSION,
                    "magic": PROTOCOL_MAGIC,
                    "type": "ping",
                    "source": str(uuid.uuid4()),
                }
            )
            found: dict[str, RemoteNode] = {}
            for _ in range(attempts):
                sock.sendto(ping, (self.multicast_group, self.multicast_port))
                deadline = time.time() + pause
                while time.time() < deadline:
                    try:
                        payload, _addr = sock.recvfrom(65535)
                    except TimeoutError:
                        break
                    node = _parse_pong(payload)
                    if node is not None:
                        found[node.node_id] = node
            return list(found.values())
        finally:
            sock.close()

    def connect(self, node: RemoteNode | None = None) -> RemoteNode:
        nodes = [node] if node is not None else self.discover()
        if not nodes:
            raise RemoteExecutionError(
                "No Unreal Editor answered remote execution. "
                "Enable Editor Preferences → Python → Enable Remote Execution, "
                "or paste the script from `pcg-as-code apply-script`."
            )
        chosen = nodes[0]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((chosen.command_ip, int(chosen.command_port)))
        self._command_socket = sock
        self._node = chosen
        _send_tcp(
            sock,
            {
                "version": PROTOCOL_VERSION,
                "magic": PROTOCOL_MAGIC,
                "type": "open_connection",
            },
        )
        return chosen

    def run(
        self,
        command: str,
        *,
        exec_mode: str = MODE_EXEC_FILE,
        unattended: bool = True,
    ) -> RemoteResult:
        if self._command_socket is None:
            self.connect()
        assert self._command_socket is not None
        command_id = str(uuid.uuid4())
        _send_tcp(
            self._command_socket,
            {
                "version": PROTOCOL_VERSION,
                "magic": PROTOCOL_MAGIC,
                "type": "command",
                "command": command,
                "unattended": unattended,
                "exec_mode": exec_mode,
                "command_id": command_id,
            },
        )
        reply = _recv_tcp(self._command_socket)
        success = bool(reply.get("success", False))
        return RemoteResult(
            success=success,
            result=reply.get("result"),
            output=str(reply.get("output") or reply.get("result") or ""),
            command_id=str(reply.get("command_id") or command_id),
        )

    def close(self) -> None:
        if self._command_socket is None:
            return
        try:
            _send_tcp(
                self._command_socket,
                {
                    "version": PROTOCOL_VERSION,
                    "magic": PROTOCOL_MAGIC,
                    "type": "close_connection",
                },
            )
        except OSError:
            pass
        try:
            self._command_socket.close()
        finally:
            self._command_socket = None
            self._node = None

    def __enter__(self) -> RemoteExecution:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def apply_remote(
    script: str,
    *,
    timeout: float = 5.0,
    exec_mode: str = MODE_EXEC_FILE,
) -> RemoteResult:
    """Send a self-contained Unreal Python script to a running editor."""
    remote = RemoteExecution(timeout=timeout)
    try:
        remote.connect()
        result = remote.run(script, exec_mode=exec_mode)
        result.raise_for_status()
        return result
    finally:
        remote.close()


def _encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


def _parse_pong(payload: bytes) -> RemoteNode | None:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if data.get("magic") != PROTOCOL_MAGIC:
        return None
    if data.get("type") not in ("pong", "advertisement"):
        return None
    node_id = data.get("node_id") or data.get("id")
    if not node_id:
        return None
    endpoint = data.get("command_endpoint") or {}
    if isinstance(endpoint, (list, tuple)) and len(endpoint) >= 2:
        host, port = endpoint[0], endpoint[1]
    else:
        host = data.get("command_ip") or DEFAULT_COMMAND_HOST
        port = data.get("command_port") or 6776
    return RemoteNode(
        node_id=str(node_id),
        node_name=str(data.get("node_name") or data.get("user") or ""),
        command_ip=str(host),
        command_port=int(port),
    )


def _send_tcp(sock: socket.socket, message: dict[str, Any]) -> None:
    body = _encode(message)
    header = f"{len(body):09d}".encode("ascii")
    sock.sendall(header + body)


def _recv_tcp(sock: socket.socket) -> dict[str, Any]:
    header = _recv_exact(sock, 9)
    size = int(header.decode("ascii"))
    body = _recv_exact(sock, size)
    return json.loads(body.decode("utf-8"))


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        piece = sock.recv(size - len(chunks))
        if not piece:
            raise RemoteExecutionError("Editor closed the remote-execution socket")
        chunks.extend(piece)
    return bytes(chunks)
