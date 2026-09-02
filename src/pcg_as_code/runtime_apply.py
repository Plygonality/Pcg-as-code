"""Self-contained Unreal apply/dump runtime.

This module has no pcg-as-code imports so it can be pasted into the editor
Python console or sent over Python remote execution. The graph JSON is the
source of truth; the .uasset is the cache.
"""

from __future__ import annotations

FORMAT = "pcg-as-code"
FORMAT_VERSION = 1

INPUT_TYPE = "Input"
OUTPUT_TYPE = "Output"

_SKIP_SETTINGS = {
    "rna_type",
    "class",
    "seed_unbound",
    "cached",
    "debug",
    "debug_settings",
    "break_debugger",
    "enabled",
    "expose_to_library",
    "category",
    "description",
    "tags_applied_on_output",
    "filter_on_tags",
}


def apply_graph_dict(
    data,
    unreal,
    *,
    asset_path=None,
    replace=True,
):
    """Rebuild a PCG graph asset from a pcg-as-code dump.

    Returns the ``PCGGraph``. Creates the asset when it does not exist.
    """
    _validate_payload(data)
    path = asset_path or data.get("asset_path") or _default_asset_path(data["name"])
    graph = _get_or_create_graph(unreal, path, data["name"], replace)
    _apply_defaults(graph, data.get("defaults") or {})
    created = _rebuild_nodes(unreal, graph, data.get("nodes") or [], data.get("defaults") or {})
    _build_links(graph, created, data.get("links") or [])
    _save_asset(unreal, graph)
    return graph


def dump_graph(graph, *, unreal_version="5.5"):
    """Serialize a live PCG graph into a pcg-as-code dict."""
    nodes = []
    links = []
    input_node = _safe_call(graph, "get_input_node")
    output_node = _safe_call(graph, "get_output_node")
    extras = list(_graph_nodes(graph))
    ordered = []
    if input_node is not None:
        ordered.append(input_node)
    for node in extras:
        if node is input_node or node is output_node:
            continue
        ordered.append(node)
    if output_node is not None and output_node not in ordered:
        ordered.append(output_node)

    id_of = {}
    used = set()
    for node in ordered:
        node_id = _node_id(node, used)
        used.add(node_id)
        id_of[id(node)] = node_id
        nodes.append(_dump_node(node, node_id, input_node, output_node))

    for node in ordered:
        links.extend(_dump_links(node, id_of))

    payload = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "name": _object_name(graph),
        "kind": "GRAPH",
        "unreal": unreal_version,
        "asset_path": _object_path(graph),
        "defaults": _dump_defaults(graph),
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "links": sorted(
            links,
            key=lambda ln: (ln["from"][0], ln["from"][1], ln["to"][0], ln["to"][1]),
        ),
    }
    if not payload["asset_path"]:
        payload.pop("asset_path")
    return payload


def dump_graph_by_path(unreal, asset_path, *, unreal_version="5.5"):
    graph = _load_graph(unreal, asset_path)
    if graph is None:
        raise FileNotFoundError(f"No PCG graph at {asset_path!r}")
    return dump_graph(graph, unreal_version=unreal_version)


def _validate_payload(data):
    fmt = data.get("format")
    if fmt not in (None, FORMAT):
        raise ValueError(f"Unsupported graph format: {fmt!r}")
    version = data.get("version", FORMAT_VERSION)
    if int(version) != FORMAT_VERSION:
        raise ValueError(f"Unsupported pcg-as-code version: {version}")
    if "name" not in data:
        raise ValueError("Graph dump is missing name")


def _default_asset_path(name):
    safe = "".join(ch if ch.isalnum() else "" for ch in name)
    return f"/Game/PCG/{safe or 'PCGGraph'}"


def _get_or_create_graph(unreal, asset_path, name, replace):
    existing = _load_graph(unreal, asset_path)
    if existing is not None:
        if replace:
            _clear_graph(existing)
        return existing
    create = getattr(unreal, "create_pcg_graph", None)
    if callable(create):
        return create(asset_path, name)
    asset_tools = _asset_tools(unreal)
    factory = _pcg_factory(unreal)
    package_path, asset_name = _split_asset_path(asset_path)
    if asset_tools is not None and factory is not None:
        graph = asset_tools.create_asset(asset_name, package_path, _pcg_graph_class(unreal), factory)
        if graph is not None:
            return graph
    raise RuntimeError(
        f"Could not create PCG graph at {asset_path!r}. "
        "Pass a fake unreal with create_pcg_graph, or run inside the editor."
    )


