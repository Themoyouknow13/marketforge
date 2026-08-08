import json
import subprocess
import sys


def test_cli_validates_and_renders_example_bundle(tmp_path):
    source_text = "Revenue was $100 million for the year ended December 31, 2025."
    source_path = tmp_path / "source.txt"
    source_path.write_text(source_text, encoding="utf-8")
    import hashlib

    bundle = {
        "run": {"run_id": "run-1", "as_of": "2026-08-08T12:00:00Z", "mode": "daily_close"},
        "sources": [
            {
                "id": "src-1",
                "url": "https://www.sec.gov/example",
                "title": "Example filing",
                "publisher": "SEC",
                "tier": 1,
                "retrieved_at": "2026-08-08T12:00:00Z",
                "snapshot_path": str(source_path),
                "content_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
            }
        ],
        "evidence": [
            {
                "id": "ev-1",
                "source_id": "src-1",
                "kind": "quote",
                "quote": source_text,
                "locator": {"section": "Item 8", "page": 42},
            }
        ],
        "claims": [
            {
                "id": "cl-1",
                "text": "Revenue was $100 million in fiscal 2025.",
                "claim_type": "fact",
                "evidence_ids": ["ev-1"],
                "as_of": "2026-08-08T12:00:00Z",
            }
        ],
        "article": {
            "title": "Daily Brief",
            "summary": "Grounded summary.",
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
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    output_path = tmp_path / "brief.html"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "marketforge.cli",
            "validate",
            str(bundle_path),
            "--render",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "PUBLISHABLE" in completed.stdout
    assert output_path.exists()
    assert "Daily Brief" in output_path.read_text(encoding="utf-8")
