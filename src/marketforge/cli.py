from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .render import render_article
from .render_thesis import render_thesis_page
from .thesis import ThesisValidationError, build_dual_thesis_bundle, validate_thesis_bundle
from .validation import ValidationError, validate_run_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marketforge-validate")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate", help="validate a run bundle")
    validate.add_argument("bundle", type=Path)
    validate.add_argument("--render", type=Path, help="write validated article HTML")

    thesis = subcommands.add_parser(
        "thesis", help="build/validate dual-thesis from approved bundle"
    )
    thesis.add_argument("bundle", type=Path, help="approved parent run bundle")
    thesis.add_argument("--thesis", type=Path, help="optional existing thesis bundle to validate")
    thesis.add_argument("--render", type=Path, help="write dual-thesis HTML")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
            result = validate_run_bundle(bundle, artifact_root=args.bundle.parent)
            if args.render:
                args.render.parent.mkdir(parents=True, exist_ok=True)
                args.render.write_text(render_article(bundle), encoding="utf-8")
            print(f"PUBLISHABLE: {bundle['run']['run_id']}")
            if args.render:
                print(f"RENDERED: {args.render}")
            return 0 if result.publishable else 2

        if args.command == "thesis":
            approved = json.loads(args.bundle.read_text(encoding="utf-8"))
            if args.thesis:
                thesis = json.loads(args.thesis.read_text(encoding="utf-8"))
            else:
                thesis = build_dual_thesis_bundle(approved)
            result = validate_thesis_bundle(
                thesis,
                approved_bundle=approved,
                artifact_root=args.bundle.parent,
            )
            if args.render:
                args.render.parent.mkdir(parents=True, exist_ok=True)
                args.render.write_text(
                    render_thesis_page(thesis, approved_bundle=approved),
                    encoding="utf-8",
                )
            print(f"PUBLISHABLE_THESIS: {approved['run']['run_id']}")
            print(f"POPULAR_DIRECTION: {thesis.get('popular_direction')}")
            if args.render:
                print(f"RENDERED: {args.render}")
            return 0 if result.publishable else 2

    except (OSError, json.JSONDecodeError, ValidationError, ThesisValidationError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
