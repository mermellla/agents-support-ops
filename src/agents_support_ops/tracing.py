from __future__ import annotations

import threading
import uuid
from typing import Any

from .audit import AuditLog
from .models import AuditEvent, EventKind


class SupportTraceProcessor:
    """Agents SDK-compatible trace processor with no hard SDK dependency."""

    def __init__(self, audit_log: AuditLog) -> None:
        self.audit_log = audit_log
        self._lock = threading.Lock()

    @staticmethod
    def _export(item: Any) -> dict[str, Any]:
        exporter = getattr(item, "export", None)
        if callable(exporter):
            return exporter() or {}
        return {}

    @staticmethod
    def _value(item: Any, name: str, default: str = "unknown") -> str:
        return str(getattr(item, name, default))

    def _record(self, trace_id: str, kind: EventKind, payload: dict[str, Any]) -> None:
        event = AuditEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            trace_id=trace_id,
            kind=kind,
            payload=payload,
        )
        with self._lock:
            self.audit_log.append(event)

    def on_trace_start(self, trace: Any) -> None:
        self._record(
            self._value(trace, "trace_id"),
            EventKind.TRACE_STARTED,
            {"name": self._value(trace, "name"), **self._export(trace)},
        )

    def on_trace_end(self, trace: Any) -> None:
        self._record(
            self._value(trace, "trace_id"), EventKind.TRACE_FINISHED, self._export(trace)
        )

    def on_span_start(self, span: Any) -> None:
        self._record(
            self._value(span, "trace_id"), EventKind.SPAN_STARTED, self._export(span)
        )

    def on_span_end(self, span: Any) -> None:
        self._record(
            self._value(span, "trace_id"), EventKind.SPAN_FINISHED, self._export(span)
        )

    def force_flush(self) -> None:
        return None

    def shutdown(self) -> None:
        self.force_flush()
