from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .validation import ValidationError, _numeric_tokens, validate_run_bundle


class ThesisValidationError(ValueError):
    """Raised when a dual-thesis package is unsafe to publish."""


@dataclass(frozen=True)
class ThesisValidationResult:
    publishable: bool
    errors: list[str]
    warnings: list[str]


_FRAME_KEYS = (
    "popular_bull",
    "contrarian_bull",
    "popular_bear",
    "contrarian_bear",
)

_BULLISH_HINTS = (
    "up ",
    " +",
    "gainer",
    "rose",
    "advanced",
    "strength",
    "risk-on",
    "buyback",
    "backlog",
    "beat",
    "growth",
)
_BEARISH_HINTS = (
    "down ",
    " -",
    "loser",
    "fell",
    "declined",
    "weak",
    "risk-off",
    "sale of",
    "selling",
    "loss",
    "cut",
    "miss",
)


def _claim_polarity(text: str) -> str:
    lowered = f" {text.lower()} "
    bull = sum(1 for hint in _BULLISH_HINTS if hint in lowered)
    bear = sum(1 for hint in _BEARISH_HINTS if hint in lowered)

    # Percentage cues: +x% bullish, -x% bearish (rough but deterministic).
    plus = len(re.findall(r"\+\d+(?:\.\d+)?%", text))
    minus = len(re.findall(r"-\d+(?:\.\d+)?%", text))
    bull += plus
    bear += minus

    if bull > bear:
        return "bull_support"
    if bear > bull:
        return "bear_support"
    if bull and bear:
        return "contested"
    return "neutral"


def _join_claim_texts(claim_index: dict[str, dict[str, Any]], claim_ids: list[str]) -> str:
    return "\n".join(claim_index[cid]["text"] for cid in claim_ids if cid in claim_index)


def _validate_numeric_against_claims(
    text: str, claim_ids: list[str], claim_index: dict[str, dict[str, Any]], label: str
) -> None:
    grounded = _join_claim_texts(claim_index, claim_ids)
    unsupported = _numeric_tokens(text) - _numeric_tokens(grounded)
    if unsupported:
        raise ThesisValidationError(
            f"{label} numeric token is not grounded: {sorted(unsupported)[0]}"
        )


