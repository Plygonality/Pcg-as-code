from __future__ import annotations

from pcg_as_code.apply import apply, dump_from_unreal, to_apply_script, to_dump_script
from pcg_as_code.samples import build_deck_scatter
from tests.fake_unreal import FakeUnreal


def _ids(graph) -> set[str]:
    names = {graph.get_input_node().node_id, graph.get_output_node().node_id}
    for node in graph.nodes:
        names.add(node.node_id or node.node_title)
    return {n for n in names if n}


def _link_keys(graph) -> set[tuple[str, str, str, str]]:
    id_of = {}
    for node in [graph.get_input_node(), *graph.nodes, graph.get_output_node()]:
        id_of[id(node)] = node.node_id or node.node_title
    keys = set()
    for node in [graph.get_input_node(), *graph.nodes, graph.get_output_node()]:
        src = id_of.get(id(node))
        for pin in node.output_pins:
            for edge in pin.edges:
                dest = edge.destination
                dst = id_of.get(id(dest.node))
                if src and dst:
                    keys.add((src, pin.properties.label, dst, dest.properties.label))
    return keys


def test_apply_deck_creates_nodes_and_links() -> None:
    unreal = FakeUnreal()
    graph_data = build_deck_scatter().to_data()
    graph = apply(graph_data, unreal=unreal)
    assert graph.get_name() == "Deck Habitat Scatter"
    assert graph.path_name == "/Game/PCG/DeckHabitatScatter"
    assert "grid" in _ids(graph)
    assert "spawner" in _ids(graph)
    keys = _link_keys(graph)
    assert ("grid", "Out", "spawner", "In") in keys
    assert ("spawner", "Out", "Output", "Out") in keys


def test_apply_then_dump_preserves_topology() -> None:
    unreal = FakeUnreal()
    original = build_deck_scatter().to_data()
    graph = apply(original, unreal=unreal)
    dumped = dump_from_unreal(graph)
    assert dumped["name"] == original.name
    assert dumped["format"] == "pcg-as-code"
    orig_ids = {n.id for n in original.nodes}
    dump_ids = {n["id"] for n in dumped["nodes"]}
    assert orig_ids == dump_ids
    orig_links = {(ln.from_node, ln.from_pin, ln.to_node, ln.to_pin) for ln in original.links}
    dump_links = {(ln["from"][0], ln["from"][1], ln["to"][0], ln["to"][1]) for ln in dumped["links"]}
    assert orig_links == dump_links
    rebuilt = apply(dumped, unreal=FakeUnreal())
    assert _link_keys(rebuilt) == _link_keys(graph)


def test_apply_resolves_cell_size_ref() -> None:
    unreal = FakeUnreal()
    graph = apply(build_deck_scatter().to_data(), unreal=unreal)
    grid = next(n for n in graph.nodes if n.node_id == "grid")
    settings = grid.get_settings()
    assert settings is not None
    cell = settings.get_editor_property("cell_size")
    assert cell is not None
    if hasattr(cell, "x"):
        assert cell.x == 100
        assert cell.y == 100
        assert cell.z == 100
    else:
        assert list(cell) == [100, 100, 100]


def test_apply_script_is_executable_python() -> None:
    script = to_apply_script(build_deck_scatter().to_data())
    compile(script, "<apply>", "exec")
    assert "apply_graph_dict" in script
    assert '"name": "Deck Habitat Scatter"' in script
    dump_script = to_dump_script("/Game/PCG/DeckHabitatScatter")
    compile(dump_script, "<dump>", "exec")
    assert "dump_graph_by_path" in dump_script
