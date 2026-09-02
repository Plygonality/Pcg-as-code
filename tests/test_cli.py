from __future__ import annotations

import json
from pathlib import Path

from pcg_as_code import Graph
from pcg_as_code.cli import main
from pcg_as_code.samples import build_deck_scatter


def test_cli_dump_diff_validate(tmp_path: Path, capsys) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(build_deck_scatter().dumps(), encoding="utf-8")
    other = Graph("Other")
    other.output(other.surface_sampler(id="sampler"))
    b.write_text(other.dumps(), encoding="utf-8")

    assert main(["validate", str(a)]) == 0
    assert capsys.readouterr().out.strip() == "ok"

    out = tmp_path / "canonical.json"
    assert main(["dump", str(a), "-o", str(out)]) == 0
    assert json.loads(out.read_text())["name"] == "Deck Habitat Scatter"

    assert main(["diff", str(a), str(a)]) == 0
    assert main(["diff", str(a), str(b)]) == 1
    captured = capsys.readouterr().out
    assert "+ node" in captured or "- node" in captured

    assert main(["mermaid", str(a)]) == 0
    assert "flowchart LR" in capsys.readouterr().out

    assert main(["apply-script", str(a), "--asset", "/Game/PCG/DeckHabitatScatter"]) == 0
    script = capsys.readouterr().out
    assert "apply_graph_dict" in script


def test_cli_apply_remote_without_editor(tmp_path: Path, capsys) -> None:
    path = tmp_path / "graph.json"
    path.write_text(build_deck_scatter().dumps(), encoding="utf-8")
    code = main(["apply-remote", str(path), "--timeout", "0.2"])
    assert code == 3
    err = capsys.readouterr().err
    assert "No Unreal Editor" in err or "remote" in err.lower()
