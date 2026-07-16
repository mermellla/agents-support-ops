from __future__ import annotations

import json
from pathlib import Path

from .audit import Redactor
from .models import ReplayBundle


class ReplayStore:
    def __init__(self, root: str | Path, redactor: Redactor | None = None) -> None:
        self.root = Path(root)
        self.redactor = redactor or Redactor()

    def save(self, bundle: ReplayBundle) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{bundle.replay_id}.json"
        payload = self.redactor.redact(bundle.model_dump(mode="json"))
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load(self, replay_id: str) -> ReplayBundle:
        path = self.root / f"{replay_id}.json"
        return ReplayBundle.model_validate_json(path.read_text(encoding="utf-8"))
