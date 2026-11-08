"""BLE connection manager for the QR65: find -> connect -> stay connected -> reconnect, forever.

The speaker keeps advertising (also in USB mode) once its Bluetooth radio is awake, so a simple
scan/connect loop recovers from PC restarts, sleep, bridge restarts and dropped links.
After a power-on straight into USB mode the radio is OFF and cannot be woken from the PC; that
state is detected by `AsleepTracker` and reported once via `on_asleep`.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

log = logging.getLogger("qr65.link")


class AsleepTracker:
    """Reports (once per episode) that the speaker has not been seen for `threshold` seconds."""

    def __init__(self, threshold: float, clock: Callable[[], float] = time.monotonic):
        self._threshold = threshold
        self._clock = clock
        self._last_seen = clock()
        self._fired = False

    def seen(self) -> None:
        self._last_seen = self._clock()
        self._fired = False

    def check(self) -> bool:
        """True exactly once when the threshold is first crossed in an episode."""
        if not self._fired and self.seconds_since_seen >= self._threshold:
            self._fired = True
            return True
        return False

    @property
    def asleep(self) -> bool:
        return self._fired

    @property
    def seconds_since_seen(self) -> float:
        return self._clock() - self._last_seen


async def _bleak_find(address: str, timeout: float):
    from bleak import BleakScanner
    return await BleakScanner.find_device_by_address(address, timeout=timeout)


def _bleak_client(device, on_disconnect):
    from bleak import BleakClient
    # Uncached service discovery: Windows sometimes hands out a stale list without the vendor service.
    return BleakClient(device, disconnected_callback=on_disconnect, timeout=20.0,
                       winrt={"use_cached_services": False})


class SpeakerLink:
    """`address=None` means "not configured yet": `discover()` is used until a speaker is found,
    then `on_address_found(address)` is called (e.g. to save it) and the address is used from then on."""

    def __init__(self, address: Optional[str], write_uuid: str, *,
                 on_connected: Optional[Callable[[], None]] = None,
                 on_asleep: Optional[Callable[[], None]] = None,
                 discover=None, on_address_found: Optional[Callable[[str], None]] = None,
                 asleep_after: float = 60.0, scan_timeout: float = 10.0, retry_delay: float = 2.0,
                 find_device=_bleak_find, client_factory=_bleak_client):
        self.address = address or None
        self._write_uuid = write_uuid
        self._on_connected = on_connected
        self._on_asleep = on_asleep
        self._discover = discover
        self._on_address_found = on_address_found
        self._scan_timeout = scan_timeout
        self._retry_delay = retry_delay
        self._find = find_device
        self._client_factory = client_factory
        self._tracker = AsleepTracker(asleep_after)
        self._client = None
        self._lost: Optional[asyncio.Event] = None
        self._last_scan_error: Optional[str] = None

    # -- state ---------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._client is not None and bool(getattr(self._client, "is_connected", True))

    @property
    def state(self) -> str:
        if self.connected:
            return "connected"
        return "asleep" if self._tracker.asleep else "searching"

    @property
    def seconds_since_seen(self) -> float:
        return 0.0 if self.connected else self._tracker.seconds_since_seen

    # -- writing ---------------------------------------------------------------
    async def write(self, packet: bytes) -> None:
        client = self._client
        if client is None or not getattr(client, "is_connected", True):
            raise ConnectionError("speaker not connected")
        try:
            await client.write_gatt_char(self._write_uuid, packet, response=False)
        except Exception as exc:
            log.warning("write failed (%s) - dropping link to reconnect", exc)
            if self._lost is not None:
                self._lost.set()
            raise ConnectionError(str(exc)) from exc

    # -- main loop -------------------------------------------------------------
    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while True:
                device = await self._scan()
                if device is None:
                    if self._tracker.check():
                        log.warning("speaker not seen for %.0fs - its Bluetooth is probably asleep "
                                    "(powered on in USB mode)", self._tracker.seconds_since_seen)
                        self._call(self._on_asleep)
                    await asyncio.sleep(self._retry_delay)
                    continue

                if self._tracker.asleep:
                    log.info("speaker is visible again")
                self._tracker.seen()
                lost = asyncio.Event()
                self._lost = lost
                client = self._client_factory(device, lambda _c: loop.call_soon_threadsafe(lost.set))
                try:
                    await client.connect()
                    if client.services.get_characteristic(self._write_uuid) is None:
                        raise RuntimeError("lighting characteristic not found")
                except Exception as exc:
                    log.warning("connect failed: %s", exc)
                    await self._disconnect_quietly(client)
                    await asyncio.sleep(self._retry_delay)
                    continue

                self._client = client
                log.info("connected to %s", self.address)
                self._call(self._on_connected)
                await lost.wait()

                self._client = None
                self._tracker.seen()
                log.info("disconnected - reconnecting")
                await self._disconnect_quietly(client)
                await asyncio.sleep(self._retry_delay)
        finally:
            client, self._client = self._client, None
            if client is not None:
                await self._disconnect_quietly(client)

    async def _scan(self):
        if self.address is None:
            return await self._discover_once()
        try:
            device = await self._find(self.address, self._scan_timeout)
        except Exception as exc:  # e.g. Bluetooth adapter switched off
            msg = str(exc)
            if msg != self._last_scan_error:
                log.warning("scan failed: %s", msg)
                self._last_scan_error = msg
            await asyncio.sleep(self._retry_delay)
            return None
        self._last_scan_error = None
        return device

    async def _discover_once(self):
        if self._discover is None:
            raise RuntimeError("no speaker address configured and no discover() given")
        try:
            found = await self._discover()
        except Exception as exc:
            log.warning("speaker search failed: %s", exc)
            await asyncio.sleep(self._retry_delay)
            return None
        if not found:
            return None
        device, name = found[0]
        self.address = device.address
        log.info("using %s at %s", name, self.address)
        if self._on_address_found is not None:
            try:
                self._on_address_found(self.address)
            except Exception:
                log.exception("on_address_found failed")
        return device

    @staticmethod
    async def _disconnect_quietly(client) -> None:
        try:
            await asyncio.wait_for(client.disconnect(), 10)
        except Exception:
            pass

    @staticmethod
    def _call(fn) -> None:
        if fn is None:
            return
        try:
            fn()
        except Exception:
            log.exception("callback failed")
