from __future__ import annotations

import json
import socket
import threading

from pcg_as_code.remote import MODE_EXEC_FILE, RemoteExecution, RemoteNode, apply_remote


def test_discover_parses_pong(monkeypatch) -> None:
    pong = json.dumps(
        {
            "version": 1,
            "magic": "ue_py",
            "type": "pong",
            "node_id": "editor-1",
            "node_name": "TestProject",
            "command_ip": "127.0.0.1",
            "command_port": 6776,
        }
    ).encode("utf-8")

    class FakeSock:
        def __init__(self, *args, **kwargs) -> None:
            self._sent = False

        def setsockopt(self, *args, **kwargs) -> None:
            return None

        def bind(self, *args, **kwargs) -> None:
            return None

        def settimeout(self, *args, **kwargs) -> None:
            return None

        def sendto(self, payload, addr) -> int:
            self._sent = True
            return len(payload)

        def recvfrom(self, size: int):
            if self._sent:
                self._sent = False
                return pong, ("127.0.0.1", 6766)
            raise TimeoutError

        def close(self) -> None:
            return None

    monkeypatch.setattr("pcg_as_code.remote.socket.socket", lambda *a, **k: FakeSock())
    nodes = RemoteExecution(timeout=0.05).discover(attempts=1, pause=0.01)
    assert len(nodes) == 1
    assert nodes[0].node_id == "editor-1"
    assert nodes[0].command_port == 6776


def test_apply_remote_roundtrip() -> None:
    received: dict[str, object] = {}

    def server() -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        received["port"] = listener.getsockname()[1]
        listener.listen(1)
        received["ready"].set()
        conn, _addr = listener.accept()
        try:
            while True:
                header = conn.recv(9)
                if not header:
                    break
                size = int(header.decode("ascii"))
                body = b""
                while len(body) < size:
                    body += conn.recv(size - len(body))
                message = json.loads(body.decode("utf-8"))
                received.setdefault("messages", []).append(message)
                if message.get("type") == "command":
                    reply = {
                        "success": True,
                        "result": "applied",
                        "output": "ok",
                        "command_id": message.get("command_id"),
                    }
                    encoded = json.dumps(reply).encode("utf-8")
                    conn.sendall(f"{len(encoded):09d}".encode("ascii") + encoded)
                if message.get("type") == "close_connection":
                    break
        finally:
            conn.close()
            listener.close()

    received["ready"] = threading.Event()
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert received["ready"].wait(1.0)

    remote = RemoteExecution(timeout=1.0)
    remote.connect(
        RemoteNode(node_id="local", command_ip="127.0.0.1", command_port=int(received["port"]))
    )
    result = remote.run("print('hi')", exec_mode=MODE_EXEC_FILE)
    remote.close()
    thread.join(1.0)
    assert result.success
    assert result.output == "ok"
    types = [m["type"] for m in received["messages"]]
    assert "open_connection" in types
    assert "command" in types


def test_apply_remote_helper_uses_connect(monkeypatch) -> None:
    class Boom(RemoteExecution):
        def discover(self, **kwargs):
            return []

    monkeypatch.setattr("pcg_as_code.remote.RemoteExecution", Boom)
    try:
        apply_remote("print(1)", timeout=0.05)
    except Exception as exc:
        assert "No Unreal Editor" in str(exc)
    else:
        raise AssertionError("expected RemoteExecutionError")
