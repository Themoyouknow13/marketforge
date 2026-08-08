"""Build dual-thesis page from an approved MarketForge run bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from marketforge.render_thesis import render_thesis_page  # noqa: E402
from marketforge.thesis import (  # noqa: E402
    ThesisValidationError,
    build_dual_thesis_bundle,
    validate_thesis_bundle,
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "Usage: python scripts/run_dual_thesis.py <approved-run-bundle.json>",
            file=sys.stderr,
        )
        return 2

    bundle_path = Path(args[0]).resolve()
    if not bundle_path.exists():
        print(f"Bundle not found: {bundle_path}", file=sys.stderr)
        return 2

    try:
        approved = json.loads(bundle_path.read_text(encoding="utf-8"))
        thesis = build_dual_thesis_bundle(approved)
        validate_thesis_bundle(
            thesis,
            approved_bundle=approved,
            artifact_root=bundle_path.parent,
        )
    except (OSError, json.JSONDecodeError, ThesisValidationError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    out_dir = bundle_path.parent
    site_out = ROOT / "site" / "output"
    site_out.mkdir(parents=True, exist_ok=True)

    thesis_path = out_dir / "thesis-bundle.json"
    thesis_path.write_text(json.dumps(thesis, indent=2), encoding="utf-8")

    html = render_thesis_page(thesis, approved_bundle=approved)
    as_of_day = str(approved["run"]["as_of"])[:10]
    report_name = f"dual-thesis-{as_of_day}.html"
    report_path = site_out / report_name
    latest_path = site_out / "dual-thesis.html"
    report_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")

    # Lightweight hub linking brief + thesis
    hub = site_out / "hub.html"
    hub.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MarketForge Hub</title>
<style>
body{{margin:0;background:#071018;color:#e8f0f5;font-family:Inter,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}}
.card{{max-width:560px;padding:28px;border:1px solid #223746;border-radius:18px;background:#101d27}}
a{{color:#7be0bd;display:block;margin:10px 0;font-size:1.05rem}}
.muted{{color:#96a8b4}}
</style></head><body><div class="card">
<h1>MarketForge Daily Hub</h1>
<p class="muted">Factual brief and dual-thesis supplement for {as_of_day}.</p>
<a href="index.html">Daily intelligence brief →</a>
<a href="{report_name}">Bull / Bear · Popular / Contrarian →</a>
</div></body></html>
""",
        encoding="utf-8",
    )

    print("PUBLISHABLE_THESIS:", approved["run"]["run_id"])
    print("THESIS_BUNDLE:", thesis_path)
    print("REPORT:", report_path)
    print("LATEST:", latest_path)
    print("HUB:", hub)
    print("POPULAR_DIRECTION:", thesis.get("popular_direction"))
    print(
        "POLARIZATION:",
        {k: len(v) for k, v in (thesis.get("polarization") or {}).items()},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
