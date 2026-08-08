from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .render import render_article
from .validation import ValidationError, validate_run_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marketforge-validate")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate", help="validate a run bundle")
    validate.add_argument("bundle", type=Path)
    validate.add_argument("--render", type=Path, help="write validated article HTML")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        result = validate_run_bundle(bundle, artifact_root=args.bundle.parent)
        if args.render:
            args.render.parent.mkdir(parents=True, exist_ok=True)
            args.render.write_text(render_article(bundle), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    print(f"PUBLISHABLE: {bundle['run']['run_id']}")
    if args.render:
        print(f"RENDERED: {args.render}")
    return 0 if result.publishable else 2


if __name__ == "__main__":
    raise SystemExit(main())
