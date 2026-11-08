"""
QR65 BLE Bridge for SignalRGB
=============================
Local HTTP server (127.0.0.1:5297) that forwards SignalRGB colors to the Edifier QR65 over BLE.

- Keeps looking for the speaker and reconnects by itself (PC restart/sleep, dropped link, ...).
- Works in USB and Bluetooth audio mode. After the speaker powers on straight into USB mode its
  Bluetooth is off; the bridge then shows a Windows notification asking for USB -> BT -> USB.
- Only the newest color is sent (rate limited), with optional per-channel color calibration.

Usage:
  python qr65_bridge.py                  # start (default port 5297)
  python qr65_bridge.py --port 5297 --brightness 100

Endpoints:
  GET  /color?r=255&g=0&b=0&brightness=100   set color (returns immediately)
  GET  /status                               connection state, colors, calibration
  GET  /ping                                 health check
  GET  /calibration   POST /calibration      read / change calibration (JSON)
  GET  /calibrate                            calibration page
"""

import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import sys

from aiohttp import web

from qr65_color import Calibration
from qr65_discover import find_speakers
from qr65_link import SpeakerLink
from qr65_notify import notify
from qr65_sender import ColorSender

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "qr65_config.json")
LOG_FILE = os.path.join(HERE, "qr65_bridge.log")
PAGE_FILE = os.path.join(HERE, "qr65_calibrate.html")

DEFAULT_CONFIG = {
    "device_address": "",   # empty = find the speaker automatically and save its address here
    "service_uuid": "48095d01-1a48-11e9-ab14-d663bd873d93",
    "write_uuid": "48090002-1a48-11e9-ab14-d663bd873d93",
    "notify_uuid": "48090001-1a48-11e9-ab14-d663bd873d93",
}

ASLEEP_TITLE = "QR65 lights: Bluetooth is asleep"
ASLEEP_MESSAGE = ("Press the speaker's input button twice (USB -> Bluetooth -> USB). "
                  "The RGB sync reconnects by itself a few seconds later.")
SETUP_TITLE = "QR65 lights: speaker not found yet"
SETUP_MESSAGE = ("Switch the QR65 to Bluetooth mode (press the input button). "
                 "The bridge finds it by itself and remembers it.")

log = logging.getLogger("qr65.bridge")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class ConfigStore:
    def __init__(self, path: str):
        self.path = path

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            log.warning("could not read %s (%s); using defaults", self.path, exc)
            return {}

    def load(self) -> dict:
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(self._read())
        return cfg

    def save_calibration(self, calibration: Calibration) -> None:
        self._update(calibration=calibration.to_dict())

    def save_address(self, address: str) -> None:
        self._update(device_address=address)

    def _update(self, **values) -> None:
        cfg = self._read() or dict(DEFAULT_CONFIG)
        cfg.update(values)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _color_dict(color):
    if color is None:
        return None
    r, g, b, brightness = color
    return {"r": r, "g": g, "b": b, "brightness": brightness}


