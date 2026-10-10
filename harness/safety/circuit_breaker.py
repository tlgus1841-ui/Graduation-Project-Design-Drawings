"""
Self-Defending SDN Tower: Emergency Circuit Breaker.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 5 (Week 13) Milestone

Safety valve against AI anomalies, command floods, or rapid false positives.
Trips open when command rate or isolation failures exceed threshold,
forcing system into manual admin override mode.
"""

import time
from enum import Enum
from typing import Dict, List, Optional


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal autonomous AI operation
    OPEN = "OPEN"            # Tripped: AI commands blocked, manual intervention only
    HALF_OPEN = "HALF_OPEN"  # Trial testing recovery after cooldown


class CircuitBreaker:
    """
    SDN 관제탑 안전 서킷 브레이커:
    - 초당 명령 유입 수 제한 (rate limiting: e.g. 5 cmds / 2 sec)
    - 이상 격리 빈도 감시 (e.g. 연속 차단 시도 초과 시 Trip)
    - Trunk 포트 차단 시도와 같은 치명적 오류 즉각 Trip
    """

    def __init__(
        self,
        max_commands_per_window: int = 5,
        window_seconds: float = 2.0,
        trip_cooldown_seconds: float = 15.0,
    ):
        self.max_commands = max_commands_per_window
        self.window_sec = window_seconds
        self.cooldown_sec = trip_cooldown_seconds

        self.state = CircuitState.CLOSED
        self.command_timestamps: List[float] = []
        self.trip_time = 0.0
        self.trip_reason = ""
        self.total_trips = 0

    def can_execute(self, current_time: Optional[float] = None) -> bool:
        """AI 명령을 컨트롤러에 전달해도 안전한지 여부 판정"""
        now = current_time if current_time is not None else time.time()

        if self.state == CircuitState.OPEN:
            if now - self.trip_time >= self.cooldown_sec:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        return True

    def record_command(self, current_time: Optional[float] = None) -> bool:
        """
        명령 실행 기록 및 빈도 한도 검사.
        한도 초과 시 Trip(OPEN)으로 전환 후 False 반환.
        """
        now = current_time if current_time is not None else time.time()

        if not self.can_execute(now):
            return False

        # Sliding window pruning
        self.command_timestamps = [
            t for t in self.command_timestamps if now - t <= self.window_sec
        ]
        self.command_timestamps.append(now)

        if len(self.command_timestamps) > self.max_commands:
            self.trip(
                reason=f"명령 빈도 초과 ({len(self.command_timestamps)} commands in {self.window_sec}s)",
                current_time=now,
            )
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Half-open 상태에서 성공적으로 명령이 통과되면 다시 CLOSED 복귀
            self.state = CircuitState.CLOSED

        return True

    def trip(self, reason: str, current_time: Optional[float] = None):
        """서킷 강제 차단 (Trip OPEN)"""
        now = current_time if current_time is not None else time.time()
        self.state = CircuitState.OPEN
        self.trip_time = now
        self.trip_reason = reason
        self.total_trips += 1

    def reset(self):
        """관리자 수동 리셋"""
        self.state = CircuitState.CLOSED
        self.command_timestamps.clear()
        self.trip_time = 0.0
        self.trip_reason = ""

    def get_status(self) -> Dict:
        return {
            "state": self.state.value,
            "total_trips": self.total_trips,
            "trip_reason": self.trip_reason,
            "is_autonomous_allowed": (self.state != CircuitState.OPEN),
        }
