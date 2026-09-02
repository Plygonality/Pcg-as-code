"""Pin kinds, graph kinds, and JSON-safe value helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
JsonValue = None | bool | int | float | str | list[Any] | dict[str, Any]


class GraphKind(str, Enum):
    """How Unreal should host the PCG asset."""

    GRAPH = "GRAPH"
    SUBGRAPH = "SUBGRAPH"


class PinUsage(str, Enum):
    """Stable PCG pin usages used in the dump format.

    These map to ``EPCGDataType`` names in apply/dump.
    """

    ANY = "Any"
    SPATIAL = "Spatial"
    POINT = "Point"
    SURFACE = "Surface"
    VOLUME = "Volume"
    PRIMITIVE = "Primitive"
    SPLINE = "Spline"
    LANDSCAPE = "Landscape"
    TEXTURE = "Texture"
    OTHER = "Other"
    PARAM = "Param"
    SETTINGS = "Settings"
    CONCRETE = "Concrete"


class ParamType(str, Enum):
    """Graph-default / user-parameter kinds."""

    FLOAT = "FLOAT"
    INT = "INT"
    BOOL = "BOOL"
    STRING = "STRING"
    VECTOR = "VECTOR"
    ROTATOR = "ROTATOR"
    NAME = "NAME"


def parse_pin_usage(value: str) -> PinUsage:
    key = value.strip().replace(" ", "")
    aliases = {
        "ANY": PinUsage.ANY,
        "SPATIAL": PinUsage.SPATIAL,
        "POINT": PinUsage.POINT,
        "POINTS": PinUsage.POINT,
        "SURFACE": PinUsage.SURFACE,
        "VOLUME": PinUsage.VOLUME,
        "PRIMITIVE": PinUsage.PRIMITIVE,
        "SPLINE": PinUsage.SPLINE,
        "LANDSCAPE": PinUsage.LANDSCAPE,
        "TEXTURE": PinUsage.TEXTURE,
        "OTHER": PinUsage.OTHER,
        "PARAM": PinUsage.PARAM,
        "PARAMS": PinUsage.PARAM,
        "ATTRIBUTESET": PinUsage.PARAM,
        "SETTINGS": PinUsage.SETTINGS,
        "CONCRETE": PinUsage.CONCRETE,
    }
    if key in aliases:
        return aliases[key]
    upper = key.upper()
    if upper in aliases:
        return aliases[upper]
    return PinUsage(key)


def parse_param_type(value: str) -> ParamType:
    key = value.strip().upper()
    aliases = {
        "BOOLEAN": ParamType.BOOL,
        "TOGGLE": ParamType.BOOL,
        "STR": ParamType.STRING,
        "VEC": ParamType.VECTOR,
        "VEC3": ParamType.VECTOR,
        "FLOAT3": ParamType.VECTOR,
        "ROTATION": ParamType.ROTATOR,
        "FNAME": ParamType.NAME,
    }
    if key in aliases:
        return aliases[key]
    return ParamType[key]


def round_number(value: float, digits: int = 6) -> float:
    rounded = round(float(value), digits)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def jsonify(value: Any) -> JsonValue:
    """Convert Unreal/Python values into JSON-safe, git-stable data."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return round_number(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): jsonify(v) for k, v in value.items()}
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [jsonify(v) for v in value]
    to_list = getattr(value, "to_list", None)
    if callable(to_list):
        return jsonify(to_list())
    if hasattr(value, "x") and hasattr(value, "y"):
        parts = [value.x, value.y]
        if hasattr(value, "z"):
            parts.append(value.z)
        if hasattr(value, "w"):
            parts.append(value.w)
        return jsonify(parts)
    path = getattr(value, "path", None)
    if callable(path):
        try:
            named = path()
        except TypeError:
            named = None
        if isinstance(named, str) and named:
            return named
    if isinstance(path, str) and path:
        return path
    name = getattr(value, "name", None)
    if callable(name):
        try:
            named = name()
        except TypeError:
            named = None
        if isinstance(named, str):
            return named
    if isinstance(name, str):
        return name
    return value


def is_param_ref(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"ref"} and isinstance(value.get("ref"), str)
