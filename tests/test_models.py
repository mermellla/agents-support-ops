from datetime import UTC, datetime

import pytest
from agents_support_ops import EscalationPackage, EvidenceItem, ReplayBundle


def evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev_1",
        source="log",
        title="API response",
        content="status=429",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


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
