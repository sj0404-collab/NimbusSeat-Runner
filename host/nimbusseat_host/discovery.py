"""UDP discovery beacon: lets NimbusSeat clients find the host on the LAN,
GeForce NOW / Steam Remote Play style (no manual IP entry)."""
from __future__ import annotations

import json
import logging
import socket
import threading

log = logging.getLogger("nimbusseat.discovery")

MAGIC = "NIMBUSSEAT/1"


class DiscoveryBeacon:
    """Answers "who is there?" probes and periodically broadcasts presence."""

    def __init__(
        self,
        host_name: str,
        api_port: int,
        discovery_port: int,
        interval: int,
        status_provider,
    ) -> None:
        self.host_name = host_name
        self.api_port = api_port
        self.port = discovery_port
        self.interval = interval
        self.status_provider = status_provider
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def _payload(self) -> bytes:
        status = self.status_provider()
        return json.dumps(
            {
                "magic": MAGIC,
                "name": self.host_name,
                "api_port": self.api_port,
                "state": status.get("state", "unknown"),
                "seconds_left": status.get("seconds_left", 0),
            }
        ).encode()

    def start(self) -> None:
        self._threads = [
            threading.Thread(target=self._broadcast_loop, daemon=True, name="disc-bcast"),
            threading.Thread(target=self._responder_loop, daemon=True, name="disc-resp"),
        ]
        for t in self._threads:
            t.start()
        log.info("discovery beacon on udp/%d", self.port)

    def stop(self) -> None:
        self._stop.set()

    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while not self._stop.wait(self.interval):
            try:
                sock.sendto(self._payload(), ("255.255.255.255", self.port))
            except OSError as exc:
                log.debug("broadcast failed: %s", exc)

    def _responder_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", self.port))
        except OSError as exc:
            log.error("cannot bind discovery port %d: %s", self.port, exc)
            return
        sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() == MAGIC.encode():
                try:
                    sock.sendto(self._payload(), addr)
                except OSError:
                    pass
