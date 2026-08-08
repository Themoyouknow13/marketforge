# Implementation Roadmap

## Phase 0 — Product and data decisions

Choose before coding live collectors:

- coverage universe (S&P 500, Russell 1000, or curated watchlist);
- premarket vs post-close canonical edition;
- licensed price/news provider and budget;
- whether reports require approval indefinitely;
- X Article eligibility vs thread fallback;
- website hosting target and domain;
- retention and correction policy.

**Exit:** signed data-source matrix, source licenses, editorial policy, and acceptance metrics.

## Phase 1 — SEC vertical slice

Build one end-to-end ticker path before adding broad market scanning:

1. resolve ticker → CIK;
2. fetch submissions and latest point-in-time 10-K/10-Q/8-K/Form 4 index;
3. save raw responses and filing documents with SHA-256;
4. parse sections and XBRL facts with accession/context/unit/period;
5. create claims and evidence;
6. render and validate one static report.

**Exit:** a report can prove every filing statement back to a stable locator and the validator blocks tampering, future dates, unsupported numbers, and approximate citations.

## Phase 2 — Market scan

Add licensed market data, exchange-calendar logic, corporate actions, sector benchmarks, relative volume, and deterministic ranking. Connect Market Pulse and SEC Sentinel to the priority score.

**Exit:** replaying the same cutoff and artifacts yields the same priority queue.

## Phase 3 — SECForge and quant

Implement filing diffing, red-flag rubric, deterministic peer selection, ratio engine, DCF, scenario calibration, and optional formal Bayesian models. Save all calculation inputs and simulation artifacts.

**Exit:** a second machine can reproduce the reported calculations and Monte Carlo percentiles from the bundle.

## Phase 4 — Editorial and website

Use the approved claim ledger to generate article JSON, run an independent auditor, render a versioned static report, and stage it behind an approval queue. Add corrections and immutable revisions.

**Exit:** a failed gate cannot update `latest.json`; an approved revision is public with source/evidence views.

## Phase 5 — X transformation

Generate a thread or X Article draft only from an approved website bundle. Validate unknown claims, numeric drift, qualification changes, duplicates, length, links, and disclaimer. Keep publishing manual.

**Exit:** reviewers can approve a draft whose every paragraph/post resolves to approved website claims.

## Phase 6 — Controlled autonomy

Run in shadow mode, compare against a human analyst, and measure:

- source/filing recall;
- unsupported-claim rate;
- numeric-error rate;
- material contradiction rate;
- correction rate;
- stale-data incidents;
- false materiality alerts;
- report usefulness and reading completion.

Enable autonomous website publishing only after sustained zero critical validation escapes. Enable X auto-publishing later, with a kill switch, spend/rate limits, idempotency ledger, and post-publication monitoring.

## Suggested production stack

- **Workflow:** Temporal, Dagster, or Prefect
- **Language:** Python for collection, financial math, validation, and orchestration activities
- **Artifact store:** S3-compatible object storage with versioning/object lock
- **Operational DB:** PostgreSQL for runs, sources, claims, approvals, and corrections
- **Analytics:** DuckDB/Parquet for point-in-time market and XBRL facts
- **Website:** Astro or Next.js static generation; CDN deployment
- **Observability:** OpenTelemetry + structured logs + alerting
- **Secrets:** managed secret store; never prompts or run bundles
- **LLM calls:** structured-output endpoints with schema validation, fixed model/version metadata, and full prompt/input/output audit records

## Launch policy

Do not market the output as real-time, exhaustive, personalized, or guaranteed accurate. Display the exact cutoff, freshness, coverage universe, known data gaps, methodology, and correction link on every report.
