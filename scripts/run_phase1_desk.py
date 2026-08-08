"""Build Phase-1 Terminal Research desk page from an approved live bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from marketforge.desk import build_desk_payload  # noqa: E402
from marketforge.render import render_article  # noqa: E402
from marketforge.validation import ValidationError, validate_run_bundle  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        bundle_path = Path(args[0]).resolve()
    else:
        candidates = sorted((ROOT / "runs").glob("live-*/run-bundle.json"), reverse=True)
        if not candidates:
            print("BLOCKED: no live bundle found", file=sys.stderr)
            return 2
        bundle_path = candidates[0]

    inventory_path = bundle_path.parent / "scrape-inventory.json"
    inventory = {}
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    desk = build_desk_payload(bundle, inventory)
    bundle["article"]["desk"] = desk
    # Keep article.summary claim-linked; prefer desk summary only if grounded.
    bundle["article"]["summary"] = desk["summary"]
    bundle["article"]["summary_claim_ids"] = desk["summary_claim_ids"]

    try:
        result = validate_run_bundle(bundle, artifact_root=bundle_path.parent)
    except ValidationError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    out_bundle = bundle_path.parent / "run-bundle.desk.json"
    out_bundle.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    html = render_article(bundle)
    site_out = ROOT / "site" / "output"
    site_out.mkdir(parents=True, exist_ok=True)
    day = str(bundle["run"]["as_of"])[:10]
    report = site_out / f"live-brief-{day}.html"
    latest = site_out / "index.html"
    report.write_text(html, encoding="utf-8")
    latest.write_text(html, encoding="utf-8")

    # Refresh hub for desk UX
    (site_out / "hub.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MarketForge Desk</title>
<style>
:root{{color-scheme:dark;font-family:Inter,system-ui,sans-serif}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#070d14;color:#e7eef5}}
.card{{width:min(640px,92vw);border:1px solid #243445;border-radius:18px;background:#0f1822;padding:28px}}
.kicker{{color:#3dde9c;text-transform:uppercase;letter-spacing:.08em;font-size:.75rem;font-weight:700}}
h1{{margin:8px 0 10px;letter-spacing:-.03em}}
.muted{{color:#8fa3b5;line-height:1.6}}
a{{color:#3dde9c;display:block;margin:12px 0;text-decoration:none;font-size:1.05rem}}
a:hover{{color:#fff}}
</style></head><body><div class="card">
<div class="kicker">Terminal Research</div>
<h1>MarketForge Desk · {day}</h1>
<p class="muted">Phase 1 layout: meaning under every print, mover/filing cards, source chips to real URLs, evidence in a drawer.</p>
<a href="index.html">1) Daily desk brief →</a>
<a href="dual-thesis.html">2) Bull / Bear · Popular / Contrarian →</a>
<a href="sandbox-trace.html">3) Sandbox agent trace →</a>
</div></body></html>
""",
        encoding="utf-8",
    )

    print("PUBLISHABLE:", bundle["run"]["run_id"])
    print("DESIGN:", desk.get("design"))
    print("BUNDLE:", out_bundle)
    print("REPORT:", report)
    print("LATEST:", latest)
    print("STATUS:", "publishable" if result.publishable else "blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
