from __future__ import annotations

from pcg_as_code import Graph, GraphData, Link, Node, Pin, validate
from pcg_as_code.types import PinUsage


def test_valid_graph_has_no_errors() -> None:
    g = Graph("Ok")
    g.output(g.create_points_grid(id="grid"))
    assert validate(g.to_data()) == []


def test_unwired_output() -> None:
    g = Graph("Bad")
    g.create_points_grid(id="grid")
    data = g.to_data()
    data.links = [ln for ln in data.links if ln.to_node != "Output"]
    codes = {e.code for e in validate(data)}
    assert "unwired_output" in codes


def test_dangling_link() -> None:
    g = Graph("Bad")
    g.output(g.create_points_grid(id="grid"))
    data = g.to_data()
    data.links.append(Link("missing", "Out", "Output", "Out"))
    codes = {e.code for e in validate(data)}
    assert "dangling_link" in codes


def test_unknown_pin_on_catalog_node() -> None:
    data = GraphData(
        name="Bad",
        nodes=[
            Node(
                id="Input",
                type="Input",
                pins_out=[Pin("In", PinUsage.ANY)],
            ),
            Node(
                id="Output",
                type="Output",
                pins_in=[Pin("Out", PinUsage.ANY)],
            ),
            Node(
                id="grid",
                type="PCGCreatePointsGridSettings",
                pins_out=[Pin("Out", PinUsage.SPATIAL)],
            ),
        ],
        links=[Link("grid", "Nope", "Output", "Out")],
    )
    codes = {e.code for e in validate(data)}
    assert "unknown_pin" in codes


def test_unknown_ref() -> None:
    g = Graph("Bad")
    g.create_points_grid(cell_size={"ref": "Missing"}, id="grid")
    g.output(g.node("PCGCreatePointsGridSettings", id="other"))
    # Wire output from grid instead
    data = g.to_data()
    codes = {e.code for e in validate(data)}
    assert "unknown_ref" in codes


def test_invalid_enum_setting() -> None:
    g = Graph("Bad")
    g.output(g.create_points_grid(coordinate_space="NotASpace", id="grid"))
    codes = {e.code for e in validate(g.to_data())}
    assert "invalid_setting" in codes
