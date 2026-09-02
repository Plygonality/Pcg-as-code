from __future__ import annotations

import os
from pathlib import Path

from pcg_as_code.dump import dumps
from pcg_as_code.samples import SAMPLES

GOLDEN_DIR = Path(__file__).resolve().parent / "goldens"


def test_sample_goldens() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    update = os.environ.get("UPDATE_GOLDENS") == "1"
    missing: list[str] = []
    for name, build in SAMPLES.items():
        got = dumps(build().to_data())
        path = GOLDEN_DIR / f"{name}.json"
        if update:
            path.write_text(got, encoding="utf-8")
        elif not path.exists():
            missing.append(name)
            continue
        expected = path.read_text(encoding="utf-8")
        assert got == expected, (
            f"{name} dump drifted from golden. "
            "Re-run with UPDATE_GOLDENS=1 if the change is intended."
        )
    assert not missing, f"Missing golden files for {missing}. Run UPDATE_GOLDENS=1 pytest tests/test_golden.py"
