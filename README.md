# Pcg-as-code

Unreal PCG graphs as data. Git is the source of truth. The `.uasset` is a cache.

Build graphs in Python. Dump them to JSON. Diff them like code.
Same thesis as [gn-as-code](https://github.com/Plygonality/gn-as-code) and
[HDA-as-code](https://github.com/Plygonality/HDA-as-code), third DCC.

This is a library you import, not another `execute_python` wrapper, and not a
Plygon Unreal MCP. Format first. Live loop second.

```python
from pathlib import Path

from pcg_as_code.samples import build_deck_scatter

Path("graphs/deck_scatter.json").write_text(build_deck_scatter().dumps())
```

Or author any graph yourself:

```python
from pcg_as_code import Graph
from pcg_as_code.unit_canon import cell_size_vector

g = Graph("Deck Habitat Scatter")
cell = g.param_vector("CellSize", cell_size_vector())
grid = g.create_points_grid(cell_size=cell, grid_extents=(800, 0, 800), id="grid")
g.output(
    g.static_mesh_spawner(
        grid,
        meshes=[{"mesh": "/Game/HabitatKit/Modules/DeckTile", "weight": 1.0}],
        id="spawner",
    )
)
```

## Why this repo exists

A PCG graph in a `.uasset` is a binary blob. You cannot review it, diff it, or
let an agent iterate on it without opening the editor.

| Role | Job |
|---|---|
| **This library** | Typed builders, canonical JSON, structural diffs, golden tests |
| **Apply script / remote exec** | Push the JSON into a running editor. The `.uasset` is the cache |
| **Habitat-kit** | Later. States should compile into this format. Do not wait for that to ship the format |
| **The `.uasset`** | Working cache, never the source of truth |

v1 is **nodes + pins + graph defaults**. Unknown settings classes are still
valid via `Graph.node`. This is not a wrap of the Unreal Python API.

## Install

```bash
pip install -e ".[dev]"
```

Python 3.10+. No Unreal Editor required to build, dump, or diff.

## Quick demo

```bash
pip install -e ".[dev]"
python -c "from pcg_as_code.samples import build_deck_scatter; print(build_deck_scatter().dumps())"
pytest -q
```

That prints the shipped deck-scatter sample as canonical JSON, then runs the suite.

## Graph JSON

Dumps are stable: nodes sorted by id, links sorted, default settings omitted,
locations rounded. Pins and graph defaults are first-class data.

```json
{
  "format": "pcg-as-code",
  "version": 1,
  "name": "Deck Habitat Scatter",
  "kind": "GRAPH",
  "unreal": "5.5",
  "defaults": {
    "has_default_constructed_inputs": true,
    "params": [{"name": "CellSize", "type": "VECTOR", "default": [100, 100, 100]}]
  },
  "nodes": [
    {"id": "Input", "type": "Input", "pins": {"out": [{"label": "In", "usage": "Any"}]}},
    {"id": "Output", "type": "Output", "pins": {"in": [{"label": "Out", "usage": "Any"}]}},
    {
      "id": "grid",
      "type": "PCGCreatePointsGridSettings",
      "settings": {"cell_size": {"ref": "CellSize"}, "grid_extents": [800, 0, 800]},
      "pins": {"out": [{"label": "Out", "usage": "Spatial"}]}
    }
  ],
  "links": [
    {"from": ["grid", "Out"], "to": ["spawner", "In"]}
  ]
}
```

`id` is the stable name. Rename nodes in the builder, not in the editor, so diffs stay readable.

`type` is the Unreal settings class (`PCGCreatePointsGridSettings`, …) or `Input` / `Output`.

A setting value is a literal or `{"ref": "CellSize"}` (graph-default binding).

## Unit-canon

Deck scatter uses [Unit-canon](https://github.com/Plygonality/Unit-canon) cell
size: **1.0 m = 100 uu**. If `unit_canon` is installed, values are read from it.
Otherwise the same numbers are baked here so this format can ship first.

## Diff

```python
from pcg_as_code import diff_graphs, format_diff, loads

diff = diff_graphs(loads(old_json), loads(new_json))
print(format_diff(diff))
```

Locations are ignored unless you pass `include_layout=True`.

```bash
pcg-as-code dump graph.json
pcg-as-code diff old.json new.json
pcg-as-code validate graph.json
pcg-as-code mermaid graph.json
pcg-as-code apply-script graph.json --asset /Game/PCG/DeckHabitatScatter
pcg-as-code dump-script /Game/PCG/DeckHabitatScatter
```

## Apply in Unreal

There is no Plygon Unreal MCP in this repo. Two apply paths:

### 1. Paste a script (always works)

```python
from pcg_as_code.apply import to_apply_script
from pcg_as_code.samples import build_deck_scatter

script = to_apply_script(build_deck_scatter().to_data())
Path("apply_deck.py").write_text(script)
```

In a project with the PCG plugin enabled, open **Output Log → Cmd**, switch to
Python, and paste the script. It creates or replaces the PCG graph asset.

Dump a live graph the other way:

```python
from pcg_as_code.apply import to_dump_script

script = to_dump_script("/Game/PCG/DeckHabitatScatter")
```

If you are already inside the editor:

```python
from pcg_as_code.apply import apply, dump_from_unreal
apply(graph.to_data(), asset_path="/Game/PCG/DeckHabitatScatter")
```

### 2. Remote execution (running editor)

Enable **Editor Preferences → Python → Enable Remote Execution**. Then:

```bash
pcg-as-code apply-remote graphs/deck_scatter.json
```

If no editor answers, the command fails with that message. Paste the apply
script instead. This client only sends a script. It does not wrap Unreal.

## Typed builders

Common PCG nodes are methods on `Graph` (`create_points_grid`,
`static_mesh_spawner`, `surface_sampler`, `transform_points`, `density_filter`,
`copy_points`, `merge`, …). Pass a pin or a node handle to wire a link; pass a
literal or `ParamRef` to set a setting.

Anything not wrapped is still valid:

```python
g.node("PCGSelfPruningSettings", id="prune", inputs={"In": points}, settings={"radius_similarity_factor": 0.2})
```

Unknown settings classes are allowed. The catalog is how builders name pins and
skip defaults without the editor.

## Tests

```bash
pytest -q
UPDATE_GOLDENS=1 pytest tests/test_golden.py   # rewrite fixtures after an intentional dump change
```

Goldens live in `tests/goldens/`. If a builder change is intentional, update them. If it is not, the test failed for a reason.

## Layout

```
src/pcg_as_code/    library
examples/           sample graphs as Python
tests/goldens/      canonical JSON fixtures
```
