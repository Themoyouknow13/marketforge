import hashlib
import json

import pytest

from marketforge.monte_carlo import run_dcf_simulation
from marketforge.validation import ValidationError, validate_run_bundle


SNAPSHOT_TEXT = "Revenue was $100 million for the year ended December 31, 2025."


def source(snapshot_path, source_id: str = "src-1", retrieved_at: str = "2026-08-08T12:00:00Z"):
    snapshot_path.write_text(SNAPSHOT_TEXT, encoding="utf-8")
    return {
        "id": source_id,
        "url": "https://www.sec.gov/Archives/example.htm",
        "title": "Example filing",
        "publisher": "SEC",
        "tier": 1,
        "retrieved_at": retrieved_at,
        "snapshot_path": str(snapshot_path),
        "content_sha256": hashlib.sha256(SNAPSHOT_TEXT.encode("utf-8")).hexdigest(),
    }


def evidence(evidence_id: str = "ev-1", source_id: str = "src-1"):
    return {
        "id": evidence_id,
        "source_id": source_id,
        "kind": "quote",
        "quote": SNAPSHOT_TEXT,
        "locator": {"section": "Item 8", "page": 42},
    }


def claim(claim_id: str = "cl-1", evidence_ids=None):
    return {
        "id": claim_id,
        "text": "Revenue was $100 million in fiscal 2025.",
        "claim_type": "fact",
        "evidence_ids": evidence_ids or ["ev-1"],
        "as_of": "2026-08-08T12:00:00Z",
    }


def bundle(tmp_path):
    return {
        "run": {
            "run_id": "run-2026-08-08",
            "as_of": "2026-08-08T12:00:00Z",
            "mode": "daily_close",
        },
        "sources": [source(tmp_path / "source.txt")],
        "evidence": [evidence()],
        "claims": [claim()],
        "article": {
            "title": "Daily Market Brief",
            "summary": "A grounded market briefing.",
            "summary_claim_ids": ["cl-1"],
            "sections": [
                {
                    "heading": "Fundamentals",
                    "paragraphs": [
                        {"text": "Revenue was $100 million in fiscal 2025.", "claim_ids": ["cl-1"]}
                    ],
                }
            ],
            "disclaimer": "Educational analysis only; not investment advice.",
        },
    }


def test_valid_bundle_passes_publish_gate(tmp_path):
    result = validate_run_bundle(bundle(tmp_path))
    assert result.publishable is True
    assert result.errors == []


def test_unsupported_article_claim_fails_closed(tmp_path):
    data = bundle(tmp_path)
    data["article"]["sections"][0]["paragraphs"][0]["claim_ids"] = ["missing"]

    with pytest.raises(ValidationError, match="unknown claim"):
        validate_run_bundle(data)


def test_claim_without_evidence_fails_closed(tmp_path):
    data = bundle(tmp_path)
    data["claims"][0]["evidence_ids"] = []

    with pytest.raises(ValidationError, match="has no evidence"):
        validate_run_bundle(data)


def test_future_dated_source_fails_cutoff_gate(tmp_path):
    data = bundle(tmp_path)
    data["sources"][0]["retrieved_at"] = "2026-08-09T00:00:00Z"

    with pytest.raises(ValidationError, match="after run cutoff"):
        validate_run_bundle(data)


def test_duplicate_ids_fail_closed(tmp_path):
    data = bundle(tmp_path)
    data["claims"].append(claim())

    with pytest.raises(ValidationError, match="duplicate claim id"):
        validate_run_bundle(data)


def test_calculation_claim_must_recompute(tmp_path):
    data = bundle(tmp_path)
    data["claims"][0] = {
        "id": "cl-1",
        "text": "Revenue growth was 25%.",
        "claim_type": "calculation",
        "evidence_ids": ["ev-1"],
        "as_of": "2026-08-08T12:00:00Z",
        "calculation": {
            "operator": "growth_rate",
            "inputs": {"current": 100.0, "previous": 80.0},
            "reported": 0.25,
            "tolerance": 1e-9,
        },
    }
    data["article"]["sections"][0]["paragraphs"][0]["text"] = "Revenue growth was 25%."

    result = validate_run_bundle(data)
    assert result.publishable


def test_incorrect_calculation_fails_closed(tmp_path):
    data = bundle(tmp_path)
    data["claims"][0] = {
        "id": "cl-1",
        "text": "Revenue growth was 30%.",
        "claim_type": "calculation",
        "evidence_ids": ["ev-1"],
        "as_of": "2026-08-08T12:00:00Z",
        "calculation": {
            "operator": "growth_rate",
            "inputs": {"current": 100.0, "previous": 80.0},
            "reported": 0.30,
            "tolerance": 1e-9,
        },
    }

    with pytest.raises(ValidationError, match="calculation mismatch"):
        validate_run_bundle(data)


def test_monte_carlo_claim_requires_reproducibility_metadata(tmp_path):
    data = bundle(tmp_path)
    data["claims"][0] = {
        "id": "cl-1",
        "text": "Median intrinsic value was $100.",
        "claim_type": "simulation",
        "evidence_ids": ["ev-1"],
        "as_of": "2026-08-08T12:00:00Z",
        "simulation": {"iterations": 10000},
    }

    with pytest.raises(ValidationError, match="simulation metadata"):
        validate_run_bundle(data)