def _load_graph(unreal, asset_path):
    loader = getattr(unreal, "load_pcg_graph", None)
    if callable(loader):
        return loader(asset_path)
    editor = getattr(unreal, "EditorAssetLibrary", None)
    if editor is None:
        return None
    load_asset = getattr(editor, "load_asset", None)
    if load_asset is None:
        return None
    try:
        return load_asset(asset_path)
    except Exception:
        return None


def _clear_graph(graph):
    input_node = _safe_call(graph, "get_input_node")
    output_node = _safe_call(graph, "get_output_node")
    for node in list(_graph_nodes(graph)):
        if node is input_node or node is output_node:
            continue
        remover = getattr(graph, "remove_node", None)
        if callable(remover):
            remover(node)


def _apply_defaults(graph, defaults):
    flag = defaults.get("has_default_constructed_inputs")
    if flag is not None:
        _set_prop(graph, "has_default_constructed_inputs", bool(flag))
    params = list(defaults.get("params") or [])
    if params:
        existing = getattr(graph, "graph_parameters", None)
        if existing is None or isinstance(existing, (list, dict)):
            graph.graph_parameters = params
    setter = getattr(graph, "set_graph_parameter", None)
    if not callable(setter):
        return
    for item in params:
        name = item.get("name")
        if not name:
            continue
        try:
            setter(name, item.get("default"))
        except Exception:
            continue


def _rebuild_nodes(unreal, graph, nodes_data, defaults):
    created = {}
    params = {item["name"]: item.get("default") for item in defaults.get("params") or [] if item.get("name")}
    input_node = _safe_call(graph, "get_input_node")
    output_node = _safe_call(graph, "get_output_node")
    if input_node is not None:
        created["Input"] = input_node
        _tag_node(input_node, "Input")
        _apply_node_body(
            unreal,
            input_node,
            _find_node(nodes_data, "Input", INPUT_TYPE),
            params,
        )
    if output_node is not None:
        created["Output"] = output_node
        _tag_node(output_node, "Output")
        _apply_node_body(
            unreal,
            output_node,
            _find_node(nodes_data, "Output", OUTPUT_TYPE),
            params,
        )

    for item in nodes_data:
        node_id = item["id"]
        node_type = item["type"]
        if node_type in (INPUT_TYPE, OUTPUT_TYPE) or node_id in created:
            continue
        settings_cls = _settings_class(unreal, node_type)
        adder = getattr(graph, "add_node_of_type", None)
        if adder is None:
            raise RuntimeError("PCGGraph.add_node_of_type is not available")
        result = adder(settings_cls)
        node, _settings = _unpack_add(result)
        _tag_node(node, node_id)
        _apply_node_body(unreal, node, item, params)
        created[node_id] = node
    return created


def _apply_node_body(unreal, node, item, params):
    if not item:
        return
    if item.get("label"):
        _set_prop(node, "node_title", item["label"])
    location = item.get("location")
    if location is not None:
        setter = getattr(node, "set_node_position", None)
        if callable(setter):
            setter(float(location[0]), float(location[1]))
        else:
            _set_prop(node, "position_x", float(location[0]))
            _set_prop(node, "position_y", float(location[1]))
    if item.get("enabled") is False:
        _set_prop(node, "enabled", False)
        settings = _node_settings(node)
        if settings is not None:
            _set_prop(settings, "enabled", False)
    settings = _node_settings(node)
    if settings is None:
        return
    for key, value in (item.get("settings") or {}).items():
        _apply_setting(unreal, settings, key, value, params)


def _apply_setting(unreal, settings, key, value, params):
    resolved = _resolve_setting_value(value, params)
    if resolved is None:
        return
    if key == "meshes":
        if _apply_meshes(unreal, settings, resolved):
            return
    if not _set_prop(settings, key, _to_unreal_value(unreal, resolved)):
        _set_prop(settings, key, resolved)


def _resolve_setting_value(value, params):
    if isinstance(value, dict) and "ref" in value and set(value) <= {"ref"}:
        return params.get(value["ref"])
    return value


