"""Example PCG graphs shipped with the library.

These are the golden fixtures: Python is how you author, JSON is what git diffs.
Habitat-kit states should compile into this format later — this sample is the
contract, not a wait-for-kit blocker.
"""

from __future__ import annotations

from pcg_as_code.graph import Graph
from pcg_as_code.unit_canon import cell_size_uu, cell_size_vector

# Placeholder Habitat-kit module paths. The kit is not required to dump or diff.
# When Habitat-kit ships, these become the compile targets for deck states.
HABITAT_KIT_ROOT = "/Game/HabitatKit/Modules"
DECK_TILE = f"{HABITAT_KIT_ROOT}/DeckTile"
DECK_GRATE = f"{HABITAT_KIT_ROOT}/DeckGrate"


def build_deck_scatter() -> Graph:
    """Scatter Habitat-kit modules on a deck grid at Unit-canon cell size.

    Create Points Grid uses the canon cell (1.0 m = 100 uu). Graph defaults
    expose CellSize, deck cell counts, and Seed so a later Habitat-kit compile
    can bind them without rewriting the node list.
    """
    cell = cell_size_uu()
    cells_x = 8
    cells_y = 8
    g = Graph(
        "Deck Habitat Scatter",
        asset_path="/Game/PCG/DeckHabitatScatter",
    )
    cell_size = g.param_vector(
        "CellSize",
        cell_size_vector(),
        description="Unit-canon grid cell in Unreal units (1.0 m = 100 uu).",
    )
    g.param_int("DeckCellsX", cells_x, min=1, max=64, description="Deck cells along X.")
    g.param_int("DeckCellsY", cells_y, min=1, max=64, description="Deck cells along Y.")
    g.param_int("Seed", 42, description="Deterministic scatter seed.")

    grid = g.create_points_grid(
        cell_size=cell_size,
        grid_extents=(cells_x * cell, 0.0, cells_y * cell),
        id="grid",
    )
    spawner = g.static_mesh_spawner(
        grid,
        meshes=[
            {"mesh": DECK_TILE, "weight": 3.0},
            {"mesh": DECK_GRATE, "weight": 1.0},
        ],
        id="spawner",
    )
    g.output(spawner)
    return g


SAMPLES = {
    "deck_scatter": build_deck_scatter,
}
