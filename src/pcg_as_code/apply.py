"""Apply / dump helpers and Unreal Python script generation.

The useful artifact is the graph JSON plus this library. Apply is a pasteable
editor script, or optional remote execution into a running editor. This repo
does not host a Plygon Unreal MCP.
"""

from __future__ import annotations

import json
from pathlib import Path

from pcg_as_code.dump import to_dict
from pcg_as_code.ir import GraphData
from pcg_as_code.runtime_apply import apply_graph_dict, dump_graph, dump_graph_by_path

_RUNTIME_PATH = Path(__file__).with_name("runtime_apply.py")


def apply(graph: GraphData | dict, unreal=None, **kwargs):
    """Apply a graph inside Unreal. Imports ``unreal`` if omitted."""
    if unreal is None:
        unreal = __import__("unreal")
    payload = graph if isinstance(graph, dict) else to_dict(graph)
    return apply_graph_dict(payload, unreal, **kwargs)


def dump_from_unreal(graph, *, unreal_version: str = "5.5") -> dict:
    return dump_graph(graph, unreal_version=unreal_version)


def to_apply_script(
    graph: GraphData | dict,
    *,
    asset_path: str | None = None,
    replace: bool = True,
) -> str:
    """Self-contained Unreal Python script. Paste into the editor console."""
    payload = graph if isinstance(graph, dict) else to_dict(graph)
    runtime = _RUNTIME_PATH.read_text(encoding="utf-8")
    path = asset_path if asset_path is not None else payload.get("asset_path")
    call = (
        "import unreal\n"
        "graph = apply_graph_dict(\n"
        f"    {json.dumps(payload, indent=2)},\n"
        "    unreal,\n"
        f"    asset_path={path!r},\n"
        f"    replace={replace!r},\n"
        ")\n"
        "print(graph.get_path_name() if hasattr(graph, 'get_path_name') else graph)\n"
    )
    return runtime + "\n\n" + call


def to_dump_script(asset_path: str, *, unreal_version: str = "5.5") -> str:
    """Self-contained Unreal Python script that prints a graph dump as JSON."""
    runtime = _RUNTIME_PATH.read_text(encoding="utf-8")
    call = (
        "import json\n"
        "import unreal\n"
        f"result = dump_graph_by_path(unreal, {asset_path!r}, unreal_version={unreal_version!r})\n"
        "print(json.dumps(result, indent=2))\n"
    )
    return runtime + "\n\n" + call


__all__ = [
    "apply",
    "apply_graph_dict",
    "dump_from_unreal",
    "dump_graph",
    "dump_graph_by_path",
    "to_apply_script",
    "to_dump_script",
]
