"""Minimal in-memory Unreal stand-in for apply/dump tests."""

from __future__ import annotations

from typing import Any


class FakeVector:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class FakePinProperties:
    def __init__(self, label: str, usage: str = "Spatial") -> None:
        self.label = label
        self.allowed_types = usage

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class FakeEdge:
    def __init__(self, destination: FakePin) -> None:
        self.destination = destination
        self.input_pin = destination


class FakePin:
    def __init__(self, node: FakeNode, label: str, usage: str = "Spatial", output: bool = False) -> None:
        self.node = node
        self.properties = FakePinProperties(label, usage)
        self.edges: list[FakeEdge] = []
        self._output = output

    def is_output_pin(self) -> bool:
        return self._output

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class FakeSettings:
    def __init__(self, type_name: str) -> None:
        self._type_name = type_name
        self._props: dict[str, Any] = {}
        if type_name == "PCGStaticMeshSpawnerSettings":
            self.mesh_selector_parameters = FakeSelector()
            self.meshes: list[Any] = []

    def get_editor_property(self, name: str) -> Any:
        if name in self._props:
            return self._props[name]
        return getattr(self, name, None)

    def set_editor_property(self, name: str, value: Any) -> None:
        self._props[name] = value
        setattr(self, name, value)

    def editor_property_names(self) -> list[str]:
        names = set(self._props)
        names.update(k for k in vars(self) if not k.startswith("_") and k != "mesh_selector_parameters")
        return sorted(names)

    def __repr__(self) -> str:
        return f"<FakeSettings {self._type_name}>"


class FakeSelector:
    def __init__(self) -> None:
        self.mesh_entries: list[Any] = []

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class FakeMeshEntry:
    def __init__(self) -> None:
        self.weight = 1.0
        self.descriptor = FakeDescriptor()
        self.mesh = ""

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class FakeDescriptor:
    def __init__(self) -> None:
        self.static_mesh = ""

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class FakeNode:
    def __init__(self, settings: FakeSettings | None, *, role: str | None = None) -> None:
        self._settings = settings
        self.node_title = ""
        self.node_id = ""
        self.pcg_as_code_id = ""
        self.position_x = 0.0
        self.position_y = 0.0
        self.enabled = True
        self.input_pins: list[FakePin] = []
        self.output_pins: list[FakePin] = []
        if role == "input":
            self.output_pins = [FakePin(self, "In", "Any", output=True)]
        elif role == "output":
            self.input_pins = [FakePin(self, "Out", "Any")]
        else:
            self.input_pins = [FakePin(self, "In", "Spatial")]
            self.output_pins = [FakePin(self, "Out", "Spatial")]

    def get_settings(self) -> FakeSettings | None:
        return self._settings

    def set_node_position(self, x: float, y: float) -> None:
        self.position_x = float(x)
        self.position_y = float(y)

    def get_input_pins(self) -> list[FakePin]:
        return self.input_pins

    def get_output_pins(self) -> list[FakePin]:
        return self.output_pins

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def pin(self, label: str, *, output: bool | None = None) -> FakePin | None:
        pools = []
        if output is True:
            pools = [self.output_pins]
        elif output is False:
            pools = [self.input_pins]
        else:
            pools = [self.output_pins, self.input_pins]
        for pool in pools:
            for pin in pool:
                if pin.properties.label == label:
                    return pin
        return None


class FakeGraph:
    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path_name = path
        self.has_default_constructed_inputs = True
        self.graph_parameters: list[dict[str, Any]] = []
        self._input = FakeNode(None, role="input")
        self._output = FakeNode(None, role="output")
        self.nodes: list[FakeNode] = []

    def get_name(self) -> str:
        return self.name

    def get_path_name(self) -> str:
        return self.path_name

    def get_input_node(self) -> FakeNode:
        return self._input

    def get_output_node(self) -> FakeNode:
        return self._output

    def add_node_of_type(self, settings_class: type) -> tuple[FakeNode, FakeSettings]:
        type_name = getattr(settings_class, "__name__", str(settings_class))
        settings_cls = type(type_name, (FakeSettings,), {})
        settings = settings_cls(type_name)
        node = FakeNode(settings)
        if type_name == "PCGCopyPointsSettings":
            node.input_pins = [
                FakePin(node, "Source", "Spatial"),
                FakePin(node, "Target", "Spatial"),
            ]
        elif type_name == "PCGCreatePointsGridSettings":
            node.input_pins = []
        self.nodes.append(node)
        return node, settings

    def add_edge(self, src: FakeNode, src_pin: str, dst: FakeNode, dst_pin: str) -> FakeNode:
        out_pin = src.pin(src_pin, output=True)
        in_pin = dst.pin(dst_pin, output=False)
        if out_pin is None or in_pin is None:
            return dst
        out_pin.edges.append(FakeEdge(in_pin))
        return dst

    def remove_node(self, node: FakeNode) -> None:
        if node in self.nodes:
            self.nodes.remove(node)

    def set_graph_parameter(self, name: str, value: Any) -> None:
        for item in self.graph_parameters:
            if item.get("name") == name:
                item["default"] = value
                return
        self.graph_parameters.append({"name": name, "default": value})

    def get_editor_property(self, name: str) -> Any:
        return getattr(self, name)

    def set_editor_property(self, name: str, value: Any) -> None:
        setattr(self, name, value)


class _SettingsType:
    def __init__(self, name: str) -> None:
        self.__name__ = name


class FakeUnreal:
    """Enough of ``unreal`` for apply/dump tests. Not a wrap of the editor API."""

    def __init__(self) -> None:
        self.graphs: dict[str, FakeGraph] = {}
        self.Vector = FakeVector
        self.PCGMeshSelectorWeightedEntry = FakeMeshEntry
        self.PCGGraph = FakeGraph
        for name in (
            "PCGCreatePointsGridSettings",
            "PCGCreatePointsSettings",
            "PCGSurfaceSamplerSettings",
            "PCGVolumeSamplerSettings",
            "PCGSplineSamplerSettings",
            "PCGStaticMeshSpawnerSettings",
            "PCGSpawnActorSettings",
            "PCGTransformPointsSettings",
            "PCGDensityFilterSettings",
            "PCGCopyPointsSettings",
            "PCGDifferenceSettings",
            "PCGIntersectionSettings",
            "PCGSelfPruningSettings",
            "PCGBoundsModifierSettings",
            "PCGAttributeNoiseSettings",
            "PCGDataFromActorSettings",
            "PCGFilterByAttributeSettings",
            "PCGNormalToDensitySettings",
            "PCGMergeSettings",
        ):
            setattr(self, name, _SettingsType(name))

    def create_pcg_graph(self, asset_path: str, name: str) -> FakeGraph:
        graph = FakeGraph(name, asset_path)
        self.graphs[asset_path] = graph
        return graph

    def load_pcg_graph(self, asset_path: str) -> FakeGraph | None:
        return self.graphs.get(asset_path)

    def save_pcg_graph(self, graph: FakeGraph) -> None:
        self.graphs[graph.path_name] = graph