def test_monte_carlo_result_hash_and_code_hash_are_verified(tmp_path):
    data = bundle(tmp_path)
    assumptions = {
        "base_fcf": 100.0,
        "shares_outstanding": 10.0,
        "net_debt": 0.0,
        "forecast_years": 5,
        "revenue_growth": {"distribution": "normal", "mean": 0.08, "std": 0.02, "min": -0.05, "max": 0.20},
        "fcf_margin": {"distribution": "normal", "mean": 0.20, "std": 0.02, "min": 0.10, "max": 0.30},
        "wacc": {"distribution": "normal", "mean": 0.10, "std": 0.01, "min": 0.07, "max": 0.14},
        "terminal_growth": {"distribution": "normal", "mean": 0.025, "std": 0.005, "min": 0.00, "max": 0.04},
    }
    result = run_dcf_simulation(assumptions, iterations=10_000, seed=42)
    result_payload = {
        key: value for key, value in result.items() if key not in {"result_sha256", "code_sha256"}
    }
    data["claims"][0] = {
        "id": "cl-1",
        "text": "The simulation produced an auditable valuation distribution.",
        "claim_type": "simulation",
        "evidence_ids": ["ev-1"],
        "as_of": "2026-08-08T12:00:00Z",
        "simulation": {
            "model_version": result["model_version"],
            "code_sha256": result["code_sha256"],
            "seed": result["seed"],
            "iterations": result["iterations"],
            "assumptions": assumptions,
            "result": result_payload,
            "result_sha256": result["result_sha256"],
        },
    }
    data["article"]["sections"][0]["paragraphs"][0]["text"] = data["claims"][0]["text"]

    assert validate_run_bundle(data).publishable

    data["claims"][0]["simulation"]["result"]["median"] += 1
    with pytest.raises(ValidationError, match="result hash mismatch"):
        validate_run_bundle(data)


def test_each_x_post_must_reference_known_claims(tmp_path):
    data = bundle(tmp_path)
    data["x_thread"] = {
        "posts": [
            {"sequence": 1, "text": "Revenue was $100 million.", "claim_ids": ["cl-1"]},
            {"sequence": 2, "text": "Margins doubled.", "claim_ids": ["missing"]},
        ]
    }

    with pytest.raises(ValidationError, match="unknown claim"):
        validate_run_bundle(data)


def test_article_requires_disclaimer(tmp_path):
    data = bundle(tmp_path)
    data["article"]["disclaimer"] = ""

    with pytest.raises(ValidationError, match="disclaimer"):
        validate_run_bundle(data)


def test_evidence_quote_must_exist_verbatim_in_snapshot(tmp_path):
    data = bundle(tmp_path)
    data["evidence"][0]["quote"] = "Revenue was $200 million."

    with pytest.raises(ValidationError, match="not found in source snapshot"):
        validate_run_bundle(data)


def test_tampered_source_snapshot_fails_hash_check(tmp_path):
    data = bundle(tmp_path)
    (tmp_path / "source.txt").write_text("tampered", encoding="utf-8")

    with pytest.raises(ValidationError, match="snapshot hash mismatch"):
        validate_run_bundle(data)


def test_factual_claim_cannot_add_a_number_missing_from_evidence(tmp_path):
    data = bundle(tmp_path)
    data["claims"][0]["text"] = "Revenue was $200 million in fiscal 2025."

    with pytest.raises(ValidationError, match="numeric token.*not grounded"):
        validate_run_bundle(data)


def test_xbrl_evidence_value_must_match_hashed_payload(tmp_path):
    data = bundle(tmp_path)
    xbrl_payload = {"value": 100000000, "unit": "USD", "filed": "2026-02-01"}
    snapshot_path = tmp_path / "xbrl.json"
    snapshot_path.write_text(json.dumps(xbrl_payload), encoding="utf-8")
    data["sources"][0]["snapshot_path"] = str(snapshot_path)
    data["sources"][0]["content_sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    data["evidence"][0] = {
        "id": "ev-1",
        "source_id": "src-1",
        "kind": "xbrl_fact",
        "value": 200000000,
        "locator": {"json_pointer": "/value"},
    }

    with pytest.raises(ValidationError, match="XBRL value mismatch"):
        validate_run_bundle(data)


def test_article_cannot_add_a_number_missing_from_linked_claims(tmp_path):
    data = bundle(tmp_path)
    data["article"]["sections"][0]["paragraphs"][0]["text"] = (
        "Revenue was $100 million and cash flow was $90 million."
    )

    with pytest.raises(ValidationError, match="article numeric token.*not grounded"):
        validate_run_bundle(data)


def test_summary_cannot_add_a_number_missing_from_linked_claims(tmp_path):
    data = bundle(tmp_path)
    data["article"]["summary"] = "Cash flow rose 90%."

    with pytest.raises(ValidationError, match="summary numeric token.*not grounded"):
        validate_run_bundle(data)


def test_snapshot_path_must_remain_inside_artifact_root(tmp_path):
    artifact_root = tmp_path / "run"
    artifact_root.mkdir()
    data = bundle(tmp_path)

    with pytest.raises(ValidationError, match="outside artifact root"):
        validate_run_bundle(data, artifact_root=artifact_root)
