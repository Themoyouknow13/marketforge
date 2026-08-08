import json

from marketforge.render import render_article


def test_renderer_emits_inline_claim_links_and_sources(tmp_path):
    bundle = {
        "run": {"run_id": "run-1", "as_of": "2026-08-08T12:00:00Z"},
        "sources": [
            {
                "id": "src-1",
                "url": "https://www.sec.gov/example",
                "title": "Example filing",
                "publisher": "SEC",
            }
        ],
        "evidence": [
            {
                "id": "ev-1",
                "source_id": "src-1",
                "quote": "Revenue was $100 million.",
                "locator": {"section": "Item 8", "page": 42},
            }
        ],
        "claims": [
            {"id": "cl-1", "text": "Revenue was $100 million.", "evidence_ids": ["ev-1"]}
        ],
        "article": {
            "title": "Daily Brief",
            "summary": "Grounded summary.",
            "summary_claim_ids": ["cl-1"],
            "sections": [
                {
                    "heading": "Mover",
                    "paragraphs": [
                        {"text": "Revenue was $100 million.", "claim_ids": ["cl-1"]}
                    ],
                }
            ],
            "disclaimer": "Educational analysis only; not investment advice.",
        },
    }
    html = render_article(bundle)
    assert "Daily Brief" in html
    assert 'id="claim-cl-1"' in html
    assert "https://www.sec.gov/example" in html
    assert "Item 8, p. 42" in html
