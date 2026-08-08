from __future__ import annotations

from html import escape
from typing import Any


def _anchors(claim_ids: list[str]) -> str:
    return "".join(
        f'<a class="claim" href="#claim-{escape(cid)}">[{escape(cid)}]</a>'
        for cid in claim_ids
    )


def render_thesis_page(thesis: dict[str, Any], *, approved_bundle: dict[str, Any]) -> str:
    """Render bull/bear × popular/contrarian thesis page."""

    run = thesis["run"]
    claims = {c["id"]: c for c in approved_bundle["claims"]}
    polarization = thesis.get("polarization") or {}
    frames = thesis["frames"]

    def frame_card(key: str) -> str:
        frame = frames[key]
        stance = frame.get("stance", "")
        style = frame.get("style", "")
        body = "".join(
            f"<p>{escape(p['text'])} {_anchors(p['claim_ids'])}</p>" for p in frame["paragraphs"]
        )
        falsifiers = "".join(
            f"<li>{escape(f['text'])} {_anchors(f['claim_ids'])}</li>"
            for f in frame.get("falsifiers") or []
        )
        return f"""
        <article class="frame {escape(stance)} {escape(style)}" id="{escape(key)}">
          <div class="frame-head">
            <h3>{escape(frame['title'])}</h3>
            <div class="tags">
              <span class="tag stance">{escape(stance)}</span>
              <span class="tag style">{escape(style)}</span>
            </div>
          </div>
          {body}
          <h4>What would falsify this</h4>
          <ul>{falsifiers}</ul>
        </article>
        """

    dialectic_rows = "".join(
        "<tr>"
        f"<td><strong>Bull point</strong><p>{escape(row['point'])} {_anchors(row['point_claim_ids'])}</p></td>"
        f"<td><strong>Bear counter</strong><p>{escape(row['counterpoint'])} {_anchors(row['counterpoint_claim_ids'])}</p></td>"
        "</tr>"
        for row in thesis.get("dialectic") or []
    )

    claim_cards = "".join(
        f'<article class="claim-card" id="claim-{escape(cid)}"><h3>{escape(cid)}</h3>'
        f"<p>{escape(claim['text'])}</p>"
        f'<div class="meta">{escape(claim.get("claim_type", ""))}</div></article>'
        for cid, claim in claims.items()
    )

    scoreboard = f"""
    <div class="scoreboard">
      <div class="score bull"><span>Bull-supporting claims</span><strong>{len(polarization.get('bull_support') or [])}</strong></div>
      <div class="score bear"><span>Bear-supporting claims</span><strong>{len(polarization.get('bear_support') or [])}</strong></div>
      <div class="score mixed"><span>Contested</span><strong>{len(polarization.get('contested') or [])}</strong></div>
      <div class="score neutral"><span>Neutral</span><strong>{len(polarization.get('neutral') or [])}</strong></div>
    </div>
    """

    parent_title = escape(thesis.get("parent_article_title") or "Daily Brief")
    direction = escape(str(thesis.get("popular_direction", "mixed")).replace("_", " "))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dual Thesis — {escape(run['run_id'])}</title>
