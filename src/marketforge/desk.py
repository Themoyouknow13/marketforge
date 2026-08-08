"""Phase-1 desk presentation helpers for Terminal Research briefs."""

from __future__ import annotations

from typing import Any


def source_urls_for_claims(
    claim_ids: list[str],
    *,
    claims: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Resolve unique external source chips for a set of claims."""

    chips: list[dict[str, str]] = []
    seen: set[str] = set()
    for claim_id in claim_ids:
        claim = claims.get(claim_id) or {}
        for evidence_id in claim.get("evidence_ids") or []:
            item = evidence.get(evidence_id) or {}
            source = sources.get(item.get("source_id", "")) or {}
            url = str(source.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            publisher = str(source.get("publisher") or "Source")
            title = str(source.get("title") or publisher)
            kind = "sec" if "sec.gov" in url else "market" if "yahoo" in url or "finance" in url else "source"
            label = _chip_label(kind, title, publisher)
            chips.append(
                {
                    "label": label,
                    "url": url,
                    "kind": kind,
                    "source_id": str(source.get("id") or ""),
                    "claim_id": claim_id,
                }
            )
    return chips


def _chip_label(kind: str, title: str, publisher: str) -> str:
    if kind == "sec":
        if "8-K" in title or "8-K" in publisher:
            return "SEC · Filing"
        if "10-Q" in title:
            return "SEC · 10-Q"
        if "Form 4" in title or "form4" in title.lower():
            return "SEC · Form 4"
        return "SEC · EDGAR"
    if kind == "market":
        return "Market · Tape"
    short = title if len(title) <= 28 else title[:25] + "…"
    return short


def build_desk_payload(bundle: dict[str, Any], inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create Phase-1 desk cards/context from an approved bundle + optional scrape inventory."""

    inventory = inventory or {}
    claims = {c["id"]: c for c in bundle.get("claims") or []}
    evidence = {e["id"]: e for e in bundle.get("evidence") or []}
    sources = {s["id"]: s for s in bundle.get("sources") or []}

    benchmarks = inventory.get("benchmarks") or {}
    gainers = inventory.get("gainers") or []
    losers = inventory.get("losers") or []
    sec_counts = inventory.get("sec_counts") or {}
    deep = inventory.get("deep_dive") or {}

    def chips(ids: list[str]) -> list[dict[str, str]]:
        return source_urls_for_claims(ids, claims=claims, evidence=evidence, sources=sources)

    def market_chip(symbol: str, url: str | None = None) -> list[dict[str, str]]:
        href = url or f"https://finance.yahoo.com/quote/{symbol}"
        return [
            {
                "label": f"Market · {symbol}",
                "url": href,
                "kind": "market",
                "source_id": "src-market",
                "claim_id": "",
            }
        ]

    # --- benchmark tiles ---
    bench_cards = []
    mapping = [
        ("SPY", "cl-spy", benchmarks.get("SPY")),
        ("QQQ", "cl-qqq", benchmarks.get("QQQ")),
        ("VIX", "cl-vix", benchmarks.get("VIX")),
    ]
    for symbol, claim_id, row in mapping:
        if claim_id not in claims:
            continue
        claim = claims[claim_id]
        change = None if not row else row.get("change_pct")
        direction = "flat"
        if isinstance(change, (int, float)):
            direction = "up" if change > 0 else "down" if change < 0 else "flat"
        link = market_chip(symbol if symbol != "VIX" else "%5EVIX", None if not row else row.get("url"))
        # Prefer human quote page for desk chips; keep API url only if no better option.
        if row and row.get("url") and "chart" in str(row.get("url")):
            human = "https://finance.yahoo.com/quote/%5EVIX" if symbol == "VIX" else f"https://finance.yahoo.com/quote/{symbol}"
            link = market_chip(symbol, human)
        bench_cards.append(
            {
                "symbol": symbol,
                "print_line": claim["text"],
                "context_line": _benchmark_context(symbol, change),
                "implication_line": _benchmark_implication(symbol, change),
                "direction": direction,
                "claim_ids": [claim_id],
                "links": link + chips([claim_id]),
            }
        )

    # --- mover cards ---
    mover_cards = []
    gainer_ids = [cid for cid in ("cl-gainer0", "cl-gainer1") if cid in claims]
    loser_ids = [cid for cid in ("cl-loser0",) if cid in claims]
    for idx, cid in enumerate(gainer_ids):
        row = gainers[idx] if idx < len(gainers) else {}
        card = _mover_card(claims[cid], row, side="gainer", chips=chips([cid]), deep=deep)
        sym = card["symbol"]
        card["links"] = market_chip(sym) + card["links"]
        if card["catalyst_status"] == "filing":
            card["links"] = chips([cid for cid in ("cl-deep-meta", "cl-deep-excerpt") if cid in claims]) + card["links"]
        mover_cards.append(card)
    for idx, cid in enumerate(loser_ids):
        row = losers[idx] if idx < len(losers) else {}
        card = _mover_card(claims[cid], row, side="loser", chips=chips([cid]), deep=deep)
        card["links"] = market_chip(card["symbol"]) + card["links"]
        mover_cards.append(card)

    # --- filing cards ---
    filing_cards = []
    if "cl-top-8k" in claims:
        filing_cards.append(
            {
                "title": "Highlighted 8-K",
                "print_line": claims["cl-top-8k"]["text"],
                "context_line": "Recent current-feed 8-K captured in today's SEC scrape.",
                "implication_line": "Open the primary filing before treating the headline as thesis-changing.",
                "catalyst_status": "filing",
                "claim_ids": ["cl-top-8k"],
                "links": chips(["cl-top-8k"]),
            }
        )
    if "cl-deep-meta" in claims:
        filing = deep.get("filing") or {}
        symbol = deep.get("symbol") or "Issuer"
        deep_links = chips([cid for cid in ("cl-deep-meta", "cl-deep-excerpt") if cid in claims])
        for url_key, label in (
            ("document_url", "SEC · Filing HTML"),
            ("index_url", "SEC · Filing index"),
        ):
            url = filing.get(url_key) or deep.get("excerpt_url")
            if url and str(url).startswith("https://"):
                deep_links = [
                    {
                        "label": label,
                        "url": str(url),
                        "kind": "sec",
                        "source_id": "src-deep",
                        "claim_id": "cl-deep-meta",
                    }
                ] + deep_links
                break
        filing_cards.append(
            {
                "title": f"Deep dive · {symbol}",
                "print_line": claims["cl-deep-meta"]["text"],
                "context_line": (
                    f"{symbol} is the session deep-dive issuer. "
                    + claims["cl-deep-meta"]["text"]
                ),
                "implication_line": (
                    "Use the filing HTML for details; the brief only carries grounded excerpt/metadata claims."
                ),
                "catalyst_status": "filing",
                "claim_ids": [cid for cid in ("cl-deep-meta", "cl-deep-excerpt", "cl-watch") if cid in claims],
                "links": deep_links,
            }
        )

    # --- section meaning blocks ---
    overview_ids = [cid for cid in ("cl-spy", "cl-qqq", "cl-vix", "cl-regime") if cid in claims]
    movers_ids = gainer_ids + loser_ids
    sec_ids = [cid for cid in ("cl-8k-count", "cl-10q-count", "cl-4-count", "cl-top-8k") if cid in claims]
    deep_ids = [cid for cid in ("cl-deep-meta", "cl-deep-excerpt", "cl-watch") if cid in claims]

    sections = [
        {
            "id": "market-overview",
            "heading": "Market Overview",
            "kicker": "What the tape did",
            "blocks": [
                {
                    "print_line": " ".join(claims[i]["text"] for i in overview_ids[:3]),
                    "context_line": _overview_context(claims, overview_ids),
                    "implication_line": _overview_implication(claims, overview_ids),
                    "claim_ids": overview_ids or ["cl-spy"],
                    "links": chips(overview_ids or ["cl-spy"]),
                }
            ],
            "cards": bench_cards,
            "card_kind": "benchmark",
        },
        {
            "id": "top-movers",
            "heading": "Top Movers & Why",
            "kicker": "Where attention concentrates",
            "blocks": [
                {
                    "print_line": " ".join(claims[i]["text"] for i in movers_ids[:3]),
                    "context_line": (
                        "These names screened from the live gainers/losers tape. "
                        "Catalyst status is filing-linked only when the package contains a matching filing claim."
                    ),
                    "implication_line": (
                        "Treat single-name spikes as attention signals until a primary filing or verified catalyst is attached."
                    ),
                    "claim_ids": movers_ids or overview_ids[:1],
                    "links": chips(movers_ids or overview_ids[:1]),
                }
            ],
            "cards": mover_cards,
            "card_kind": "mover",
        },
        {
            "id": "sec-highlights",
            "heading": "SEC Highlights",
            "kicker": "What filings hit the wire",
            "blocks": [
                {
                    "print_line": " ".join(claims[i]["text"] for i in sec_ids[:4]),
                    "context_line": (
                        " ".join(claims[i]["text"] for i in sec_ids)
                        if sec_ids
                        else "SEC current feeds were packaged into grounded count and highlight claims."
                    ),
                    "implication_line": (
                        "Filing volume is a radar, not a verdict — open the HTML before upgrading a name to a thesis."
                    ),
                    "claim_ids": sec_ids or overview_ids[:1],
                    "links": chips(sec_ids or overview_ids[:1]),
                }
            ],
            "cards": filing_cards,
            "card_kind": "filing",
        },
        {
            "id": "deep-dive",
            "heading": f"Deep Dive — {deep.get('symbol') or 'Focus name'}",
            "kicker": "Primary case study",
            "blocks": [
                {
                    "print_line": " ".join(claims[i]["text"] for i in deep_ids[:2]),
                    "context_line": (
                        "This section is the session's forensic focus. "
                        "Read the issuer filing directly for event details beyond grounded metadata/excerpt claims."
                    ),
                    "implication_line": (
                        claims.get("cl-watch", {}).get("text")
                        or "Watch follow-through only against the filing-linked claims in this package."
                    ),
                    "claim_ids": deep_ids or overview_ids[:1],
                    "links": chips(deep_ids or overview_ids[:1]),
                }
            ],
            "cards": [],
            "card_kind": "none",
        },
        {
            "id": "watchlist",
            "heading": "Watchlist & Key Metric",
            "kicker": "What to monitor next",
            "blocks": [
                {
                    "print_line": (
                        claims["cl-watch"]["text"]
                        if "cl-watch" in claims
                        else claims[overview_ids[0]]["text"]
                    ),
                    "context_line": "A good desk ends on one falsifiable next check, not a pile of open questions.",
                    "implication_line": (
                        "If the watch item breaks, revisit both the popular and contrarian frames on the Ideas desk."
                    ),
                    "claim_ids": [cid for cid in ("cl-watch", "cl-deep-meta") if cid in claims]
                    or overview_ids[:1],
                    "links": chips(
                        [cid for cid in ("cl-watch", "cl-deep-meta") if cid in claims]
                        or overview_ids[:1]
                    ),
                }
            ],
            "cards": [],
            "card_kind": "none",
        },
    ]

    # Ensure claim ids exist
    for section in sections:
        for block in section["blocks"]:
            block["claim_ids"] = [cid for cid in block["claim_ids"] if cid in claims]
            if not block["claim_ids"]:
                block["claim_ids"] = [next(iter(claims))]

    summary_ids = [cid for cid in ("cl-spy", "cl-qqq", "cl-gainer0", "cl-8k-count", "cl-deep-meta") if cid in claims]
    if not summary_ids:
        summary_ids = list(claims)[:3]

    desk_summary = _desk_summary(claims, summary_ids, deep)

    return {
        "design": "terminal_research_phase1",
        "summary": desk_summary,
        "summary_claim_ids": summary_ids,
        "summary_links": chips(summary_ids),
        "sections": sections,
        "nav": [
            {"href": "#market-overview", "label": "Markets"},
            {"href": "#top-movers", "label": "Movers"},
            {"href": "#sec-highlights", "label": "SEC"},
            {"href": "#deep-dive", "label": "Deep dive"},
            {"href": "#watchlist", "label": "Watchlist"},
            {"href": "dual-thesis.html", "label": "Bull / Bear"},
            {"href": "#sources-drawer", "label": "Sources"},
        ],
    }


def _mover_card(
    claim: dict[str, Any],
    row: dict[str, Any],
    *,
    side: str,
    chips: list[dict[str, str]],
    deep: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(row.get("symbol") or _guess_symbol(claim["text"]) or "NAME")
    deep_symbol = str(deep.get("symbol") or "")
    if deep_symbol and symbol.upper() == deep_symbol.upper():
        catalyst = "filing"
        context = f"{symbol} is linked to today's deep-dive filing package."
        implication = "Priority name: confirm the filing details before extrapolating the move."
    else:
        catalyst = "none"
        context = f"{symbol} screened on the live {side} tape in this package."
        implication = "No primary catalyst claim is attached in-package — treat as tape attention until filing/news is linked."
    return {
        "symbol": symbol,
        "side": side,
        "print_line": claim["text"],
        "context_line": context,
        "implication_line": implication,
        "catalyst_status": catalyst,
        "claim_ids": [claim["id"]],
        "links": chips,
    }


def _guess_symbol(text: str) -> str | None:
    import re

    match = re.search(r"\b([A-Z]{1,5})\b", text)
    return match.group(1) if match else None


def _benchmark_context(symbol: str, change: float | None) -> str:
    if change is None:
        return f"{symbol} print packaged from the live market snapshot."
    if change > 1:
        return f"{symbol} posted a firm up-session versus the prior close in the live package."
    if change < -1:
        return f"{symbol} posted a firm down-session versus the prior close in the live package."
    return f"{symbol} change was modest versus the prior close in the live package."


def _benchmark_implication(symbol: str, change: float | None) -> str:
    if change is None:
        return f"Use the {symbol} source chip to open the underlying market print."
    if symbol == "VIX":
        return "Volatility easing can support risk appetite, but it does not validate single-name spikes by itself."
    if change > 0:
        return "Benchmark strength favors a risk-on desk posture until breadth or filings contradict it."
    return "Benchmark weakness favors defense until leadership stabilizes."


def _overview_context(claims: dict[str, dict[str, Any]], ids: list[str]) -> str:
    has_vix = "cl-vix" in ids
    if has_vix:
        return (
            "Benchmarks and volatility are shown together so the session regime is readable at a glance. "
            + claims.get("cl-regime", {}).get("text", "")
        ).strip()
    return "Benchmark prints are the session anchor for every later mover and filing interpretation."


def _overview_implication(claims: dict[str, dict[str, Any]], ids: list[str]) -> str:
    if "cl-regime" in claims:
        return claims["cl-regime"]["text"]
    return "Let benchmark direction set the prior; let filings and single-name evidence update it."


def _desk_summary(claims: dict[str, dict[str, Any]], ids: list[str], deep: dict[str, Any]) -> str:
    parts = [claims[i]["text"] for i in ids if i in claims]
    focus = deep.get("symbol")
    if focus and "cl-deep-meta" in claims:
        parts.append(f"Focus filing case study: {focus}.")
    return " ".join(parts)
