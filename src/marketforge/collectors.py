"""Live MarketForge collectors: SEC EDGAR + public market data."""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


SEC_UA = "MarketForge Research contact@example.com"
YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass
class FetchedDocument:
    url: str
    content_type: str
    text: str
    raw: bytes


def fetch(
    url: str,
    *,
    user_agent: str,
    timeout: int = 45,
    accept: str | None = None,
    host: str | None = None,
) -> FetchedDocument:
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if accept:
        headers["Accept"] = accept
    if host:
        headers["Host"] = host
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc

    text = raw.decode("utf-8", errors="replace")
    return FetchedDocument(url=url, content_type=content_type, text=text, raw=raw)


def polite_pause(seconds: float = 0.2) -> None:
    time.sleep(seconds)


def fetch_sec(url: str) -> FetchedDocument:
    polite_pause(0.2)
    host = "data.sec.gov" if "data.sec.gov" in url else "www.sec.gov"
    return fetch(
        url,
        user_agent=SEC_UA,
        accept="application/atom+xml,application/json,text/html,*/*",
        host=host,
    )


def fetch_yahoo(url: str) -> FetchedDocument:
    polite_pause(0.1)
    return fetch(url, user_agent=YAHOO_UA, accept="application/json")


def strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    no_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", no_tags).strip()


def parse_atom_filings(atom_text: str, limit: int = 12) -> list[dict[str, Any]]:
    root = ET.fromstring(atom_text)
    filings: list[dict[str, Any]] = []
    for entry in root.findall("a:entry", ATOM_NS)[:limit]:
        title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
        link_el = entry.find("a:link", ATOM_NS)
        href = link_el.get("href") if link_el is not None else ""
        if href.startswith("/"):
            href = "https://www.sec.gov" + href
        summary = strip_html(entry.findtext("a:summary", default="", namespaces=ATOM_NS) or "")
        updated = entry.findtext("a:updated", default="", namespaces=ATOM_NS) or ""
        form = ""
        category = entry.find("a:category", ATOM_NS)
        if category is not None:
            form = category.get("term", "") or ""
        accession = ""
        acc_match = re.search(r"AccNo:\s*([0-9\-]+)", summary)
        if acc_match:
            accession = acc_match.group(1)
        company = title
        tickerish = title
        # title format: "8-K - Company Name (0001234567) (Filer)"
        company_match = re.match(r"^[^-]+-\s*(.+?)\s*\(\d+\)", title)
        if company_match:
            company = company_match.group(1).strip()
        filings.append(
            {
                "title": title,
                "company": company,
                "form": form or title.split(" - ")[0].strip(),
                "url": href,
                "summary": summary,
                "updated": updated,
                "accession": accession,
                "raw_title": tickerish,
            }
        )
    return filings


def yahoo_chart(symbol: str, range_: str = "5d", interval: str = "1d") -> dict[str, Any]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?interval={interval}&range={range_}"
    )
    doc = fetch_yahoo(url)
    payload = json.loads(doc.text)
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        error = (payload.get("chart") or {}).get("error")
        raise RuntimeError(f"No chart data for {symbol}: {error}")
    meta = result[0].get("meta") or {}
    indicators = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    closes = [c for c in (indicators.get("close") or []) if c is not None]
    volumes = [v for v in (indicators.get("volume") or []) if v is not None]
    previous = meta.get("chartPreviousClose")
    last = meta.get("regularMarketPrice")
    if last is None and closes:
        last = closes[-1]
    change_pct = None
    if last is not None and previous not in (None, 0):
        change_pct = (float(last) - float(previous)) / float(previous) * 100.0
    return {
        "symbol": meta.get("symbol") or symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "last": float(last) if last is not None else None,
        "previous_close": float(previous) if previous is not None else None,
        "change_pct": change_pct,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "volume": meta.get("regularMarketVolume") or (volumes[-1] if volumes else None),
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "as_of_unix": meta.get("regularMarketTime"),
        "raw_json": doc.text,
        "url": url,
    }


def yahoo_screener(scr_id: str, count: int = 10) -> dict[str, Any]:
    url = (
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        f"?formatted=false&lang=en-US&region=US&scrIds={scr_id}&count={count}"
    )
    doc = fetch_yahoo(url)
    payload = json.loads(doc.text)
    result = (payload.get("finance") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"No screener results for {scr_id}")
    quotes = result[0].get("quotes") or []
    rows: list[dict[str, Any]] = []
    for quote in quotes:
        rows.append(
            {
                "symbol": quote.get("symbol"),
                "name": quote.get("shortName") or quote.get("longName") or quote.get("symbol"),
                "price": quote.get("regularMarketPrice"),
                "change_pct": quote.get("regularMarketChangePercent"),
                "volume": quote.get("regularMarketVolume"),
                "market_cap": quote.get("marketCap"),
                "sector": quote.get("sector"),
            }
        )
    return {"id": scr_id, "title": result[0].get("title") or scr_id, "url": url, "raw_json": doc.text, "quotes": rows}


def load_company_tickers() -> dict[str, dict[str, Any]]:
    url = "https://www.sec.gov/files/company_tickers.json"
    doc = fetch_sec(url)
    payload = json.loads(doc.text)
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in payload.values():
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        by_ticker[ticker] = {
            "ticker": ticker,
            "cik": int(row["cik_str"]),
            "cik10": f"{int(row['cik_str']):010d}",
            "title": row.get("title") or ticker,
            "source_url": url,
            "raw_json": doc.text if ticker == "AAPL" else None,  # avoid huge duplication later
        }
    # attach one shared raw blob via sentinel
    by_ticker["__raw__"] = {"raw_json": doc.text, "url": url}
    return by_ticker


def sec_company_submissions(cik10: str) -> dict[str, Any]:
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    doc = fetch_sec(url)
    payload = json.loads(doc.text)
    payload["_source_url"] = url
    payload["_raw_json"] = doc.text
    return payload


def recent_company_filings(submissions: dict[str, Any], forms: set[str], limit: int = 8) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms_list = recent.get("form", [])
    out: list[dict[str, Any]] = []
    for idx, form in enumerate(forms_list):
        if form not in forms:
            continue
        accession = recent.get("accessionNumber", [None])[idx]
        primary = recent.get("primaryDocument", [None])[idx]
        filed = recent.get("filingDate", [None])[idx]
        report_date = recent.get("reportDate", [None])[idx]
        items = recent.get("items", [None])[idx] if "items" in recent else None
        description = recent.get("primaryDocDescription", [None])[idx]
        cik = str(submissions.get("cik") or "").lstrip("0") or "0"
        acc_nodash = (accession or "").replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{accession}-index.htm"
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{primary}"
            if primary
            else index_url
        )
        out.append(
            {
                "form": form,
                "accession": accession,
                "filed": filed,
                "report_date": report_date,
                "items": items,
                "description": description,
                "primary_document": primary,
                "index_url": index_url,
                "document_url": doc_url,
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_filing_excerpt(url: str, max_chars: int = 12000) -> str:
    doc = fetch_sec(url)
    text = strip_html(doc.text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{float(value):,.{digits}f}"


def format_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}%"
