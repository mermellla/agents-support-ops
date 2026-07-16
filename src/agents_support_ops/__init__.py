"""Operational support primitives for agent workflows."""

from importlib.metadata import PackageNotFoundError, version

from .audit import AuditLog, Redactor
from .failure import CircuitOpenError, FailurePolicy, ToolExecutor
from .models import (
    ApprovalRecord,
    AuditEvent,
    EscalationPackage,
    EvidenceItem,
    ExecutionMode,
    ModelOutputProvenance,
    ModelRunMetadata,
    ReplayBundle,
    ReplayIntegrity,
    RunProvenance,
    TokenUsage,
    ToolExchange,
    ToolResultProvenance,
)
from .replay import ReplayStore
from .tracing import SupportTraceProcessor

__all__ = [
    "ApprovalRecord",
    "AuditEvent",
    "AuditLog",
    "CircuitOpenError",
    "EscalationPackage",
    "EvidenceItem",
    "ExecutionMode",
    "FailurePolicy",
    "ModelOutputProvenance",
    "ModelRunMetadata",
    "Redactor",
    "ReplayBundle",
    "ReplayIntegrity",
    "ReplayStore",
    "RunProvenance",
    "SupportTraceProcessor",
    "TokenUsage",
    "ToolExchange",
    "ToolExecutor",
    "ToolResultProvenance",
]

try:
    __version__ = version("agents-support-ops")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"
