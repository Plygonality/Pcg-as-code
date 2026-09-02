"""Write example graph dumps next to this file."""

from pcg_as_code.samples import SAMPLES


def main() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parent
    for name, build in SAMPLES.items():
        text = build().dumps()
        (root / f"{name}.json").write_text(text, encoding="utf-8")
        print(f"wrote {name}.json ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
