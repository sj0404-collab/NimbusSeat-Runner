"""Entry point: python -m nimbusseat_host run"""
from __future__ import annotations

import argparse
import logging
import sys

from .api import create_app
from .config import AppConfig
from .discovery import DiscoveryBeacon
from .manager import HostManager


def main() -> int:
    parser = argparse.ArgumentParser(prog="nimbusseat_host")
    sub = parser.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="start the host-manager")
    run.add_argument("--config", default=None, help="path to config.json")
    run.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.cmd != "run":
        parser.print_help()
        return 1

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config = AppConfig.load(args.config)
    manager = HostManager(config)
    manager.startup()

    beacon = DiscoveryBeacon(
        host_name=config.host_name,
        api_port=config.network.api_port,
        discovery_port=config.network.discovery_port,
        interval=config.network.discovery_interval_seconds,
        status_provider=manager.status,
    )
    beacon.start()

    app = create_app(manager, config)
    from waitress import serve

    logging.getLogger("nimbusseat").info(
        "REST API on 0.0.0.0:%d (LAN-only enforced)", config.network.api_port
    )
    serve(app, host="0.0.0.0", port=config.network.api_port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
