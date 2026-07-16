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


class ExecutionMode(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL = "model"


class ToolResultProvenance(StrEnum):
    EXECUTED = "executed"
    RECORDED = "recorded"


class ModelOutputProvenance(StrEnum):
    NOT_USED = "not_used"
    NEWLY_GENERATED = "newly_generated"
    RECORDED = "recorded"
    REGENERATED = "regenerated"


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
    result_provenance: ToolResultProvenance = ToolResultProvenance.EXECUTED


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_count: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def populate_total(self) -> "TokenUsage":
        if self.total_tokens == 0 and (self.input_tokens or self.output_tokens):
            self.total_tokens = self.input_tokens + self.output_tokens
        return self


class ModelRunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai"] = "openai"
    model: str
    prompt_id: str
    prompt_version: str
    prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost_usd: float = Field(default=0, ge=0)
    pricing_catalog_version: str


class RunProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_mode: ExecutionMode = ExecutionMode.DETERMINISTIC
    tool_results: ToolResultProvenance = ToolResultProvenance.EXECUTED
    evaluation: Literal["deterministic"] = "deterministic"
    model_output: ModelOutputProvenance = ModelOutputProvenance.NOT_USED
    parent_replay_id: str | None = None


class ReplayIntegrity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["sha256"] = "sha256"
    canonical_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReplayBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.1"
    replay_id: str
    trace_id: str
    ticket: dict[str, Any]
    evidence: list[EvidenceItem]
    tool_exchanges: list[ToolExchange] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(
        default_factory=dict,
        deprecated="Use model_run.usage for typed token accounting.",
    )
    estimated_cost_usd: float = Field(
        default=0,
        deprecated="Use model_run.estimated_cost_usd.",
    )
    generated_model_output: bool = Field(
        default=False,
        deprecated="Use provenance.model_output.",
    )
    provenance: RunProvenance = Field(default_factory=RunProvenance)
    model_run: ModelRunMetadata | None = None
    model_output: dict[str, Any] | None = None
    recorded_output: dict[str, Any] | None = None
    integrity: ReplayIntegrity | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def normalize_compatibility_fields(self) -> "ReplayBundle":
        generated_model_output = bool(self.__dict__.get("generated_model_output", False))
        if self.schema_version == "1.0" and generated_model_output:
            if self.provenance.model_output == ModelOutputProvenance.NOT_USED:
                self.provenance.model_output = ModelOutputProvenance.NEWLY_GENERATED
        self.generated_model_output = (
            self.provenance.model_output != ModelOutputProvenance.NOT_USED
        )
        if self.integrity is not None and not self.verify_integrity():
            raise ValueError("Replay bundle integrity verification failed")
        return self

    def canonical_digest(self) -> str:
        stable = _without_runtime_timestamps(
            self.model_dump(mode="json", exclude={"integrity"})
        )
        encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def with_integrity(self) -> "ReplayBundle":
        return self.model_copy(
            update={
                "integrity": ReplayIntegrity(canonical_sha256=self.canonical_digest())
            }
        )

    def verify_integrity(self) -> bool:
        if self.integrity is None:
            return self.schema_version == "1.0"
        return self.integrity.canonical_sha256 == self.canonical_digest()


_RUNTIME_TIMESTAMP_PATHS = frozenset(
    {
        ("created_at",),
        ("evidence", "*", "observed_at"),
        ("approvals", "*", "decided_at"),
        ("model_run", "generated_at"),
        ("recorded_output", "evidence", "*", "observed_at"),
        ("recorded_output", "escalation", "evidence", "*", "observed_at"),
    }
)


def _without_runtime_timestamps(value: Any, path: tuple[str, ...] = ()) -> Any:
    """Remove only modeled runtime timestamps from canonical replay content.

    Arbitrary user-controlled mappings such as ``ticket``, ``model_output``, and
    ``recorded_output`` remain fully integrity-covered even when their keys look
    like timestamps or integrity metadata.
    """

    if isinstance(value, dict):
        return {
            key: _without_runtime_timestamps(item, path + (key,))
            for key, item in value.items()
            if path + (key,) not in _RUNTIME_TIMESTAMP_PATHS
        }
    if isinstance(value, list):
        return [_without_runtime_timestamps(item, path + ("*",)) for item in value]
    return value


_NARRATIVE_FIELDS = (
    "summary",
    "impact",
    "reproduction_steps",
    "suspected_component",
    "recommended_next_action",
)


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
    narrative_evidence: dict[str, list[str]]
    trace_id: str

    @model_validator(mode="after")
    def factual_narrative_requires_evidence(self) -> "EscalationPackage":
        evidence_ids = {item.evidence_id for item in self.evidence}
        required_fields = set(_NARRATIVE_FIELDS)
        provided_fields = set(self.narrative_evidence)
        missing = required_fields - provided_fields
        if missing:
            raise ValueError(f"Narrative fields have no evidence citations: {sorted(missing)}")
        unexpected = provided_fields - required_fields
        if unexpected:
            raise ValueError(f"Unknown narrative evidence fields: {sorted(unexpected)}")
        for field_name in _NARRATIVE_FIELDS:
            cited = self.narrative_evidence[field_name]
            if not cited or any(not evidence_id.strip() for evidence_id in cited):
                raise ValueError(f"Narrative field has no evidence citation: {field_name}")
            unknown = set(cited) - evidence_ids
            if unknown:
                raise ValueError(
                    f"Narrative field cites unknown evidence ({field_name}): {sorted(unknown)}"
                )
        for claim in self.confirmed_claims:
            cited = self.claim_evidence.get(claim, [])
            if not cited:
                raise ValueError(f"Confirmed claim has no evidence citation: {claim}")
            unknown = set(cited) - evidence_ids
            if unknown:
                raise ValueError(f"Claim cites unknown evidence: {sorted(unknown)}")
        return self

    def to_markdown(self) -> str:
        def narrative_citations(field_name: str) -> str:
            return f" (`{', '.join(self.narrative_evidence[field_name])}`)"

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
            f"## Summary\n\n{self.summary}{narrative_citations('summary')}\n\n"
            f"## Impact\n\n{self.impact}{narrative_citations('impact')}\n\n"
            f"## Evidence\n\n{evidence}\n\n## Confirmed claims\n\n{claims}\n\n"
            f"## Hypotheses\n\n{hypotheses}\n\n## Reproduction\n\n{steps}"
            f"{narrative_citations('reproduction_steps')}\n\n"
            f"## Suspected component\n\n{self.suspected_component}"
            f"{narrative_citations('suspected_component')}\n\n"
            f"## Recommended next action\n\n{self.recommended_next_action}"
            f"{narrative_citations('recommended_next_action')}\n"
        )
