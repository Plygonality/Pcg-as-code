from __future__ import annotations

import json

from pcg_as_code import Graph, dumps, from_dict, loads, to_dict
from pcg_as_code.dump import fingerprint, to_mermaid
from pcg_as_code.samples import build_deck_scatter


def test_roundtrip_dict() -> None:
    graph = build_deck_scatter()
    payload = graph.to_dict()
    restored = from_dict(payload)
    assert to_dict(restored) == payload


def test_dumps_is_stable() -> None:
    a = dumps(build_deck_scatter().to_data())
    b = dumps(build_deck_scatter().to_data())
    assert a == b
    json.loads(a)


def test_loads_roundtrip_text() -> None:
    text = build_deck_scatter().dumps()
    assert dumps(loads(text)) == text


def test_fingerprint_ignores_layout() -> None:
    g = Graph("A")
    grid = g.create_points_grid(id="grid", location=(10, 20))
    g.output(grid)
    other = Graph("A")
    grid2 = other.create_points_grid(id="grid", location=(99, -4))
    other.output(grid2)
    assert fingerprint(g.to_data()) == fingerprint(other.to_data())
    assert fingerprint(g.to_data(), include_layout=True) != fingerprint(
        other.to_data(), include_layout=True
    )


def test_canonical_node_order() -> None:
    g = Graph("Order")
    b = g.create_points_grid(id="b")
    a = g.create_points_grid(id="a")
    g.output(g.merge(a, b, id="join"))
    ids = [n["id"] for n in g.to_dict()["nodes"]]
    assert ids == sorted(ids)


def test_mermaid_contains_nodes_and_edges() -> None:
    text = to_mermaid(build_deck_scatter().to_data())
    assert text.startswith("flowchart LR")
    assert "grid" in text
    assert "spawner" in text
    assert "-->" in text
