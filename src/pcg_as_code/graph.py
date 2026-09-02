"""Typed PCG graph builder.

A ``Graph`` is both the authoring API and the in-memory IR. Call ``to_dict`` /
``dumps`` when you want the version-controlled artifact.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pcg_as_code.catalog import (
    CATALOG_BY_METHOD,
    INPUT_TYPE,
    OUTPUT_TYPE,
    NodeSpec,
    get_spec,
    values_equal,
)
from pcg_as_code.ir import GraphData, GraphDefaults, Link, Node, ParamItem, Pin
from pcg_as_code.types import GraphKind, JsonValue, ParamType, PinUsage, jsonify

InputValue = Any


@dataclass(frozen=True)
class ParamRef:
    """A graph default that can drive a node setting."""

    name: str
    param_type: ParamType | None = None


@dataclass(frozen=True)
class PinRef:
    """A named output pin that can be wired into another node."""

    node: str
    pin: str
    usage: PinUsage | None = None

    def as_link_src(self) -> tuple[str, str]:
        return self.node, self.pin


@dataclass
class NodeHandle:
    """Handle to a node already in the graph. Attribute access yields output pins."""

    graph: Graph
    id: str
    spec: NodeSpec | None = None

    def out(self, pin: str = "Out") -> PinRef:
        spec = self.spec
        usage = None
        if spec is not None:
            found = spec.output_map().get(pin)
            if found is None:
                lowered = {p.label.lower(): p for p in spec.outputs}
                found = lowered.get(pin.lower())
            if found is not None:
                pin = found.label
                usage = found.usage
        return PinRef(self.id, pin, usage)

    def __getitem__(self, pin: str | int) -> PinRef:
        if isinstance(pin, int):
            if self.spec is None or pin >= len(self.spec.outputs):
                return PinRef(self.id, "Out" if pin == 0 else str(pin))
            spec = self.spec.outputs[pin]
            return PinRef(self.id, spec.label, spec.usage)
        return self.out(pin)

    def __getattr__(self, name: str) -> PinRef:
        if name.startswith("_"):
            raise AttributeError(name)
        if self.spec is not None:
            ident = _snake_to_pin(name)
            outputs = self.spec.output_map()
            if ident in outputs:
                return self.out(ident)
            lowered = {key.lower(): key for key in outputs}
            if ident.lower() in lowered:
                return self.out(lowered[ident.lower()])
            if name.lower() in {"out", "geo", "points"} and "Out" in outputs:
                return self.out("Out")
        return self.out(_snake_to_pin(name))

    def as_pin(self) -> PinRef:
        if self.spec is not None:
            primary = self.spec.primary_output()
            if primary is not None:
                return PinRef(self.id, primary.label, primary.usage)
        return PinRef(self.id, "Out", PinUsage.SPATIAL)


def _snake_to_pin(name: str) -> str:
    specials = {
        "in_": "In",
        "out": "Out",
        "source": "Source",
        "target": "Target",
        "differences": "Differences",
        "overrides": "Overrides",
    }
    if name in specials:
        return specials[name]
    return name.replace("_", " ").title()


class Graph:
    """Author a PCG graph as data."""

    def __init__(
        self,
        name: str,
        *,
        kind: GraphKind | str = GraphKind.GRAPH,
        unreal: str = "5.5",
        asset_path: str = "",
        has_default_constructed_inputs: bool = True,
    ) -> None:
        self.name = name
        self.kind = GraphKind(kind)
        self.unreal = unreal
        self.asset_path = asset_path
        self.has_default_constructed_inputs = has_default_constructed_inputs
        self._params: list[ParamItem] = []
        self._nodes: dict[str, Node] = {}
        self._links: list[Link] = []
        self._used_ids: set[str] = set()
        self._input_node_id = "Input"
        self._output_node_id = "Output"
        self._ensure_io_nodes()

    # --- graph defaults ----------------------------------------------------

    def param(
        self,
        name: str,
        type: ParamType | str,
        default: JsonValue = None,
        *,
        min: float | None = None,
        max: float | None = None,
        description: str = "",
    ) -> ParamRef:
        ptype = type if isinstance(type, ParamType) else ParamType(type)
        item = ParamItem(
            name=name,
            type=ptype,
            default=jsonify(default) if default is not None else None,
            min=min,
            max=max,
            description=description,
        )
        existing = next((i for i in self._params if i.name == name), None)
        if existing is not None:
            self._params[self._params.index(existing)] = item
        else:
            self._params.append(item)
        return ParamRef(name, ptype)

    def param_float(
        self,
        name: str,
        default: float = 0.0,
        *,
        min: float | None = None,
        max: float | None = None,
        description: str = "",
    ) -> ParamRef:
        return self.param(name, ParamType.FLOAT, default, min=min, max=max, description=description)

    def param_int(
        self,
        name: str,
        default: int = 0,
        *,
        min: float | None = None,
        max: float | None = None,
        description: str = "",
    ) -> ParamRef:
        return self.param(name, ParamType.INT, default, min=min, max=max, description=description)

    def param_bool(self, name: str, default: bool = False, *, description: str = "") -> ParamRef:
        return self.param(name, ParamType.BOOL, default, description=description)

    def param_string(self, name: str, default: str = "", *, description: str = "") -> ParamRef:
        return self.param(name, ParamType.STRING, default, description=description)

    def param_vector(
        self,
        name: str,
        default: Sequence[float] = (0.0, 0.0, 0.0),
        *,
        description: str = "",
    ) -> ParamRef:
        return self.param(name, ParamType.VECTOR, tuple(default), description=description)

    # --- output ------------------------------------------------------------

    def output(self, source: InputValue, pin: str = "Out") -> NodeHandle:
        self._connect(source, self._output_node_id, pin)
        return NodeHandle(self, self._output_node_id, get_spec(OUTPUT_TYPE))

    # --- generic node spawn ------------------------------------------------

    def node(
        self,
        type: str,
        *,
        id: str | None = None,
        label: str = "",
        location: Sequence[float] | None = None,
        enabled: bool = True,
        comment: str = "",
        inputs: Sequence[InputValue] | dict[str, InputValue] | None = None,
        settings: dict[str, InputValue] | None = None,
        pins_in: Sequence[Pin] | None = None,
        pins_out: Sequence[Pin] | None = None,
        **extra_settings: InputValue,
    ) -> NodeHandle:
        spec = get_spec(type)
        node_id = self._fresh_id(id or (spec.method if spec else type))
        merged = dict(settings or {})
        merged.update(extra_settings)
        recorded = self._record_settings(spec, merged)
        loc = None if location is None else (float(location[0]), float(location[1]))
        in_pins = list(pins_in) if pins_in is not None else self._default_pins(spec, incoming=True)
        out_pins = list(pins_out) if pins_out is not None else self._default_pins(spec, incoming=False)
        self._nodes[node_id] = Node(
            id=node_id,
            type=type,
            label=label,
            location=loc,
            enabled=enabled,
            comment=comment,
            settings=recorded,
            pins_in=in_pins,
            pins_out=out_pins,
        )
        self._wire_inputs(node_id, inputs, spec)
        return NodeHandle(self, node_id, spec)

    def link(self, source: InputValue, target: NodeHandle | str, pin: str = "In") -> None:
        node_id = target.id if isinstance(target, NodeHandle) else target
        self._connect(source, node_id, pin)

    # --- typed factories ---------------------------------------------------

    def create_points_grid(
        self,
        *,
        cell_size: InputValue = (100.0, 100.0, 100.0),
        grid_extents: InputValue = (800.0, 0.0, 800.0),
        coordinate_space: InputValue = "Local",
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGCreatePointsGridSettings",
            id=id,
            settings={
                "cell_size": cell_size,
                "grid_extents": grid_extents,
                "coordinate_space": coordinate_space,
            },
            **node_kw,
        )

    def static_mesh_spawner(
        self,
        points: InputValue = None,
        *,
        meshes: InputValue = (),
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGStaticMeshSpawnerSettings",
            id=id,
            inputs={"In": points} if points is not None else None,
            settings={"meshes": meshes},
            **node_kw,
        )

    def surface_sampler(
        self,
        surface: InputValue = None,
        *,
        points_per_squared_meter: InputValue = 0.1,
        point_extents: InputValue = (50.0, 50.0, 50.0),
        seed: InputValue = 42,
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGSurfaceSamplerSettings",
            id=id,
            inputs={"In": surface} if surface is not None else None,
            settings={
                "points_per_squared_meter": points_per_squared_meter,
                "point_extents": point_extents,
                "seed": seed,
            },
            **node_kw,
        )

    def transform_points(
        self,
        points: InputValue = None,
        *,
        offset_min: InputValue = (0.0, 0.0, 0.0),
        offset_max: InputValue = (0.0, 0.0, 0.0),
        rotation_min: InputValue = (0.0, 0.0, 0.0),
        rotation_max: InputValue = (0.0, 0.0, 0.0),
        scale_min: InputValue = (1.0, 1.0, 1.0),
        scale_max: InputValue = (1.0, 1.0, 1.0),
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGTransformPointsSettings",
            id=id,
            inputs={"In": points} if points is not None else None,
            settings={
                "offset_min": offset_min,
                "offset_max": offset_max,
                "rotation_min": rotation_min,
                "rotation_max": rotation_max,
                "scale_min": scale_min,
                "scale_max": scale_max,
            },
            **node_kw,
        )

    def density_filter(
        self,
        points: InputValue = None,
        *,
        lower_bound: InputValue = 0.5,
        upper_bound: InputValue = 1.0,
        invert_filter: InputValue = False,
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGDensityFilterSettings",
            id=id,
            inputs={"In": points} if points is not None else None,
            settings={
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "invert_filter": invert_filter,
            },
            **node_kw,
        )

    def copy_points(
        self,
        source: InputValue,
        target: InputValue,
        *,
        id: str | None = None,
        **node_kw: Any,
    ) -> NodeHandle:
        return self.node(
            "PCGCopyPointsSettings",
            id=id,
            inputs={"Source": source, "Target": target},
            **node_kw,
        )

    def merge(self, *sources: InputValue, id: str | None = None, **node_kw: Any) -> NodeHandle:
        handle = self.node("PCGMergeSettings", id=id, **node_kw)
        for source in sources:
            self._connect(source, handle.id, "In")
        return handle

    def __getattr__(self, name: str) -> Any:
        spec = CATALOG_BY_METHOD.get(name)
        if spec is None:
            raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

        def factory(*args: Any, id: str | None = None, **kwargs: Any) -> NodeHandle:
            inputs: dict[str, InputValue] = {}
            settings: dict[str, Any] = {}
            positional = list(args)
            required_pins = [p for p in spec.inputs if p.label != "Overrides"]
            for pin in required_pins:
                if pin.label in kwargs:
                    inputs[pin.label] = kwargs.pop(pin.label)
                elif positional:
                    inputs[pin.label] = positional.pop(0)
            for setting in spec.settings:
                if setting.name in kwargs:
                    settings[setting.name] = kwargs.pop(setting.name)
            return self.node(
                spec.type,
                id=id,
                inputs=inputs or None,
                settings=settings,
                **kwargs,
            )

        factory.__name__ = spec.method
        factory.__doc__ = f"Create a {spec.label} ({spec.type}) node."
        return factory

    # --- layout ------------------------------------------------------------

    def autolayout(self, *, x_step: float = 280.0, y_step: float = 140.0) -> None:
        """Assign stable left-to-right locations from topology. Existing locations win."""
        levels = self._levels()
        for level, ids in enumerate(levels):
            count = len(ids)
            for i, node_id in enumerate(sorted(ids)):
                node = self._nodes[node_id]
                if node.location is not None:
                    continue
                y = (count - 1) * y_step / 2.0 - i * y_step
                node.location = (level * x_step, y)

    # --- serialize ---------------------------------------------------------

    def to_data(self, *, autolayout: bool = True) -> GraphData:
        if autolayout:
            self.autolayout()
        return GraphData(
            name=self.name,
            kind=self.kind,
            unreal=self.unreal,
            asset_path=self.asset_path,
            defaults=GraphDefaults(
                has_default_constructed_inputs=self.has_default_constructed_inputs,
                params=list(self._params),
            ),
            nodes=list(self._nodes.values()),
            links=list(self._links),
        ).canonical()

    def to_dict(self, *, autolayout: bool = True) -> dict[str, Any]:
        from pcg_as_code.dump import to_dict

        return to_dict(self.to_data(autolayout=autolayout))

    def dumps(self, *, autolayout: bool = True) -> str:
        from pcg_as_code.dump import dumps

        return dumps(self.to_data(autolayout=autolayout))

    def to_mermaid(self) -> str:
        from pcg_as_code.dump import to_mermaid

        return to_mermaid(self.to_data(autolayout=False))

    @classmethod
    def from_data(cls, data: GraphData) -> Graph:
        graph = cls(
            data.name,
            kind=data.kind,
            unreal=data.unreal,
            asset_path=data.asset_path,
            has_default_constructed_inputs=data.defaults.has_default_constructed_inputs,
        )
        graph._params = list(data.defaults.params)
        graph._nodes = {node.id: node for node in data.nodes}
        graph._links = list(data.links)
        graph._used_ids = set(graph._nodes)
        if "Input" in graph._nodes:
            graph._input_node_id = "Input"
        if "Output" in graph._nodes:
            graph._output_node_id = "Output"
        return graph

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Graph:
        return cls.from_data(GraphData.from_dict(data))

    # --- internals ---------------------------------------------------------

    def _ensure_io_nodes(self) -> None:
        if self._input_node_id not in self._nodes:
            spec = get_spec(INPUT_TYPE)
            self._nodes[self._input_node_id] = Node(
                id=self._input_node_id,
                type=INPUT_TYPE,
                pins_in=self._default_pins(spec, incoming=True),
                pins_out=self._default_pins(spec, incoming=False),
            )
            self._used_ids.add(self._input_node_id)
        if self._output_node_id not in self._nodes:
            spec = get_spec(OUTPUT_TYPE)
            self._nodes[self._output_node_id] = Node(
                id=self._output_node_id,
                type=OUTPUT_TYPE,
                pins_in=self._default_pins(spec, incoming=True),
                pins_out=self._default_pins(spec, incoming=False),
            )
            self._used_ids.add(self._output_node_id)

    def _default_pins(self, spec: NodeSpec | None, *, incoming: bool) -> list[Pin]:
        if spec is None:
            if incoming:
                return [Pin(label="In", usage=PinUsage.SPATIAL)]
            return [Pin(label="Out", usage=PinUsage.SPATIAL)]
        source = spec.inputs if incoming else spec.outputs
        return [
            Pin(
                label=pin.label,
                usage=pin.usage,
                allow_multiple=pin.allow_multiple,
            )
            for pin in source
            if pin.label != "Overrides"
        ]

    def _fresh_id(self, base: str) -> str:
        candidate = _safe_node_id(base)
        n = 1
        while candidate in self._used_ids:
            n += 1
            candidate = f"{_safe_node_id(base)}_{n}"
        self._used_ids.add(candidate)
        return candidate

    def _record_settings(self, spec: NodeSpec | None, settings: dict[str, InputValue]) -> dict[str, JsonValue]:
        recorded: dict[str, JsonValue] = {}
        known = spec.setting_map() if spec is not None else {}
        for key, value in settings.items():
            if isinstance(value, ParamRef):
                recorded[key] = {"ref": value.name}
                continue
            if isinstance(value, dict) and set(value) <= {"ref"}:
                recorded[key] = dict(value)
                continue
            if spec is not None:
                catalog = known.get(key)
                if catalog is not None and catalog.default is not None and values_equal(value, catalog.default):
                    continue
            recorded[key] = jsonify(value)
        return recorded

    def _wire_inputs(
        self,
        node_id: str,
        inputs: Sequence[InputValue] | dict[str, InputValue] | None,
        spec: NodeSpec | None,
    ) -> None:
        if inputs is None:
            return
        if isinstance(inputs, dict):
            for pin, value in inputs.items():
                if value is None:
                    continue
                self._connect(value, node_id, pin)
            return
        required = [p for p in (spec.inputs if spec else ()) if p.label != "Overrides"]
        for index, value in enumerate(inputs):
            if value is None:
                continue
            pin = required[index].label if index < len(required) else "In"
            self._connect(value, node_id, pin)

    def _as_pin(self, value: InputValue) -> PinRef:
        if isinstance(value, PinRef):
            return value
        if isinstance(value, NodeHandle):
            return value.as_pin()
        raise TypeError(f"Expected a pin or node handle, got {type(value)!r}")

    def _connect(self, source: InputValue, to_node: str, to_pin: str) -> None:
        ref = self._as_pin(source)
        spec = get_spec(self._nodes[to_node].type) if to_node in self._nodes else None
        ident = to_pin
        if spec is not None:
            if ident not in spec.input_map():
                titled = _snake_to_pin(ident)
                if titled in spec.input_map():
                    ident = titled
                else:
                    lowered = {p.label.lower(): p.label for p in spec.inputs}
                    ident = lowered.get(ident.lower(), ident)
        link = Link(ref.node, ref.pin, to_node, ident)
        if any(existing.key() == link.key() for existing in self._links):
            return
        self._links.append(link)

    def _levels(self) -> list[list[str]]:
        incoming: dict[str, set[str]] = {node_id: set() for node_id in self._nodes}
        for link in self._links:
            if link.from_node in incoming and link.to_node in incoming:
                incoming[link.to_node].add(link.from_node)
        levels: list[list[str]] = []
        remaining = set(self._nodes)
        while remaining:
            ready = [n for n in remaining if incoming[n].isdisjoint(remaining)]
            if not ready:
                ready = sorted(remaining)
            levels.append(ready)
            remaining.difference_update(ready)
        return levels


def _safe_node_id(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)
    return cleaned or "node"
