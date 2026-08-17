"""LAN-only access control: allow requests only from configured local subnets."""
from __future__ import annotations

import ipaddress
import logging

log = logging.getLogger("nimbusseat.lan")


class LanGuard:
    def __init__(self, subnets: list[str]) -> None:
        self.networks = [ipaddress.ip_network(s) for s in subnets]

    def is_allowed(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.is_loopback:
            return True
        allowed = any(addr in net for net in self.networks)
        if not allowed:
            log.warning("blocked non-LAN request from %s", ip)
        return allowed
