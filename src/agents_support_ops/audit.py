from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Iterable

from .models import AuditEvent


class Redactor:
    """Recursively removes configured PII fields and secret-like strings."""

    DEFAULT_KEYS = frozenset(
        {"authorization", "api_key", "apikey", "email", "password", "secret", "token"}
    )
    SECRET_PATTERNS = (
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{8,}\b", re.IGNORECASE),
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    )

    def __init__(self, keys: Iterable[str] | None = None, replacement: str = "[REDACTED]") -> None:
        self.keys = {key.casefold() for key in (keys or self.DEFAULT_KEYS)}
        self.replacement = replacement

    def redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self.replacement if str(key).casefold() in self.keys else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            result = value
            for pattern in self.SECRET_PATTERNS:
                result = pattern.sub(self.replacement, result)
            return result
        return value


class AuditLog:
    """Thread-safe append-only JSONL audit sink."""

    def __init__(self, path: str | Path, redactor: Redactor | None = None) -> None:
        self.path = Path(path)
        self.redactor = redactor or Redactor()
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        payload = self.redactor.redact(event.model_dump(mode="json"))
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read(self) -> list[AuditEvent]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [AuditEvent.model_validate_json(line) for line in handle if line.strip()]
