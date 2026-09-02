from __future__ import annotations

from pcg_as_code.unit_canon import cell_size_uu, cell_size_vector, load


def test_baked_canon_matches_unit_canon_file() -> None:
    canon = load()
    assert canon.uu_per_meter == 100
    assert canon.meters_per_grid == 1.0
    assert cell_size_uu() == 100
    assert cell_size_vector() == (100, 100, 100)
    assert canon.deck_height_uu == 300
