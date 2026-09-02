from __future__ import annotations

from pcg_as_code import Graph, diff_graphs, format_diff
from pcg_as_code.samples import build_deck_scatter


def test_identical_graphs_empty_diff() -> None:
    a = build_deck_scatter().to_data()
    b = build_deck_scatter().to_data()
    diff = diff_graphs(a, b)
    assert diff.is_empty()
    assert format_diff(diff) == "No differences.\n"


def test_added_and_removed_nodes() -> None:
    old = Graph("G")
    old.output(old.create_points_grid(id="grid"))
    new = Graph("G")
    new.output(new.surface_sampler(id="sampler"))
    diff = diff_graphs(old.to_data(), new.to_data())
    assert [n["id"] for n in diff.nodes_added] == ["sampler"]
    assert [n["id"] for n in diff.nodes_removed] == ["grid"]
    assert "grid.Out" in format_diff(diff) or "sampler" in format_diff(diff)


def test_changed_setting_and_link() -> None:
    old = Graph("G")
    old.output(old.create_points_grid(cell_size=(100, 100, 100), id="grid"))
    new = Graph("G")
    cell = new.param_vector("CellSize", (200, 200, 200))
    new.output(new.create_points_grid(cell_size=cell, id="grid"))
    diff = diff_graphs(old.to_data(), new.to_data())
    assert diff.defaults is not None
    changed_ids = [c.id for c in diff.nodes_changed]
    assert "grid" in changed_ids


def test_layout_ignored_by_default() -> None:
    a = Graph("G")
    a.output(a.create_points_grid(id="grid", location=(0, 0)))
    b = Graph("G")
    b.output(b.create_points_grid(id="grid", location=(100, 50)))
    assert diff_graphs(a.to_data(autolayout=False), b.to_data(autolayout=False)).is_empty()
    diff = diff_graphs(
        a.to_data(autolayout=False),
        b.to_data(autolayout=False),
        include_layout=True,
    )
    assert not diff.is_empty()
    assert any(c.id == "grid" for c in diff.nodes_changed)
