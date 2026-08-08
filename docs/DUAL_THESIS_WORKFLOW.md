# Dual-Thesis Workflow (Bull / Bear × Popular / Contrarian)

## Purpose

Supplement the MarketForge daily intelligence brief with a structured **opinion layer**:

- **Bull thesis** vs **Bear thesis**
- each framed as **Popular (consensus)** and **Contrarian** readings

This is **not** a second research scrape. It is a transformation of an **already approved** MarketForge run bundle. No new prices, filings, or facts may enter.

## Design principles

1. **Approved claims only** — thesis agents receive the immutable claim/evidence ledger, never free browsing.
2. **Steelman both sides** — each thesis must use the strongest available supporting claims, not strawmen.
3. **Separate fact from speculation** — speculative language is labeled `stance` or `scenario`, never presented as observed fact.
4. **Popular ≠ true** — “popular” means the reading most consistent with the session’s dominant tape/narrative claims; “contrarian” is the coherent opposing frame.
5. **Fail closed** — every thesis paragraph must cite claim_ids; numeric tokens must remain grounded; no trade instructions.
6. **Educational framing** — output is analytical speculation for readers, not personalized advice.

## Multi-agent topology

```text
Approved MarketForge Run Bundle
            │
            ▼
   [0] Thesis Orchestrator
            │
     ┌──────┴──────┐
     ▼             ▼
[1] Evidence    [2] Consensus
    Polarizer       Classifier
     │             │
     └──────┬──────┘
            ▼
   ┌────────┴────────┐
   ▼                 ▼
[3] Bull           [4] Bear
    Architect          Architect
   └────────┬────────┘
            ▼
   [5] Dialectic Critic
            ▼
   [6] Dual-Thesis Editor
            ▼
   [7] Grounding Auditor
            ▼
   validate_thesis_bundle → render_thesis_page → site
```

### Agent roles

| # | Agent | Job | May not |
|---|---|---|---|
| 0 | Thesis Orchestrator | Load approved bundle, freeze claim set, set subject scope | scrape or mutate claims |
| 1 | Evidence Polarizer | Tag each claim `bull_support` / `bear_support` / `contested` / `neutral` | invent catalysts |
| 2 | Consensus Classifier | Infer what the “popular” session narrative is from regime + movers + filings | declare popular = correct |
| 3 | Bull Architect | Build steelman bull case with popular + contrarian variants | use unapproved claims |
| 4 | Bear Architect | Build steelman bear case with popular + contrarian variants | use unapproved claims |
| 5 | Dialectic Critic | Require each side to answer the other’s top 3 points | add facts |
| 6 | Dual-Thesis Editor | Write the public page structure | browse |
| 7 | Grounding Auditor | Fail any unsupported number/claim/overclaim | repair silently |

## Output structure (public page)

1. **Session framing** — what the approved brief established (claim-linked)
2. **Scoreboard** — claim counts supporting bull vs bear vs contested
3. **Popular Bull** — consensus upside reading
4. **Contrarian Bull** — upside case *against* the popular tape (if tape is risk-off) or extension risk-aware bull
5. **Popular Bear** — consensus downside reading
6. **Contrarian Bear** — fade/mean-reversion or structural risk case
7. **Dialectic** — point/counterpoint table
8. **What would falsify each thesis** — claim-linked watch items
9. **Disclaimer**

## Popular vs Contrarian definition

Given the approved claim set:

- **Popular direction** = sign of benchmark/mover leadership implied by market claims
  - e.g. SPY/QQQ up + gainers leadership ⇒ popular risk-on / bullish tape
- **Popular Bull** = thesis agreeing with that tape, using bull-supporting claims
- **Popular Bear** = still required: the best downside case *acknowledging* the tape (late-cycle / blow-off / event risk)
- **Contrarian Bull** = bull case that *disagrees* with a weak tape, or that says strength is early not late
- **Contrarian Bear** = bear case that *fades* a strong tape (distribution, overextension, filing risk)

Both sides always publish. Strength is expressed by claim coverage counts and explicit uncertainty — not by suppressing a side.

## Speculation rules

Allowed speculative verbs when labeled as stance:

- “one reading is…”
- “a bull interpretation is…”
- “a bear risk is…”
- “this would be falsified if…”

Forbidden:

- “will go to”
- “guaranteed”
- “buy/sell now”
- new targets not present in approved simulation/calculation claims
- probabilities not present in approved claims

## Automation boundary

```text
PHASE A — MarketForge Daily Intelligence
  collectors → claims → article → validate_run_bundle → daily brief

PHASE B — Dual Thesis (this workflow)
  approved bundle only → polarize → bull/bear architects → dialectic
  → thesis article → validate_thesis_bundle → thesis page
```

Keep phases separate (same reason as MarketForge vs X): the opinion layer must not contaminate the factual brief.

## Commands

```bash
# Build dual-thesis page from an approved run bundle
uv run python scripts/run_dual_thesis.py runs/live-YYYYMMDD-HHMMSS/run-bundle.json

# Validate only
uv run python -m marketforge.cli thesis runs/.../run-bundle.json --thesis runs/.../thesis-bundle.json
```
