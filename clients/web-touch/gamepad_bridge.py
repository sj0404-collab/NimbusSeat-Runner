#!/usr/bin/env python3
"""NimbusSeat gamepad bridge.

Creates a VIRTUAL Xbox 360 controller on the host (Linux uinput) and feeds it
with state received over WebSocket from the browser page (nimbus.html).
The browser side sends either on-screen touch gamepad input or a real
Bluetooth gamepad read via the W3C Gamepad API - so games and even
GeForce NOW inside Chrome see a genuine controller.

Message format (JSON):
  {"b": [17 x 0/1  - standard gamepad buttons], "a": [lx, ly, rx, ry, lt, rt]}
Standard mapping: 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 6 LT, 7 RT,
                  8 Back, 9 Start, 10 LS, 11 RS, 12-15 dpad, 16 Guide.

Run as root (uinput):  sudo python3 gamepad_bridge.py --port 6081
"""
import argparse
import asyncio
import json
import logging

from evdev import AbsInfo, UInput, ecodes as e

log = logging.getLogger("gamepad-bridge")

BTN_MAP = {
    0: e.BTN_A, 1: e.BTN_B, 2: e.BTN_X, 3: e.BTN_Y,
    4: e.BTN_TL, 5: e.BTN_TR,
    8: e.BTN_SELECT, 9: e.BTN_START,
    10: e.BTN_THUMBL, 11: e.BTN_THUMBR,
    16: e.BTN_MODE,
}

CAPS = {
    e.EV_KEY: list(BTN_MAP.values()),
    e.EV_ABS: [
        (e.ABS_X,  AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_Y,  AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_Z,  AbsInfo(0, 0, 255, 0, 0, 0)),    # LT
        (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),    # RT
        (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),  # dpad
        (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
    ],
}


def clamp(v: float) -> float:
    return max(-1.0, min(1.0, float(v)))


class Bridge:
    def __init__(self) -> None:
        # Pretend to be a real wired Xbox 360 pad - maximum compatibility.
        self.ui = UInput(
            CAPS, name="Microsoft X-Box 360 pad",
            vendor=0x045E, product=0x028E, version=0x110, bustype=e.BUS_USB,
        )
        log.info("virtual Xbox 360 pad created: %s", self.ui.device)

    def apply(self, msg: dict) -> None:
        b = msg.get("b") or []
        a = msg.get("a") or []
        b += [0] * (17 - len(b))
        a += [0] * (6 - len(a))

        for idx, code in BTN_MAP.items():
            self.ui.write(e.EV_KEY, code, 1 if b[idx] else 0)

        # dpad -> hat
        self.ui.write(e.EV_ABS, e.ABS_HAT0Y, (-1 if b[12] else 0) + (1 if b[13] else 0))
        self.ui.write(e.EV_ABS, e.ABS_HAT0X, (-1 if b[14] else 0) + (1 if b[15] else 0))

        self.ui.write(e.EV_ABS, e.ABS_X,  int(clamp(a[0]) * 32767))
        self.ui.write(e.EV_ABS, e.ABS_Y,  int(clamp(a[1]) * 32767))
        self.ui.write(e.EV_ABS, e.ABS_RX, int(clamp(a[2]) * 32767))
        self.ui.write(e.EV_ABS, e.ABS_RY, int(clamp(a[3]) * 32767))
        self.ui.write(e.EV_ABS, e.ABS_Z,  int(max(0.0, min(1.0, float(a[4]))) * 255))
        self.ui.write(e.EV_ABS, e.ABS_RZ, int(max(0.0, min(1.0, float(a[5]))) * 255))
        self.ui.syn()


async def main() -> None:
    import websockets

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=6081)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bridge = Bridge()

    async def handler(ws):
        peer = getattr(ws, "remote_address", "?")
        log.info("client connected: %s", peer)
        try:
            async for raw in ws:
                try:
                    bridge.apply(json.loads(raw))
                except (ValueError, KeyError):
                    pass
        finally:
            bridge.apply({"b": [], "a": []})  # release everything
            log.info("client disconnected: %s", peer)

    async with websockets.serve(handler, "0.0.0.0", args.port):
        log.info("gamepad bridge listening on ws://0.0.0.0:%d", args.port)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