def create_app(link, sender: ColorSender, store: ConfigStore,
               default_brightness: int = 100, page_file: str = PAGE_FILE) -> web.Application:

    async def handle_color(request: web.Request):
        q = request.query
        try:
            r, g, b = int(q.get("r", "0")), int(q.get("g", "0")), int(q.get("b", "0"))
            brightness = int(q["brightness"]) if "brightness" in q else default_brightness
        except ValueError:
            return web.json_response({"ok": False, "error": "r, g, b, brightness must be integers"}, status=400)
        sender.set_target(r, g, b, brightness)
        return web.json_response({"ok": True, "connected": link.connected})

    async def handle_status(request: web.Request):
        return web.json_response({
            "connected": link.connected,
            "state": link.state,
            "address": link.address,
            "last_color": _color_dict(sender.target),
            "sent_color": _color_dict(sender.sent),
            "calibration": sender.calibration.to_dict(),
            "seconds_since_seen": round(link.seconds_since_seen, 1),
        })

    async def handle_ping(request: web.Request):
        return web.json_response({"ok": True})

    async def handle_get_calibration(request: web.Request):
        return web.json_response(sender.calibration.to_dict())

    async def handle_post_calibration(request: web.Request):
        # JSON-only: browsers cannot send this cross-site without a CORS preflight, which we never allow.
        if request.content_type != "application/json":
            return web.json_response({"error": "Content-Type must be application/json"}, status=415)
        try:
            calibration = Calibration.from_dict(await request.json())
        except (ValueError, AttributeError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        try:
            store.save_calibration(calibration)
        except OSError as exc:
            log.error("could not save calibration: %s", exc)
            return web.json_response({"error": f"could not save: {exc}"}, status=500)
        sender.set_calibration(calibration)
        log.info("calibration updated: %s", calibration.to_dict())
        return web.json_response(calibration.to_dict())

    async def handle_calibrate_page(request: web.Request):
        return web.FileResponse(page_file, headers={"Cache-Control": "no-store"})

    @web.middleware
    async def local_only(request: web.Request, handler):
        # The server only listens on 127.0.0.1; also refuse requests addressed to any other host name,
        # so a web page using DNS rebinding cannot drive the bridge through the browser.
        host = (request.host or "").rsplit(":", 1)[0].strip("[]").lower()
        if host not in ("127.0.0.1", "localhost"):
            return web.json_response({"error": "forbidden"}, status=403)
        return await handler(request)

    app = web.Application(middlewares=[local_only])
    app.router.add_get("/color", handle_color)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/calibration", handle_get_calibration)
    app.router.add_post("/calibration", handle_post_calibration)
    app.router.add_get("/calibrate", handle_calibrate_page)
    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2,
                                                        encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    if sys.stderr is not None and sys.stderr.isatty():  # interactive run only; the service log is the file
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
    logging.getLogger("bleak").setLevel(logging.WARNING)

    def excepthook(exc_type, exc, tb):
        log.critical("unhandled exception", exc_info=(exc_type, exc, tb))
    sys.excepthook = excepthook


async def run(port: int, brightness: int) -> None:
    store = ConfigStore(CONFIG_FILE)
    cfg = store.load()
    try:
        calibration = Calibration.from_dict(cfg.get("calibration"))
    except ValueError as exc:
        log.warning("ignoring invalid calibration in config (%s)", exc)
        calibration = Calibration()

    def on_asleep():
        if link.address is None:
            notify(SETUP_TITLE, SETUP_MESSAGE)
        else:
            notify(ASLEEP_TITLE, ASLEEP_MESSAGE)

    def on_address_found(address: str):
        log.info("saving speaker address %s to %s", address, store.path)
        store.save_address(address)

    if not cfg["device_address"]:
        log.info("no speaker configured yet - searching for an Edifier QR65")
    link = SpeakerLink(cfg["device_address"], cfg["write_uuid"],
                       on_connected=lambda: sender.force_resend(), on_asleep=on_asleep,
                       discover=find_speakers, on_address_found=on_address_found)
    sender = ColorSender(link.write, calibration)

    runner = web.AppRunner(create_app(link, sender, store, brightness), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", port).start()
    except OSError as exc:
        log.error("cannot listen on 127.0.0.1:%d (%s) - is another bridge already running?", port, exc)
        await runner.cleanup()
        raise SystemExit(1)
    log.info("bridge started on http://127.0.0.1:%d (speaker %s)", port, link.address)

    tasks = [asyncio.create_task(link.run(), name="link"), asyncio.create_task(sender.run(), name="sender")]
    try:
        await asyncio.gather(*tasks)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.cleanup()
        log.info("bridge stopped")


async def find_and_save() -> int:
    """`--find`: search once, save the best match to the config. Exit code 0 = found."""
    print("Searching for Edifier QR65 speakers (about 15-30 seconds)...")
    found = await find_speakers()
    if not found:
        print("No QR65 found. Switch the speaker to Bluetooth mode and try again.")
        return 1
    for device, name in found:
        print(f"  found Edifier speaker {device.address}  (it calls itself '{name}')")
    device, name = found[0]
    ConfigStore(CONFIG_FILE).save_address(device.address)
    print(f"Using {device.address} - saved to {CONFIG_FILE}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="QR65 BLE Bridge for SignalRGB")
    parser.add_argument("--port", type=int, default=5297, help="HTTP port (default: 5297)")
    parser.add_argument("--brightness", type=int, default=100, help="Default brightness 0-100 (default: 100)")
    parser.add_argument("--find", action="store_true", help="search for the speaker, save it, and exit")
    args = parser.parse_args()
    setup_logging()
    if args.find:
        raise SystemExit(asyncio.run(find_and_save()))
    try:
        asyncio.run(run(args.port, args.brightness))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