<style>
:root {{
  color-scheme: dark;
  --bg:#071018; --panel:#101d27; --line:#223746; --text:#e8f0f5; --muted:#96a8b4;
  --bull:#7be0bd; --bear:#ff8f8f; --claim:#ffca64; --link:#81bff8;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:radial-gradient(circle at top,#122033 0%, var(--bg) 45%); color:var(--text); }}
.shell {{ max-width:1100px; margin:auto; padding:28px 18px 96px; }}
.topbar {{ display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; color:var(--muted); margin-bottom:18px; }}
.badge {{ border:1px solid var(--line); border-radius:999px; padding:.4rem .8rem; background:rgba(16,29,39,.85); }}
.badge strong {{ color:var(--bull); }}
.hero {{ background:rgba(16,29,39,.9); border:1px solid var(--line); border-radius:22px; padding:26px; }}
h1 {{ margin:10px 0 12px; font-size:clamp(1.8rem,4vw,3rem); letter-spacing:-.03em; }}
.summary {{ color:#c5d4de; line-height:1.75; font-size:1.08rem; }}
.claim {{ color:var(--claim); text-decoration:none; margin-left:.15rem; }}
.scoreboard {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:22px 0; }}
.score {{ background:rgba(7,16,24,.55); border:1px solid var(--line); border-radius:14px; padding:14px; }}
.score span {{ display:block; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.06em; }}
.score strong {{ display:block; margin-top:6px; font-size:1.4rem; }}
.score.bull strong {{ color:var(--bull); }}
.score.bear strong {{ color:var(--bear); }}
.grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:18px; }}
.frame {{ background:rgba(16,29,39,.72); border:1px solid var(--line); border-radius:18px; padding:18px; }}
.frame.bull {{ border-top:3px solid var(--bull); }}
.frame.bear {{ border-top:3px solid var(--bear); }}
.frame-head {{ display:flex; justify-content:space-between; gap:10px; align-items:start; }}
.frame h3 {{ margin:0; }}
.frame h4 {{ color:var(--muted); font-size:.9rem; text-transform:uppercase; letter-spacing:.06em; }}
.tags {{ display:flex; gap:6px; flex-wrap:wrap; }}
.tag {{ border-radius:999px; padding:.2rem .55rem; font-size:.72rem; text-transform:uppercase; border:1px solid var(--line); color:var(--muted); }}
.tag.stance {{ color:#071018; border:none; }}
.frame.bull .tag.stance {{ background:var(--bull); }}
.frame.bear .tag.stance {{ background:var(--bear); }}
.tag.style {{ color:var(--claim); }}
p {{ line-height:1.75; color:#dce7ee; }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; background:rgba(16,29,39,.55); border:1px solid var(--line); border-radius:14px; overflow:hidden; }}
td {{ width:50%; vertical-align:top; padding:14px; border-bottom:1px solid var(--line); }}
.section {{ margin-top:28px; background:rgba(16,29,39,.55); border:1px solid var(--line); border-radius:18px; padding:8px 18px 18px; }}
.section h2 {{ color:var(--bull); }}
.claim-card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px; margin:12px 0; }}
.claim-card h3 {{ margin:0; color:var(--claim); }}
.meta {{ color:var(--muted); font-size:.82rem; text-transform:uppercase; }}
.disclaimer {{ margin-top:24px; color:var(--muted); border:1px solid var(--line); border-radius:16px; padding:16px 18px; line-height:1.7; }}
a {{ color:var(--link); }}
@media (max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} td {{ display:block; width:100%; }} }}
</style>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="badge"><strong>MarketForge</strong> Dual Thesis</div>
    <div>Parent run <code>{escape(run['run_id'])}</code> · as of {escape(run['as_of'])}</div>
  </div>

  <header class="hero">
    <div class="badge">Supplement to: {parent_title}</div>
    <h1>Bull &amp; Bear · Popular &amp; Contrarian</h1>
    <p class="summary">{escape(thesis['summary'])} {_anchors(thesis.get('summary_claim_ids') or [])}</p>
    <p class="summary">Inferred popular direction: <strong>{direction}</strong></p>
    {scoreboard}
    <p><a href="index.html">← Back to daily brief</a></p>
  </header>

  <section class="section">
    <h2>Four Frames</h2>
    <div class="grid">
      {frame_card('popular_bull')}
      {frame_card('contrarian_bull')}
      {frame_card('popular_bear')}
      {frame_card('contrarian_bear')}
    </div>
  </section>

  <section class="section">
    <h2>Dialectic</h2>
    <p>Point / counterpoint using only approved claims. Neither side is allowed unsupported ammunition.</p>
    <table>{dialectic_rows}</table>
  </section>

  <section class="section">
    <h2>Claim Ledger (parent brief)</h2>
    {claim_cards}
  </section>

  <p class="disclaimer">{escape(thesis['disclaimer'])}</p>
</div>
</body>
</html>"""
