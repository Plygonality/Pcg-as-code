"""Canonical PCG graph IR.

The dump format is the source of truth. A ``.uasset`` is a cache you apply into.
v1 is nodes, pins, and graph defaults — not a wrap of the Unreal Python API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pcg_as_code.types import GraphKind, ParamType, PinUsage, jsonify

FORMAT = "pcg-as-code"
FORMAT_VERSION = 1


@dataclass
class ParamItem:
    """A graph-level user parameter (PCG graph defaults)."""

    name: str
    type: ParamType
    default: Any = None
    min: float | None = None
    max: float | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
        }
        if self.default is not None:
            data["default"] = jsonify(self.default)
        if self.min is not None:
            data["min"] = jsonify(self.min)
        if self.max is not None:
            data["max"] = jsonify(self.max)
        if self.description:
            data["description"] = self.description
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParamItem:
        return cls(
            name=data["name"],
            type=data["type"] if isinstance(data["type"], ParamType) else ParamType(data["type"]),
            default=data.get("default"),
            min=data.get("min"),
            max=data.get("max"),
            description=data.get("description", ""),
        )


@dataclass
class Pin:
    """A named pin on a PCG node."""

    label: str
    usage: PinUsage = PinUsage.SPATIAL
    tooltip: str = ""
    allow_multiple: bool = False

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "usage": self.usage.value,
        }
        if self.tooltip:
            data["tooltip"] = self.tooltip
        if self.allow_multiple:
            data["allow_multiple"] = True
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pin:
        usage_raw = data.get("usage", PinUsage.SPATIAL.value)
        if isinstance(usage_raw, PinUsage):
            usage = usage_raw
        else:
            from pcg_as_code.types import parse_pin_usage

            usage = parse_pin_usage(str(usage_raw))
        return cls(
            label=data["label"],
            usage=usage,
            tooltip=data.get("tooltip", ""),
            allow_multiple=bool(data.get("allow_multiple", False)),
        )


@dataclass
class Node:
    id: str
    type: str
    label: str = ""
    location: tuple[float, float] | None = None
    enabled: bool = True
    comment: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    pins_in: list[Pin] = field(default_factory=list)
    pins_out: list[Pin] = field(default_factory=list)

    def pin_in_map(self) -> dict[str, Pin]:
        return {pin.label: pin for pin in self.pins_in}

    def pin_out_map(self) -> dict[str, Pin]:
        return {pin.label: pin for pin in self.pins_out}

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
        }
        if self.label:
            data["label"] = self.label
        if self.location is not None:
            data["location"] = [jsonify(self.location[0]), jsonify(self.location[1])]
        if not self.enabled:
            data["enabled"] = False
        if self.comment:
            data["comment"] = self.comment
        if self.settings:
            data["settings"] = {k: _jsonify_setting(v) for k, v in sorted(self.settings.items())}
        pins: dict[str, Any] = {}
        if self.pins_in:
            pins["in"] = [pin.to_dict() for pin in self.pins_in]
        if self.pins_out:
            pins["out"] = [pin.to_dict() for pin in self.pins_out]
        if pins:
            data["pins"] = pins
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        location = data.get("location")
        loc = None
        if location is not None:
            loc = (float(location[0]), float(location[1]))
        pins = data.get("pins") or {}
        return cls(
            id=data["id"],
            type=data["type"],
            label=data.get("label", ""),
            location=loc,
            enabled=bool(data.get("enabled", True)),
            comment=data.get("comment", ""),
            settings=dict(data.get("settings") or {}),
            pins_in=[Pin.from_dict(x) for x in pins.get("in", [])],
            pins_out=[Pin.from_dict(x) for x in pins.get("out", [])],
        )


@dataclass
class Link:
    from_node: str
    from_pin: str
    to_node: str
    to_pin: str

    def key(self) -> tuple[str, str, str, str]:
        return (self.from_node, self.from_pin, self.to_node, self.to_pin)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": [self.from_node, self.from_pin],
            "to": [self.to_node, self.to_pin],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Link:
        if "from" in data:
            src, dst = data["from"], data["to"]
            return cls(str(src[0]), str(src[1]), str(dst[0]), str(dst[1]))
        return cls(
            data["from_node"],
            str(data.get("from_pin", data.get("from_socket", "Out"))),
            data["to_node"],
            str(data.get("to_pin", data.get("to_socket", "In"))),
        )


@dataclass
class GraphDefaults:
    """Graph-level flags and user parameters."""

    has_default_constructed_inputs: bool = True
    params: list[ParamItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "has_default_constructed_inputs": self.has_default_constructed_inputs,
        }
        if self.params:
            data["params"] = [item.to_dict() for item in self.params]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GraphDefaults:
        raw = data or {}
        params = raw.get("params", raw.get("interface", {}).get("params", []) if isinstance(raw.get("interface"), dict) else [])
        if not params and isinstance(raw.get("params"), list):
            params = raw["params"]
        return cls(
            has_default_constructed_inputs=bool(raw.get("has_default_constructed_inputs", True)),
            params=[ParamItem.from_dict(x) for x in params],
        )


@dataclass
class GraphData:
    name: str
    kind: GraphKind = GraphKind.GRAPH
    unreal: str = "5.5"
    asset_path: str = ""
    defaults: GraphDefaults = field(default_factory=GraphDefaults)
    nodes: list[Node] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def node_map(self) -> dict[str, Node]:
        return {node.id: node for node in self.nodes}

    def canonical(self) -> GraphData:
        """Return a copy sorted for stable dumps and diffs."""
        return GraphData(
            name=self.name,
            kind=self.kind,
            unreal=self.unreal,
            asset_path=self.asset_path,
            defaults=GraphDefaults(
                has_default_constructed_inputs=self.defaults.has_default_constructed_inputs,
                params=list(self.defaults.params),
            ),
            nodes=sorted(self.nodes, key=lambda n: n.id),
            links=sorted(self.links, key=lambda ln: ln.key()),
        )

    def to_dict(self) -> dict[str, Any]:
        graph = self.canonical()
        payload: dict[str, Any] = {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "name": graph.name,
            "kind": graph.kind.value,
            "unreal": graph.unreal,
        }
        if graph.asset_path:
            payload["asset_path"] = graph.asset_path
        payload["defaults"] = graph.defaults.to_dict()
        payload["nodes"] = [node.to_dict() for node in graph.nodes]
        payload["links"] = [link.to_dict() for link in graph.links]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphData:
        fmt = data.get("format")
        if fmt not in (None, FORMAT):
            raise ValueError(f"Unsupported graph format: {fmt!r}")
        version = data.get("version", FORMAT_VERSION)
        if int(version) != FORMAT_VERSION:
            raise ValueError(f"Unsupported pcg-as-code version: {version}")
        kind_raw = data.get("kind", GraphKind.GRAPH.value)
        defaults_raw = data.get("defaults") or {}
        if "params" not in defaults_raw and "interface" in data:
            interface = data.get("interface") or {}
            defaults_raw = {
                **defaults_raw,
                "params": interface.get("params", []),
                "has_default_constructed_inputs": defaults_raw.get(
                    "has_default_constructed_inputs",
                    data.get("has_default_constructed_inputs", True),
                ),
            }
        return cls(
            name=data["name"],
            kind=GraphKind(kind_raw),
            unreal=str(data.get("unreal", "5.5")),
            asset_path=str(data.get("asset_path", "")),
            defaults=GraphDefaults.from_dict(defaults_raw),
            nodes=[Node.from_dict(x) for x in data.get("nodes", [])],
            links=[Link.from_dict(x) for x in data.get("links", [])],
        ).canonical()


def _jsonify_setting(value: Any) -> Any:
    if isinstance(value, dict) and "ref" in value and set(value) <= {"ref"}:
        return dict(value)
    return jsonify(value)
