"""Catalog of common PCG nodes (Unreal 5.4 / 5.5).

Unknown nodes still work via ``Graph.node`` — the catalog exists so builders
can name pins, skip default settings, and validate links without the editor.
This is not a wrap of the Unreal Python API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pcg_as_code.types import PinUsage

PU = PinUsage

INPUT_TYPE = "Input"
OUTPUT_TYPE = "Output"


@dataclass(frozen=True)
class PinSpec:
    label: str
    usage: PinUsage
    allow_multiple: bool = False
    optional: bool = False


@dataclass(frozen=True)
class SettingSpec:
    name: str
    default: Any = None
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class NodeSpec:
    type: str
    method: str
    label: str
    inputs: tuple[PinSpec, ...] = ()
    outputs: tuple[PinSpec, ...] = ()
    settings: tuple[SettingSpec, ...] = ()

    def input_map(self) -> dict[str, PinSpec]:
        return {p.label: p for p in self.inputs}

    def output_map(self) -> dict[str, PinSpec]:
        return {p.label: p for p in self.outputs}

    def setting_map(self) -> dict[str, SettingSpec]:
        return {s.name: s for s in self.settings}

    def primary_output(self) -> PinSpec | None:
        if not self.outputs:
            return None
        for pin in self.outputs:
            if pin.label == "Out":
                return pin
        return self.outputs[0]

    def primary_input(self) -> PinSpec | None:
        if not self.inputs:
            return None
        for pin in self.inputs:
            if pin.label == "In":
                return pin
        return self.inputs[0]


def _pin(
    label: str,
    usage: PinUsage = PinUsage.SPATIAL,
    *,
    allow_multiple: bool = False,
    optional: bool = False,
) -> PinSpec:
    return PinSpec(label, usage, allow_multiple=allow_multiple, optional=optional)


def _s(name: str, default: Any = None, *items: str) -> SettingSpec:
    return SettingSpec(name, default, items)


_IN = _pin("In", PU.SPATIAL)
_OUT = _pin("Out", PU.SPATIAL)
_OVERRIDES = _pin("Overrides", PU.PARAM, optional=True)

_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec(
        INPUT_TYPE,
        "input_node",
        "Input",
        outputs=(_pin("In", PU.ANY),),
    ),
    NodeSpec(
        OUTPUT_TYPE,
        "output_node",
        "Output",
        inputs=(_pin("Out", PU.ANY),),
    ),
    NodeSpec(
        "PCGCreatePointsGridSettings",
        "create_points_grid",
        "Create Points Grid",
        inputs=(_OVERRIDES,),
        outputs=(_OUT,),
        settings=(
            _s("cell_size", (100.0, 100.0, 100.0)),
            _s("grid_extents", (100.0, 0.0, 100.0)),
            _s("point_steepness", 0.5),
            _s("coordinate_space", "Local", "Local", "World", "Original"),
            _s("cull_points_outside_volume", False),
        ),
    ),
    NodeSpec(
        "PCGCreatePointsSettings",
        "create_points",
        "Create Points",
        inputs=(_OVERRIDES,),
        outputs=(_OUT,),
        settings=(
            _s("grid_size", (100.0, 100.0, 100.0)),
            _s("coordinate_space", "Local", "Local", "World", "Original"),
        ),
    ),
    NodeSpec(
        "PCGSurfaceSamplerSettings",
        "surface_sampler",
        "Surface Sampler",
        inputs=(_pin("In", PU.SURFACE), _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("points_per_squared_meter", 0.1),
            _s("point_extents", (50.0, 50.0, 50.0)),
            _s("looseness", 0.0),
            _s("apply_density_to_points", True),
            _s("seed", 42),
        ),
    ),
    NodeSpec(
        "PCGVolumeSamplerSettings",
        "volume_sampler",
        "Volume Sampler",
        inputs=(_pin("In", PU.VOLUME), _OVERRIDES),
        outputs=(_OUT,),
        settings=(_s("voxel_size", (100.0, 100.0, 100.0)), _s("seed", 42)),
    ),
    NodeSpec(
        "PCGSplineSamplerSettings",
        "spline_sampler",
        "Spline Sampler",
        inputs=(_pin("In", PU.SPLINE), _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("mode", "Subdivision", "Subdivision", "Distance"),
            _s("subdivision", 10),
            _s("distance", 100.0),
        ),
    ),
    NodeSpec(
        "PCGStaticMeshSpawnerSettings",
        "static_mesh_spawner",
        "Static Mesh Spawner",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("meshes", ()),
            _s("synchronize_mesh_selector_attribute_name", False),
            _s("mesh_attribute_name", "Mesh"),
        ),
    ),
    NodeSpec(
        "PCGSpawnActorSettings",
        "spawn_actor",
        "Spawn Actor",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("actor", ""),
            _s("spawn_mode", "CollapseToOwner", "CollapseToOwner", "CreateNewChild"),
        ),
    ),
    NodeSpec(
        "PCGTransformPointsSettings",
        "transform_points",
        "Transform Points",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("offset_min", (0.0, 0.0, 0.0)),
            _s("offset_max", (0.0, 0.0, 0.0)),
            _s("rotation_min", (0.0, 0.0, 0.0)),
            _s("rotation_max", (0.0, 0.0, 0.0)),
            _s("scale_min", (1.0, 1.0, 1.0)),
            _s("scale_max", (1.0, 1.0, 1.0)),
            _s("absolute_offset", False),
            _s("absolute_rotation", False),
            _s("absolute_scale", False),
        ),
    ),
    NodeSpec(
        "PCGDensityFilterSettings",
        "density_filter",
        "Density Filter",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("lower_bound", 0.5),
            _s("upper_bound", 1.0),
            _s("invert_filter", False),
        ),
    ),
    NodeSpec(
        "PCGCopyPointsSettings",
        "copy_points",
        "Copy Points",
        inputs=(
            _pin("Source", PU.SPATIAL),
            _pin("Target", PU.SPATIAL),
            _OVERRIDES,
        ),
        outputs=(_OUT,),
        settings=(
            _s("rotation_inheritance", "Relative", "Relative", "Source", "Target"),
            _s("scale_inheritance", "Relative", "Relative", "Source", "Target"),
        ),
    ),
    NodeSpec(
        "PCGDifferenceSettings",
        "difference",
        "Difference",
        inputs=(
            _pin("In", PU.SPATIAL, allow_multiple=True),
            _pin("Differences", PU.SPATIAL, allow_multiple=True),
            _OVERRIDES,
        ),
        outputs=(_OUT,),
        settings=(_s("density_function", "Binary", "Binary", "Minimum", "Maximum"),),
    ),
    NodeSpec(
        "PCGIntersectionSettings",
        "intersection",
        "Intersection",
        inputs=(_pin("In", PU.SPATIAL, allow_multiple=True), _OVERRIDES),
        outputs=(_OUT,),
        settings=(_s("density_function", "Multiply", "Multiply", "Minimum"),),
    ),
    NodeSpec(
        "PCGSelfPruningSettings",
        "self_pruning",
        "Self Pruning",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("pruning_type", "LargeToSmall", "LargeToSmall", "SmallToLarge"),
            _s("radius_similarity_factor", 0.25),
        ),
    ),
    NodeSpec(
        "PCGBoundsModifierSettings",
        "bounds_modifier",
        "Bounds Modifier",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("mode", "Scale", "Scale", "Set", "Intersect"),
            _s("bounds_min", (-50.0, -50.0, -50.0)),
            _s("bounds_max", (50.0, 50.0, 50.0)),
        ),
    ),
    NodeSpec(
        "PCGAttributeNoiseSettings",
        "attribute_noise",
        "Attribute Noise",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("mode", "Range", "Range", "Offset"),
            _s("input_source", "Density"),
            _s("output_target", "Density"),
            _s("seed", 42),
        ),
    ),
    NodeSpec(
        "PCGDataFromActorSettings",
        "data_from_actor",
        "Get Actor Data",
        inputs=(_OVERRIDES,),
        outputs=(_OUT,),
        settings=(
            _s("actor_selector", {}),
            _s("mode", "ParseActorComponents", "ParseActorComponents", "GetSinglePoint"),
        ),
    ),
    NodeSpec(
        "PCGFilterByAttributeSettings",
        "filter_by_attribute",
        "Filter By Attribute",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("attribute", ""),
            _s("operator", "Equal", "Equal", "NotEqual", "Greater", "Lesser"),
        ),
    ),
    NodeSpec(
        "PCGNormalToDensitySettings",
        "normal_to_density",
        "Normal To Density",
        inputs=(_IN, _OVERRIDES),
        outputs=(_OUT,),
        settings=(
            _s("normal", (0.0, 0.0, 1.0)),
            _s("offset", 0.0),
            _s("strength", 1.0),
        ),
    ),
    NodeSpec(
        "PCGMergeSettings",
        "merge",
        "Merge",
        inputs=(_pin("In", PU.SPATIAL, allow_multiple=True), _OVERRIDES),
        outputs=(_OUT,),
    ),
)

CATALOG: tuple[NodeSpec, ...] = _SPECS
CATALOG_BY_TYPE: dict[str, NodeSpec] = {spec.type: spec for spec in _SPECS}
CATALOG_BY_METHOD: dict[str, NodeSpec] = {spec.method: spec for spec in _SPECS}


def get_spec(node_type: str) -> NodeSpec | None:
    if node_type in CATALOG_BY_TYPE:
        return CATALOG_BY_TYPE[node_type]
    # Accept U-prefixed or settings-stripped aliases.
    stripped = node_type[1:] if node_type.startswith("U") else node_type
    if stripped in CATALOG_BY_TYPE:
        return CATALOG_BY_TYPE[stripped]
    aliases = {
        "InputNode": CATALOG_BY_TYPE[INPUT_TYPE],
        "OutputNode": CATALOG_BY_TYPE[OUTPUT_TYPE],
    }
    return aliases.get(node_type)


def values_equal(left: Any, right: Any) -> bool:
    if left == right:
        return True
    if isinstance(left, dict) or isinstance(right, dict):
        return left == right
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(values_equal(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-9
    return False
