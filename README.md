# MarketForge

MarketForge is a production scaffold for a source-grounded daily market intelligence and publishing system. It separates retrieval, deterministic financial computation, bounded LLM analysis, editorial synthesis, independent audit, and publication.

## What exists now

- A full production workflow and agent map: `docs/WORKFLOW.md`
- A visual architecture diagram: `docs/marketforge-architecture.html`
- A phased implementation roadmap: `docs/IMPLEMENTATION_ROADMAP.md`
- Strict role contracts for every agent: `docs/AGENT_CONTRACTS.md`
- Daily-run orchestration prompt: `prompts/daily-run.md`
- Separate approved-brief → X prompt: `prompts/x-article.md`
- Fail-closed run bundle schema: `schemas/run-bundle.schema.yaml`
- Workflow/source/feature configuration: `config/workflow.yaml`
- Deterministic validation gate: `src/marketforge/validation.py`
- Reproducible Monte Carlo DCF engine: `src/marketforge/monte_carlo.py`
- Cited static HTML renderer: `src/marketforge/render.py`
- CLI validator/renderer: `src/marketforge/cli.py`
- Tests for provenance, temporal cutoffs, quote/hash checks, numeric drift, calculations, simulation reproducibility, rendering, and CLI behavior.

## Quick start

```bash
uv sync --extra dev
uv run pytest -q

# Minimal fixture
uv run python -m marketforge.cli validate examples/valid-run.json \
  --render site/output/example-report.html

# Full end-to-end demo briefing (grounded bundle → validate → shippable HTML)
uv run python scripts/run_demo_briefing.py
# Open: site/output/daily-brief-YYYY-MM-DD.html  or  site/index.html

# LIVE scrape (Yahoo market prints + SEC EDGAR feeds → validate → HTML)
uv run python scripts/run_live_briefing.py
# Open: site/output/live-brief-YYYY-MM-DD.html
```

## Live site

- **Homepage:** https://themoyouknow13.github.io/marketforge/
- **Latest brief:** https://themoyouknow13.github.io/marketforge/output/daily-brief-2026-08-08.html
- **Repo:** https://github.com/Themoyouknow13/marketforge

Hosted on GitHub Pages from the `gh-pages` branch (contents of `site/`). Local preview:

```bash
cd site && python -m http.server 8080
# http://127.0.0.1:8080/
```

The CLI exits non-zero and prints `BLOCKED` if any publication gate fails.

## Non-negotiable design rule

LLMs may write prose, rank events, interpret evidence, and surface uncertainty. They may not own numeric truth, citations, timestamps, DCF calculations, Bayesian updates, Monte Carlo outputs, or publication approval.

A probabilistic model cannot guarantee “zero hallucinations.” MarketForge instead guarantees that the publisher **fails closed** when a publishable claim lacks validated evidence lineage.

## Environment variables needed for live operation

```text
SEC_USER_AGENT="YourCompany contact@example.com"
MARKET_DATA_API_KEY=...
NEWS_API_KEY=...
X_CLIENT_ID=...
X_CLIENT_SECRET=...
X_REFRESH_TOKEN=...
```

Do not configure X publishing until draft validation and human approval are working. The website should be the canonical source; X should link to its approved revision.

## Recommended implementation order

1. SEC collector + immutable snapshot store + XBRL normalization.
2. Licensed point-in-time market data collector with corporate-action adjustment.
3. Claim/evidence database and exact filing locators.
4. Market Pulse, SEC Sentinel, Regime, SECForge, and editor invocations using strict JSON contracts.
5. Workflow engine (Temporal, Dagster, or Prefect) with retries and idempotency.
6. Static website deployment with approval queue and corrections.
7. X draft automation; enable publication only after explicit approval and duplicate protection.

## Authoritative implementation notes

- `docs/SOURCE_NOTES.md` records the SEC and X platform constraints used by this scaffold.

## Primary-source constraints

The SEC provides unauthenticated real-time submissions/XBRL APIs and bulk archives. Automated access must use a declared User-Agent and respect the SEC’s fair-access policy. See `docs/SOURCE_NOTES.md` for the authoritative source links.
