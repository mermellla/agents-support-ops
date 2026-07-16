from __future__ import annotations

import json
import re
from pathlib import Path

from .audit import Redactor
from .models import ReplayBundle


_SAFE_REPLAY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class ReplayStore:
    def __init__(self, root: str | Path, redactor: Redactor | None = None) -> None:
        self.root = Path(root)
        self.redactor = redactor or Redactor()

    def save(self, bundle: ReplayBundle) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path_for(bundle.replay_id)
        payload = self.redactor.redact(
            bundle.model_dump(mode="json", exclude={"integrity"})
        )
        persisted = ReplayBundle.model_validate(payload).with_integrity()
        payload = persisted.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load(self, replay_id: str) -> ReplayBundle:
        path = self._path_for(replay_id)
        bundle = ReplayBundle.model_validate_json(path.read_text(encoding="utf-8"))
        if not bundle.verify_integrity():
            raise ValueError("Replay bundle is missing required integrity metadata")
        return bundle

    def _path_for(self, replay_id: str) -> Path:
        if not _SAFE_REPLAY_ID.fullmatch(replay_id) or replay_id in {".", ".."}:
            raise ValueError("Replay ID contains unsafe path characters")

        root = self.root.resolve()
        path = (root / f"{replay_id}.json").resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Replay path escapes the configured store") from exc
        return path
