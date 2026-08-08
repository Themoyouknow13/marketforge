from __future__ import annotations

from html import escape
from typing import Any


def _locator_text(locator: dict[str, Any]) -> str:
    parts: list[str] = []
    if locator.get("section"):
        parts.append(str(locator["section"]))
    if locator.get("note"):
        parts.append(f"Note {locator['note']}")
    if locator.get("page") is not None:
        parts.append(f"p. {locator['page']}")
    if locator.get("json_pointer"):
        parts.append(f"pointer {locator['json_pointer']}")
    return ", ".join(parts) or "locator on file"


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "section"


def _source_chips(links: list[dict[str, Any]] | None) -> str:
    if not links:
        return ""
    chips = []
    for link in links:
        label = escape(str(link.get("label") or "Source"))
        url = escape(str(link.get("url") or "#"))
        kind = escape(str(link.get("kind") or "source"))
        chips.append(
            f'<a class="source-chip {kind}" href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )
    return f'<div class="source-chips">{"".join(chips)}</div>'


def _meaning_block(block: dict[str, Any]) -> str:
    print_line = escape(str(block.get("print_line") or block.get("text") or ""))
    context = escape(str(block.get("context_line") or ""))
    implication = escape(str(block.get("implication_line") or ""))
    return f"""
    <div class="meaning">
      <p class="print mono">{print_line}</p>
      {"<p class='context'><span>Context</span> " + context + "</p>" if context else ""}
      {"<p class='implication'><span>So what</span> " + implication + "</p>" if implication else ""}
      {_source_chips(block.get("links"))}
    </div>
    """


def _benchmark_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    items = []
    for card in cards:
        direction = escape(str(card.get("direction") or "flat"))
        items.append(
            f"""
            <article class="tile benchmark {direction}">
              <div class="tile-top">
                <div class="symbol mono">{escape(str(card.get('symbol') or ''))}</div>
                <div class="dir">{'▲' if direction=='up' else '▼' if direction=='down' else '•'}</div>
              </div>
              <p class="print mono">{escape(str(card.get('print_line') or ''))}</p>
              <p class="context">{escape(str(card.get('context_line') or ''))}</p>
              <p class="implication">{escape(str(card.get('implication_line') or ''))}</p>
              {_source_chips(card.get('links'))}
            </article>
            """
        )
    return f'<div class="card-grid benchmarks">{"".join(items)}</div>'


def _mover_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    items = []
    for card in cards:
        side = escape(str(card.get("side") or ""))
        catalyst = escape(str(card.get("catalyst_status") or "none"))
        catalyst_label = {
            "filing": "Catalyst: filing in package",
            "news": "Catalyst: news in package",
            "none": "Catalyst: none in package",
        }.get(str(card.get("catalyst_status") or "none"), "Catalyst: unknown")
        items.append(
            f"""
            <article class="tile mover {side}">
              <div class="tile-top">
                <div class="symbol mono">{escape(str(card.get('symbol') or ''))}</div>
                <div class="pill {catalyst}">{escape(catalyst_label)}</div>
              </div>
              <p class="print mono">{escape(str(card.get('print_line') or ''))}</p>
              <p class="context"><span>Why it screened</span> {escape(str(card.get('context_line') or ''))}</p>
              <p class="implication"><span>So what</span> {escape(str(card.get('implication_line') or ''))}</p>
              {_source_chips(card.get('links'))}
            </article>
            """
        )
    return f'<div class="card-grid movers">{"".join(items)}</div>'


def _filing_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    items = []
    for card in cards:
        items.append(
            f"""
            <article class="tile filing">
              <div class="tile-top">
                <div class="symbol">{escape(str(card.get('title') or 'Filing'))}</div>
                <div class="pill filing">SEC</div>
              </div>
              <p class="print mono">{escape(str(card.get('print_line') or ''))}</p>
              <p class="context"><span>Context</span> {escape(str(card.get('context_line') or ''))}</p>
              <p class="implication"><span>So what</span> {escape(str(card.get('implication_line') or ''))}</p>
              {_source_chips(card.get('links'))}
            </article>
            """
        )
    return f'<div class="card-grid filings">{"".join(items)}</div>'


def render_article(bundle: dict[str, Any]) -> str:
    """Render a validated article bundle as a Terminal Research desk page."""

    article = bundle["article"]
    run = bundle["run"]
    sources = {item["id"]: item for item in bundle["sources"]}
    evidence = {item["id"]: item for item in bundle["evidence"]}
    claims = {item["id"]: item for item in bundle["claims"]}
    desk = article.get("desk")

    # Fallback: classic sections if no desk payload.
    if not desk:
        return _render_classic(bundle)

    nav = "".join(
        f'<a href="{escape(item["href"])}">{escape(item["label"])}</a>'
        for item in desk.get("nav") or []
    )

    section_html: list[str] = []
    toc_items: list[str] = []
    for section in desk.get("sections") or []:
        section_id = escape(str(section.get("id") or _slug(section.get("heading", "section"))))
        heading = escape(str(section.get("heading") or "Section"))
        kicker = escape(str(section.get("kicker") or ""))
        toc_items.append(f'<li><a href="#{section_id}">{heading}</a></li>')
        blocks = "".join(_meaning_block(block) for block in section.get("blocks") or [])
        kind = section.get("card_kind") or "none"
        cards = section.get("cards") or []
        if kind == "benchmark":
            card_html = _benchmark_cards(cards)
        elif kind == "mover":
            card_html = _mover_cards(cards)
        elif kind == "filing":
            card_html = _filing_cards(cards)
        else:
            card_html = ""
        section_html.append(
            f"""
            <section class="desk-section" id="{section_id}">
              <div class="section-head">
                <div>
                  <div class="kicker">{kicker}</div>
                  <h2>{heading}</h2>
                </div>
              </div>
              {blocks}
              {card_html}
            </section>
            """
        )

    # Evidence drawer
    claim_items: list[str] = []
    for claim_id, claim in claims.items():
        evidence_items: list[str] = []
        for evidence_id in claim["evidence_ids"]:
            item = evidence[evidence_id]
            source = sources[item["source_id"]]
            locator = _locator_text(item.get("locator", {}))
            evidence_text = item.get("quote", item.get("value", ""))
            tier = source.get("tier", "?")
            evidence_items.append(
                "<li>"
                f'<a href="{escape(source["url"])}" target="_blank" rel="noopener noreferrer">{escape(source["title"])}</a>'
                f' <span class="meta">Tier {escape(str(tier))} · {escape(locator)}</span>'
                f"<blockquote>{escape(str(evidence_text))}</blockquote>"
                "</li>"
            )
        claim_type = escape(str(claim.get("claim_type", "fact")))
        claim_items.append(
            f'<article class="claim-card" id="claim-{escape(claim_id)}">'
            f'<div class="claim-head"><h3 class="mono">{escape(claim_id)}</h3>'
            f'<span class="pill">{claim_type}</span></div>'
            f"<p>{escape(claim['text'])}</p>"
            f"<ul>{''.join(evidence_items)}</ul></article>"
        )

    source_rows = "".join(
        "<tr>"
        f"<td class='mono'>{escape(source['id'])}</td>"
        f"<td><a href=\"{escape(source['url'])}\" target=\"_blank\" rel=\"noopener noreferrer\">{escape(source['title'])}</a></td>"
        f"<td>{escape(str(source.get('publisher', '')))}</td>"
        f"<td>{escape(str(source.get('tier', '')))}</td>"
        f"<td class='mono'><code>{escape(source.get('content_sha256', '')[:12])}…</code></td>"
        "</tr>"
        for source in bundle["sources"]
    )

    summary_links = _source_chips(desk.get("summary_links"))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{escape(str(desk.get('summary') or article['summary'])[:240])}">
<meta name="robots" content="index,follow">
<title>{escape(article['title'])}</title>
<style>
:root {{
  color-scheme: dark;
  --bg:#070d14;
  --panel:#0f1822;
  --panel2:#132030;
  --line:#243445;
  --text:#e7eef5;
  --muted:#8fa3b5;
  --accent:#3dde9c;
  --up:#3dde9c;
  --down:#ff6b7a;
  --chip:#1a2a39;
  --link:#7cc4ff;
  --warn:#ffd27a;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
  font-family: var(--sans);
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:
  radial-gradient(1200px 500px at 10% -10%, #143049 0%, transparent 55%),
  radial-gradient(900px 400px at 90% 0%, #10261d 0%, transparent 40%),
  var(--bg); color:var(--text); }}
a {{ color:var(--link); }}
.shell {{ max-width:1180px; margin:auto; padding:18px 16px 80px; }}
.topnav {{
  position:sticky; top:0; z-index:20; backdrop-filter: blur(10px);
  display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between;
  padding:10px 0 14px; margin-bottom:8px; border-bottom:1px solid rgba(36,52,69,.8);
  background:rgba(7,13,20,.82);
}}
.brand {{ display:flex; gap:8px; align-items:center; color:var(--muted); font-size:.9rem; }}
.brand strong {{ color:var(--accent); letter-spacing:.04em; }}
.navlinks {{ display:flex; gap:8px; flex-wrap:wrap; }}
.navlinks a {{
  text-decoration:none; color:#d5e4f0; border:1px solid var(--line); background:rgba(15,24,34,.9);
  border-radius:999px; padding:.4rem .75rem; font-size:.86rem;
}}
.navlinks a:hover {{ border-color:var(--accent); color:white; }}
.hero {{
  display:grid; grid-template-columns: 1.4fr .8fr; gap:16px; margin:18px 0 20px;
}}
.hero-main, .hero-rail, .desk-section, .drawer {{
  background:linear-gradient(180deg, rgba(19,32,48,.95), rgba(15,24,34,.92));
  border:1px solid var(--line); border-radius:18px;
}}
.hero-main {{ padding:22px; }}
.hero-rail {{ padding:16px; }}
.kicker {{ color:var(--accent); text-transform:uppercase; letter-spacing:.08em; font-size:.75rem; font-weight:700; }}
h1 {{ margin:8px 0 12px; font-size:clamp(1.8rem, 4vw, 2.8rem); letter-spacing:-.03em; line-height:1.05; }}
h2 {{ margin:0; font-size:1.35rem; letter-spacing:-.02em; }}
.summary {{ color:#c9d7e4; line-height:1.7; font-size:1.05rem; }}
.meta {{ color:var(--muted); font-size:.86rem; }}
.mono {{ font-family:var(--mono); }}
.rail-stats {{ display:grid; gap:10px; }}
.stat {{
  background:rgba(7,13,20,.45); border:1px solid var(--line); border-radius:12px; padding:12px;
}}
.stat span {{ display:block; color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.07em; }}
.stat strong {{ display:block; margin-top:4px; font-size:1.15rem; }}
.layout {{ display:grid; grid-template-columns: 200px minmax(0,1fr); gap:16px; }}
.toc {{
  position:sticky; top:64px; align-self:start; border:1px solid var(--line); border-radius:16px;
  background:rgba(15,24,34,.9); padding:14px;
}}
.toc h3 {{ margin:0 0 8px; color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }}
.toc ol {{ margin:0; padding-left:1.1rem; color:var(--muted); }}
.toc a {{ color:#d7e6ef; text-decoration:none; font-size:.9rem; }}
.desk-section {{ padding:18px 18px 16px; margin-bottom:14px; }}
.section-head {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:12px; }}
.meaning {{
  background:rgba(7,13,20,.35); border:1px solid rgba(36,52,69,.85); border-radius:14px;
  padding:14px; margin-bottom:12px;
}}
.meaning .print {{ margin:0 0 8px; font-size:.98rem; color:#f2f7fb; }}
.context, .implication {{ margin:8px 0; color:#c4d3e0; line-height:1.6; }}
.context span, .implication span {{
  display:inline-block; min-width:64px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.06em; font-size:.72rem; font-weight:700; margin-right:6px;
}}
.source-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
.source-chip {{
  display:inline-flex; align-items:center; gap:.35rem; text-decoration:none;
  border:1px solid var(--line); background:var(--chip); color:#dceaf7;
  border-radius:999px; padding:.35rem .7rem; font-size:.8rem;
}}
.source-chip:hover {{ border-color:var(--link); color:white; }}
.source-chip.sec {{ border-color:#35506a; }}
.source-chip.market {{ border-color:#2f5a48; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }}
.tile {{
  background:rgba(7,13,20,.5); border:1px solid var(--line); border-radius:14px; padding:12px 12px 10px;
}}
.tile-top {{ display:flex; justify-content:space-between; gap:8px; align-items:center; margin-bottom:8px; }}
.symbol {{ font-weight:700; letter-spacing:.03em; }}
.tile .print {{ margin:0 0 8px; font-size:.86rem; color:#eef5fb; line-height:1.45; }}
.tile .context, .tile .implication {{ font-size:.88rem; }}
.benchmark.up {{ box-shadow: inset 3px 0 0 var(--up); }}
.benchmark.down {{ box-shadow: inset 3px 0 0 var(--down); }}
.mover.gainer {{ box-shadow: inset 3px 0 0 var(--up); }}
.mover.loser {{ box-shadow: inset 3px 0 0 var(--down); }}
.filing {{ box-shadow: inset 3px 0 0 #7cc4ff; }}
.dir {{ color:var(--muted); }}
.benchmark.up .dir {{ color:var(--up); }}
.benchmark.down .dir {{ color:var(--down); }}
.pill {{
  border-radius:999px; border:1px solid var(--line); color:var(--muted);
  padding:.18rem .5rem; font-size:.7rem; text-transform:uppercase; letter-spacing:.05em;
}}
.pill.filing {{ color:#9fd0ff; border-color:#35506a; }}
.pill.none {{ color:var(--warn); border-color:#5a4a28; }}
.drawer {{ padding:8px 16px 16px; margin-top:16px; }}
.drawer summary {{
  cursor:pointer; list-style:none; padding:12px 0; color:var(--muted);
  text-transform:uppercase; letter-spacing:.08em; font-size:.78rem; font-weight:700;
}}
.claim-card {{
  background:rgba(7,13,20,.45); border:1px solid var(--line); border-radius:12px;
  padding:12px; margin:10px 0;
}}
.claim-head {{ display:flex; justify-content:space-between; gap:8px; align-items:center; }}
.claim-card h3 {{ margin:0; color:var(--warn); font-size:.95rem; }}
blockquote {{ margin:8px 0 0; padding-left:10px; border-left:3px solid var(--accent); color:#b7c8d6; }}
table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
th, td {{ text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); vertical-align:top; font-size:.9rem; }}
th {{ color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }}
.disclaimer {{
  margin-top:16px; color:var(--muted); border:1px solid var(--line); border-radius:14px;
  padding:14px 16px; line-height:1.65; background:rgba(15,24,34,.7);
}}
footer {{ margin-top:14px; text-align:center; color:#6d8192; font-size:.82rem; }}
@media (max-width: 960px) {{
  .hero, .layout {{ grid-template-columns:1fr; }}
  .toc {{ position:static; }}
}}
</style>
</head>
<body>
<div class="shell">
  <div class="topnav">
    <div class="brand"><strong>MARKETFORGE</strong><span>Terminal Research</span></div>
    <nav class="navlinks" aria-label="Desk navigation">{nav}</nav>
  </div>

  <header class="hero">
    <div class="hero-main">
      <div class="kicker">Daily desk brief · {escape(str(run.get('mode','')))}</div>
      <h1>{escape(article['title'])}</h1>
      <p class="summary">{escape(str(desk.get('summary') or article['summary']))}</p>
      {summary_links}
      <p class="meta" style="margin-top:12px">As of <span class="mono">{escape(run['as_of'])}</span> · run <span class="mono">{escape(run['run_id'])}</span></p>
    </div>
    <aside class="hero-rail">
      <div class="rail-stats">
        <div class="stat"><span>Sources</span><strong>{len(bundle['sources'])}</strong></div>
        <div class="stat"><span>Evidence</span><strong>{len(bundle['evidence'])}</strong></div>
        <div class="stat"><span>Claims</span><strong>{len(bundle['claims'])}</strong></div>
        <div class="stat"><span>Publish gate</span><strong>Validated</strong></div>
        <div class="stat"><span>Ideas desk</span><strong><a href="dual-thesis.html">Bull / Bear</a></strong></div>
      </div>
    </aside>
  </header>

  <div class="layout">
    <nav class="toc" aria-label="Contents">
      <h3>Contents</h3>
      <ol>{''.join(toc_items)}<li><a href="#sources-drawer">Sources</a></li></ol>
    </nav>
    <main>
      {''.join(section_html)}

      <details class="drawer" id="sources-drawer">
        <summary>Sources &amp; evidence drawer · open for provenance</summary>
        <p class="meta">Primary reading uses source chips above. This drawer keeps the full fail-closed ledger available without blocking the desk flow.</p>
        <h3>Source index</h3>
        <table>
          <thead><tr><th>ID</th><th>Title</th><th>Publisher</th><th>Tier</th><th>Hash</th></tr></thead>
          <tbody>{source_rows}</tbody>
        </table>
        <h3 style="margin-top:18px">Claim ledger</h3>
        {''.join(claim_items)}
      </details>

      <p class="disclaimer">{escape(article['disclaimer'])}</p>
      <footer>MarketForge Terminal Research · educational only · not investment advice</footer>
    </main>
  </div>
</div>
</body>
</html>"""


def _render_classic(bundle: dict[str, Any]) -> str:
    """Backward-compatible classic renderer when desk payload is absent."""

    article = bundle["article"]
    run = bundle["run"]
    # Minimal classic path: reuse desk shell with section paragraphs only.
    pseudo_sections = []
    for section in article.get("sections", []):
        blocks = []
        for paragraph in section.get("paragraphs", []):
            blocks.append(
                {
                    "print_line": paragraph.get("text", ""),
                    "context_line": "",
                    "implication_line": "",
                    "claim_ids": paragraph.get("claim_ids") or [],
                    "links": [],
                }
            )
        pseudo_sections.append(
            {
                "id": _slug(section.get("heading", "section")),
                "heading": section.get("heading", "Section"),
                "kicker": "Brief",
                "blocks": blocks,
                "cards": [],
                "card_kind": "none",
            }
        )
    enriched = dict(bundle)
    enriched_article = dict(article)
    enriched_article["desk"] = {
        "design": "classic-fallback",
        "summary": article.get("summary", ""),
        "summary_claim_ids": article.get("summary_claim_ids") or [],
        "summary_links": [],
        "sections": pseudo_sections,
        "nav": [{"href": f"#{s['id']}", "label": s["heading"]} for s in pseudo_sections]
        + [{"href": "#sources-drawer", "label": "Sources"}],
    }
    enriched["article"] = enriched_article
    # Prevent recursion
    if not enriched["article"]["desk"]["sections"]:
        return "<html><body>Empty article</body></html>"
    return render_article(enriched)
