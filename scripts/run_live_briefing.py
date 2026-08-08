"""Live end-to-end MarketForge run using current SEC + market scrapes."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from marketforge.collectors import (  # noqa: E402
    fetch_filing_excerpt,
    format_number,
    format_pct,
    load_company_tickers,
    parse_atom_filings,
    recent_company_filings,
    sec_company_submissions,
    fetch_sec,
    yahoo_chart,
    yahoo_screener,
)
from marketforge.render import render_article  # noqa: E402
from marketforge.validation import ValidationError, validate_run_bundle  # noqa: E402


def write_bytes(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def write_text(path: Path, text: str) -> str:
    payload = text.replace("\r\n", "\n").encode("utf-8")
    return write_bytes(path, payload)


def money(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"${format_number(value)}"


def volume(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return format_number(int(value), 0)


def main() -> int:
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    as_of_iso = as_of.isoformat().replace("+00:00", "Z")
    run_id = f"live-{as_of.strftime('%Y%m%d-%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    snaps = run_dir / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "site" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[live] run_id={run_id}")
    print("[live] scraping market benchmarks...")

    spy = yahoo_chart("SPY")
    qqq = yahoo_chart("QQQ")
    try:
        vix = yahoo_chart("^VIX")
    except Exception as exc:  # noqa: BLE001
        print(f"[live] VIX chart failed ({exc}); continuing without VIX")
        vix = None

    print("[live] scraping day gainers/losers...")
    gainers = yahoo_screener("day_gainers", count=8)
    losers = yahoo_screener("day_losers", count=8)

    print("[live] scraping SEC current filings...")
    atom_8k = fetch_sec(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=include&count=20&output=atom"
    )
    atom_10q = fetch_sec(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-Q&owner=include&count=10&output=atom"
    )
    atom_4 = fetch_sec(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=only&count=15&output=atom"
    )

    filings_8k = parse_atom_filings(atom_8k.text, limit=12)
    filings_10q = parse_atom_filings(atom_10q.text, limit=8)
    filings_4 = parse_atom_filings(atom_4.text, limit=10)

    print("[live] loading SEC ticker map + deep-dive candidate...")
    tickers = load_company_tickers()
    ticker_raw = tickers["__raw__"]

    # Prefer a gainer that maps cleanly to a CIK for deep dive.
    deep_symbol = None
    deep_quote = None
    for quote in gainers["quotes"]:
        sym = str(quote.get("symbol") or "").upper()
        if sym in tickers and not sym.endswith("W") and len(sym) <= 5:
            deep_symbol = sym
            deep_quote = quote
            break
    if deep_symbol is None:
        # fallback liquid names
        for sym in ("NVDA", "AAPL", "MSFT", "AMZN", "META"):
            if sym in tickers:
                deep_symbol = sym
                break
    if deep_symbol is None:
        raise RuntimeError("Could not resolve any deep-dive ticker to a CIK")

    deep_meta = tickers[deep_symbol]
    submissions = sec_company_submissions(deep_meta["cik10"])
    company_filings = recent_company_filings(submissions, {"8-K", "10-Q", "10-K"}, limit=6)
    if not company_filings:
        raise RuntimeError(f"No recent 8-K/10-Q/10-K filings for {deep_symbol}")

    focus_filing = company_filings[0]
    print(f"[live] deep dive {deep_symbol} filing {focus_filing['form']} {focus_filing['accession']}")
    # Prefer primary document excerpt; fall back to index page text.
    try:
        excerpt = fetch_filing_excerpt(focus_filing["document_url"], max_chars=10000)
        excerpt_url = focus_filing["document_url"]
    except Exception:  # noqa: BLE001
        excerpt = fetch_filing_excerpt(focus_filing["index_url"], max_chars=10000)
        excerpt_url = focus_filing["index_url"]

    # Build human-readable snapshot texts that contain exact claim quotes.
    market_lines = [
        "MarketForge LIVE market snapshot (public Yahoo Finance chart/screener endpoints).",
        f"Retrieved at {as_of_iso}.",
        (
            f"SPY last price {format_number(spy['last'])} versus previous close "
            f"{format_number(spy['previous_close'])}, change {format_pct(spy['change_pct'])}, "
            f"volume {volume(spy['volume'])}."
        ),
        (
            f"QQQ last price {format_number(qqq['last'])} versus previous close "
            f"{format_number(qqq['previous_close'])}, change {format_pct(qqq['change_pct'])}, "
            f"volume {volume(qqq['volume'])}."
        ),
    ]
    if vix and vix.get("last") is not None:
        market_lines.append(
            f"VIX last price {format_number(vix['last'])}, change {format_pct(vix['change_pct'])}."
        )
    market_lines.append("Day gainers (Yahoo predefined screener):")
    for row in gainers["quotes"][:5]:
        market_lines.append(
            f"- {row['symbol']}: {format_pct(row.get('change_pct'))} to {money(row.get('price'))}, "
            f"volume {volume(row.get('volume'))}."
        )
    market_lines.append("Day losers (Yahoo predefined screener):")
    for row in losers["quotes"][:5]:
        market_lines.append(
            f"- {row['symbol']}: {format_pct(row.get('change_pct'))} to {money(row.get('price'))}, "
            f"volume {volume(row.get('volume'))}."
        )
    if deep_quote is not None:
        market_lines.append(
            (
                f"Deep-dive candidate {deep_symbol} appeared on the day-gainers list at "
                f"{format_pct(deep_quote.get('change_pct'))} and {money(deep_quote.get('price'))}."
            )
        )
    market_text = "\n".join(market_lines) + "\n"

    sec_feed_lines = [
        "MarketForge LIVE SEC EDGAR current-filings snapshot.",
        f"Retrieved at {as_of_iso}.",
        f"8-K feed updated entries captured: {len(filings_8k)}.",
        f"10-Q feed updated entries captured: {len(filings_10q)}.",
        f"Form 4 feed updated entries captured: {len(filings_4)}.",
        "Selected recent 8-K filings:",
    ]
    for row in filings_8k[:6]:
        sec_feed_lines.append(
            f"- {row['company']} filed {row['form']} (accession {row['accession'] or 'n/a'}). {row['summary'][:220]}"
        )
    sec_feed_lines.append("Selected recent 10-Q filings:")
    for row in filings_10q[:4]:
        sec_feed_lines.append(
            f"- {row['company']} filed {row['form']} (accession {row['accession'] or 'n/a'}). {row['summary'][:180]}"
        )
    sec_feed_lines.append("Selected recent Form 4 filings:")
    for row in filings_4[:4]:
        sec_feed_lines.append(
            f"- {row['title'][:120]} (accession {row['accession'] or 'n/a'})."
        )
    sec_feed_text = "\n".join(sec_feed_lines) + "\n"

    deep_lines = [
        f"MarketForge LIVE deep-dive package for {deep_symbol} / {deep_meta['title']}.",
        f"CIK {deep_meta['cik10']}.",
        f"Focus filing form {focus_filing['form']}, accession {focus_filing['accession']}, filed {focus_filing['filed']}.",
        f"Primary document URL: {excerpt_url}",
        f"Filing index URL: {focus_filing['index_url']}",
    ]
    if focus_filing.get("items"):
        deep_lines.append(f"Items disclosed: {focus_filing['items']}.")
    if focus_filing.get("description"):
        deep_lines.append(f"Primary document description: {focus_filing['description']}.")
    deep_lines.append("Filing excerpt follows:")
    deep_lines.append(excerpt)
    deep_text = "\n".join(deep_lines) + "\n"

    # Persist raw + narrative snapshots
    market_hash = write_text(snaps / "market-live.txt", market_text)
    write_text(snaps / "spy-chart.json", spy["raw_json"])
    write_text(snaps / "qqq-chart.json", qqq["raw_json"])
    if vix:
        write_text(snaps / "vix-chart.json", vix["raw_json"])
    write_text(snaps / "gainers.json", gainers["raw_json"])
    write_text(snaps / "losers.json", losers["raw_json"])

    sec_feed_hash = write_text(snaps / "sec-current-feeds.txt", sec_feed_text)
    write_bytes(snaps / "sec-8k.atom.xml", atom_8k.raw)
    write_bytes(snaps / "sec-10q.atom.xml", atom_10q.raw)
    write_bytes(snaps / "sec-form4.atom.xml", atom_4.raw)

    deep_hash = write_text(snaps / "deep-dive.txt", deep_text)
    write_text(snaps / "submissions.json", submissions["_raw_json"])
    write_text(snaps / "company-tickers.json", ticker_raw["raw_json"])

    # ---- claims / evidence (only numbers that appear in snapshot quotes) ----
    sources = [
        {
            "id": "src-market",
            "url": spy["url"],
            "title": "Live market snapshot (Yahoo Finance charts + screeners)",
            "publisher": "Yahoo Finance (public endpoints)",
            "tier": 2,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/market-live.txt",
            "content_sha256": market_hash,
        },
        {
            "id": "src-sec-feed",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=include&count=20&output=atom",
            "title": "SEC EDGAR current filings feeds (8-K / 10-Q / Form 4)",
            "publisher": "U.S. Securities and Exchange Commission",
            "tier": 1,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/sec-current-feeds.txt",
            "content_sha256": sec_feed_hash,
        },
        {
            "id": "src-deep",
            "url": excerpt_url if excerpt_url.startswith("https://") else focus_filing["index_url"],
            "title": f"{deep_symbol} focus filing excerpt ({focus_filing['form']})",
            "publisher": "U.S. Securities and Exchange Commission",
            "tier": 1,
            "retrieved_at": as_of_iso,
            "snapshot_path": "snapshots/deep-dive.txt",
            "content_sha256": deep_hash,
        },
    ]

    # Exact quotes from market snapshot
    spy_quote = (
        f"SPY last price {format_number(spy['last'])} versus previous close "
        f"{format_number(spy['previous_close'])}, change {format_pct(spy['change_pct'])}, "
        f"volume {volume(spy['volume'])}."
    )
    qqq_quote = (
        f"QQQ last price {format_number(qqq['last'])} versus previous close "
        f"{format_number(qqq['previous_close'])}, change {format_pct(qqq['change_pct'])}, "
        f"volume {volume(qqq['volume'])}."
    )
    gainer0 = gainers["quotes"][0]
    loser0 = losers["quotes"][0]
    gainer_quote = (
        f"- {gainer0['symbol']}: {format_pct(gainer0.get('change_pct'))} to {money(gainer0.get('price'))}, "
        f"volume {volume(gainer0.get('volume'))}."
    )
    loser_quote = (
        f"- {loser0['symbol']}: {format_pct(loser0.get('change_pct'))} to {money(loser0.get('price'))}, "
        f"volume {volume(loser0.get('volume'))}."
    )
    gainer1 = gainers["quotes"][1] if len(gainers["quotes"]) > 1 else gainer0
    gainer1_quote = (
        f"- {gainer1['symbol']}: {format_pct(gainer1.get('change_pct'))} to {money(gainer1.get('price'))}, "
        f"volume {volume(gainer1.get('volume'))}."
    )

    top_8k = filings_8k[0]
    top_8k_quote = (
        f"- {top_8k['company']} filed {top_8k['form']} (accession {top_8k['accession'] or 'n/a'}). "
        f"{top_8k['summary'][:220]}"
    )
    count_quote = (
        f"8-K feed updated entries captured: {len(filings_8k)}."
    )
    count_10q_quote = f"10-Q feed updated entries captured: {len(filings_10q)}."
    count_4_quote = f"Form 4 feed updated entries captured: {len(filings_4)}."

    deep_form_quote = (
        f"Focus filing form {focus_filing['form']}, accession {focus_filing['accession']}, filed {focus_filing['filed']}."
    )
    deep_company_quote = f"MarketForge LIVE deep-dive package for {deep_symbol} / {deep_meta['title']}."

    # Pull a short verbatim window from excerpt for evidence if possible.
    excerpt_sentence = None
    for sentence in re.split(r"(?<=[.:;])\s+", excerpt):
        cleaned = sentence.strip()
        if 40 <= len(cleaned) <= 280 and re.search(r"\d", cleaned):
            excerpt_sentence = cleaned
            break
    if excerpt_sentence is None:
        excerpt_sentence = excerpt[:240].strip()
    # Ensure the sentence is in deep_text
    if excerpt_sentence not in deep_text:
        excerpt_sentence = deep_form_quote

    evidence = [
        {"id": "ev-spy", "source_id": "src-market", "kind": "quote", "quote": spy_quote, "locator": {"section": "SPY chart"}},
        {"id": "ev-qqq", "source_id": "src-market", "kind": "quote", "quote": qqq_quote, "locator": {"section": "QQQ chart"}},
        {"id": "ev-gainer0", "source_id": "src-market", "kind": "quote", "quote": gainer_quote, "locator": {"section": "Day gainers"}},
        {"id": "ev-gainer1", "source_id": "src-market", "kind": "quote", "quote": gainer1_quote, "locator": {"section": "Day gainers"}},
        {"id": "ev-loser0", "source_id": "src-market", "kind": "quote", "quote": loser_quote, "locator": {"section": "Day losers"}},
        {"id": "ev-8k-count", "source_id": "src-sec-feed", "kind": "quote", "quote": count_quote, "locator": {"section": "8-K feed"}},
        {"id": "ev-10q-count", "source_id": "src-sec-feed", "kind": "quote", "quote": count_10q_quote, "locator": {"section": "10-Q feed"}},
        {"id": "ev-4-count", "source_id": "src-sec-feed", "kind": "quote", "quote": count_4_quote, "locator": {"section": "Form 4 feed"}},
        {"id": "ev-top-8k", "source_id": "src-sec-feed", "kind": "quote", "quote": top_8k_quote, "locator": {"section": "Selected 8-K", "accession": top_8k.get("accession")}},
        {"id": "ev-deep-meta", "source_id": "src-deep", "kind": "quote", "quote": deep_form_quote, "locator": {"section": "Focus filing metadata", "accession": focus_filing["accession"]}},
        {"id": "ev-deep-company", "source_id": "src-deep", "kind": "quote", "quote": deep_company_quote, "locator": {"section": "Issuer"}},
        {"id": "ev-deep-excerpt", "source_id": "src-deep", "kind": "quote", "quote": excerpt_sentence, "locator": {"section": "Filing excerpt", "accession": focus_filing["accession"]}},
    ]

    if vix and vix.get("last") is not None:
        vix_quote = f"VIX last price {format_number(vix['last'])}, change {format_pct(vix['change_pct'])}."
        evidence.append(
            {"id": "ev-vix", "source_id": "src-market", "kind": "quote", "quote": vix_quote, "locator": {"section": "VIX chart"}}
        )

    claims: list[dict[str, Any]] = [
        {
            "id": "cl-spy",
            "text": (
                f"SPY last traded at {format_number(spy['last'])}, "
                f"{format_pct(spy['change_pct'])} versus previous close {format_number(spy['previous_close'])}, "
                f"volume {volume(spy['volume'])}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-spy"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-qqq",
            "text": (
                f"QQQ last traded at {format_number(qqq['last'])}, "
                f"{format_pct(qqq['change_pct'])} versus previous close {format_number(qqq['previous_close'])}, "
                f"volume {volume(qqq['volume'])}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-qqq"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-gainer0",
            "text": (
                f"Top live gainer {gainer0['symbol']} moved {format_pct(gainer0.get('change_pct'))} "
                f"to {money(gainer0.get('price'))}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-gainer0"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-gainer1",
            "text": (
                f"Additional gainer {gainer1['symbol']} moved {format_pct(gainer1.get('change_pct'))} "
                f"to {money(gainer1.get('price'))}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-gainer1"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-loser0",
            "text": (
                f"Top live loser {loser0['symbol']} moved {format_pct(loser0.get('change_pct'))} "
                f"to {money(loser0.get('price'))}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-loser0"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-8k-count",
            "text": f"The SEC current 8-K feed returned {len(filings_8k)} recent entries in this scrape.",
            "claim_type": "fact",
            "evidence_ids": ["ev-8k-count"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-10q-count",
            "text": f"The SEC current 10-Q feed returned {len(filings_10q)} recent entries in this scrape.",
            "claim_type": "fact",
            "evidence_ids": ["ev-10q-count"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-4-count",
            "text": f"The SEC current Form 4 feed returned {len(filings_4)} recent entries in this scrape.",
            "claim_type": "fact",
            "evidence_ids": ["ev-4-count"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-top-8k",
            "text": (
                f"A highlighted recent 8-K came from {top_8k['company']} "
                f"(accession {top_8k['accession'] or 'n/a'})."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-top-8k"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-deep-meta",
            "text": (
                f"{deep_symbol} focus filing is form {focus_filing['form']}, "
                f"accession {focus_filing['accession']}, filed {focus_filing['filed']}."
            ),
            "claim_type": "fact",
            "evidence_ids": ["ev-deep-meta", "ev-deep-company"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-deep-excerpt",
            "text": f"Filing excerpt: {excerpt_sentence}",
            "claim_type": "fact",
            "evidence_ids": ["ev-deep-excerpt"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-regime",
            "text": (
                f"Benchmark tape showed SPY at {format_pct(spy['change_pct'])} and "
                f"QQQ at {format_pct(qqq['change_pct'])} in the latest public prints."
            ),
            "claim_type": "interpretation",
            "evidence_ids": ["ev-spy", "ev-qqq"],
            "as_of": as_of_iso,
        },
        {
            "id": "cl-watch",
            "text": (
                f"Next watch item is follow-through in {deep_symbol} after the "
                f"{focus_filing['form']} filed {focus_filing['filed']}."
            ),
            "claim_type": "interpretation",
            "evidence_ids": ["ev-deep-meta"],
            "as_of": as_of_iso,
        },
    ]

    summary_claim_ids = ["cl-spy", "cl-qqq", "cl-gainer0", "cl-8k-count", "cl-deep-meta"]
    if vix and vix.get("last") is not None:
        claims.insert(
            2,
            {
                "id": "cl-vix",
                "text": f"VIX last printed at {format_number(vix['last'])} ({format_pct(vix['change_pct'])}).",
                "claim_type": "fact",
                "evidence_ids": ["ev-vix"],
                "as_of": as_of_iso,
            },
        )
        summary_claim_ids.insert(2, "cl-vix")

    vix_sentence = ""
    vix_ids: list[str] = []
    if any(c["id"] == "cl-vix" for c in claims):
        vix_sentence = (
            f" VIX last printed at {format_number(vix['last'])} ({format_pct(vix['change_pct'])})."
        )
        vix_ids = ["cl-vix"]

    article = {
        "title": f"MarketForge Live Brief — {as_of.strftime('%B %d, %Y %H:%M UTC')}",
        "summary": (
            f"Live scrape as of {as_of_iso}: SPY {format_number(spy['last'])} ({format_pct(spy['change_pct'])}), "
            f"QQQ {format_number(qqq['last'])} ({format_pct(qqq['change_pct'])}). "
            f"Top gainer {gainer0['symbol']} {format_pct(gainer0.get('change_pct'))}. "
            f"SEC feed captured {len(filings_8k)} recent 8-K entries; deep dive on {deep_symbol} "
            f"{focus_filing['form']} accession {focus_filing['accession']}."
        ),
        "summary_claim_ids": summary_claim_ids,
        "sections": [
            {
                "heading": "Market Overview",
                "paragraphs": [
                    {
                        "text": (
                            f"Public benchmark prints show SPY at {format_number(spy['last'])} "
                            f"({format_pct(spy['change_pct'])} vs prior close {format_number(spy['previous_close'])}) "
                            f"and QQQ at {format_number(qqq['last'])} "
                            f"({format_pct(qqq['change_pct'])} vs {format_number(qqq['previous_close'])})."
                            f"{vix_sentence}"
                        ),
                        "claim_ids": ["cl-spy", "cl-qqq", *vix_ids],
                    },
                    {
                        "text": (
                            f"Benchmark tape showed SPY at {format_pct(spy['change_pct'])} and "
                            f"QQQ at {format_pct(qqq['change_pct'])} in the latest public prints."
                        ),
                        "claim_ids": ["cl-regime"],
                    },
                ],
            },
            {
                "heading": "Top Movers & Why",
                "paragraphs": [
                    {
                        "text": (
                            f"Top live gainer {gainer0['symbol']} moved {format_pct(gainer0.get('change_pct'))} "
                            f"to {money(gainer0.get('price'))}. "
                            f"Additional gainer {gainer1['symbol']} moved {format_pct(gainer1.get('change_pct'))} "
                            f"to {money(gainer1.get('price'))}."
                        ),
                        "claim_ids": ["cl-gainer0", "cl-gainer1"],
                    },
                    {
                        "text": (
                            f"Top live loser {loser0['symbol']} moved {format_pct(loser0.get('change_pct'))} "
                            f"to {money(loser0.get('price'))}."
                        ),
                        "claim_ids": ["cl-loser0"],
                    },
                ],
            },
            {
                "heading": "SEC Highlights",
                "paragraphs": [
                    {
                        "text": (
                            f"The SEC current 8-K feed returned {len(filings_8k)} recent entries in this scrape, "
                            f"with {len(filings_10q)} recent 10-Q entries and {len(filings_4)} Form 4 entries."
                        ),
                        "claim_ids": ["cl-8k-count", "cl-10q-count", "cl-4-count"],
                    },
                    {
                        "text": (
                            f"A highlighted recent 8-K came from {top_8k['company']} "
                            f"(accession {top_8k['accession'] or 'n/a'})."
                        ),
                        "claim_ids": ["cl-top-8k"],
                    },
                ],
            },
            {
                "heading": f"Deep Dive — {deep_symbol}",
                "paragraphs": [
                    {
                        "text": (
                            f"{deep_symbol} focus filing is form {focus_filing['form']}, "
                            f"accession {focus_filing['accession']}, filed {focus_filing['filed']}."
                        ),
                        "claim_ids": ["cl-deep-meta"],
                    },
                    {
                        "text": f"Filing excerpt: {excerpt_sentence}",
                        "claim_ids": ["cl-deep-excerpt"],
                    },
                ],
            },
            {
                "heading": "Watchlist & Key Metric",
                "paragraphs": [
                    {
                        "text": (
                            f"Next watch item is follow-through in {deep_symbol} after the "
                            f"{focus_filing['form']} filed {focus_filing['filed']}."
                        ),
                        "claim_ids": ["cl-watch"],
                    }
                ],
            },
            {
                "heading": "Data Freshness & Limitations",
                "paragraphs": [
                    {
                        "text": (
                            f"This brief is a point-in-time live scrape at {as_of_iso}. Market prints come from "
                            f"public Yahoo Finance endpoints; filings come from SEC EDGAR atom feeds and "
                            f"company submissions JSON. Weekend/holiday sessions may reflect the prior cash close. "
                            f"SPY volume in this scrape was {volume(spy['volume'])}."
                        ),
                        "claim_ids": ["cl-spy", "cl-8k-count"],
                    }
                ],
            },
        ],
        "disclaimer": (
            "Educational market-intelligence demonstration only. Not investment advice. "
            "Figures are captured from public endpoints at the stated cutoff and may be delayed, "
            "revised, or incomplete. Always verify primary SEC filings and licensed market data "
            "before making decisions."
        ),
    }

    # Ensure summary doesn't introduce ungrounded tokens - rebuild from claims only numbers
    # The summary has as_of_iso with dates - years might need to be in claims. Dates like 2026-08-08
    # may extract 2026. Include filed date year via deep meta claim which has filed date.
    # ISO date in summary: "as of 2026-08-08T..." - 2026 might be ungrounded if not in claims.
    # cl-deep-meta has filed date like 2026-08-07 hopefully.
    # Safer summary without full ISO:
    article["summary"] = (
        f"Live scrape: SPY {format_number(spy['last'])} ({format_pct(spy['change_pct'])}), "
        f"QQQ {format_number(qqq['last'])} ({format_pct(qqq['change_pct'])}). "
        f"Top gainer {gainer0['symbol']} {format_pct(gainer0.get('change_pct'))}. "
        f"SEC feed captured {len(filings_8k)} recent 8-K entries; deep dive on {deep_symbol} "
        f"{focus_filing['form']} accession {focus_filing['accession']}."
    )

    # Fix data freshness paragraph - as_of_iso may add ungrounded date tokens
    article["sections"][-1]["paragraphs"][0]["text"] = (
        "This brief is a point-in-time live scrape from public Yahoo Finance endpoints and SEC EDGAR feeds. "
        f"SPY last traded at {format_number(spy['last'])} with volume {volume(spy['volume'])}. "
        f"The SEC current 8-K feed returned {len(filings_8k)} recent entries in this scrape."
    )

    x_thread = {
        "posts": [
            {
                "sequence": 1,
                "text": (
                    f"MarketForge live: SPY {format_number(spy['last'])} ({format_pct(spy['change_pct'])}), "
                    f"QQQ {format_number(qqq['last'])} ({format_pct(qqq['change_pct'])}). "
                    f"Top gainer {gainer0['symbol']} {format_pct(gainer0.get('change_pct'))}."
                ),
                "claim_ids": ["cl-spy", "cl-qqq", "cl-gainer0"],
            },
            {
                "sequence": 2,
                "text": (
                    f"SEC live feed: {len(filings_8k)} recent 8-K entries, {len(filings_10q)} 10-Q, "
                    f"{len(filings_4)} Form 4. Highlight: {top_8k['company']} accession "
                    f"{top_8k['accession'] or 'n/a'}."
                ),
                "claim_ids": ["cl-8k-count", "cl-10q-count", "cl-4-count", "cl-top-8k"],
            },
            {
                "sequence": 3,
                "text": (
                    f"Deep dive {deep_symbol}: {focus_filing['form']} accession {focus_filing['accession']} "
                    f"filed {focus_filing['filed']}. Educational only — not advice."
                ),
                "claim_ids": ["cl-deep-meta"],
            },
        ]
    }

    bundle = {
        "run": {"run_id": run_id, "as_of": as_of_iso, "mode": "daily_close"},
        "sources": sources,
        "evidence": evidence,
        "claims": claims,
        "article": article,
        "x_thread": x_thread,
    }

    bundle_path = run_dir / "run-bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    # Save scrape inventory for audit
    inventory = {
        "run_id": run_id,
        "as_of": as_of_iso,
        "benchmarks": {
            "SPY": {k: spy[k] for k in ("last", "previous_close", "change_pct", "volume", "url")},
            "QQQ": {k: qqq[k] for k in ("last", "previous_close", "change_pct", "volume", "url")},
            "VIX": (
                {k: vix[k] for k in ("last", "previous_close", "change_pct", "volume", "url")}
                if vix
                else None
            ),
        },
        "gainers": gainers["quotes"][:8],
        "losers": losers["quotes"][:8],
        "sec_counts": {"8-K": len(filings_8k), "10-Q": len(filings_10q), "4": len(filings_4)},
        "deep_dive": {
            "symbol": deep_symbol,
            "cik": deep_meta["cik10"],
            "filing": focus_filing,
            "excerpt_url": excerpt_url,
        },
    }
    (run_dir / "scrape-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    try:
        result = validate_run_bundle(bundle, artifact_root=run_dir)
    except ValidationError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        print(f"Bundle left at {bundle_path} for debugging", file=sys.stderr)
        return 2

    html = render_article(bundle)
    report_name = f"live-brief-{as_of.strftime('%Y-%m-%d')}.html"
    report_path = out_dir / report_name
    latest_path = out_dir / "index.html"
    report_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")

    (ROOT / "site" / "index.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=output/{report_name}">
<title>MarketForge Live</title>
<style>body{{margin:0;background:#071018;color:#e8f0f5;font-family:system-ui;display:grid;place-items:center;min-height:100vh}}a{{color:#7be0bd}}</style>
</head><body><p>Opening live brief… <a href="output/{report_name}">open report</a></p></body></html>
""",
        encoding="utf-8",
    )

    (run_dir / "x-thread.json").write_text(json.dumps(x_thread, indent=2), encoding="utf-8")

    print("PUBLISHABLE:", run_id)
    print("AS_OF:", as_of_iso)
    print("DEEP_DIVE:", deep_symbol, focus_filing["form"], focus_filing["accession"])
    print("BUNDLE:", bundle_path)
    print("REPORT:", report_path)
    print("LATEST:", latest_path)
    print("CLAIMS:", len(claims), "SOURCES:", len(sources), "EVIDENCE:", len(evidence))
    print("STATUS:", "publishable" if result.publishable else "blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
