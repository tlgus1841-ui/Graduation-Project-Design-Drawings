"""
Unit tests for Emergency Circuit Breaker (Week 13).
Author: Sihyeon Park (22101489 / Tech Lead)
"""

from harness.safety.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_initially_closed():
    cb = CircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_trips_on_rate_limit():
    # Allow at most 3 commands per 2.0s
    cb = CircuitBreaker(max_commands_per_window=3, window_seconds=2.0)
    t0 = 100.0

    assert cb.record_command(current_time=t0) is True
    assert cb.record_command(current_time=t0 + 0.1) is True
    assert cb.record_command(current_time=t0 + 0.2) is True
    # 4th command within window must TRIP circuit
    assert cb.record_command(current_time=t0 + 0.3) is False
    assert cb.state == CircuitState.OPEN
    assert cb.total_trips == 1


def test_circuit_breaker_cooldown_to_half_open():
    cb = CircuitBreaker(
        max_commands_per_window=2, window_seconds=1.0, trip_cooldown_seconds=5.0
    )
    t0 = 100.0
    cb.trip("manual test trip", current_time=t0)
    assert cb.can_execute(current_time=t0 + 1.0) is False

    # After cooldown period expires, enters HALF_OPEN
    assert cb.can_execute(current_time=t0 + 5.1) is True
    assert cb.state == CircuitState.HALF_OPEN

    # Successful command in HALF_OPEN resets to CLOSED
    assert cb.record_command(current_time=t0 + 5.2) is True
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_manual_reset():
    cb = CircuitBreaker()
    cb.trip("error")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True
