from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventKind(StrEnum):
    TRACE_STARTED = "trace.started"
    TRACE_FINISHED = "trace.finished"
    SPAN_STARTED = "span.started"
    SPAN_FINISHED = "span.finished"
    TOOL_RETRY = "tool.retry"
    CIRCUIT_OPENED = "circuit.opened"
    APPROVAL = "approval.recorded"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    trace_id: str
    kind: EventKind | str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = "system"
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: str
    title: str
    content: str
    observed_at: datetime | None = None


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    tool_call_id: str
    decision: Literal["approved", "rejected"]
    reviewer: str
    reason: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    error: str | None = None
    attempt: int = 1
    latency_ms: float = 0


class ReplayBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    replay_id: str
    trace_id: str
    ticket: dict[str, Any]
    evidence: list[EvidenceItem]
    tool_exchanges: list[ToolExchange] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float = 0
    generated_model_output: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def canonical_digest(self) -> str:
        stable = self.model_dump(mode="json", exclude={"created_at"})
        encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class EscalationPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    escalation_id: str
    ticket_id: str
    summary: str
    impact: str
    evidence: list[EvidenceItem]
    reproduction_steps: list[str]
    suspected_component: str
    recommended_next_action: str
    confirmed_claims: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    claim_evidence: dict[str, list[str]] = Field(default_factory=dict)
    trace_id: str

    @model_validator(mode="after")
    def confirmed_claims_require_evidence(self) -> "EscalationPackage":
        evidence_ids = {item.evidence_id for item in self.evidence}
        for claim in self.confirmed_claims:
            cited = self.claim_evidence.get(claim, [])
            if not cited:
                raise ValueError(f"Confirmed claim has no evidence citation: {claim}")
            unknown = set(cited) - evidence_ids
            if unknown:
                raise ValueError(f"Claim cites unknown evidence: {sorted(unknown)}")
        return self

    def to_markdown(self) -> str:
        evidence = "\n".join(
            f"- **{item.evidence_id} — {item.title}:** {item.content}" for item in self.evidence
        )
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(self.reproduction_steps, 1))
        claims = "\n".join(
            f"- {claim} (`{', '.join(self.claim_evidence[claim])}`)" for claim in self.confirmed_claims
        ) or "- None"
        hypotheses = "\n".join(f"- {item} _(hypothesis)_" for item in self.hypotheses) or "- None"
        return (
            f"# Escalation {self.escalation_id}\n\n"
            f"**Ticket:** {self.ticket_id}  \n**Trace:** `{self.trace_id}`\n\n"
            f"## Summary\n\n{self.summary}\n\n## Impact\n\n{self.impact}\n\n"
            f"## Evidence\n\n{evidence}\n\n## Confirmed claims\n\n{claims}\n\n"
            f"## Hypotheses\n\n{hypotheses}\n\n## Reproduction\n\n{steps}\n\n"
            f"## Suspected component\n\n{self.suspected_component}\n\n"
            f"## Recommended next action\n\n{self.recommended_next_action}\n"
        )
