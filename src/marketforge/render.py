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


def render_article(bundle: dict[str, Any]) -> str:
    """Render a validated article bundle as a self-contained cited HTML page."""

    article = bundle["article"]
    run = bundle["run"]
    sources = {item["id"]: item for item in bundle["sources"]}
    evidence = {item["id"]: item for item in bundle["evidence"]}
    claims = {item["id"]: item for item in bundle["claims"]}

    summary_anchors = "".join(
        f'<a class="claim" href="#claim-{escape(claim_id)}">[{escape(claim_id)}]</a>'
        for claim_id in article["summary_claim_ids"]
    )

    toc_items: list[str] = []
    body_sections: list[str] = []
    for section in article.get("sections", []):
        section_id = _slug(section["heading"])
        toc_items.append(f'<li><a href="#{escape(section_id)}">{escape(section["heading"])}</a></li>')
        paragraphs: list[str] = []
        for paragraph in section.get("paragraphs", []):
            anchors = "".join(
                f'<a class="claim" href="#claim-{escape(claim_id)}">[{escape(claim_id)}]</a>'
                for claim_id in paragraph["claim_ids"]
            )
            paragraphs.append(f"<p>{escape(paragraph['text'])} {anchors}</p>")
        body_sections.append(
            f'<section id="{escape(section_id)}">'
            f"<h2>{escape(section['heading'])}</h2>"
            f"{''.join(paragraphs)}"
            "</section>"
        )

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
                f'<a href="{escape(source["url"])}">{escape(source["title"])}</a>'
                f" <span class=\"meta\">Tier {escape(str(tier))} · {escape(locator)}</span>"
                f"<blockquote>{escape(str(evidence_text))}</blockquote>"
                "</li>"
            )
        claim_type = escape(str(claim.get("claim_type", "fact")))
        claim_items.append(
            f'<article class="claim-card" id="claim-{escape(claim_id)}">'
            f'<div class="claim-head"><h3>{escape(claim_id)}</h3>'
            f'<span class="pill">{claim_type}</span></div>'
            f"<p>{escape(claim['text'])}</p>"
            f"<ul>{''.join(evidence_items)}</ul></article>"
        )

    source_rows = "".join(
        "<tr>"
        f"<td>{escape(source['id'])}</td>"
        f"<td><a href=\"{escape(source['url'])}\">{escape(source['title'])}</a></td>"
        f"<td>{escape(str(source.get('publisher', '')))}</td>"
        f"<td>{escape(str(source.get('tier', '')))}</td>"
        f"<td><code>{escape(source.get('content_sha256', '')[:12])}…</code></td>"
        "</tr>"
        for source in bundle["sources"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{escape(article['summary'][:240])}">
<meta name="robots" content="index,follow">
<title>{escape(article['title'])}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #071018;
  --panel: #101d27;
  --line: #223746;
  --text: #e8f0f5;
  --muted: #96a8b4;
  --accent: #7be0bd;
  --claim: #ffca64;
  --link: #81bff8;
  --pill: #1b3344;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: radial-gradient(circle at top, #0d1b27 0%, var(--bg) 42%); color: var(--text); }}
.shell {{ max-width: 980px; margin: auto; padding: 28px 20px 96px; }}
.topbar {{
  display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  align-items: center; margin-bottom: 28px; color: var(--muted); font-size: .92rem;
}}
.badge {{
  display: inline-flex; gap: .5rem; align-items: center;
  border: 1px solid var(--line); background: rgba(16,29,39,.85);
  border-radius: 999px; padding: .45rem .85rem;
}}
.badge strong {{ color: var(--accent); font-weight: 600; }}
header.hero {{
  background: linear-gradient(180deg, rgba(16,29,39,.95), rgba(16,29,39,.55));
  border: 1px solid var(--line); border-radius: 22px; padding: 28px 28px 24px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
}}
h1 {{
  font-size: clamp(2rem, 5vw, 3.4rem); line-height: 1.02; letter-spacing: -0.03em;
  margin: 10px 0 14px;
}}
.summary {{ font-size: 1.12rem; line-height: 1.7; color: #c5d4de; margin: 0; }}
.meta-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-top: 22px;
}}
.meta-card {{
  background: rgba(7,16,24,.55); border: 1px solid var(--line);
  border-radius: 14px; padding: 12px 14px;
}}
.meta-card span {{ display: block; color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }}
.meta-card strong {{ display: block; margin-top: 4px; font-size: .98rem; }}
.layout {{
  display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 28px; margin-top: 28px;
}}
nav.toc {{
  position: sticky; top: 18px; align-self: start;
  background: rgba(16,29,39,.8); border: 1px solid var(--line);
  border-radius: 16px; padding: 16px;
}}
nav.toc h2 {{ margin: 0 0 10px; font-size: .85rem; color: var(--accent); text-transform: uppercase; letter-spacing: .08em; }}
nav.toc ol {{ margin: 0; padding-left: 1.1rem; color: var(--muted); }}
nav.toc a {{ color: #d7e6ef; text-decoration: none; font-size: .92rem; }}
nav.toc a:hover {{ color: var(--accent); }}
main.article section {{
  background: rgba(16,29,39,.55); border: 1px solid var(--line);
  border-radius: 18px; padding: 8px 22px 18px; margin-bottom: 18px;
}}
h2 {{ margin-top: 18px; color: var(--accent); font-size: 1.25rem; }}
p {{ line-height: 1.8; color: #dce7ee; }}
.claim {{ color: var(--claim); margin-left: .15rem; text-decoration: none; font-size: .92em; }}
.claim:hover {{ text-decoration: underline; }}
.ledger {{ margin-top: 18px; }}
.claim-card {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 16px;
  padding: 16px 18px; margin: 14px 0;
}}
.claim-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
.claim-card h3 {{ margin: 0; font-size: 1rem; color: var(--claim); }}
.pill {{
  display: inline-block; background: var(--pill); color: var(--accent);
  border-radius: 999px; padding: .2rem .6rem; font-size: .75rem; text-transform: uppercase;
}}
.claim-card ul {{ padding-left: 1.1rem; }}
.claim-card li {{ margin: 10px 0; }}
.meta {{ color: var(--muted); font-size: .86rem; }}
blockquote {{
  color: #b8c8d2; border-left: 3px solid var(--accent); margin: 8px 0 0;
  padding: 4px 0 4px 12px;
}}
table {{
  width: 100%; border-collapse: collapse; margin-top: 12px;
  background: rgba(16,29,39,.55); border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
}}
th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86em; color: #cfe7ff; }}
a {{ color: var(--link); }}
.disclaimer {{
  margin-top: 28px; padding: 18px 20px; border: 1px solid var(--line);
  border-radius: 16px; color: var(--muted); background: rgba(16,29,39,.55); line-height: 1.7;
}}
footer {{
  margin-top: 24px; color: #6f8290; font-size: .86rem; text-align: center;
}}
@media (max-width: 860px) {{
  .layout {{ grid-template-columns: 1fr; }}
  nav.toc {{ position: static; }}
}}
</style>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="badge"><strong>MarketForge</strong><span>Daily Intelligence</span></div>
    <div>Run <code>{escape(run['run_id'])}</code> · mode <code>{escape(str(run.get('mode', '')))}</code></div>
  </div>

  <header class="hero">
    <div class="badge">As of {escape(run['as_of'])}</div>
    <h1>{escape(article['title'])}</h1>
    <p class="summary">{escape(article['summary'])} {summary_anchors}</p>
    <div class="meta-grid">
      <div class="meta-card"><span>Sources</span><strong>{len(bundle['sources'])}</strong></div>
      <div class="meta-card"><span>Evidence</span><strong>{len(bundle['evidence'])}</strong></div>
      <div class="meta-card"><span>Claims</span><strong>{len(bundle['claims'])}</strong></div>
      <div class="meta-card"><span>Publish gate</span><strong>Validated</strong></div>
    </div>
  </header>

  <div class="layout">
    <nav class="toc" aria-label="Table of contents">
      <h2>Contents</h2>
      <ol>
        {''.join(toc_items)}
        <li><a href="#sources">Source index</a></li>
        <li><a href="#ledger">Claim &amp; evidence ledger</a></li>
      </ol>
    </nav>
    <main class="article">
      {''.join(body_sections)}

      <section id="sources">
        <h2>Source Index</h2>
        <p>Every publishable statement in this report traces to one of these hashed snapshots.</p>
        <table>
          <thead><tr><th>ID</th><th>Title</th><th>Publisher</th><th>Tier</th><th>Hash</th></tr></thead>
          <tbody>{source_rows}</tbody>
        </table>
      </section>

      <section class="ledger" id="ledger">
        <h2>Claim &amp; Evidence Ledger</h2>
        <p>Click any gold claim marker in the article to jump here. Expand the supporting quote and source path before acting on a statement.</p>
        {''.join(claim_items)}
      </section>

      <p class="disclaimer">{escape(article['disclaimer'])}</p>
      <footer>Generated by MarketForge · fail-closed claim lineage · educational use only</footer>
    </main>
  </div>
</div>
</body>
</html>"""
