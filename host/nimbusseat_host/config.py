from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAMES = ("config.json", "config.example.json")


@dataclass
class SessionConfig:
    max_duration_minutes: int = 360          # 6 hours
    warn_at_minutes_left: list[int] = field(default_factory=lambda: [30, 10, 5])
    grace_period_seconds: int = 60
    cooldown_minutes: int = 15


@dataclass
class NetworkConfig:
    lan_subnets: list[str] = field(
        default_factory=lambda: ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
    )
    api_port: int = 48120
    discovery_port: int = 48121
    discovery_interval_seconds: int = 3

    @property
    def networks(self) -> list[ipaddress.IPv4Network]:
        return [ipaddress.ip_network(s) for s in self.lan_subnets]


@dataclass
class DuoConfig:
    install_dir: str = r"C:/Program Files/Duo"
    executable: str = r"C:/Program Files/Duo/duo.exe"
    service_name: str = "DuoService"
    web_ui: str = "https://localhost:47990"
    stream_ports: list[int] = field(
        default_factory=lambda: [47984, 47989, 47990, 47998, 47999, 48000, 48002, 48010]
    )


@dataclass
class AsterConfig:
    enabled: bool = True
    astctl: str = r"C:/Program Files/ASTER/astctl.exe"
    guest_seat_id: int = 2


@dataclass
class AppConfig:
    session: SessionConfig = field(default_factory=SessionConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    duo: DuoConfig = field(default_factory=DuoConfig)
    aster: AsterConfig = field(default_factory=AsterConfig)
    audio: dict[str, Any] = field(default_factory=lambda: {"guest_device_hint": ""})
    host_name: str = "NimbusSeat Host"

    @classmethod
    def load(cls, path: str | None = None) -> "AppConfig":
        base = Path(__file__).resolve().parent.parent
        candidates = [Path(path)] if path else [base / n for n in DEFAULT_CONFIG_NAMES]
        for candidate in candidates:
            if candidate.is_file():
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                return cls(
                    session=SessionConfig(**raw.get("session", {})),
                    network=NetworkConfig(**raw.get("network", {})),
                    duo=DuoConfig(**raw.get("duo", {})),
                    aster=AsterConfig(**raw.get("aster", {})),
                    audio=raw.get("audio", {}),
                    host_name=raw.get("host_name", "NimbusSeat Host"),
                )
        return cls()
