from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from agents_support_ops import (
    ApprovalRecord,
    EscalationPackage,
    EvidenceItem,
    ModelOutputProvenance,
    ModelRunMetadata,
    ReplayBundle,
    ToolExchange,
)


def evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev_1",
        source="log",
        title="API response",
        content="status=429",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def narrative_evidence(evidence_id: str = "ev_1") -> dict[str, list[str]]:
    return {
        "summary": [evidence_id],
        "impact": [evidence_id],
        "reproduction_steps": [evidence_id],
        "suspected_component": [evidence_id],
        "recommended_next_action": [evidence_id],
    }


def test_confirmed_claim_requires_known_evidence() -> None:
    with pytest.raises(ValueError, match="no evidence"):
        EscalationPackage(
            escalation_id="esc_1",
            ticket_id="ticket_1",
            summary="Requests are being rate limited.",
            impact="Uploads pause.",
            evidence=[evidence()],
            reproduction_steps=["Submit six requests."],
            suspected_component="rate limiter",
            recommended_next_action="Inspect quota state.",
            confirmed_claims=["The API returned 429."],
            narrative_evidence=narrative_evidence(),
            trace_id="trace_1",
        )


def test_replay_digest_ignores_creation_time() -> None:
    common = dict(
        schema_version="1.0",
        replay_id="r1",
        trace_id="t1",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
    )
    first = ReplayBundle(**common, created_at=datetime(2026, 1, 1, tzinfo=UTC))
    second = ReplayBundle(**common, created_at=datetime(2026, 2, 1, tzinfo=UTC))
    assert first.canonical_digest() == second.canonical_digest()


