"""Unit-canon lengths used by PCG graphs.

This package does not depend on Unit-canon. If that package is installed,
values are read from it so Habitat-kit compile cannot drift. Otherwise the
numbers match ``Plygonality/Unit-canon`` as of schema 1.
"""

from __future__ import annotations

from dataclasses import dataclass

# Unreal's unit system, not ours. 1 authored meter = 100 Unreal units.
UU_PER_METER = 100.0
METERS_PER_GRID = 1.0
DECK_HEIGHT_M = 3.0
AIRLOCK_DIAMETER_M = 1.0
HUMAN_STANDING_HEIGHT_M = 1.8


@dataclass(frozen=True, slots=True)
class UnitCanon:
    """Unreal-side lengths derived from the unit canon."""

    uu_per_meter: float
    meters_per_grid: float
    cell_size_uu: float
    deck_height_uu: float
    airlock_diameter_uu: float
    human_standing_height_uu: float


def _from_unit_canon_package() -> UnitCanon | None:
    try:
        from unit_canon.unreal_export import conversion
    except ImportError:
        return None
    conv = conversion()
    return UnitCanon(
        uu_per_meter=float(conv.uu_per_meter),
        meters_per_grid=float(conv.grid_size_uu) / float(conv.uu_per_meter),
        cell_size_uu=float(conv.grid_size_uu),
        deck_height_uu=float(conv.deck_height_uu),
        airlock_diameter_uu=float(conv.airlock_diameter_uu),
        human_standing_height_uu=float(conv.human_standing_height_uu),
    )


def load() -> UnitCanon:
    packaged = _from_unit_canon_package()
    if packaged is not None:
        return packaged
    return UnitCanon(
        uu_per_meter=UU_PER_METER,
        meters_per_grid=METERS_PER_GRID,
        cell_size_uu=METERS_PER_GRID * UU_PER_METER,
        deck_height_uu=DECK_HEIGHT_M * UU_PER_METER,
        airlock_diameter_uu=AIRLOCK_DIAMETER_M * UU_PER_METER,
        human_standing_height_uu=HUMAN_STANDING_HEIGHT_M * UU_PER_METER,
    )


def cell_size_uu() -> float:
    """World-grid cell size in Unreal units. One Unit-canon grid cell."""
    return load().cell_size_uu


def cell_size_vector() -> tuple[float, float, float]:
    """Create-Points-Grid ``cell_size`` for a deck on the XY plane."""
    size = cell_size_uu()
    return (size, size, size)


def deck_height_uu() -> float:
    return load().deck_height_uu
