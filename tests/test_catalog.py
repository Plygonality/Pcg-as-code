from __future__ import annotations

from pcg_as_code.catalog import CATALOG, CATALOG_BY_METHOD, CATALOG_BY_TYPE


def test_catalog_ids_unique() -> None:
    types = [s.type for s in CATALOG]
    methods = [s.method for s in CATALOG]
    assert len(types) == len(set(types))
    assert len(methods) == len(set(methods))
    assert CATALOG_BY_TYPE["PCGCreatePointsGridSettings"].method == "create_points_grid"
    assert CATALOG_BY_METHOD["static_mesh_spawner"].type == "PCGStaticMeshSpawnerSettings"
