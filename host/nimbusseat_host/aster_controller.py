"""Integration with ASTER V7 multiseat (IBIK).

ASTER splits one Windows PC into independent workplaces ("seats"). Seat 1 is
the physical owner's place; seat 2 hosts the guest gaming session whose
display is the Duo virtual monitor, with its own audio endpoint and injected
input from Moonlight. astctl.exe is ASTER's official command-line tool.
"""
from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger("nimbusseat.aster")

IS_WINDOWS = sys.platform == "win32"


class AsterController:
    def __init__(self, astctl: str, guest_seat_id: int = 2, enabled: bool = True) -> None:
        self.astctl = astctl
        self.seat = guest_seat_id
        self.enabled = enabled

    def enable_guest_seat(self) -> bool:
        """Make sure ASTER is running so seat 2 is available for the guest."""
        return self._ctl(["enable"]) if self.enabled else True

    def notify_guest(self, message: str) -> bool:
        """Show a popup on the guest seat (used for timer warnings)."""
        if not self.enabled:
            return True
        return self._ctl(["msg", f"/seat:{self.seat}", message])

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        out = self._run([self.astctl, "status"])
        return (out or "unknown").strip()

    def _ctl(self, args: list[str]) -> bool:
        return self._run([self.astctl, *args]) is not None

    @staticmethod
    def _run(cmd: list[str]) -> str | None:
        if not IS_WINDOWS:
            log.info("[dry-run] %s", " ".join(cmd))
            return "dry-run"
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                log.error("%s failed: %s", " ".join(cmd), proc.stderr.strip())
                return None
            return proc.stdout
        except Exception as exc:  # noqa: BLE001
            log.error("%s failed: %s", " ".join(cmd), exc)
            return None
