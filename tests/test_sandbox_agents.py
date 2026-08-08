from pathlib import Path
import hashlib

from marketforge.sandbox_agents import run_sandbox_pipeline
from marketforge.validation import validate_run_bundle


def _bundle(tmp_path: Path):
    text = (
        "SPY last price 773.26 versus previous close 747.03, change +3.51%.\n"
        "Top loser SEZL moved -33.89% to $118.02.\n"
    )
    payload = text.encode("utf-8")
    path = tmp_path / "src.txt"
    path.write_bytes(payload)
    source = {
        "id": "src-1",
        "url": "https://example.com/m",
        "title": "Tape",
        "publisher": "Test",
        "tier": 2,
        "retrieved_at": "2026-08-08T17:00:00Z",
        "snapshot_path": str(path),
        "content_sha256": hashlib.sha256(payload).hexdigest(),
    }
    return {
        "run": {"run_id": "run-sandbox", "as_of": "2026-08-08T17:00:00Z", "mode": "daily_close"},
        "sources": [source],
        "evidence": [
            {
                "id": "ev-1",
                "source_id": "src-1",
                "kind": "quote",
                "quote": "SPY last price 773.26 versus previous close 747.03, change +3.51%.",
                "locator": {"section": "SPY"},
            },
            {
                "id": "ev-2",
                "source_id": "src-1",
                "kind": "quote",
                "quote": "Top loser SEZL moved -33.89% to $118.02.",
                "locator": {"section": "Losers"},
            },
        ],
        "claims": [
            {
                "id": "cl-spy",
                "text": "SPY last traded at 773.26, +3.51% versus previous close 747.03.",
                "claim_type": "fact",
                "evidence_ids": ["ev-1"],
                "as_of": "2026-08-08T17:00:00Z",
            },
            {
                "id": "cl-sezl",
                "text": "Top live loser SEZL moved -33.89% to $118.02.",
                "claim_type": "fact",
                "evidence_ids": ["ev-2"],
                "as_of": "2026-08-08T17:00:00Z",
            },
        ],
        "article": {
            "title": "Sandbox Parent",
            "summary": "SPY 773.26 (+3.51%).",
            "summary_claim_ids": ["cl-spy"],
            "sections": [
                {
                    "heading": "Overview",
                    "paragraphs": [
                        {
                            "text": "SPY last traded at 773.26, +3.51% versus previous close 747.03.",
                            "claim_ids": ["cl-spy"],
                        }
                    ],
                }
            ],
            "disclaimer": "Educational analysis only; not investment advice.",
        },
    }


def test_sandbox_pipeline_passes_on_approved_bundle(tmp_path):
    bundle = _bundle(tmp_path)
    validate_run_bundle(bundle, artifact_root=tmp_path)
    result = run_sandbox_pipeline(bundle, artifact_root=str(tmp_path))
    assert result["sandbox"]["status"] == "passed"
    assert result["thesis_bundle"] is not None
    agents = [s["agent"] for s in result["sandbox"]["stages"]]
    assert agents == [
        "thesis_orchestrator",
        "parent_bundle_validator",
        "evidence_polarizer",
        "consensus_classifier",
        "bull_architect",
        "bear_architect",
        "dialectic_critic",
        "dual_thesis_editor",
        "grounding_auditor",
    ]
    assert all(s["status"] == "ok" for s in result["sandbox"]["stages"])
