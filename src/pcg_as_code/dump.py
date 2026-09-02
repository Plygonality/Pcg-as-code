"""Canonical JSON dump / load and mermaid rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TextIO

from pcg_as_code.catalog import get_spec
from pcg_as_code.ir import FORMAT, FORMAT_VERSION, GraphData
from pcg_as_code.types import jsonify

PathLike = str | Path


def to_dict(graph: GraphData | dict[str, Any]) -> dict[str, Any]:
    if isinstance(graph, dict):
        return GraphData.from_dict(graph).to_dict()
    return graph.canonical().to_dict()


def from_dict(data: dict[str, Any]) -> GraphData:
    return GraphData.from_dict(data)


def dumps(graph: GraphData | dict[str, Any], *, indent: int = 2) -> str:
    payload = to_dict(graph)
    return json.dumps(payload, indent=indent, sort_keys=False, ensure_ascii=False) + "\n"


def loads(text: str) -> GraphData:
    return from_dict(json.loads(text))


def dump(graph: GraphData | dict[str, Any], path: PathLike, *, indent: int = 2) -> None:
    Path(path).write_text(dumps(graph, indent=indent), encoding="utf-8")


def load(path: PathLike) -> GraphData:
    return loads(Path(path).read_text(encoding="utf-8"))


def dump_fp(graph: GraphData | dict[str, Any], fp: TextIO, *, indent: int = 2) -> None:
    fp.write(dumps(graph, indent=indent))


def to_mermaid(graph: GraphData | dict[str, Any]) -> str:
    data = graph if isinstance(graph, GraphData) else GraphData.from_dict(graph)
    data = data.canonical()
    lines = ["flowchart LR"]
    for node in data.nodes:
        spec = get_spec(node.type)
        title = node.label or (spec.label if spec else node.type)
        label = f"{node.id}<br/>{title}".replace('"', "'")
        lines.append(f'  {_mid(node.id)}["{label}"]')
    for link in data.links:
        pin = str(link.from_pin).replace('"', "'")
        lines.append(f"  {_mid(link.from_node)} -->|{pin}| {_mid(link.to_node)}")
    return "\n".join(lines) + "\n"


def _mid(node_id: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in node_id)
    if not safe or safe[0].isdigit():
        safe = "n_" + safe
    return safe


def fingerprint(graph: GraphData | dict[str, Any], *, include_layout: bool = False) -> dict[str, Any]:
    """Identity of a graph for equality tests. Layout is ignored by default."""
    data = to_dict(graph)
    if not include_layout:
        for node in data.get("nodes", []):
            node.pop("location", None)
    return jsonify(data)  # type: ignore[return-value]


__all__ = [
    "FORMAT",
    "FORMAT_VERSION",
    "dump",
    "dump_fp",
    "dumps",
    "fingerprint",
    "from_dict",
    "load",
    "loads",
    "to_dict",
    "to_mermaid",
]