def _apply_meshes(unreal, settings, meshes):
    if not isinstance(meshes, (list, tuple)):
        return False
    entries = []
    entry_cls = getattr(unreal, "PCGMeshSelectorWeightedEntry", None)
    for item in meshes:
        if not isinstance(item, dict):
            continue
        path = item.get("mesh") or item.get("path") or ""
        weight = item.get("weight", 1.0)
        if entry_cls is not None:
            entry = entry_cls()
            _set_prop(entry, "weight", weight)
            descriptor = _get_prop(entry, "descriptor")
            if descriptor is not None:
                mesh = _load_soft_mesh(unreal, path)
                _set_prop(descriptor, "static_mesh", mesh if mesh is not None else path)
            else:
                _set_prop(entry, "mesh", path)
            entries.append(entry)
        else:
            entries.append({"mesh": path, "weight": weight})
    selector = _get_prop(settings, "mesh_selector_parameters")
    if selector is not None and entries:
        if _set_prop(selector, "mesh_entries", entries):
            return True
    return _set_prop(settings, "meshes", entries if entries else meshes)


def _to_unreal_value(unreal, value):
    if value is None:
        return value
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, (int, float)) for v in value):
        vector_cls = getattr(unreal, "Vector", None)
        if vector_cls is not None and len(value) == 3:
            return vector_cls(float(value[0]), float(value[1]), float(value[2]))
        rotator_cls = getattr(unreal, "Rotator", None)
        if rotator_cls is not None and len(value) == 3:
            return value
    return value


def _build_links(graph, created, links):
    adder = getattr(graph, "add_edge", None)
    if adder is None:
        raise RuntimeError("PCGGraph.add_edge is not available")
    for link in links:
        src = created.get(link["from"][0])
        dst = created.get(link["to"][0])
        if src is None or dst is None:
            continue
        adder(src, str(link["from"][1]), dst, str(link["to"][1]))


def _dump_node(node, node_id, input_node, output_node):
    if node is input_node:
        node_type = INPUT_TYPE
    elif node is output_node:
        node_type = OUTPUT_TYPE
    else:
        settings = _node_settings(node)
        node_type = type(settings).__name__ if settings is not None else "PCGSettings"
    item = {"id": node_id, "type": node_type}
    title = _get_prop(node, "node_title")
    if title and str(title) not in (node_id, "", "None"):
        item["label"] = str(title)
    loc = _node_location(node)
    if loc is not None:
        item["location"] = [loc[0], loc[1]]
    settings = _node_settings(node)
    dumped_settings = _dump_settings(settings) if settings is not None else {}
    if dumped_settings:
        item["settings"] = dumped_settings
    pins = {"in": _dump_pins(node, output=False), "out": _dump_pins(node, output=True)}
    if pins["in"] or pins["out"]:
        item["pins"] = {k: v for k, v in pins.items() if v}
    return item


def _dump_settings(settings):
    payload = {}
    meshes = _dump_meshes(settings)
    if meshes:
        payload["meshes"] = meshes
    names = _editor_property_names(settings)
    for name in names:
        if name in _SKIP_SETTINGS or name in {
            "mesh_selector_parameters",
            "mesh_selector_instance",
            "mesh_selector_type",
        }:
            continue
        value = _get_prop(settings, name)
        if value is None:
            continue
        payload[name] = _json_value(value)
    return payload


def _dump_meshes(settings):
    selector = _get_prop(settings, "mesh_selector_parameters")
    entries = None
    if selector is not None:
        entries = _get_prop(selector, "mesh_entries")
    if entries is None:
        entries = _get_prop(settings, "meshes")
    if not entries:
        return []
    dumped = []
    for entry in list(entries):
        if isinstance(entry, dict):
            dumped.append(dict(entry))
            continue
        weight = _get_prop(entry, "weight")
        descriptor = _get_prop(entry, "descriptor")
        mesh = None
        if descriptor is not None:
            mesh = _get_prop(descriptor, "static_mesh")
        if mesh is None:
            mesh = _get_prop(entry, "mesh")
        dumped.append(
            {
                "mesh": _asset_ref(mesh),
                "weight": _json_value(weight if weight is not None else 1),
            }
        )
    return dumped


