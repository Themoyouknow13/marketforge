"""End-to-end MarketForge demo: build grounded bundle → validate → render shippable HTML."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from marketforge.monte_carlo import run_dcf_simulation  # noqa: E402
from marketforge.render import render_article  # noqa: E402
from marketforge.validation import ValidationError, validate_run_bundle  # noqa: E402


def write_snapshot(path: Path, text: str) -> str:
    # Write exact UTF-8 bytes (LF newlines) so the on-disk SHA-256 is stable on Windows.
    payload = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    as_of_iso = as_of.isoformat().replace("+00:00", "Z")
    run_id = f"demo-{as_of.strftime('%Y%m%d-%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    snaps = run_dir / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "site" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Source snapshots (all publishable facts must come from these) ---
    market_text = (
        "MarketForge DEMO market tape for educational pipeline testing only.\n"
        "S&P 500 closed at 5,420.15, up 0.85% on the session.\n"
        "Nasdaq-100 closed at 19,180.40, up 1.20%.\n"
        "VIX settled at 14.8.\n"
        "Top gainer in the demo universe: DEMO-A rose 6.4% on volume of 18.2 million shares, "
        "about 2.4x its 20-day average volume.\n"
        "Top laggard in the demo universe: DEMO-B fell 3.1% after a quiet session with no new filing.\n"
        "Sector leadership: Information Technology +1.6%, Energy -0.7%.\n"
    )
    sec_text = (
        "MarketForge DEMO 8-K excerpt for DEMO-A (educational fixture, not a real SEC filing).\n"
        "Item 2.02 Results of Operations and Financial Condition.\n"
        "For the quarter ended June 30, 2026, DEMO-A reported revenue of $412 million, "
        "compared with $348 million in the prior-year quarter.\n"
        "Operating cash flow was $91 million for the same quarter.\n"
        "Management stated: backlog stood at $1.85 billion at June 30, 2026.\n"
        "The company also disclosed a $40 million share repurchase completed during the quarter.\n"
    )
    form4_text = (
        "MarketForge DEMO Form 4 cluster summary for DEMO-A (educational fixture).\n"
        "Over the five trading days ended August 7, 2026, three open-market sales totaled "
        "42,000 shares and one purchase totaled 5,000 shares.\n"
        "Net insider activity was a sale of 37,000 shares.\n"
        "No 10b5-1 plan was disclosed in this demo excerpt.\n"
    )
    news_text = (
        "MarketForge DEMO news desk note (educational fixture).\n"
        "Sell-side commentary described DEMO-A demand as resilient, while peer DEMO-C guided "
        "conservatively on second-half volumes.\n"
        "Overall market narrative in this demo: risk-on with selective rotation into growth.\n"
    )

    market_hash = write_snapshot(snaps / "market-tape.txt", market_text)
    sec_hash = write_snapshot(snaps / "demo-a-8k.txt", sec_text)
    form4_hash = write_snapshot(snaps / "demo-a-form4.txt", form4_text)
    news_hash = write_snapshot(snaps / "news-desk.txt", news_text)

    # Deterministic calculation claim: revenue growth (412-348)/348
    growth = (412.0 - 348.0) / 348.0  # ≈ 0.183908...

    # Monte Carlo on explicit demo assumptions (not a real company valuation)
    assumptions = {
        "base_fcf": 91.0,
        "shares_outstanding": 120.0,
        "net_debt": 180.0,
        "forecast_years": 5,
        "revenue_growth": {
            "distribution": "normal",
            "mean": 0.10,
            "std": 0.03,
            "min": 0.02,
            "max": 0.18,
        },
        "fcf_margin": {
            "distribution": "normal",
            "mean": 0.18,
            "std": 0.02,
            "min": 0.12,
            "max": 0.24,
        },
        "wacc": {
            "distribution": "normal",
            "mean": 0.095,
            "std": 0.01,
            "min": 0.08,
            "max": 0.12,
        },
        "terminal_growth": {
            "distribution": "normal",
            "mean": 0.025,
            "std": 0.005,
            "min": 0.01,
            "max": 0.035,
        },
    }
    sim = run_dcf_simulation(assumptions, iterations=10_000, seed=42)
    sim_result = {k: v for k, v in sim.items() if k not in {"result_sha256", "code_sha256"}}
    median_iv = round(float(sim["median"]), 2)
    p05 = round(float(sim["p05"]), 2)
    p95 = round(float(sim["p95"]), 2)

    sources = [
        {
            "id": "src-market",
            "url": "https://example.local/marketforge/demo/market-tape",
            "title": "Demo market tape",
            "publisher": "MarketForge Demo",
            "tier": 2,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/market-tape.txt",
            "content_sha256": market_hash,
        },
        {
            "id": "src-8k",
            "url": "https://example.local/marketforge/demo/demo-a-8k",
            "title": "DEMO-A Item 2.02 8-K excerpt",
            "publisher": "MarketForge Demo SEC Fixture",
            "tier": 1,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/demo-a-8k.txt",
            "content_sha256": sec_hash,
        },
        {
            "id": "src-form4",
            "url": "https://example.local/marketforge/demo/demo-a-form4",
            "title": "DEMO-A Form 4 cluster summary",
            "publisher": "MarketForge Demo SEC Fixture",
            "tier": 1,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/demo-a-form4.txt",
            "content_sha256": form4_hash,
        },
        {
            "id": "src-news",
            "url": "https://example.local/marketforge/demo/news-desk",
            "title": "Demo news desk note",
            "publisher": "MarketForge Demo",
            "tier": 3,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/news-desk.txt",
            "content_sha256": news_hash,
        },
    ]

    evidence = [
        {
            "id": "ev-spx",
            "source_id": "src-market",
            "kind": "quote",
            "quote": "S&P 500 closed at 5,420.15, up 0.85% on the session.",
            "locator": {"section": "Index closes"},
        },
        {
            "id": "ev-ndx",
            "source_id": "src-market",
            "kind": "quote",
            "quote": "Nasdaq-100 closed at 19,180.40, up 1.20%.",
            "locator": {"section": "Index closes"},
        },
        {
            "id": "ev-vix",
            "source_id": "src-market",
            "kind": "quote",
            "quote": "VIX settled at 14.8.",
            "locator": {"section": "Volatility"},
        },
        {
            "id": "ev-demo-a-move",
            "source_id": "src-market",
            "kind": "quote",
            "quote": (
                "Top gainer in the demo universe: DEMO-A rose 6.4% on volume of 18.2 million shares, "
                "about 2.4x its 20-day average volume."
            ),
            "locator": {"section": "Movers"},
        },
        {
            "id": "ev-demo-b-move",
            "source_id": "src-market",
            "kind": "quote",
            "quote": "Top laggard in the demo universe: DEMO-B fell 3.1% after a quiet session with no new filing.",
            "locator": {"section": "Movers"},
        },
        {
            "id": "ev-sectors",
            "source_id": "src-market",
            "kind": "quote",
            "quote": "Sector leadership: Information Technology +1.6%, Energy -0.7%.",
            "locator": {"section": "Sectors"},
        },
        {
            "id": "ev-rev",
            "source_id": "src-8k",
            "kind": "quote",
            "quote": (
                "For the quarter ended June 30, 2026, DEMO-A reported revenue of $412 million, "
                "compared with $348 million in the prior-year quarter."
            ),
            "locator": {"section": "Item 2.02", "page": 2},
        },
        {
            "id": "ev-ocf",
            "source_id": "src-8k",
            "kind": "quote",
            "quote": "Operating cash flow was $91 million for the same quarter.",
            "locator": {"section": "Item 2.02", "page": 2},
        },
        {
            "id": "ev-backlog",
            "source_id": "src-8k",
            "kind": "quote",
            "quote": "Management stated: backlog stood at $1.85 billion at June 30, 2026.",
            "locator": {"section": "Item 2.02", "page": 3},
        },
        {
            "id": "ev-buyback",
            "source_id": "src-8k",
            "kind": "quote",
            "quote": "The company also disclosed a $40 million share repurchase completed during the quarter.",
            "locator": {"section": "Item 2.02", "page": 3},
        },
        {
            "id": "ev-insider",
            "source_id": "src-form4",
            "kind": "quote",
            "quote": "Net insider activity was a sale of 37,000 shares.",
            "locator": {"section": "Form 4 cluster"},
        },
        {
            "id": "ev-narrative",
            "source_id": "src-news",
            "kind": "quote",
            "quote": "Overall market narrative in this demo: risk-on with selective rotation into growth.",
            "locator": {"section": "Narrative"},
        },
        {
            "id": "ev-sim-input",
            "source_id": "src-8k",
            "kind": "quote",
            "quote": "Operating cash flow was $91 million for the same quarter.",
            "locator": {"section": "Item 2.02", "page": 2},
        },
    ]

    claims = [
        {
            "id": "cl-spx",
            "text": "The S&P 500 closed at 5,420.15, up 0.85%.",
            "claim_type": "fact",
            "evidence_ids": ["ev-spx"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-ndx",
            "text": "The Nasdaq-100 closed at 19,180.40, up 1.20%.",
            "claim_type": "fact",
            "evidence_ids": ["ev-ndx"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-vix",
            "text": "The VIX settled at 14.8.",
            "claim_type": "fact",
            "evidence_ids": ["ev-vix"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-demo-a-move",
            "text": "DEMO-A rose 6.4% on 18.2 million shares, about 2.4x average volume.",
            "claim_type": "fact",
            "evidence_ids": ["ev-demo-a-move"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-demo-b-move",
            "text": "DEMO-B fell 3.1% with no new filing in the demo tape.",
            "claim_type": "fact",
            "evidence_ids": ["ev-demo-b-move"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-sectors",
            "text": "Information Technology led at +1.6% while Energy lagged at -0.7%.",
            "claim_type": "fact",
            "evidence_ids": ["ev-sectors"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-rev",
            "text": "DEMO-A reported quarterly revenue of $412 million versus $348 million a year earlier.",
            "claim_type": "fact",
            "evidence_ids": ["ev-rev"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-growth",
            "text": "DEMO-A quarterly revenue growth was 18.39%.",
            "claim_type": "calculation",
            "evidence_ids": ["ev-rev"],
            "as_of": as_of_iso,
            "calculation": {
                "operator": "growth_rate",
                "inputs": {"current": 412.0, "previous": 348.0},
                "reported": round(growth, 4),
                "tolerance": 1e-4,
            },
        },
        {
            "id": "cl-ocf",
            "text": "DEMO-A operating cash flow was $91 million in the quarter.",
            "claim_type": "fact",
            "evidence_ids": ["ev-ocf"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-backlog",
            "text": "DEMO-A backlog stood at $1.85 billion at June 30, 2026.",
            "claim_type": "fact",
            "evidence_ids": ["ev-backlog"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-buyback",
            "text": "DEMO-A completed a $40 million share repurchase during the quarter.",
            "claim_type": "fact",
            "evidence_ids": ["ev-buyback"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-insider",
            "text": "Net insider activity was a sale of 37,000 shares over five trading days.",
            "claim_type": "fact",
            "evidence_ids": ["ev-insider"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-narrative",
            "text": "The demo market narrative was risk-on with selective rotation into growth.",
            "claim_type": "interpretation",
            "evidence_ids": ["ev-narrative", "ev-spx", "ev-ndx"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-sim",
            "text": (
                f"A reproducible DCF Monte Carlo (10,000 iterations, seed 42) on demo assumptions "
                f"produced a median intrinsic value of ${median_iv}, with a 5th–95th percentile band "
                f"of ${p05} to ${p95}."
            ),
            "claim_type": "simulation",
            "evidence_ids": ["ev-sim-input"],
            "as_of": as_of_iso,
            "simulation": {
                "model_version": sim["model_version"],
                "code_sha256": sim["code_sha256"],
                "seed": sim["seed"],
                "iterations": sim["iterations"],
                "assumptions": assumptions,
                "result": sim_result,
                "result_sha256": sim["result_sha256"],
            },
        },
        {
            "id": "cl-watch",
            "text": "The single metric to watch next is DEMO-A backlog conversion against the $1.85 billion figure.",
            "claim_type": "interpretation",
            "evidence_ids": ["ev-backlog"],
            "as_of": as_of_iso,
        },
    ]

    article = {
        "title": f"MarketForge Daily Brief — {as_of.strftime('%B %d, %Y')}",
        "summary": (
            "Equities finished higher in this educational demo session, with the S&P 500 at 5,420.15 "
            "(+0.85%) and the Nasdaq-100 at 19,180.40 (+1.20%). DEMO-A led on a 6.4% move after reporting "
            "$412 million in quarterly revenue and $1.85 billion of backlog. This report is a pipeline "
            "fixture for hosting tests — not live market advice."
        ),
        "summary_claim_ids": [
            "cl-spx",
            "cl-ndx",
            "cl-demo-a-move",
            "cl-rev",
            "cl-backlog",
        ],
        "sections": [
            {
                "heading": "Market Overview",
                "paragraphs": [
                    {
                        "text": (
                            "U.S. equity benchmarks advanced in the demo tape. The S&P 500 closed at "
                            "5,420.15, up 0.85%, while the Nasdaq-100 closed at 19,180.40, up 1.20%. "
                            "The VIX settled at 14.8, consistent with a calm risk-on tape in this fixture."
                        ),
                        "claim_ids": ["cl-spx", "cl-ndx", "cl-vix"],
                    },
                    {
                        "text": (
                            "Sector leadership favored Information Technology at +1.6%, while Energy "
                            "lagged at -0.7%. The broader demo narrative was risk-on with selective "
                            "rotation into growth."
                        ),
                        "claim_ids": ["cl-sectors", "cl-narrative"],
                    },
                ],
            },
            {
                "heading": "Top Movers & Why",
                "paragraphs": [
                    {
                        "text": (
                            "DEMO-A rose 6.4% on 18.2 million shares, about 2.4x average volume, after "
                            "the demo 8-K highlighted stronger results and a large backlog."
                        ),
                        "claim_ids": ["cl-demo-a-move", "cl-rev", "cl-backlog"],
                    },
                    {
                        "text": (
                            "DEMO-B fell 3.1% with no new filing in the demo tape, making it the session's "
                            "primary laggard in this educational universe."
                        ),
                        "claim_ids": ["cl-demo-b-move"],
                    },
                ],
            },
            {
                "heading": "SEC Highlights",
                "paragraphs": [
                    {
                        "text": (
                            "DEMO-A's operations update reported revenue of $412 million versus "
                            "$348 million a year earlier. Deterministic recomputation puts quarterly "
                            "revenue growth at 18.39%."
                        ),
                        "claim_ids": ["cl-rev", "cl-growth"],
                    },
                    {
                        "text": (
                            "Operating cash flow was $91 million. Management also reported backlog of "
                            "$1.85 billion at June 30, 2026 and a completed $40 million share repurchase."
                        ),
                        "claim_ids": ["cl-ocf", "cl-backlog", "cl-buyback"],
                    },
                    {
                        "text": (
                            "Insider filing activity in the demo window showed net selling of 37,000 shares "
                            "over five trading days. That is a watch item, not a standalone thesis flip."
                        ),
                        "claim_ids": ["cl-insider"],
                    },
                ],
            },
            {
                "heading": "Deep Dive — DEMO-A Fundamentals & Valuation Fixture",
                "paragraphs": [
                    {
                        "text": (
                            "Fundamentally, the demo filing links the price move to revenue of $412 million, "
                            "cash generation of $91 million, and backlog visibility at $1.85 billion."
                        ),
                        "claim_ids": ["cl-rev", "cl-ocf", "cl-backlog"],
                    },
                    {
                        "text": (
                            f"A reproducible DCF Monte Carlo (10,000 iterations, seed 42) on demo assumptions "
                            f"produced a median intrinsic value of ${median_iv}, with a 5th–95th percentile band "
                            f"of ${p05} to ${p95}. These outputs are educational pipeline fixtures only."
                        ),
                        "claim_ids": ["cl-sim"],
                    },
                ],
            },
            {
                "heading": "Sentiment & Positioning Snapshot",
                "paragraphs": [
                    {
                        "text": (
                            "The demo news desk characterized the session as risk-on with selective rotation "
                            "into growth, aligning with the stronger Nasdaq-100 print at 19,180.40 (+1.20%) "
                            "and softer Energy performance at -0.7%."
                        ),
                        "claim_ids": ["cl-narrative", "cl-ndx", "cl-sectors"],
                    }
                ],
            },
            {
                "heading": "Watchlist & Key Metric",
                "paragraphs": [
                    {
                        "text": (
                            "Priority names in this fixture: DEMO-A (filing + volume thrust), DEMO-B "
                            "(laggard without catalyst), and the Information Technology leadership tape at +1.6%."
                        ),
                        "claim_ids": ["cl-demo-a-move", "cl-demo-b-move", "cl-sectors"],
                    },
                    {
                        "text": (
                            "The single metric to watch next is DEMO-A backlog conversion against the "
                            "$1.85 billion figure."
                        ),
                        "claim_ids": ["cl-watch", "cl-backlog"],
                    },
                ],
            },
            {
                "heading": "Risk Flags",
                "paragraphs": [
                    {
                        "text": (
                            "Key cautions in the demo package: net insider selling of 37,000 shares, "
                            "dependence on backlog conversion from the $1.85 billion total, and the fact "
                            "that this entire report is a synthetic fixture for website hosting tests."
                        ),
                        "claim_ids": ["cl-insider", "cl-backlog"],
                    }
                ],
            },
        ],
        "disclaimer": (
            "Educational analysis and pipeline demonstration only. Not investment advice. "
            "DEMO tickers and figures are synthetic fixtures used to exercise MarketForge's "
            "claim → evidence → source publication gate. Always verify primary sources and "
            "consult licensed professionals before making financial decisions."
        ),
    }

    x_thread = {
        "posts": [
            {
                "sequence": 1,
                "text": (
                    "MarketForge demo brief: S&P 500 5,420.15 (+0.85%), "
                    "Nasdaq-100 19,180.40 (+1.20%). DEMO-A +6.4% after $412M revenue print."
                ),
                "claim_ids": ["cl-spx", "cl-ndx", "cl-demo-a-move", "cl-rev"],
            },
            {
                "sequence": 2,
                "text": (
                    "SEC fixture: DEMO-A revenue $412M vs $348M (growth 18.39%), OCF $91M, "
                    "backlog $1.85B, $40M buyback. Net insider sales 37,000 shares."
                ),
                "claim_ids": [
                    "cl-rev",
                    "cl-growth",
                    "cl-ocf",
                    "cl-backlog",
                    "cl-buyback",
                    "cl-insider",
                ],
            },
            {
                "sequence": 3,
                "text": (
                    f"Reproducible Monte Carlo DCF used 10000 iterations and seed 42; "
                    f"median ${median_iv} (p5 ${p05} / p95 ${p95}). Educational only — not advice."
                ),
                "claim_ids": ["cl-sim"],
            },
        ]
    }

    bundle = {
        "run": {
            "run_id": run_id,
            "as_of": as_of_iso,
            "mode": "daily_close",
        },
        "sources": sources,
        "evidence": evidence,
        "claims": claims,
        "article": article,
        "x_thread": x_thread,
    }

    bundle_path = run_dir / "run-bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    try:
        result = validate_run_bundle(bundle, artifact_root=run_dir)
    except ValidationError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    html = render_article(bundle)
    report_name = f"daily-brief-{as_of.strftime('%Y-%m-%d')}.html"
    report_path = out_dir / report_name
    latest_path = out_dir / "index.html"
    report_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")

    # Also write a simple static site shell for personal hosting
    site_index = out_dir.parent / "index.html"
    site_index.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MarketForge Daily</title>
<meta http-equiv="refresh" content="0; url=output/{report_name}">
<style>
body{{margin:0;background:#071018;color:#e8f0f5;font-family:Inter,system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}}
a{{color:#7be0bd}}
</style>
</head>
<body>
<p>Opening latest brief… If you are not redirected, <a href="output/{report_name}">open the report</a>.</p>
</body>
</html>
""",
        encoding="utf-8",
    )

    x_path = run_dir / "x-thread.json"
    x_path.write_text(json.dumps(x_thread, indent=2), encoding="utf-8")

    print("PUBLISHABLE:", run_id)
    print("AS_OF:", as_of_iso)
    print("BUNDLE:", bundle_path)
    print("REPORT:", report_path)
    print("LATEST:", latest_path)
    print("SITE_ENTRY:", site_index)
    print("X_THREAD:", x_path)
    print("CLAIMS:", len(claims))
    print("SOURCES:", len(sources))
    print("SIM_MEDIAN:", median_iv)
    print("STATUS:", "publishable" if result.publishable else "blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
