"""Structural validation of a PCG graph dump. No Unreal editor required."""

from __future__ import annotations

from dataclasses import dataclass

from pcg_as_code.catalog import OUTPUT_TYPE, get_spec
from pcg_as_code.ir import GraphData, Link, Node
from pcg_as_code.types import is_param_ref


@dataclass
class GraphError:
    code: str
    message: str
    node: str | None = None

    def __str__(self) -> str:
        if self.node:
            return f"{self.code}: {self.node}: {self.message}"
        return f"{self.code}: {self.message}"


def validate(graph: GraphData) -> list[GraphError]:
    errors: list[GraphError] = []
    ids = [node.id for node in graph.nodes]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        for node_id in ids:
            if node_id in seen:
                errors.append(
                    GraphError("duplicate_id", f"Node id {node_id!r} is used twice", node_id)
                )
            seen.add(node_id)
    nodes = graph.node_map()

    if not graph.nodes:
        errors.append(GraphError("empty_graph", "Graph has no nodes"))

    param_names = [item.name for item in graph.defaults.params]
    if len(param_names) != len(set(param_names)):
        errors.append(GraphError("duplicate_param", "Duplicate graph default names"))

    if not any(n.type == OUTPUT_TYPE for n in graph.nodes):
        errors.append(GraphError("missing_output", "Graph has no Output node"))

    for node in graph.nodes:
        errors.extend(_validate_node(node, param_names))

    for link in graph.links:
        errors.extend(_validate_link(link, nodes))

    output_nodes = [n for n in graph.nodes if n.type == OUTPUT_TYPE]
    if output_nodes:
        out_id = output_nodes[0].id
        wired = {ln.to_pin for ln in graph.links if ln.to_node == out_id}
        expected = {pin.label for pin in output_nodes[0].pins_in} or {"Out"}
        for label in expected:
            if label not in wired:
                errors.append(
                    GraphError(
                        "unwired_output",
                        f"Output pin {label!r} is not connected",
                        out_id,
                    )
                )
    return errors


def _validate_node(node: Node, param_names: list[str]) -> list[GraphError]:
    errors: list[GraphError] = []
    spec = get_spec(node.type)
    known_settings = spec.setting_map() if spec is not None else {}
    for key, value in node.settings.items():
        if spec is not None and known_settings and key not in known_settings:
            errors.append(
                GraphError(
                    "unknown_setting",
                    f"Setting {key!r} is not a catalog setting on {node.type}",
                    node.id,
                )
            )
        if is_param_ref(value) and value["ref"] not in param_names:
            errors.append(
                GraphError(
                    "unknown_ref",
                    f"Setting {key!r} references missing graph default {value['ref']!r}",
                    node.id,
                )
            )
        if spec is None:
            continue
        catalog = known_settings.get(key)
        if catalog is not None and catalog.items and not is_param_ref(value):
            if value not in catalog.items:
                errors.append(
                    GraphError(
                        "invalid_setting",
                        f"Setting {key!r}={value!r} not in {catalog.items}",
                        node.id,
                    )
                )

    if spec is not None:
        known_in = spec.input_map()
        for pin in node.pins_in:
            if known_in and pin.label not in known_in:
                errors.append(
                    GraphError(
                        "unknown_pin",
                        f"Input pin {pin.label!r} is not a catalog pin on {node.type}",
                        node.id,
                    )
                )
        known_out = spec.output_map()
        for pin in node.pins_out:
            if known_out and pin.label not in known_out:
                errors.append(
                    GraphError(
                        "unknown_pin",
                        f"Output pin {pin.label!r} is not a catalog pin on {node.type}",
                        node.id,
                    )
                )
    return errors


def _validate_link(link: Link, nodes: dict[str, Node]) -> list[GraphError]:
    errors: list[GraphError] = []
    if link.from_node not in nodes:
        errors.append(GraphError("dangling_link", f"from_node {link.from_node!r} does not exist"))
        return errors
    if link.to_node not in nodes:
        errors.append(GraphError("dangling_link", f"to_node {link.to_node!r} does not exist"))
        return errors
    src = nodes[link.from_node]
    dst = nodes[link.to_node]
    src_pins = {pin.label for pin in src.pins_out}
    if not src_pins:
        spec = get_spec(src.type)
        if spec is not None:
            src_pins = set(spec.output_map())
    if src_pins and link.from_pin not in src_pins:
        errors.append(
            GraphError(
                "unknown_pin",
                f"Node {src.type} has no output pin {link.from_pin!r}",
                src.id,
            )
        )
    dst_pins = {pin.label for pin in dst.pins_in}
    if not dst_pins:
        spec = get_spec(dst.type)
        if spec is not None:
            dst_pins = set(spec.input_map())
    if dst_pins and link.to_pin not in dst_pins:
        errors.append(
            GraphError(
                "unknown_pin",
                f"Node {dst.type} has no input pin {link.to_pin!r}",
                dst.id,
            )
        )
    return errors