def _dump_pins(node, *, output):
    attr = "output_pins" if output else "input_pins"
    pins = _get_prop(node, attr)
    if pins is None:
        getter = getattr(node, "get_output_pins" if output else "get_input_pins", None)
        pins = getter() if callable(getter) else []
    dumped = []
    for pin in list(pins or []):
        props = _get_prop(pin, "properties")
        label = _get_prop(props, "label") if props is not None else _get_prop(pin, "label")
        usage = _get_prop(props, "allowed_types") if props is not None else _get_prop(pin, "usage")
        if label is None:
            continue
        item = {"label": str(label)}
        if usage is not None:
            item["usage"] = str(usage).split(".")[-1]
        dumped.append(item)
    return dumped


def _dump_links(node, id_of):
    links = []
    src_id = id_of.get(id(node))
    if src_id is None:
        return links
    pins = _get_prop(node, "output_pins")
    if pins is None:
        getter = getattr(node, "get_output_pins", None)
        pins = getter() if callable(getter) else []
    for pin in list(pins or []):
        props = _get_prop(pin, "properties")
        label = _get_prop(props, "label") if props is not None else _get_prop(pin, "label")
        edges = _get_prop(pin, "edges") or []
        for edge in list(edges):
            dest = _edge_destination(edge, pin)
            if dest is None:
                continue
            dest_node = _get_prop(dest, "node")
            dest_props = _get_prop(dest, "properties")
            dest_label = (
                _get_prop(dest_props, "label") if dest_props is not None else _get_prop(dest, "label")
            )
            dest_id = id_of.get(id(dest_node)) if dest_node is not None else None
            if dest_id is None or dest_label is None:
                continue
            links.append({"from": [src_id, str(label)], "to": [dest_id, str(dest_label)]})
    return links


def _edge_destination(edge, source_pin):
    for name in ("input_pin", "to_pin", "in_pin"):
        pin = _get_prop(edge, name)
        if pin is not None and pin is not source_pin:
            return pin
    # Fake / limited Python bindings store the destination pin directly.
    dest = getattr(edge, "destination", None)
    if dest is not None:
        return dest
    return None


def _dump_defaults(graph):
    defaults = {
        "has_default_constructed_inputs": bool(
            _get_prop(graph, "has_default_constructed_inputs")
            if _get_prop(graph, "has_default_constructed_inputs") is not None
            else True
        )
    }
    params = getattr(graph, "graph_parameters", None)
    if callable(params):
        params = params()
    dumped = []
    if isinstance(params, dict):
        for name, value in params.items():
            dumped.append({"name": str(name), "type": _guess_param_type(value), "default": _json_value(value)})
    elif isinstance(params, (list, tuple)):
        for item in params:
            if isinstance(item, dict) and "name" in item:
                dumped.append(item)
    if dumped:
        defaults["params"] = dumped
    return defaults


def _guess_param_type(value):
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, (list, tuple)):
        return "VECTOR"
    return "STRING"


def _graph_nodes(graph):
    nodes = _get_prop(graph, "nodes")
    if nodes is None:
        return []
    return list(nodes)


def _node_settings(node):
    getter = getattr(node, "get_settings", None)
    if callable(getter):
        return getter()
    return _get_prop(node, "settings")


def _node_id(node, used):
    tagged = _get_prop(node, "node_id") or _get_prop(node, "pcg_as_code_id")
    if tagged:
        return str(tagged)
    title = _get_prop(node, "node_title")
    if title and str(title) not in ("", "None"):
        candidate = str(title)
        if candidate not in used:
            return candidate
    settings = _node_settings(node)
    base = type(settings).__name__ if settings is not None else "node"
    if base.endswith("Settings"):
        base = base[: -len("Settings")]
    if base.startswith("PCG"):
        base = base[3:]
    candidate = base or "node"
    n = 1
    name = candidate
    while name in used:
        n += 1
        name = f"{candidate}_{n}"
    return name


def _tag_node(node, node_id):
    _set_prop(node, "node_id", node_id)
    _set_prop(node, "pcg_as_code_id", node_id)
    title = _get_prop(node, "node_title")
    if not title:
        _set_prop(node, "node_title", node_id)


def _node_location(node):
    setter_x = _get_prop(node, "position_x")
    setter_y = _get_prop(node, "position_y")
    if setter_x is not None and setter_y is not None:
        return (_json_value(setter_x), _json_value(setter_y))
    loc = _get_prop(node, "position")
    if loc is not None and hasattr(loc, "x"):
        return (_json_value(loc.x), _json_value(loc.y))
    return None