def test_replay_digest_ignores_only_modeled_runtime_timestamps() -> None:
    first = ReplayBundle(
        replay_id="r1",
        trace_id="t1",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
        approvals=[
            ApprovalRecord(
                tool_name="publish",
                tool_call_id="call_1",
                decision="approved",
                reviewer="reviewer",
                reason="Evidence is complete.",
                decided_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ],
        model_run=ModelRunMetadata(
            model="model-snapshot",
            prompt_id="support-investigation",
            prompt_version="1.0.0",
            prompt_sha256="a" * 64,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            pricing_catalog_version="2026-07-16",
        ),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = first.model_copy(deep=True)
    assert second.evidence[0].observed_at is not None
    second.evidence[0].observed_at += timedelta(hours=1)
    second.approvals[0].decided_at += timedelta(hours=1)
    assert second.model_run is not None
    second.model_run.generated_at += timedelta(hours=1)
    second.created_at += timedelta(hours=1)

    assert first.canonical_digest() == second.canonical_digest()


def test_legacy_generated_output_maps_to_provenance() -> None:
    bundle = ReplayBundle(
        schema_version="1.0",
        replay_id="legacy",
        trace_id="trace_legacy",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
        generated_model_output=True,
    )

    assert bundle.provenance.model_output == ModelOutputProvenance.NEWLY_GENERATED
    assert bundle.verify_integrity()


def test_version_1_1_bundle_can_be_sealed_and_verified() -> None:
    bundle = ReplayBundle(
        replay_id="sealed",
        trace_id="trace_sealed",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
    ).with_integrity()

    assert bundle.schema_version == "1.1"
    assert bundle.integrity is not None
    assert bundle.verify_integrity()


def test_recorded_output_is_covered_by_replay_integrity() -> None:
    bundle = ReplayBundle(
        replay_id="sealed-output",
        trace_id="trace_sealed",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
        recorded_output={"summary": "Original evidence-backed result"},
    ).with_integrity()

    payload = bundle.model_dump(mode="json")
    payload["recorded_output"]["summary"] = "Tampered result"

    with pytest.raises(ValueError, match="integrity verification failed"):
        ReplayBundle.model_validate(payload)


@pytest.mark.parametrize("field_name", ["status_at", "integrity"])
def test_recorded_output_metadata_like_keys_are_integrity_covered(field_name: str) -> None:
    bundle = ReplayBundle(
        replay_id="sealed-output",
        trace_id="trace_sealed",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
        recorded_output={field_name: "original"},
    ).with_integrity()
    payload = bundle.model_dump(mode="json")
    payload["recorded_output"][field_name] = "tampered"

    with pytest.raises(ValueError, match="integrity verification failed"):
        ReplayBundle.model_validate(payload)


def test_replay_digest_ignores_only_typed_recorded_output_evidence_timestamps() -> None:
    bundle = ReplayBundle(
        replay_id="sealed-recorded-evidence",
        trace_id="trace_sealed",
        ticket={"id": "ticket_1"},
        evidence=[evidence()],
        recorded_output={
            "evidence": [
                {
                    "evidence_id": "ev_1",
                    "observed_at": "2026-01-01T00:00:00Z",
                }
            ],
            "escalation": {
                "evidence": [
                    {
                        "evidence_id": "ev_1",
                        "observed_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
            "status_at": "original-status",
            "integrity": "original-nested-integrity",
        },
    ).with_integrity()
    timestamp_update = bundle.model_dump(mode="json")
    timestamp_update["recorded_output"]["evidence"][0]["observed_at"] = (
        "2026-02-01T00:00:00Z"
    )
    timestamp_update["recorded_output"]["escalation"]["evidence"][0]["observed_at"] = (
        "2026-02-01T00:00:00Z"
    )

    updated = ReplayBundle.model_validate(timestamp_update)
    assert updated.canonical_digest() == bundle.canonical_digest()

    for protected_field in ("status_at", "integrity"):
        tampered = bundle.model_dump(mode="json")
        tampered["recorded_output"][protected_field] = "tampered"
        with pytest.raises(ValueError, match="integrity verification failed"):
            ReplayBundle.model_validate(tampered)


@pytest.mark.parametrize(
    ("container", "field_name"),
    [
        ("ticket", "created_at"),
        ("ticket", "integrity"),
        ("tool", "status_at"),
        ("tool", "integrity"),
    ],
)
def test_arbitrary_nested_ticket_and_tool_keys_are_integrity_covered(
    container: str, field_name: str
) -> None:
    bundle = ReplayBundle(
        replay_id="sealed-nested",
        trace_id="trace_sealed",
        ticket={"details": {field_name: "original"}},
        evidence=[evidence()],
        tool_exchanges=[
            ToolExchange(
                tool_call_id="call_1",
                tool_name="inspect",
                arguments={"details": {field_name: "original"}},
            )
        ],
    ).with_integrity()
    payload = bundle.model_dump(mode="json")
    if container == "ticket":
        payload["ticket"]["details"][field_name] = "tampered"
    else:
        payload["tool_exchanges"][0]["arguments"]["details"][field_name] = "tampered"

    with pytest.raises(ValueError, match="integrity verification failed"):
        ReplayBundle.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda citations: citations.pop("summary"),
            "Narrative fields have no evidence citations",
        ),
        (
            lambda citations: citations.__setitem__("impact", []),
            "Narrative field has no evidence citation: impact",
        ),
        (
            lambda citations: citations.__setitem__("suspected_component", ["unknown"]),
            "Narrative field cites unknown evidence",
        ),
        (
            lambda citations: citations.__setitem__("extra", ["ev_1"]),
            "Unknown narrative evidence fields",
        ),
    ],
)
def test_escalation_narrative_requires_known_field_specific_evidence(
    mutate: Callable[[dict[str, list[str]]], object], message: str
) -> None:
    citations = narrative_evidence()
    mutate(citations)

    with pytest.raises(ValueError, match=message):
        EscalationPackage(
            escalation_id="esc_1",
            ticket_id="ticket_1",
            summary="Requests are being rate limited.",
            impact="Uploads pause.",
            evidence=[evidence()],
            reproduction_steps=["Submit six requests."],
            suspected_component="rate limiter",
            recommended_next_action="Inspect quota state.",
            narrative_evidence=citations,
            trace_id="trace_1",
        )


def test_escalation_exports_field_specific_narrative_evidence() -> None:
    package = EscalationPackage(
        escalation_id="esc_1",
        ticket_id="ticket_1",
        summary="Requests are being rate limited.",
        impact="Uploads pause.",
        evidence=[evidence()],
        reproduction_steps=["Submit six requests."],
        suspected_component="rate limiter",
        recommended_next_action="Inspect quota state.",
        narrative_evidence=narrative_evidence(),
        trace_id="trace_1",
    )

    assert package.model_dump(mode="json")["narrative_evidence"] == narrative_evidence()
    assert package.to_markdown().count("(`ev_1`)") == 5
