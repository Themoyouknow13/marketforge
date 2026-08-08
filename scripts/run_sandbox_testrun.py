"""Sandbox testrun: deploy dual-thesis agents against today's live MarketForge bundle."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from marketforge.render_thesis import render_thesis_page  # noqa: E402
from marketforge.sandbox_agents import run_sandbox_pipeline  # noqa: E402


def _find_latest_live_bundle() -> Path:
    runs = ROOT / "runs"
    candidates = sorted(runs.glob("live-*/run-bundle.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError("No live-*/run-bundle.json found under runs/")
    return candidates[0]


def _render_sandbox_trace(result: dict, parent_title: str) -> str:
    sandbox = result["sandbox"]
    rows = []
    for stage in sandbox["stages"]:
        status_color = "#7be0bd" if stage["status"] == "ok" else "#ff8f8f"
        notes = "; ".join(stage.get("notes") or []) or "—"
        err = stage.get("error") or "—"
        out_keys = ", ".join(sorted((stage.get("output") or {}).keys())) or "—"
        rows.append(
            f"<tr>"
            f"<td><code>{stage['agent']}</code></td>"
            f"<td style='color:{status_color}'><strong>{stage['status']}</strong></td>"
            f"<td>{stage['duration_ms']} ms</td>"
            f"<td>{notes}</td>"
            f"<td>{out_keys}</td>"
            f"<td>{err}</td>"
            f"</tr>"
        )
    thesis = result.get("thesis_bundle") or {}
    direction = thesis.get("popular_direction", "n/a")
    pol = thesis.get("polarization") or {}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sandbox Agent Trace — {sandbox.get('parent_run_id')}</title>
<style>
:root{{color-scheme:dark;font-family:Inter,system-ui,sans-serif}}
body{{margin:0;background:#071018;color:#e8f0f5}}
.shell{{max-width:1100px;margin:auto;padding:28px 18px 80px}}
.card{{background:#101d27;border:1px solid #223746;border-radius:16px;padding:18px;margin:16px 0}}
h1{{margin:0 0 8px}}
.muted{{color:#96a8b4}}
.ok{{color:#7be0bd}} .bad{{color:#ff8f8f}}
table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid #223746;vertical-align:top;font-size:.92rem}}
th{{color:#96a8b4;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}}
a{{color:#81bff8}}
code{{color:#cfe7ff}}
.badge{{display:inline-block;border:1px solid #223746;border-radius:999px;padding:.35rem .75rem;margin-right:8px}}
</style></head><body><div class="shell">
<div class="card">
  <div class="badge">MarketForge Sandbox</div>
  <div class="badge">Dual-Thesis Agents v1</div>
  <h1>Agent deployment testrun</h1>
  <p class="muted">Parent brief: {parent_title}</p>
  <p>Status:
    <strong class="{'ok' if sandbox['status']=='passed' else 'bad'}">{sandbox['status'].upper()}</strong>
    · parent run <code>{sandbox.get('parent_run_id')}</code>
    · as of <code>{sandbox.get('parent_as_of')}</code>
  </p>
  <p>Popular direction: <strong>{direction}</strong>
     · bull {len(pol.get('bull_support') or [])}
     · bear {len(pol.get('bear_support') or [])}
     · contested {len(pol.get('contested') or [])}
     · neutral {len(pol.get('neutral') or [])}
  </p>
  <p>
    <a href="dual-thesis.html">Open dual-thesis page →</a> ·
    <a href="index.html">Daily brief →</a> ·
    <a href="hub.html">Hub →</a>
  </p>
</div>
<div class="card">
  <h2>Stage trace</h2>
  <table>
    <thead><tr><th>Agent</th><th>Status</th><th>Duration</th><th>Notes</th><th>Output keys</th><th>Error</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<div class="card">
  <h2>Failed stages</h2>
  <p>{', '.join(sandbox.get('failed_stages') or []) or 'None'}</p>
  <p class="muted">Completed at {sandbox.get('completed_at')}</p>
</div>
</div></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    bundle_path = Path(args[0]).resolve() if args else _find_latest_live_bundle()
    if not bundle_path.exists():
        print(f"BLOCKED: bundle not found: {bundle_path}", file=sys.stderr)
        return 2

    approved = json.loads(bundle_path.read_text(encoding="utf-8"))
    print(f"[sandbox] parent_bundle={bundle_path}")
    print(f"[sandbox] parent_run={approved['run']['run_id']} as_of={approved['run']['as_of']}")
    print("[sandbox] deploying dual-thesis agent chain...")

    result = run_sandbox_pipeline(approved, artifact_root=str(bundle_path.parent))
    sandbox = result["sandbox"]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sandbox_dir = bundle_path.parent / f"sandbox-{stamp}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    # Persist full trace + per-stage outputs
    (sandbox_dir / "sandbox-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    for stage in sandbox["stages"]:
        stage_path = sandbox_dir / f"stage-{stage['agent']}.json"
        stage_path.write_text(json.dumps(stage, indent=2), encoding="utf-8")

    site_out = ROOT / "site" / "output"
    site_out.mkdir(parents=True, exist_ok=True)
    parent_title = approved.get("article", {}).get("title", "Daily Brief")

    trace_html = _render_sandbox_trace(result, parent_title)
    trace_name = f"sandbox-trace-{stamp}.html"
    (site_out / trace_name).write_text(trace_html, encoding="utf-8")
    (site_out / "sandbox-trace.html").write_text(trace_html, encoding="utf-8")

    if sandbox["status"] != "passed" or not result.get("thesis_bundle"):
        print("SANDBOX_FAILED:", sandbox["failed_stages"], file=sys.stderr)
        print("TRACE:", sandbox_dir)
        print("TRACE_HTML:", site_out / "sandbox-trace.html")
        return 2

    thesis = result["thesis_bundle"]
    thesis_path = bundle_path.parent / "thesis-bundle.sandbox.json"
    thesis_path.write_text(json.dumps(thesis, indent=2), encoding="utf-8")
    # Also refresh canonical thesis bundle used by site
    (bundle_path.parent / "thesis-bundle.json").write_text(
        json.dumps(thesis, indent=2), encoding="utf-8"
    )

    html = render_thesis_page(thesis, approved_bundle=approved)
    day = str(approved["run"]["as_of"])[:10]
    report_name = f"dual-thesis-{day}.html"
    (site_out / report_name).write_text(html, encoding="utf-8")
    (site_out / "dual-thesis.html").write_text(html, encoding="utf-8")
    (site_out / "dual-thesis.sandbox.html").write_text(html, encoding="utf-8")

    # Update hub with sandbox link
    (site_out / "hub.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MarketForge Hub</title>
<style>
body{{margin:0;background:#071018;color:#e8f0f5;font-family:Inter,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}}
.card{{max-width:620px;padding:28px;border:1px solid #223746;border-radius:18px;background:#101d27}}
a{{color:#7be0bd;display:block;margin:10px 0;font-size:1.05rem}}
.muted{{color:#96a8b4}}
.ok{{color:#7be0bd}}
</style></head><body><div class="card">
<h1>MarketForge Daily Hub</h1>
<p class="muted">Live package for {day}. Sandbox agent testrun: <span class="ok">PASSED</span></p>
<a href="index.html">1) Daily intelligence brief →</a>
<a href="dual-thesis.html">2) Bull / Bear · Popular / Contrarian →</a>
<a href="sandbox-trace.html">3) Sandbox agent deployment trace →</a>
</div></body></html>
""",
        encoding="utf-8",
    )

    print("SANDBOX_STATUS:", sandbox["status"])
    print(
        "STAGES:",
        ", ".join(f"{s['agent']}={s['status']}" for s in sandbox["stages"]),
    )
    print("POPULAR_DIRECTION:", thesis.get("popular_direction"))
    print("POLARIZATION:", {k: len(v) for k, v in (thesis.get("polarization") or {}).items()})
    print("THESIS:", thesis_path)
    print("REPORT:", site_out / report_name)
    print("TRACE_DIR:", sandbox_dir)
    print("TRACE_HTML:", site_out / "sandbox-trace.html")
    print("HUB:", site_out / "hub.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
