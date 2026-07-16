from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class CircuitOpenError(RuntimeError):
    pass


@dataclass(frozen=True)
class FailurePolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: float = 30.0
    injected_failure_rate: float = 0.0
    retryable_exceptions: tuple[type[Exception], ...] = (TimeoutError, ConnectionError)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not 0 <= self.injected_failure_rate <= 1:
            raise ValueError("injected_failure_rate must be between 0 and 1")


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None


@dataclass
class ToolExecutor(Generic[P, R]):
    policy: FailurePolicy
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    random_source: random.Random = field(default_factory=random.Random)
    state: CircuitState = field(default_factory=CircuitState)
    retry_count: int = 0

    @property
    def circuit_status(self) -> str:
        if self.state.opened_at is None:
            return "closed"
        if self.clock() - self.state.opened_at >= self.policy.circuit_cooldown_seconds:
            return "half-open"
        return "open"

    def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        status = self.circuit_status
        if status == "open":
            raise CircuitOpenError("Tool circuit is open; wait for the cooldown before retrying")
        if status == "half-open":
            self.state.opened_at = None

        last_error: Exception | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                if self.random_source.random() < self.policy.injected_failure_rate:
                    raise TimeoutError("Injected tool timeout")
                result = func(*args, **kwargs)
                self.state.consecutive_failures = 0
                return result
            except self.policy.retryable_exceptions as exc:
                last_error = exc
                self.state.consecutive_failures += 1
                if self.state.consecutive_failures >= self.policy.circuit_failure_threshold:
                    self.state.opened_at = self.clock()
                if attempt == self.policy.max_attempts:
                    break
                self.retry_count += 1
                delay = min(
                    self.policy.base_delay_seconds * (2 ** (attempt - 1)),
                    self.policy.max_delay_seconds,
                )
                self.sleep(delay)
        assert last_error is not None
        raise last_error
