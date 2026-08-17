"""Control of the Duo (Apollo/Sunshine fork) streaming host.

Duo runs as a Windows service and exposes Moonlight-compatible streaming.
The manager starts/stops the service around guest sessions and kills active
streams when the 6-hour timer fires.
"""
from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger("nimbusseat.duo")

IS_WINDOWS = sys.platform == "win32"


class DuoController:
    def __init__(self, service_name: str, executable: str) -> None:
        self.service_name = service_name
        self.executable = executable

    # -- service control ----------------------------------------------------

    def start_service(self) -> bool:
        return self._sc("start")

    def stop_service(self) -> bool:
        return self._sc("stop")

    def restart_service(self) -> bool:
        self.stop_service()
        return self.start_service()

    def is_running(self) -> bool:
        if not IS_WINDOWS:
            return False
        out = self._run(["sc", "query", self.service_name])
        return out is not None and "RUNNING" in out

    # -- stream control -------------------------------------------------------

    def kick_active_stream(self) -> None:
        """Terminate the active Moonlight stream (used when timer expires).

        Restarting the Duo service drops all connected clients; Duo keeps its
        pairing state on disk so clients stay paired and can reconnect after
        cooldown.
        """
        log.info("kicking active stream by restarting %s", self.service_name)
        self.restart_service()

    # -- helpers ------------------------------------------------------------

    def _sc(self, verb: str) -> bool:
        if not IS_WINDOWS:
            log.info("[dry-run] sc %s %s", verb, self.service_name)
            return True
        return self._run(["sc", verb, self.service_name]) is not None

    @staticmethod
    def _run(cmd: list[str]) -> str | None:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                log.error("%s failed: %s", " ".join(cmd), proc.stderr.strip())
                return None
            return proc.stdout
        except Exception as exc:  # noqa: BLE001
            log.error("%s failed: %s", " ".join(cmd), exc)
            return None
