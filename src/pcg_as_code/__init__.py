"""Unreal PCG graphs as data.

This library is the graph. Git is the source of truth. The .uasset is a cache.
There is no Plygon Unreal MCP here.
"""

from pcg_as_code.diff import GraphDiff, diff_graphs, format_diff
from pcg_as_code.dump import dumps, from_dict, loads, to_dict
from pcg_as_code.graph import Graph, NodeHandle, ParamRef, PinRef
from pcg_as_code.ir import (
    FORMAT,
    FORMAT_VERSION,
    GraphData,
    GraphDefaults,
    Link,
    Node,
    ParamItem,
    Pin,
)
from pcg_as_code.types import GraphKind, ParamType, PinUsage
from pcg_as_code.validate import GraphError, validate

__all__ = [
    "FORMAT",
    "FORMAT_VERSION",
    "Graph",
    "GraphData",
    "GraphDefaults",
    "GraphDiff",
    "GraphError",
    "GraphKind",
    "Link",
    "Node",
    "NodeHandle",
    "ParamItem",
    "ParamRef",
    "ParamType",
    "Pin",
    "PinRef",
    "PinUsage",
    "diff_graphs",
    "dumps",
    "format_diff",
    "from_dict",
    "loads",
    "to_dict",
    "validate",
]

__version__ = "0.1.0"
