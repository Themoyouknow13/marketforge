import json
from pathlib import Path

import pytest

from marketforge.thesis import (
    ThesisValidationError,
    build_dual_thesis_bundle,
    validate_thesis_bundle,
)
from marketforge.validation import validate_run_bundle


def _source(tmp_path: Path, text: str, source_id: str = "src-1"):
    path = tmp_path / f"{source_id}.txt"
    payload = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(payload)
    import hashlib

    return {
        "id": source_id,
        "url": "https://example.com/market",
        "title": "Tape",
        "publisher": "Test",
        "tier": 2,
        "retrieved_at": "2026-08-08T17:00:00Z",
        "snapshot_path": str(path),
        "content_sha256": hashlib.sha256(payload).hexdigest(),
    }


def approved_bundle(tmp_path: Path):
    text = (
        "SPY last price 773.26 versus previous close 747.03, change +3.51%.\n"
        "QQQ last price 723.03 versus previous close 687.99, change +5.09%.\n"
        "Top gainer TEAM moved +35.31% to $149.07.\n"
        "Top loser SEZL moved -33.89% to $118.02.\n"
        "VIX last price 14.90, change -6.05%.\n"
    )
    source = _source(tmp_path, text)
    evidence = [
        {
            "id": "ev-spy",
            "source_id": "src-1",
            "kind": "quote",
            "quote": "SPY last price 773.26 versus previous close 747.03, change +3.51%.",
            "locator": {"section": "SPY"},
        },
        {
            "id": "ev-qqq",
            "source_id": "src-1",
            "kind": "quote",
            "quote": "QQQ last price 723.03 versus previous close 687.99, change +5.09%.",
            "locator": {"section": "QQQ"},
        },
        {
            "id": "ev-team",
            "source_id": "src-1",
            "kind": "quote",
            "quote": "Top gainer TEAM moved +35.31% to $149.07.",
            "locator": {"section": "Gainers"},
        },
        {
            "id": "ev-sezl",
            "source_id": "src-1",
            "kind": "quote",
            "quote": "Top loser SEZL moved -33.89% to $118.02.",
            "locator": {"section": "Losers"},
        },
        {
            "id": "ev-vix",
            "source_id": "src-1",
            "kind": "quote",
            "quote": "VIX last price 14.90, change -6.05%.",
            "locator": {"section": "VIX"},
        },
    ]
    claims = [
        {
            "id": "cl-spy",
            "text": "SPY last traded at 773.26, +3.51% versus previous close 747.03.",
            "claim_type": "fact",
            "evidence_ids": ["ev-spy"],
            "as_of": "2026-08-08T17:00:00Z",
        },
        {
            "id": "cl-qqq",
            "text": "QQQ last traded at 723.03, +5.09% versus previous close 687.99.",
            "claim_type": "fact",
            "evidence_ids": ["ev-qqq"],
            "as_of": "2026-08-08T17:00:00Z",
        },
        {
            "id": "cl-team",
            "text": "Top live gainer TEAM moved +35.31% to $149.07.",
            "claim_type": "fact",
            "evidence_ids": ["ev-team"],
            "as_of": "2026-08-08T17:00:00Z",
        },
        {
            "id": "cl-sezl",
            "text": "Top live loser SEZL moved -33.89% to $118.02.",
            "claim_type": "fact",
            "evidence_ids": ["ev-sezl"],
            "as_of": "2026-08-08T17:00:00Z",
        },
        {
            "id": "cl-vix",
            "text": "VIX last printed at 14.90 (-6.05%).",
            "claim_type": "fact",
            "evidence_ids": ["ev-vix"],
            "as_of": "2026-08-08T17:00:00Z",
        },
    ]
    return {
        "run": {"run_id": "run-test", "as_of": "2026-08-08T17:00:00Z", "mode": "daily_close"},
        "sources": [source],
        "evidence": evidence,
        "claims": claims,
        "article": {
            "title": "Test Brief",
            "summary": "SPY 773.26 (+3.51%) and QQQ 723.03 (+5.09%).",
            "summary_claim_ids": ["cl-spy", "cl-qqq"],
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


def test_build_dual_thesis_from_approved_bundle(tmp_path):
    bundle = approved_bundle(tmp_path)
    validate_run_bundle(bundle, artifact_root=tmp_path)
    thesis = build_dual_thesis_bundle(bundle)
    result = validate_thesis_bundle(thesis, approved_bundle=bundle, artifact_root=tmp_path)
    assert result.publishable is True
    assert set(thesis["frames"].keys()) == {
        "popular_bull",
        "contrarian_bull",
        "popular_bear",
        "contrarian_bear",
    }
    for frame in thesis["frames"].values():
        assert frame["claim_ids"]
        assert frame["paragraphs"]


def test_thesis_cannot_reference_unknown_claim(tmp_path):
    bundle = approved_bundle(tmp_path)
    thesis = build_dual_thesis_bundle(bundle)
    thesis["frames"]["popular_bull"]["claim_ids"].append("cl-missing")
    with pytest.raises(ThesisValidationError, match="unknown claim"):
        validate_thesis_bundle(thesis, approved_bundle=bundle, artifact_root=tmp_path)


def test_thesis_paragraph_numbers_must_be_grounded(tmp_path):
    bundle = approved_bundle(tmp_path)
    thesis = build_dual_thesis_bundle(bundle)
    thesis["frames"]["popular_bull"]["paragraphs"][0]["text"] += " Target 9999."
    with pytest.raises(ThesisValidationError, match="numeric token"):
        validate_thesis_bundle(thesis, approved_bundle=bundle, artifact_root=tmp_path)


def test_both_sides_required(tmp_path):
    bundle = approved_bundle(tmp_path)
    thesis = build_dual_thesis_bundle(bundle)
    del thesis["frames"]["popular_bear"]
    with pytest.raises(ThesisValidationError, match="missing frame"):
        validate_thesis_bundle(thesis, approved_bundle=bundle, artifact_root=tmp_path)
