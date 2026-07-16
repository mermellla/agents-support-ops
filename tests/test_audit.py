import json

from agents_support_ops import AuditEvent, AuditLog, Redactor


def test_redactor_removes_nested_secrets_and_pii(tmp_path) -> None:
    audit = AuditLog(tmp_path / "audit.jsonl", Redactor())
    audit.append(
        AuditEvent(
            event_id="evt_1",
            trace_id="trace_1",
            kind="tool.finished",
            payload={
                "authorization": "Bearer should-never-appear",
                "nested": {"email": "person@example.com", "note": "key sk-secretvalue123"},
            },
        )
    )
    raw = (tmp_path / "audit.jsonl").read_text()
    assert "person@example.com" not in raw
    assert "should-never-appear" not in raw
    assert "sk-secretvalue123" not in raw
    parsed = json.loads(raw)
    assert parsed["payload"]["authorization"] == "[REDACTED]"


def test_redactor_removes_pii_and_secrets_from_mapping_keys() -> None:
    redacted = Redactor().redact(
        {"Claim from person@example.com with sk-secretvalue123": ["ev_1"]}
    )

    serialized = json.dumps(redacted)
    assert "person@example.com" not in serialized
    assert "sk-secretvalue123" not in serialized
    assert "Claim from [REDACTED] with [REDACTED]" in redacted
