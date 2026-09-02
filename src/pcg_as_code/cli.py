"""CLI: dump, diff, validate, mermaid, apply-script, apply-remote."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pcg_as_code.apply import to_apply_script, to_dump_script
from pcg_as_code.diff import diff_graphs, format_diff
from pcg_as_code.dump import dump as dump_file
from pcg_as_code.dump import load, to_mermaid
from pcg_as_code.validate import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pcg-as-code",
        description="Build, dump, and diff Unreal PCG graphs as data.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump", help="Rewrite a graph JSON into canonical form")
    p_dump.add_argument("path")
    p_dump.add_argument("-o", "--output")

    p_diff = sub.add_parser("diff", help="Structural diff of two graph dumps")
    p_diff.add_argument("old")
    p_diff.add_argument("new")
    p_diff.add_argument("--layout", action="store_true", help="Include node locations")
    p_diff.add_argument("--json", action="store_true", help="Emit JSON instead of text")

    p_val = sub.add_parser("validate", help="Validate a graph dump")
    p_val.add_argument("path")

    p_mmd = sub.add_parser("mermaid", help="Render a graph dump as mermaid")
    p_mmd.add_argument("path")

    p_apply = sub.add_parser(
        "apply-script",
        help="Emit an Unreal Python script to paste into a running editor",
    )
    p_apply.add_argument("path")
    p_apply.add_argument("--asset")
    p_apply.add_argument("-o", "--output")

    p_from = sub.add_parser(
        "dump-script",
        help="Emit an Unreal Python script that prints a live graph as JSON",
    )
    p_from.add_argument("asset_path")
    p_from.add_argument("-o", "--output")

    p_remote = sub.add_parser(
        "apply-remote",
        help="Send apply-script to a running editor via Python remote execution",
    )
    p_remote.add_argument("path")
    p_remote.add_argument("--asset")
    p_remote.add_argument("--timeout", type=float, default=5.0)

    args = parser.parse_args(argv)
    if args.cmd == "dump":
        data = load(args.path)
        if args.output:
            dump_file(data, args.output)
        else:
            sys.stdout.write(json.dumps(data.to_dict(), indent=2) + "\n")
        return 0
    if args.cmd == "diff":
        diff = diff_graphs(load(args.old), load(args.new), include_layout=args.layout)
        if args.json:
            sys.stdout.write(json.dumps(diff.to_dict(), indent=2) + "\n")
        else:
            sys.stdout.write(format_diff(diff))
        return 0 if diff.is_empty() else 1
    if args.cmd == "validate":
        errors = validate(load(args.path))
        if not errors:
            sys.stdout.write("ok\n")
            return 0
        for err in errors:
            sys.stderr.write(str(err) + "\n")
        return 2
    if args.cmd == "mermaid":
        sys.stdout.write(to_mermaid(load(args.path)))
        return 0
    if args.cmd == "apply-script":
        script = to_apply_script(load(args.path), asset_path=args.asset)
        if args.output:
            Path(args.output).write_text(script, encoding="utf-8")
        else:
            sys.stdout.write(script)
        return 0
    if args.cmd == "dump-script":
        script = to_dump_script(args.asset_path)
        if args.output:
            Path(args.output).write_text(script, encoding="utf-8")
        else:
            sys.stdout.write(script)
        return 0
    if args.cmd == "apply-remote":
        from pcg_as_code.remote import RemoteExecutionError, apply_remote

        script = to_apply_script(load(args.path), asset_path=args.asset)
        try:
            result = apply_remote(script, timeout=args.timeout)
        except RemoteExecutionError as exc:
            sys.stderr.write(str(exc) + "\n")
            return 3
        sys.stdout.write((result.output or "ok") + "\n")
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