def _find_node(nodes_data, node_id, node_type):
    for item in nodes_data:
        if item.get("id") == node_id or item.get("type") == node_type:
            return item
    return None


def _unpack_add(result):
    if isinstance(result, tuple) and len(result) >= 1:
        node = result[0]
        settings = result[1] if len(result) > 1 else _node_settings(node)
        return node, settings
    return result, _node_settings(result)


def _settings_class(unreal, type_name):
    if hasattr(unreal, type_name):
        return getattr(unreal, type_name)
    find_class = getattr(unreal, "find_class", None)
    if callable(find_class):
        found = find_class(type_name)
        if found is not None:
            return found
    raise KeyError(f"Unknown PCG settings class: {type_name}")


def _pcg_graph_class(unreal):
    return getattr(unreal, "PCGGraph", None)


def _pcg_factory(unreal):
    cls = getattr(unreal, "PCGGraphFactory", None)
    return cls() if cls is not None else None


def _asset_tools(unreal):
    helpers = getattr(unreal, "AssetToolsHelpers", None)
    if helpers is None:
        return None
    getter = getattr(helpers, "get_asset_tools", None)
    return getter() if callable(getter) else None


def _split_asset_path(asset_path):
    trimmed = asset_path.rstrip("/")
    if "/" not in trimmed:
        return "/Game/PCG", trimmed
    package, name = trimmed.rsplit("/", 1)
    return package, name


def _save_asset(unreal, graph):
    saver = getattr(unreal, "save_pcg_graph", None)
    if callable(saver):
        saver(graph)
        return
    editor = getattr(unreal, "EditorAssetLibrary", None)
    if editor is None:
        return
    save = getattr(editor, "save_loaded_asset", None)
    if callable(save):
        try:
            save(graph)
        except Exception:
            return


def _load_soft_mesh(unreal, path):
    if not path:
        return None
    loader = getattr(unreal, "EditorAssetLibrary", None)
    if loader is None:
        return path
    load_asset = getattr(loader, "load_asset", None)
    if not callable(load_asset):
        return path
    try:
        return load_asset(path)
    except Exception:
        return path


def _asset_ref(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    path = getattr(value, "get_path_name", None)
    if callable(path):
        try:
            return str(path())
        except Exception:
            pass
    named = getattr(value, "path_name", None)
    if isinstance(named, str):
        return named
    return str(value)


def _object_name(obj):
    getter = getattr(obj, "get_name", None)
    if callable(getter):
        return str(getter())
    name = getattr(obj, "name", None)
    if callable(name):
        try:
            return str(name())
        except TypeError:
            pass
    if isinstance(name, str) and name:
        return name
    return "PCGGraph"


def _object_path(obj):
    getter = getattr(obj, "get_path_name", None)
    if callable(getter):
        path = str(getter())
        return path.split(".", 1)[0]
    path = getattr(obj, "path_name", None)
    if isinstance(path, str):
        return path.split(".", 1)[0]
    return ""


def _editor_property_names(obj):
    getter = getattr(obj, "editor_property_names", None)
    if callable(getter):
        return list(getter())
    names = getattr(obj, "_editor_properties", None)
    if names:
        return list(names)
    dumped = []
    for key, value in vars(obj).items() if hasattr(obj, "__dict__") else []:
        if key.startswith("_"):
            continue
        if callable(value):
            continue
        dumped.append(key)
    return dumped


def _get_prop(obj, name):
    if obj is None:
        return None
    getter = getattr(obj, "get_editor_property", None)
    if callable(getter):
        try:
            return getter(name)
        except Exception:
            pass
    return getattr(obj, name, None)


def _set_prop(obj, name, value):
    if obj is None:
        return False
    setter = getattr(obj, "set_editor_property", None)
    if callable(setter):
        try:
            setter(name, value)
            return True
        except Exception:
            pass
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _safe_call(obj, name):
    method = getattr(obj, name, None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:
        return None


def _json_value(value):
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        rounded = round(float(value), 6)
        return int(rounded) if rounded == int(rounded) else rounded
    if hasattr(value, "x") and hasattr(value, "y"):
        parts = [value.x, value.y]
        if hasattr(value, "z"):
            parts.append(value.z)
        return [_json_value(p) for p in parts]
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    return str(value)
