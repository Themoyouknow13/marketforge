"""Sandbox multi-agent dual-thesis runtime.

Each agent is a discrete stage with frozen inputs/outputs for audit.
Default implementations are deterministic and fail-closed.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable

from .thesis import (
    ThesisValidationError,
    build_dual_thesis_bundle,
    infer_popular_direction,
    polarize_claims,
    validate_thesis_bundle,
)
from .validation import ValidationError, validate_run_bundle


@dataclass
class AgentStageResult:
    agent: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    input_summary: dict[str, Any]
    output: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_stage(
    agent: str,
    input_summary: dict[str, Any],
    fn: Callable[[], dict[str, Any]],
    notes: list[str] | None = None,
) -> AgentStageResult:
    started = _utc_now()
    t0 = time.perf_counter()
    try:
        output = fn()
        status = "ok"
        error = None
    except Exception as exc:  # noqa: BLE001 - sandbox must capture stage failures
        output = {}
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    finished = _utc_now()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return AgentStageResult(
        agent=agent,
        status=status,
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        input_summary=input_summary,
        output=output,
        notes=notes or [],
        error=error,
    )


def agent_orchestrator(approved_bundle: dict[str, Any]) -> AgentStageResult:
    def work() -> dict[str, Any]:
        run = approved_bundle["run"]
        return {
            "run_id": run["run_id"],
            "as_of": run["as_of"],
            "claim_count": len(approved_bundle.get("claims") or []),
            "source_count": len(approved_bundle.get("sources") or []),
            "boundary": "approved_bundle_only",
            "phase": "B_dual_thesis_sandbox",
        }

    return _run_stage(
        "thesis_orchestrator",
        {"bundle_run_id": approved_bundle.get("run", {}).get("run_id")},
        work,
        notes=["Frozen parent claim ledger; no browsing permitted."],
    )


def agent_parent_validator(
    approved_bundle: dict[str, Any], *, artifact_root: str | None
) -> AgentStageResult:
    def work() -> dict[str, Any]:
        result = validate_run_bundle(approved_bundle, artifact_root=artifact_root)
        if not result.publishable:
            raise ValidationError("parent bundle not publishable")
        return {
            "publishable": True,
            "claim_ids": [c["id"] for c in approved_bundle.get("claims") or []],
        }

    return _run_stage(
        "parent_bundle_validator",
        {"artifact_root": artifact_root},
        work,
        notes=["Parent MarketForge bundle must already be fail-closed publishable."],
    )


def agent_evidence_polarizer(approved_bundle: dict[str, Any]) -> AgentStageResult:
    def work() -> dict[str, Any]:
        claims = approved_bundle.get("claims") or []
        polarization = polarize_claims(claims)
        claim_index = {c["id"]: c["text"] for c in claims}
        tagged = []
        for bucket, ids in polarization.items():
            for cid in ids:
                tagged.append({"claim_id": cid, "tag": bucket, "text": claim_index.get(cid, "")})
        return {
            "polarization": polarization,
            "tagged_claims": tagged,
            "counts": {k: len(v) for k, v in polarization.items()},
        }

    return _run_stage(
        "evidence_polarizer",
        {"claim_count": len(approved_bundle.get("claims") or [])},
        work,
        notes=["Tags derived only from approved claim text polarity."],
    )


def agent_consensus_classifier(
    approved_bundle: dict[str, Any], polarization: dict[str, list[str]]
) -> AgentStageResult:
    def work() -> dict[str, Any]:
        direction = infer_popular_direction(polarization)
        if direction == "risk_on":
            drivers = polarization.get("bull_support") or []
            note = "More bull-supporting than bear-supporting claims in the approved ledger."
        elif direction == "risk_off":
            drivers = polarization.get("bear_support") or []
            note = "More bear-supporting than bull-supporting claims in the approved ledger."
        else:
            drivers = (polarization.get("bull_support") or [])[:2] + (
                polarization.get("bear_support") or []
            )[:2]
            note = "Bull and bear support are balanced or sparse; direction marked mixed."
        return {
            "popular_direction": direction,
            "driver_claim_ids": drivers[:6],
            "confidence_note": note,
            "popular_is_not_truth": True,
        }

    return _run_stage(
        "consensus_classifier",
        {"polarization_counts": {k: len(v) for k, v in polarization.items()}},
        work,
        notes=["Popular direction is a tape-consensus label, not a correctness claim."],
    )


def agent_bull_architect(thesis_bundle: dict[str, Any]) -> AgentStageResult:
    def work() -> dict[str, Any]:
        frames = thesis_bundle["frames"]
        return {
            "frames": {
                "popular_bull": deepcopy(frames["popular_bull"]),
                "contrarian_bull": deepcopy(frames["contrarian_bull"]),
            }
        }

    return _run_stage(
        "bull_architect",
        {"available_frames": ["popular_bull", "contrarian_bull"]},
        work,
        notes=["Steelman upside using only approved claim_ids."],
    )


def agent_bear_architect(thesis_bundle: dict[str, Any]) -> AgentStageResult:
    def work() -> dict[str, Any]:
        frames = thesis_bundle["frames"]
        return {
            "frames": {
                "popular_bear": deepcopy(frames["popular_bear"]),
                "contrarian_bear": deepcopy(frames["contrarian_bear"]),
            }
        }

    return _run_stage(
        "bear_architect",
        {"available_frames": ["popular_bear", "contrarian_bear"]},
        work,
        notes=["Steelman downside; does not suppress bull evidence."],
    )


def agent_dialectic_critic(thesis_bundle: dict[str, Any]) -> AgentStageResult:
    def work() -> dict[str, Any]:
        return {"dialectic": deepcopy(thesis_bundle.get("dialectic") or [])}

    return _run_stage(
        "dialectic_critic",
        {"row_budget": 3},
        work,
        notes=["Point/counterpoint only; no winner declaration."],
    )


def agent_dual_thesis_editor(
    approved_bundle: dict[str, Any],
    polarization: dict[str, list[str]],
    consensus: dict[str, Any],
    bull_frames: dict[str, Any],
    bear_frames: dict[str, Any],
    dialectic: list[dict[str, Any]],
) -> AgentStageResult:
    def work() -> dict[str, Any]:
        # Rebuild via canonical builder for consistency, then overlay stage outputs.
        thesis = build_dual_thesis_bundle(approved_bundle)
        thesis["polarization"] = polarization
        thesis["popular_direction"] = consensus["popular_direction"]
        thesis["frames"]["popular_bull"] = bull_frames["popular_bull"]
        thesis["frames"]["contrarian_bull"] = bull_frames["contrarian_bull"]
        thesis["frames"]["popular_bear"] = bear_frames["popular_bear"]
        thesis["frames"]["contrarian_bear"] = bear_frames["contrarian_bear"]
        thesis["dialectic"] = dialectic
        thesis["run"]["thesis_engine"] = "sandbox-agents-v1"
        thesis["run"]["sandbox"] = True
        return {"thesis_bundle": thesis}

    return _run_stage(
        "dual_thesis_editor",
        {
            "parent_run_id": approved_bundle["run"]["run_id"],
            "direction": consensus.get("popular_direction"),
        },
        work,
        notes=["Assembled four frames + dialectic into publish schema."],
    )


def agent_grounding_auditor(
    thesis_bundle: dict[str, Any],
    approved_bundle: dict[str, Any],
    *,
    artifact_root: str | None,
) -> AgentStageResult:
    def work() -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        # Advice-language scan
        banned = ("buy now", "sell now", "guaranteed", "will go to")
        blob = json_dumps_lower(thesis_bundle)
        for token in banned:
            if token in blob:
                findings.append({"severity": "error", "rule": "advice_language", "detail": token})
        result = validate_thesis_bundle(
            thesis_bundle,
            approved_bundle=approved_bundle,
            artifact_root=artifact_root,
        )
        if not result.publishable:
            findings.append(
                {"severity": "error", "rule": "validate_thesis_bundle", "detail": "not publishable"}
            )
        if findings and any(f["severity"] == "error" for f in findings):
            raise ThesisValidationError(
                "; ".join(f"{f['rule']}:{f['detail']}" for f in findings if f["severity"] == "error")
            )
        return {"pass": True, "findings": findings, "publishable": True}

    return _run_stage(
        "grounding_auditor",
        {"thesis_engine": thesis_bundle.get("run", {}).get("thesis_engine")},
        work,
        notes=["Independent audit; no silent repairs."],
    )


def json_dumps_lower(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=True).lower()


def run_sandbox_pipeline(
    approved_bundle: dict[str, Any], *, artifact_root: str | None = None
) -> dict[str, Any]:
    """Execute the full dual-thesis agent chain in sandbox mode."""

    stages: list[AgentStageResult] = []

    stages.append(agent_orchestrator(approved_bundle))
    stages.append(agent_parent_validator(approved_bundle, artifact_root=artifact_root))
    if stages[-1].status != "ok":
        return _finalize(stages, approved_bundle, None)

    polarizer = agent_evidence_polarizer(approved_bundle)
    stages.append(polarizer)
    if polarizer.status != "ok":
        return _finalize(stages, approved_bundle, None)

    consensus = agent_consensus_classifier(approved_bundle, polarizer.output["polarization"])
    stages.append(consensus)
    if consensus.status != "ok":
        return _finalize(stages, approved_bundle, None)

    # Build a complete thesis once so bull/bear architects can specialize from it.
    base_thesis = build_dual_thesis_bundle(approved_bundle)
    base_thesis["polarization"] = polarizer.output["polarization"]
    base_thesis["popular_direction"] = consensus.output["popular_direction"]

    bull = agent_bull_architect(base_thesis)
    stages.append(bull)
    bear = agent_bear_architect(base_thesis)
    stages.append(bear)
    dialectic = agent_dialectic_critic(base_thesis)
    stages.append(dialectic)
    if any(stage.status != "ok" for stage in (bull, bear, dialectic)):
        return _finalize(stages, approved_bundle, None)

    editor = agent_dual_thesis_editor(
        approved_bundle,
        polarizer.output["polarization"],
        consensus.output,
        bull.output["frames"],
        bear.output["frames"],
        dialectic.output["dialectic"],
    )
    stages.append(editor)
    if editor.status != "ok":
        return _finalize(stages, approved_bundle, None)

    thesis_bundle = editor.output["thesis_bundle"]
    auditor = agent_grounding_auditor(
        thesis_bundle, approved_bundle, artifact_root=artifact_root
    )
    stages.append(auditor)

    final_thesis = thesis_bundle if auditor.status == "ok" else None
    return _finalize(stages, approved_bundle, final_thesis)


def _finalize(
    stages: list[AgentStageResult],
    approved_bundle: dict[str, Any],
    thesis_bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    ok = all(stage.status == "ok" for stage in stages) and thesis_bundle is not None
    return {
        "sandbox": {
            "mode": "dual_thesis_agents_v1",
            "status": "passed" if ok else "failed",
            "completed_at": _utc_now(),
            "parent_run_id": approved_bundle.get("run", {}).get("run_id"),
            "parent_as_of": approved_bundle.get("run", {}).get("as_of"),
            "stages": [asdict(stage) for stage in stages],
            "stage_count": len(stages),
            "failed_stages": [s.agent for s in stages if s.status != "ok"],
        },
        "thesis_bundle": thesis_bundle,
    }
