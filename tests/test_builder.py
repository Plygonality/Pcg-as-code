from __future__ import annotations

from pcg_as_code import Graph, ParamType, validate
from pcg_as_code.samples import build_deck_scatter
from pcg_as_code.unit_canon import cell_size_uu


def test_grid_to_spawner_wires_pins() -> None:
    g = Graph("Deck")
    grid = g.create_points_grid(cell_size=(200, 200, 200), grid_extents=(400, 0, 400), id="grid")
    g.output(g.static_mesh_spawner(grid, meshes=[{"mesh": "/Game/M", "weight": 1.0}], id="spawner"))
    data = g.to_data()
    assert data.name == "Deck"
    assert {node.id for node in data.nodes} >= {"grid", "spawner", "Input", "Output"}
    links = {(ln.from_node, ln.from_pin, ln.to_node, ln.to_pin) for ln in data.links}
    assert ("grid", "Out", "spawner", "In") in links
    assert ("spawner", "Out", "Output", "Out") in links
    node = data.node_map()["grid"]
    assert node.settings["cell_size"] == [200, 200, 200]
    assert "coordinate_space" not in node.settings
    assert validate(data) == []


def test_param_ref_is_graph_default_binding() -> None:
    g = Graph("Sized")
    cell = g.param_vector("CellSize", (100, 100, 100))
    g.create_points_grid(cell_size=cell, id="grid")
    g.output(g.node("PCGCreatePointsGridSettings", id="unused"))
    data = g.to_data()
    assert data.defaults.params[0].name == "CellSize"
    assert data.defaults.params[0].type == ParamType.VECTOR
    assert data.node_map()["grid"].settings["cell_size"] == {"ref": "CellSize"}


def test_duplicate_ids_get_suffix() -> None:
    g = Graph("Dup")
    g.create_points_grid(id="grid")
    second = g.create_points_grid(id="grid")
    assert second.id == "grid_2"


def test_handle_pin_attr_and_index() -> None:
    g = Graph("Pins")
    grid = g.create_points_grid(id="grid")
    assert grid.out().pin == "Out"
    assert grid["Out"].node == "grid"
    assert grid[0].pin == "Out"
    g.output(grid)


def test_unknown_type_still_builds() -> None:
    g = Graph("Custom")
    custom = g.node("PCGCustomStudioSettings", id="custom", settings={"foo": 1})
    g.output(custom)
    data = g.to_data()
    assert data.node_map()["custom"].type == "PCGCustomStudioSettings"
    assert data.node_map()["custom"].settings["foo"] == 1
    # Unknown types are allowed; only catalog pins are checked when present.
    errors = validate(data)
    assert all(e.code != "unknown_setting" for e in errors)


def test_sample_validates() -> None:
    data = build_deck_scatter().to_data()
    assert validate(data) == []
    grid = data.node_map()["grid"]
    assert grid.settings["cell_size"] == {"ref": "CellSize"}
    cell = next(p for p in data.defaults.params if p.name == "CellSize")
    assert cell.default == [cell_size_uu(), cell_size_uu(), cell_size_uu()]
    spawner = data.node_map()["spawner"]
    meshes = spawner.settings["meshes"]
    assert any("HabitatKit" in item["mesh"] for item in meshes)
