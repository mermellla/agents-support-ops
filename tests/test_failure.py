from agents_support_ops import CircuitOpenError, FailurePolicy, ToolExecutor


def test_retry_then_success() -> None:
    calls = 0

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("slow")
        return "ok"

    executor = ToolExecutor(FailurePolicy(max_attempts=3), sleep=lambda _: None)
    assert executor.execute(flaky) == "ok"
    assert executor.retry_count == 2


def test_circuit_opens_after_threshold() -> None:
    executor = ToolExecutor(
        FailurePolicy(max_attempts=1, circuit_failure_threshold=2, circuit_cooldown_seconds=60),
        sleep=lambda _: None,
    )

    def broken() -> None:
        raise ConnectionError("offline")

    for _ in range(2):
        try:
            executor.execute(broken)
        except ConnectionError:
            pass
    assert executor.circuit_status == "open"
    try:
        executor.execute(broken)
    except CircuitOpenError:
        pass
    else:
        raise AssertionError("Expected open circuit")
