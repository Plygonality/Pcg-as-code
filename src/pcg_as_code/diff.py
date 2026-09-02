"""Structural diff of PCG graphs.

Locations are ignored unless ``include_layout=True`` so git-friendly dumps
don't explode when someone nudges a node in the editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pcg_as_code.dump import fingerprint, to_dict
from pcg_as_code.ir import GraphData, Link


@dataclass
class NodeChange:
    id: str
    fields: dict[str, tuple[Any, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fields": {k: {"from": a, "to": b} for k, (a, b) in sorted(self.fields.items())},
        }


@dataclass
class GraphDiff:
    nodes_added: list[dict[str, Any]] = field(default_factory=list)
    nodes_removed: list[dict[str, Any]] = field(default_factory=list)
    nodes_changed: list[NodeChange] = field(default_factory=list)
    links_added: list[dict[str, Any]] = field(default_factory=list)
    links_removed: list[dict[str, Any]] = field(default_factory=list)
    defaults: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.nodes_added
            or self.nodes_removed
            or self.nodes_changed
            or self.links_added
            or self.links_removed
            or self.defaults
            or self.meta
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.meta:
            payload["meta"] = self.meta
        if self.defaults:
            payload["defaults"] = self.defaults
        if self.nodes_added:
            payload["nodes_added"] = self.nodes_added
        if self.nodes_removed:
            payload["nodes_removed"] = self.nodes_removed
        if self.nodes_changed:
            payload["nodes_changed"] = [c.to_dict() for c in self.nodes_changed]
        if self.links_added:
            payload["links_added"] = self.links_added
        if self.links_removed:
            payload["links_removed"] = self.links_removed
        return payload


def diff_graphs(
    old: GraphData | dict[str, Any],
    new: GraphData | dict[str, Any],
    *,
    include_layout: bool = False,
) -> GraphDiff:
    a = to_dict(old)
    b = to_dict(new)
    if not include_layout:
        a = fingerprint(a, include_layout=False)  # type: ignore[assignment]
        b = fingerprint(b, include_layout=False)  # type: ignore[assignment]

    result = GraphDiff()
    if a.get("name") != b.get("name"):
        result.meta["name"] = {"from": a.get("name"), "to": b.get("name")}
    if a.get("kind") != b.get("kind"):
        result.meta["kind"] = {"from": a.get("kind"), "to": b.get("kind")}
    if a.get("unreal") != b.get("unreal"):
        result.meta["unreal"] = {"from": a.get("unreal"), "to": b.get("unreal")}
    if a.get("asset_path") != b.get("asset_path"):
        result.meta["asset_path"] = {"from": a.get("asset_path"), "to": b.get("asset_path")}

    result.defaults = _defaults_diff(a.get("defaults") or {}, b.get("defaults") or {})

    old_nodes = {n["id"]: n for n in a.get("nodes", [])}
    new_nodes = {n["id"]: n for n in b.get("nodes", [])}
    for nid in sorted(set(new_nodes) - set(old_nodes)):
        result.nodes_added.append(new_nodes[nid])
    for nid in sorted(set(old_nodes) - set(new_nodes)):
        result.nodes_removed.append(old_nodes[nid])
    for nid in sorted(set(old_nodes) & set(new_nodes)):
        change = _node_change(old_nodes[nid], new_nodes[nid])
        if change is not None:
            result.nodes_changed.append(change)

    old_links = {_link_key(x): x for x in a.get("links", [])}
    new_links = {_link_key(x): x for x in b.get("links", [])}
    for key in sorted(set(new_links) - set(old_links)):
        result.links_added.append(new_links[key])
    for key in sorted(set(old_links) - set(new_links)):
        result.links_removed.append(old_links[key])
    return result


def format_diff(diff: GraphDiff) -> str:
    if diff.is_empty():
        return "No differences.\n"
    lines: list[str] = []
    for key, value in diff.meta.items():
        lines.append(f"~ {key}: {value['from']!r} -> {value['to']!r}")
    if diff.defaults:
        lines.append("defaults:")
        lines.extend(_format_defaults_diff(diff.defaults, indent="  "))
    for node in diff.nodes_added:
        lines.append(f"+ node {node['id']} ({node['type']})")
    for node in diff.nodes_removed:
        lines.append(f"- node {node['id']} ({node['type']})")
    for change in diff.nodes_changed:
        lines.append(f"~ node {change.id}")
        for name, (old, new) in sorted(change.fields.items()):
            lines.append(f"    {name}: {old!r} -> {new!r}")
    for link in diff.links_added:
        lines.append(f"+ link {_fmt_link(link)}")
    for link in diff.links_removed:
        lines.append(f"- link {_fmt_link(link)}")
    return "\n".join(lines) + "\n"


def _defaults_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if old.get("has_default_constructed_inputs") != new.get("has_default_constructed_inputs"):
        payload["has_default_constructed_inputs"] = {
            "from": old.get("has_default_constructed_inputs"),
            "to": new.get("has_default_constructed_inputs"),
        }
    params = _list_diff(old.get("params") or [], new.get("params") or [], key="name")
    if params:
        payload["params"] = params
    return payload or None


def _format_defaults_diff(diff: dict[str, Any], indent: str = "") -> list[str]:
    lines: list[str] = []
    if "has_default_constructed_inputs" in diff:
        value = diff["has_default_constructed_inputs"]
        lines.append(
            f"{indent}has_default_constructed_inputs: {value['from']!r} -> {value['to']!r}"
        )
    params = diff.get("params")
    if params:
        lines.append(f"{indent}params:")
        lines.extend(_format_list_diff(params, indent=indent + "  "))
    return lines


def _node_change(old: dict[str, Any], new: dict[str, Any]) -> NodeChange | None:
    fields: dict[str, tuple[Any, Any]] = {}
    for key in ("type", "label", "enabled", "comment", "location"):
        if old.get(key) != new.get(key):
            fields[key] = (old.get(key), new.get(key))
    old_settings = old.get("settings") or {}
    new_settings = new.get("settings") or {}
    if old_settings != new_settings:
        fields["settings"] = (old_settings, new_settings)
    old_pins = old.get("pins") or {}
    new_pins = new.get("pins") or {}
    if old_pins != new_pins:
        fields["pins"] = (old_pins, new_pins)
    if not fields:
        return None
    return NodeChange(id=old["id"], fields=fields)


def _list_diff(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, Any] | None:
    old_map = {item[key]: item for item in old}
    new_map = {item[key]: item for item in new}
    added = [new_map[k] for k in sorted(set(new_map) - set(old_map))]
    removed = [old_map[k] for k in sorted(set(old_map) - set(new_map))]
    changed = []
    for k in sorted(set(old_map) & set(new_map)):
        if old_map[k] != new_map[k]:
            changed.append({"from": old_map[k], "to": new_map[k]})
    if not (added or removed or changed):
        return None
    payload: dict[str, Any] = {}
    if added:
        payload["added"] = added
    if removed:
        payload["removed"] = removed
    if changed:
        payload["changed"] = changed
    return payload


def _format_list_diff(diff: dict[str, Any], indent: str = "") -> list[str]:
    lines: list[str] = []
    for item in diff.get("added", []):
        lines.append(f"{indent}+ {item.get('name', item)}")
    for item in diff.get("removed", []):
        lines.append(f"{indent}- {item.get('name', item)}")
    for item in diff.get("changed", []):
        name = item["to"].get("name", item["from"].get("name"))
        lines.append(f"{indent}~ {name}: {item['from']} -> {item['to']}")
    return lines


def _link_key(link: dict[str, Any]) -> tuple[str, str, str, str]:
    parsed = Link.from_dict(link)
    return parsed.key()


def _fmt_link(link: dict[str, Any]) -> str:
    parsed = Link.from_dict(link)
    return f"{parsed.from_node}.{parsed.from_pin} -> {parsed.to_node}.{parsed.to_pin}"