def polarize_claims(claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets = {
        "bull_support": [],
        "bear_support": [],
        "contested": [],
        "neutral": [],
    }
    for claim in claims:
        buckets[_claim_polarity(claim.get("text", ""))].append(claim["id"])
    return buckets


def infer_popular_direction(polarized: dict[str, list[str]]) -> str:
    bull_n = len(polarized["bull_support"])
    bear_n = len(polarized["bear_support"])
    if bull_n > bear_n:
        return "risk_on"
    if bear_n > bull_n:
        return "risk_off"
    return "mixed"


def _frame(
    key: str,
    title: str,
    stance: str,
    style: str,
    claim_ids: list[str],
    paragraphs: list[dict[str, Any]],
    falsifiers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "stance": stance,  # bull | bear
        "style": style,  # popular | contrarian
        "claim_ids": claim_ids,
        "paragraphs": paragraphs,
        "falsifiers": falsifiers,
    }


def build_dual_thesis_bundle(approved_bundle: dict[str, Any]) -> dict[str, Any]:
    """Deterministic dual-thesis builder over an approved MarketForge bundle.

    This is the default Phase-B implementation. LLM agents may replace the
    wording step later, but must emit the same schema and pass validation.
    """

    claims = approved_bundle.get("claims") or []
    if not claims:
        raise ThesisValidationError("approved bundle has no claims")
    claim_index = {c["id"]: c for c in claims}
    polarized = polarize_claims(claims)
    popular_dir = infer_popular_direction(polarized)

    bull_ids = list(dict.fromkeys(polarized["bull_support"] + polarized["contested"]))
    bear_ids = list(dict.fromkeys(polarized["bear_support"] + polarized["contested"]))
    # Ensure each side has at least something to cite if only one polarity exists.
    if not bull_ids:
        bull_ids = [c["id"] for c in claims[:2]]
    if not bear_ids:
        bear_ids = [c["id"] for c in claims[-2:]]

    def texts(ids: list[str]) -> list[str]:
        return [claim_index[i]["text"] for i in ids if i in claim_index]

    bull_points = texts(bull_ids)[:4]
    bear_points = texts(bear_ids)[:4]

    if popular_dir == "risk_on":
        popular_context = "The approved tape claims skew risk-on / bullish."
        contrarian_context = "A contrarian frame asks whether strength is extended or selective."
    elif popular_dir == "risk_off":
        popular_context = "The approved tape claims skew risk-off / bearish."
        contrarian_context = "A contrarian frame asks whether weakness is overdone or hiding rotation."
    else:
        popular_context = "The approved tape claims are mixed."
        contrarian_context = "With mixed evidence, both extension and mean-reversion readings remain open."

    popular_bull_ids = bull_ids[:5]
    contrarian_bull_ids = list(dict.fromkeys(bull_ids[:3] + bear_ids[:2]))
    popular_bear_ids = list(dict.fromkeys(bear_ids[:5])) if bear_ids else [claims[0]["id"]]
    # Popular bear still must acknowledge the tape if risk-on: include one bull claim as context.
    if popular_dir == "risk_on" and bull_ids:
        popular_bear_ids = list(dict.fromkeys(bear_ids[:3] + bull_ids[:2]))
    contrarian_bear_ids = list(dict.fromkeys(bear_ids[:3] + bull_ids[:2]))

    def para(text: str, ids: list[str]) -> dict[str, Any]:
        # Link every approved claim whose full text was embedded in this paragraph.
        embedded = [cid for cid, claim in claim_index.items() if claim["text"] in text]
        ordered = [cid for cid in ids if cid in embedded]
        ordered.extend(cid for cid in embedded if cid not in ordered)
        if not ordered:
            ordered = ids[:1]
        return {"text": text, "claim_ids": ordered}

    frames = {
        "popular_bull": _frame(
            "popular_bull",
            "Popular Bull",
            "bull",
            "popular",
            popular_bull_ids,
            [
                para(
                    f"{popular_context} A popular bull reading emphasizes: " + " ".join(bull_points[:2]),
                    popular_bull_ids[: max(1, min(3, len(popular_bull_ids)))],
                ),
                para(
                    "In this frame, leadership and benchmark strength are treated as confirmation rather than a trap. "
                    + (" ".join(bull_points[2:4]) if len(bull_points) > 2 else bull_points[0]),
                    popular_bull_ids[: max(1, min(4, len(popular_bull_ids)))],
                ),
            ],
            [
                para(
                    "This bull reading would weaken if the bear-supporting claims reassert control of the tape. "
                    + (bear_points[0] if bear_points else bull_points[0]),
                    (bear_ids[:1] or popular_bull_ids[:1]),
                )
            ],
        ),
        "contrarian_bull": _frame(
            "contrarian_bull",
            "Contrarian Bull",
            "bull",
            "contrarian",
            contrarian_bull_ids,
            [
                para(
                    f"{contrarian_context} A contrarian bull reading still finds constructive evidence: "
                    + " ".join(bull_points[:2]),
                    contrarian_bull_ids[: max(1, min(3, len(contrarian_bull_ids)))],
                ),
                para(
                    "This stance argues that visible weakness or contested signals do not automatically invalidate upside follow-through. "
                    + (bear_points[0] if bear_points else bull_points[0]),
                    contrarian_bull_ids[: max(1, min(4, len(contrarian_bull_ids)))],
                ),
            ],
            [
                para(
                    "Contrarian bull would be challenged if downside claims broaden beyond isolated losers. "
                    + (bear_points[0] if bear_points else bull_points[0]),
                    (bear_ids[:1] or contrarian_bull_ids[:1]),
                )
            ],
        ),
        "popular_bear": _frame(
            "popular_bear",
            "Popular Bear",
            "bear",
            "popular",
            popular_bear_ids,
            [
                para(
                    f"{popular_context} A popular bear reading stresses the weakest approved evidence: "
                    + " ".join(bear_points[:2] if bear_points else bull_points[:1]),
                    popular_bear_ids[: max(1, min(3, len(popular_bear_ids)))],
                ),
                para(
                    "Even when benchmarks are firm, this frame treats sharp single-name downside and contested signals as risk markers rather than noise. "
                    + (bear_points[0] if bear_points else bull_points[0]),
                    popular_bear_ids[: max(1, min(4, len(popular_bear_ids)))],
                ),
            ],
            [
                para(
                    "Popular bear would be challenged if bull-supporting claims continue to dominate breadth and leadership. "
                    + (bull_points[0] if bull_points else bear_points[0]),
                    (bull_ids[:1] or popular_bear_ids[:1]),
                )
            ],
        ),
        "contrarian_bear": _frame(
            "contrarian_bear",
            "Contrarian Bear",
            "bear",
            "contrarian",
            contrarian_bear_ids,
            [
                para(
                    f"{contrarian_context} A contrarian bear reading fades strength by asking what the winners are pricing in too quickly. "
                    + " ".join(bull_points[:1] + bear_points[:1]),
                    contrarian_bear_ids[: max(1, min(3, len(contrarian_bear_ids)))],
                ),
                para(
                    "This stance does not deny the bull evidence; it reinterprets it as potential late-move vulnerability. "
                    + (bull_points[0] if bull_points else bear_points[0]),
                    contrarian_bear_ids[: max(1, min(4, len(contrarian_bear_ids)))],
                ),
            ],
            [
                para(
                    "Contrarian bear would be challenged if upside claims keep expanding without deteriorating breadth claims. "
                    + (bull_points[0] if bull_points else bear_points[0]),
                    (bull_ids[:1] or contrarian_bear_ids[:1]),
                )
            ],
        ),
    }

    # Ensure frame.claim_ids includes every claim cited by paragraphs/falsifiers.
    for frame in frames.values():
        cited: list[str] = []
        for paragraph in frame["paragraphs"]:
            cited.extend(paragraph["claim_ids"])
        for falsifier in frame.get("falsifiers") or []:
            cited.extend(falsifier["claim_ids"])
        frame["claim_ids"] = list(dict.fromkeys(cited + frame["claim_ids"]))

    dialectic = []
    for idx in range(min(3, max(len(bull_points), len(bear_points)))):
        bull_claim = bull_ids[idx] if idx < len(bull_ids) else bull_ids[0]
        bear_claim = bear_ids[idx] if idx < len(bear_ids) else bear_ids[0]
        dialectic.append(
            {
                "point": claim_index[bull_claim]["text"],
                "point_claim_ids": [bull_claim],
                "counterpoint": claim_index[bear_claim]["text"],
                "counterpoint_claim_ids": [bear_claim],
            }
        )

    summary_ids = list(dict.fromkeys(bull_ids[:2] + bear_ids[:2]))
    direction_label = {
        "risk_on": "risk on",
        "risk_off": "risk off",
        "mixed": "mixed",
    }[popular_dir]
    summary = (
        f"Dual-thesis supplement for the approved MarketForge briefing. "
        f"Popular direction inferred as {direction_label}. "
        + " ".join(claim_index[i]["text"] for i in summary_ids)
    )

    return {
        "run": {
            "run_id": approved_bundle["run"]["run_id"],
            "as_of": approved_bundle["run"]["as_of"],
            "parent_mode": approved_bundle["run"].get("mode"),
            "thesis_engine": "deterministic-v1",
        },
        "parent_article_title": approved_bundle.get("article", {}).get("title", ""),
        "popular_direction": popular_dir,
        "polarization": polarized,
        "summary": summary,
        "summary_claim_ids": summary_ids,
        "frames": frames,
        "dialectic": dialectic,
        "disclaimer": (
            "Educational dual-thesis analysis only. Not investment advice. "
            "Bull/bear and popular/contrarian frames are interpretive readings of an approved "
            "MarketForge claim ledger. They do not add facts, prices, or filings beyond that ledger."
        ),
    }


def validate_thesis_bundle(
    thesis: dict[str, Any],
    *,
    approved_bundle: dict[str, Any],
    artifact_root: str | Path | None = None,
) -> ThesisValidationResult:
    """Validate a dual-thesis package against its parent approved run bundle."""

    # Parent must itself be a valid publishable factual bundle.
    try:
        parent = validate_run_bundle(approved_bundle, artifact_root=artifact_root)
    except ValidationError as exc:
        raise ThesisValidationError(f"parent bundle invalid: {exc}") from exc
    if not parent.publishable:
        raise ThesisValidationError("parent bundle is not publishable")

    claim_index = {c["id"]: c for c in approved_bundle.get("claims", [])}
    if not claim_index:
        raise ThesisValidationError("parent bundle has no claims")

    if thesis.get("run", {}).get("run_id") != approved_bundle["run"]["run_id"]:
        raise ThesisValidationError("thesis run_id must match parent run_id")
    if thesis.get("run", {}).get("as_of") != approved_bundle["run"]["as_of"]:
        raise ThesisValidationError("thesis as_of must match parent as_of")

    if not (thesis.get("disclaimer") or "").strip():
        raise ThesisValidationError("thesis disclaimer is required")
    if not (thesis.get("summary") or "").strip():
        raise ThesisValidationError("thesis summary is required")
    summary_ids = thesis.get("summary_claim_ids") or []
    if not summary_ids:
        raise ThesisValidationError("thesis summary_claim_ids required")
    for cid in summary_ids:
        if cid not in claim_index:
            raise ThesisValidationError(f"summary references unknown claim: {cid}")
    _validate_numeric_against_claims(thesis["summary"], summary_ids, claim_index, "summary")

    frames = thesis.get("frames") or {}
    for key in _FRAME_KEYS:
        if key not in frames:
            raise ThesisValidationError(f"missing frame: {key}")

    for key, frame in frames.items():
        ids = frame.get("claim_ids") or []
        if not ids:
            raise ThesisValidationError(f"frame {key} has no claim_ids")
        for cid in ids:
            if cid not in claim_index:
                raise ThesisValidationError(f"frame {key} references unknown claim: {cid}")
        paragraphs = frame.get("paragraphs") or []
        if not paragraphs:
            raise ThesisValidationError(f"frame {key} has no paragraphs")
        for paragraph in paragraphs:
            p_ids = paragraph.get("claim_ids") or []
            if not p_ids:
                raise ThesisValidationError(f"frame {key} paragraph missing claim_ids")
            for cid in p_ids:
                if cid not in claim_index:
                    raise ThesisValidationError(f"frame {key} references unknown claim: {cid}")
            _validate_numeric_against_claims(
                paragraph.get("text", ""), p_ids, claim_index, f"frame {key}"
            )
        for falsifier in frame.get("falsifiers") or []:
            f_ids = falsifier.get("claim_ids") or []
            if not f_ids:
                raise ThesisValidationError(f"frame {key} falsifier missing claim_ids")
            for cid in f_ids:
                if cid not in claim_index:
                    raise ThesisValidationError(f"frame {key} falsifier unknown claim: {cid}")
            _validate_numeric_against_claims(
                falsifier.get("text", ""), f_ids, claim_index, f"frame {key} falsifier"
            )

    for row in thesis.get("dialectic") or []:
        for field in ("point_claim_ids", "counterpoint_claim_ids"):
            ids = row.get(field) or []
            if not ids:
                raise ThesisValidationError(f"dialectic {field} required")
            for cid in ids:
                if cid not in claim_index:
                    raise ThesisValidationError(f"dialectic references unknown claim: {cid}")
        _validate_numeric_against_claims(
            row.get("point", ""), row.get("point_claim_ids") or [], claim_index, "dialectic point"
        )
        _validate_numeric_against_claims(
            row.get("counterpoint", ""),
            row.get("counterpoint_claim_ids") or [],
            claim_index,
            "dialectic counterpoint",
        )

    return ThesisValidationResult(publishable=True, errors=[], warnings=[])
