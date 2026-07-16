import json

import pytest
from agents_support_ops import EvidenceItem, ReplayBundle, ReplayStore


def test_replay_store_redacts_then_seals(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    bundle = ReplayBundle(
        replay_id="replay_1",
        trace_id="trace_1",
        ticket={"email": "person@example.com"},
        evidence=[
            EvidenceItem(
                evidence_id="ev_1",
                source="ticket",
                title="Report",
                content="Authorization: Bearer should-never-appear",
            )
        ],
    )

    path = store.save(bundle)
    raw = path.read_text(encoding="utf-8")
    loaded = store.load("replay_1")

    assert "person@example.com" not in raw
    assert "should-never-appear" not in raw
    assert loaded.verify_integrity()


def test_replay_store_rejects_tampering(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    path = store.save(
        ReplayBundle(
            replay_id="replay_2",
            trace_id="trace_2",
            ticket={"summary": "Original"},
            evidence=[],
        )
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ticket"]["summary"] = "Altered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity verification failed"):
        store.load("replay_2")


@pytest.mark.parametrize(
    "replay_id",
    [
        "../escaped",
        "..\\escaped",
        "nested/escaped",
        "nested\\escaped",
        ".",
        "..",
        "/absolute/path",
        "C:\\absolute\\path",
        "nested/../escaped",
        "",
    ],
)
def test_replay_store_rejects_unsafe_ids_for_save_and_load(tmp_path, replay_id: str) -> None:
    store = ReplayStore(tmp_path / "replays")
    bundle = ReplayBundle(
        replay_id=replay_id,
        trace_id="trace_unsafe",
        ticket={"summary": "Unsafe ID"},
        evidence=[],
    )

    with pytest.raises(ValueError, match="unsafe path characters"):
        store.save(bundle)
    with pytest.raises(ValueError, match="unsafe path characters"):
        store.load(replay_id)

    assert not (tmp_path / "escaped.json").exists()


@pytest.mark.parametrize(
    "replay_id",
    ["replay_1", "Replay-2026.07.16", "a", "0" * 128],
)
def test_replay_store_accepts_normal_ids(tmp_path, replay_id: str) -> None:
    store = ReplayStore(tmp_path)
    bundle = ReplayBundle(
        replay_id=replay_id,
        trace_id="trace_safe",
        ticket={"summary": "Safe ID"},
        evidence=[],
    )

    path = store.save(bundle)

    assert path.parent == tmp_path.resolve()
    assert store.load(replay_id).replay_id == replay_id


def test_replay_store_rejects_resolved_symlink_escape(tmp_path) -> None:
    root = tmp_path / "replays"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged", encoding="utf-8")
    link = root / "linked.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:  # pragma: no cover - Windows may deny symlink creation
        pytest.skip(f"Symlink creation unavailable: {exc}")

    store = ReplayStore(root)
    bundle = ReplayBundle(
        replay_id="linked",
        trace_id="trace_symlink",
        ticket={"summary": "Contained path required"},
        evidence=[],
    )

    with pytest.raises(ValueError, match="escapes the configured store"):
        store.save(bundle)
    with pytest.raises(ValueError, match="escapes the configured store"):
        store.load("linked")
    assert outside.read_text(encoding="utf-8") == "unchanged"
