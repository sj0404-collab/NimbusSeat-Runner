"""Six-hour session timer with warnings, grace period and cooldown."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

log = logging.getLogger("nimbusseat.timer")


class SessionState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    GRACE = "grace"          # time is up, waiting grace period before hard stop
    COOLDOWN = "cooldown"    # short lock-out between sessions


@dataclass
class SessionInfo:
    state: SessionState = SessionState.IDLE
    client_ip: str | None = None
    started_at: float | None = None
    ends_at: float | None = None
    cooldown_until: float | None = None
    warnings_sent: list[int] = field(default_factory=list)

    def seconds_left(self) -> int:
        if self.state == SessionState.ACTIVE and self.ends_at:
            return max(0, int(self.ends_at - time.time()))
        return 0

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "client_ip": self.client_ip,
            "started_at": self.started_at,
            "ends_at": self.ends_at,
            "seconds_left": self.seconds_left(),
            "cooldown_until": self.cooldown_until,
        }


class SessionTimer:
    """Tracks a single guest session and enforces the time limit.

    Callbacks:
        on_warning(minutes_left)  -- fired at each configured checkpoint
        on_expired()              -- limit reached, grace period starts
        on_terminate()            -- grace period over, stream must be killed
    """

    def __init__(
        self,
        max_duration_minutes: int = 360,
        warn_at_minutes_left: list[int] | None = None,
        grace_period_seconds: int = 60,
        cooldown_minutes: int = 15,
        on_warning: Callable[[int], None] | None = None,
        on_expired: Callable[[], None] | None = None,
        on_terminate: Callable[[], None] | None = None,
    ) -> None:
        self.max_duration = max_duration_minutes * 60
        self.warn_at = sorted(warn_at_minutes_left or [30, 10, 5], reverse=True)
        self.grace_period = grace_period_seconds
        self.cooldown = cooldown_minutes * 60
        self.on_warning = on_warning or (lambda m: None)
        self.on_expired = on_expired or (lambda: None)
        self.on_terminate = on_terminate or (lambda: None)

        self.info = SessionInfo()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- public API -------------------------------------------------------

    def start(self, client_ip: str) -> bool:
        with self._lock:
            now = time.time()
            if self.info.state == SessionState.COOLDOWN and self.info.cooldown_until:
                if now < self.info.cooldown_until:
                    log.info("start rejected: cooldown until %s", self.info.cooldown_until)
                    return False
                self.info = SessionInfo()
            if self.info.state != SessionState.IDLE:
                return False
            self.info = SessionInfo(
                state=SessionState.ACTIVE,
                client_ip=client_ip,
                started_at=now,
                ends_at=now + self.max_duration,
            )
            self._stop.clear()
            self._thread = threading.Thread(target=self._watch, daemon=True, name="session-timer")
            self._thread.start()
            log.info("session started for %s, %d min limit", client_ip, self.max_duration // 60)
            return True

    def stop(self, reason: str = "manual") -> None:
        with self._lock:
            if self.info.state in (SessionState.ACTIVE, SessionState.GRACE):
                log.info("session stopped (%s)", reason)
                self._stop.set()
                self.info.state = SessionState.COOLDOWN
                self.info.cooldown_until = time.time() + self.cooldown

    def status(self) -> dict:
        with self._lock:
            info = self.info
            if (
                info.state == SessionState.COOLDOWN
                and info.cooldown_until
                and time.time() >= info.cooldown_until
            ):
                self.info = SessionInfo()
                info = self.info
            return info.to_dict()

    # -- internals --------------------------------------------------------

    def _watch(self) -> None:
        while not self._stop.wait(1.0):
            with self._lock:
                if self.info.state != SessionState.ACTIVE:
                    return
                left = self.info.seconds_left()
                for checkpoint in self.warn_at:
                    if left <= checkpoint * 60 and checkpoint not in self.info.warnings_sent:
                        self.info.warnings_sent.append(checkpoint)
                        threading.Thread(
                            target=self.on_warning, args=(checkpoint,), daemon=True
                        ).start()
                if left <= 0:
                    self.info.state = SessionState.GRACE
                    break
        else:
            return

        log.info("session limit reached, grace period %ds", self.grace_period)
        self.on_expired()
        if self._stop.wait(self.grace_period):
            return
        log.info("grace period over, terminating stream")
        self.on_terminate()
        self.stop(reason="time limit")
