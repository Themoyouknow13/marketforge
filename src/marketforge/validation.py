from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import inspect
import json
from math import isclose
from pathlib import Path
import re
from typing import Any, Iterable


class ValidationError(ValueError):
    """Raised when a run bundle is unsafe to publish."""


@dataclass(frozen=True)
class ValidationResult:
    publishable: bool
    errors: list[str]
    warnings: list[str]


def _parse_timestamp(value: str, label: str) -> datetime:
    if not value:
        raise ValidationError(f"{label} is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"invalid timestamp for {label}: {value}") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{label} must include a timezone")
    return parsed


def _index_unique(items: Iterable[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            raise ValidationError(f"{kind} id is required")
        if item_id in indexed:
            raise ValidationError(f"duplicate {kind} id: {item_id}")
        indexed[item_id] = item
    return indexed


def _validate_sha256(value: str, source_id: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
        raise ValidationError(f"source {source_id} has invalid content_sha256")


def _read_verified_snapshot(source: dict[str, Any], artifact_root: Path | None = None) -> str:
    source_id = source["id"]
    snapshot_path = source.get("snapshot_path")
    if not snapshot_path:
        raise ValidationError(f"source {source_id} has no snapshot_path")
    raw_path = Path(snapshot_path)
    if artifact_root is not None and not raw_path.is_absolute():
        resolved_path = (artifact_root / raw_path).resolve()
    else:
        resolved_path = raw_path.resolve()
    if artifact_root is not None:
        resolved_root = artifact_root.resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValidationError(f"source {source_id} snapshot is outside artifact root") from exc
    try:
        payload = resolved_path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"source {source_id} snapshot is unreadable") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != source["content_sha256"].lower():
        raise ValidationError(f"source {source_id} snapshot hash mismatch")
    return payload.decode("utf-8")


_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
_FORM_LABEL_TAIL = re.compile(r"-[A-Za-z]")
_FORM_PREFIX = re.compile(r"(?i)(?:\bform|\bitem)\s+$")


def _numeric_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    source = text or ""
    for match in _NUMBER_PATTERN.finditer(source):
        # Skip ISO date fragments such as the "-08" in 2026-08-08.
        if match.group(0).startswith("-") and match.start() > 0 and source[match.start() - 1].isdigit():
            continue
        # Skip EDGAR-style form labels such as 8-K, 10-Q, 13D/A.
        tail = source[match.end() : match.end() + 4]
        if _FORM_LABEL_TAIL.match(tail):
            continue
        # Skip "Form 4" / "Item 2.02" style references.
        prefix = source[max(0, match.start() - 8) : match.start()]
        if _FORM_PREFIX.search(prefix):
            continue
        normalized = match.group(0).replace(",", "").lower()
        # Treat "+0.85%" and "0.85%" as the same grounded quantity.
        if normalized.startswith("+"):
            normalized = normalized[1:]
        tokens.add(normalized)
    return tokens


def _validate_numeric_grounding(text: str, grounded_text: str, label: str) -> None:
    unsupported = _numeric_tokens(text) - _numeric_tokens(grounded_text)
    if unsupported:
        raise ValidationError(f"{label} numeric token is not grounded: {sorted(unsupported)[0]}")


def _resolve_json_pointer(payload: Any, pointer: str) -> Any:
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ValidationError(f"invalid JSON pointer: {pointer}")
    current = payload
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(part)] if isinstance(current, list) else current[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValidationError(f"JSON pointer does not resolve: {pointer}") from exc
    return current


def _compute_calculation(calculation: dict[str, Any]) -> float:
    operator = calculation.get("operator")
    inputs = calculation.get("inputs") or {}
    if operator == "growth_rate":
        current = float(inputs["current"])
        previous = float(inputs["previous"])
        if previous == 0:
            raise ValidationError("growth_rate previous value cannot be zero")
        return (current - previous) / previous
    if operator == "ratio":
        numerator = float(inputs["numerator"])
        denominator = float(inputs["denominator"])
        if denominator == 0:
            raise ValidationError("ratio denominator cannot be zero")
        return numerator / denominator
    if operator == "average":
        values = [float(value) for value in inputs["values"]]
        if not values:
            raise ValidationError("average requires at least one value")
        return sum(values) / len(values)
    raise ValidationError(f"unsupported calculation operator: {operator}")


def _validate_calculation(claim: dict[str, Any]) -> None:
    calculation = claim.get("calculation")
    if not calculation:
        raise ValidationError(f"calculation claim {claim['id']} is missing calculation metadata")
    try:
        expected = _compute_calculation(calculation)
        reported = float(calculation["reported"])
        tolerance = float(calculation.get("tolerance", 1e-9))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"calculation claim {claim['id']} has invalid metadata") from exc
    if not isclose(expected, reported, rel_tol=tolerance, abs_tol=tolerance):
        raise ValidationError(
            f"calculation mismatch for claim {claim['id']}: expected {expected}, reported {reported}"
        )


def _validate_simulation(claim: dict[str, Any]) -> None:
    simulation = claim.get("simulation") or {}
    required = {
        "model_version",
        "code_sha256",
        "seed",
        "iterations",
        "assumptions",
        "result",
        "result_sha256",
    }
    if not required.issubset(simulation):
        missing = ", ".join(sorted(required - set(simulation)))
        raise ValidationError(f"simulation metadata missing for claim {claim['id']}: {missing}")
    if not isinstance(simulation["seed"], int) or simulation["seed"] < 0:
        raise ValidationError(f"simulation claim {claim['id']} requires a non-negative integer seed")
    if not isinstance(simulation["iterations"], int) or simulation["iterations"] < 10_000:
        raise ValidationError(f"simulation claim {claim['id']} requires at least 10000 iterations")
    if not isinstance(simulation["assumptions"], dict) or not simulation["assumptions"]:
        raise ValidationError(f"simulation claim {claim['id']} requires explicit assumptions")
    _validate_sha256(simulation["code_sha256"], claim["id"])
    _validate_sha256(simulation["result_sha256"], claim["id"])
    from .monte_carlo import run_dcf_simulation

    current_code_sha256 = hashlib.sha256(
        inspect.getsource(run_dcf_simulation).encode("utf-8")
    ).hexdigest()
    if simulation["code_sha256"] != current_code_sha256:
        raise ValidationError(f"simulation code hash mismatch for claim {claim['id']}")
    canonical_result = json.dumps(
        simulation["result"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical_result).hexdigest() != simulation["result_sha256"]:
        raise ValidationError(f"simulation result hash mismatch for claim {claim['id']}")


def _validate_content_claim_refs(content: dict[str, Any], claim_index: dict[str, dict[str, Any]]) -> None:
    article = content.get("article")
    if not article:
        raise ValidationError("article is required")
    if not article.get("disclaimer", "").strip():
        raise ValidationError("article disclaimer is required")
    summary_refs = article.get("summary_claim_ids") or []
    if not summary_refs:
        raise ValidationError("article summary has no claim ids")
    for claim_id in summary_refs:
        if claim_id not in claim_index:
            raise ValidationError(f"article summary references unknown claim: {claim_id}")
    grounded_summary = "\n".join(claim_index[claim_id]["text"] for claim_id in summary_refs)
    _validate_numeric_grounding(article.get("summary", ""), grounded_summary, "summary")

    # Optional Phase-1 desk presentation layer.
    desk = article.get("desk")
    if desk:
        _validate_desk_layer(desk, claim_index)

    for section in article.get("sections", []):
        for paragraph in section.get("paragraphs", []):
            refs = paragraph.get("claim_ids") or []
            if not refs:
                raise ValidationError("article paragraph has no claim ids")
            for claim_id in refs:
                if claim_id not in claim_index:
                    raise ValidationError(f"article references unknown claim: {claim_id}")
            grounded_claims = "\n".join(claim_index[claim_id]["text"] for claim_id in refs)
            _validate_numeric_grounding(paragraph.get("text", ""), grounded_claims, "article")
            for field in ("context_line", "implication_line", "print_line"):
                if paragraph.get(field):
                    _validate_numeric_grounding(str(paragraph[field]), grounded_claims, f"article {field}")

    for post in (content.get("x_thread") or {}).get("posts", []):
        refs = post.get("claim_ids") or []
        if not refs:
            raise ValidationError(f"x post {post.get('sequence')} has no claim ids")
        for claim_id in refs:
            if claim_id not in claim_index:
                raise ValidationError(f"x thread references unknown claim: {claim_id}")
        grounded_claims = "\n".join(claim_index[claim_id]["text"] for claim_id in refs)
        _validate_numeric_grounding(post.get("text", ""), grounded_claims, "x post")


def _validate_desk_layer(desk: dict[str, Any], claim_index: dict[str, dict[str, Any]]) -> None:
    summary_refs = desk.get("summary_claim_ids") or []
    if not summary_refs:
        raise ValidationError("desk summary has no claim ids")
    for claim_id in summary_refs:
        if claim_id not in claim_index:
            raise ValidationError(f"desk summary references unknown claim: {claim_id}")
    grounded = "\n".join(claim_index[cid]["text"] for cid in summary_refs)
    _validate_numeric_grounding(str(desk.get("summary", "")), grounded, "desk summary")

    for section in desk.get("sections") or []:
        for block in section.get("blocks") or []:
            refs = block.get("claim_ids") or []
            if not refs:
                raise ValidationError("desk block has no claim ids")
            for claim_id in refs:
                if claim_id not in claim_index:
                    raise ValidationError(f"desk block references unknown claim: {claim_id}")
            grounded_block = "\n".join(claim_index[cid]["text"] for cid in refs)
            for field in ("print_line", "context_line", "implication_line"):
                if block.get(field):
                    _validate_numeric_grounding(str(block[field]), grounded_block, f"desk {field}")
            for link in block.get("links") or []:
                if not str(link.get("url", "")).startswith("https://"):
                    raise ValidationError("desk block link must be https")
        for card in section.get("cards") or []:
            refs = card.get("claim_ids") or []
            if not refs:
                raise ValidationError("desk card has no claim ids")
            for claim_id in refs:
                if claim_id not in claim_index:
                    raise ValidationError(f"desk card references unknown claim: {claim_id}")
            grounded_card = "\n".join(claim_index[cid]["text"] for cid in refs)
            for field in ("print_line", "context_line", "implication_line"):
                if card.get(field):
                    _validate_numeric_grounding(str(card[field]), grounded_card, f"desk card {field}")
            for link in card.get("links") or []:
                if not str(link.get("url", "")).startswith("https://"):
                    raise ValidationError("desk card link must be https")


def validate_run_bundle(
    bundle: dict[str, Any], *, artifact_root: str | Path | None = None
) -> ValidationResult:
    """Validate a complete run and fail closed on missing provenance or bad math."""

    run = bundle.get("run") or {}
    cutoff = _parse_timestamp(run.get("as_of", ""), "run.as_of")
    source_index = _index_unique(bundle.get("sources", []), "source")
    evidence_index = _index_unique(bundle.get("evidence", []), "evidence")
    claim_index = _index_unique(bundle.get("claims", []), "claim")
    source_snapshots: dict[str, str] = {}

    if not source_index:
        raise ValidationError("at least one source is required")
    if not evidence_index:
        raise ValidationError("at least one evidence item is required")
    if not claim_index:
        raise ValidationError("at least one claim is required")

    for source_id, source in source_index.items():
        retrieved_at = _parse_timestamp(source.get("retrieved_at", ""), f"source {source_id}.retrieved_at")
        if retrieved_at > cutoff:
            raise ValidationError(f"source {source_id} was retrieved after run cutoff")
        if source.get("tier") not in {1, 2, 3}:
            raise ValidationError(f"source {source_id} has invalid source tier")
        if not str(source.get("url", "")).startswith("https://"):
            raise ValidationError(f"source {source_id} must use https")
        _validate_sha256(source.get("content_sha256", ""), source_id)
        root = Path(artifact_root) if artifact_root is not None else None
        source_snapshots[source_id] = _read_verified_snapshot(source, root)

    for evidence_id, item in evidence_index.items():
        if item.get("source_id") not in source_index:
            raise ValidationError(f"evidence {evidence_id} references unknown source")
        if item.get("kind") == "quote" and not item.get("quote", "").strip():
            raise ValidationError(f"quote evidence {evidence_id} is empty")
        if item.get("kind") == "quote" and item["quote"] not in source_snapshots[item["source_id"]]:
            raise ValidationError(f"evidence {evidence_id} quote not found in source snapshot")
        if item.get("kind") == "xbrl_fact":
            pointer = (item.get("locator") or {}).get("json_pointer")
            if not pointer:
                raise ValidationError(f"XBRL evidence {evidence_id} has no json_pointer")
            try:
                payload = json.loads(source_snapshots[item["source_id"]])
            except json.JSONDecodeError as exc:
                raise ValidationError(f"XBRL evidence {evidence_id} source is not JSON") from exc
            if _resolve_json_pointer(payload, pointer) != item.get("value"):
                raise ValidationError(f"XBRL value mismatch for evidence {evidence_id}")
        if not item.get("locator"):
            raise ValidationError(f"evidence {evidence_id} has no locator")

    for claim_id, claim in claim_index.items():
        evidence_ids = claim.get("evidence_ids") or []
        if not evidence_ids:
            raise ValidationError(f"claim {claim_id} has no evidence")
        for evidence_id in evidence_ids:
            if evidence_id not in evidence_index:
                raise ValidationError(f"claim {claim_id} references unknown evidence: {evidence_id}")
        claim_as_of = _parse_timestamp(claim.get("as_of", ""), f"claim {claim_id}.as_of")
        if claim_as_of > cutoff:
            raise ValidationError(f"claim {claim_id} is after run cutoff")
        if claim.get("claim_type") == "calculation":
            _validate_calculation(claim)
        elif claim.get("claim_type") == "simulation":
            _validate_simulation(claim)
        elif claim.get("claim_type") in {"fact", "interpretation"}:
            grounded_evidence = "\n".join(
                str(
                    evidence_index[evidence_id].get(
                        "quote", evidence_index[evidence_id].get("value", "")
                    )
                )
                for evidence_id in evidence_ids
            )
            _validate_numeric_grounding(claim.get("text", ""), grounded_evidence, f"claim {claim_id}")
        else:
            raise ValidationError(f"unsupported claim type for claim {claim_id}")

    _validate_content_claim_refs(bundle, claim_index)
    return ValidationResult(publishable=True, errors=[], warnings=[])
