"""HostManager glues everything together: timer + Duo + ASTER + discovery."""
from __future__ import annotations

import logging

from .aster_controller import AsterController
from .config import AppConfig
from .duo_controller import DuoController
from .session_timer import SessionTimer

log = logging.getLogger("nimbusseat.manager")


class HostManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.duo = DuoController(config.duo.service_name, config.duo.executable)
        self.aster = AsterController(
            config.aster.astctl, config.aster.guest_seat_id, config.aster.enabled
        )
        self.timer = SessionTimer(
            max_duration_minutes=config.session.max_duration_minutes,
            warn_at_minutes_left=config.session.warn_at_minutes_left,
            grace_period_seconds=config.session.grace_period_seconds,
            cooldown_minutes=config.session.cooldown_minutes,
            on_warning=self._on_warning,
            on_expired=self._on_expired,
            on_terminate=self._on_terminate,
        )

    # -- lifecycle ----------------------------------------------------------

    def startup(self) -> None:
        log.info("host-manager starting")
        self.aster.enable_guest_seat()
        if not self.duo.is_running():
            self.duo.start_service()

    def start_session(self, client_ip: str) -> tuple[bool, str]:
        state = self.timer.status()["state"]
        if state == "active":
            return False, "Сессия уже занята другим клиентом"
        if state == "cooldown":
            return False, "Хост на перерыве после предыдущей сессии, попробуйте позже"
        self.aster.enable_guest_seat()
        if not self.duo.is_running():
            self.duo.start_service()
        if not self.timer.start(client_ip):
            return False, "Не удалось запустить таймер сессии"
        return True, "Сессия начата: доступно 6 часов игрового времени"

    def stop_session(self, reason: str = "manual") -> None:
        self.timer.stop(reason=reason)

    def status(self) -> dict:
        st = self.timer.status()
        st["duo_running"] = self.duo.is_running()
        st["max_session_minutes"] = self.config.session.max_duration_minutes
        return st

    # -- timer callbacks ------------------------------------------------------

    def _on_warning(self, minutes_left: int) -> None:
        log.info("warning: %d minutes left", minutes_left)
        self.aster.notify_guest(
            f"NimbusSeat: осталось {minutes_left} мин игрового времени. "
            f"Сохраните прогресс."
        )

    def _on_expired(self) -> None:
        log.info("session expired, grace period started")
        self.aster.notify_guest(
            "NimbusSeat: 6 часов истекли. Стрим завершится через минуту — сохранитесь!"
        )

    def _on_terminate(self) -> None:
        log.info("terminating guest stream")
        self.duo.kick_active_stream()
