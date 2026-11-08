"""Latest-color-wins sender: SignalRGB can post colors as fast as it likes; the speaker only ever
receives the newest one, at most once per `min_interval`, and never the same color twice in a row.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from qr65_color import Calibration
from qr65_protocol import build_set_color

log = logging.getLogger("qr65.sender")

Color = tuple  # (r, g, b, brightness)


def _clamp(v, lo, hi) -> int:
    return max(lo, min(hi, int(v)))


class ColorSender:
    def __init__(self, write: Callable[[bytes], Awaitable[None]],
                 calibration: Optional[Calibration] = None, min_interval: float = 0.05):
        self._write = write
        self._calibration = calibration or Calibration()
        self._min_interval = min_interval
        self._target: Optional[Color] = None
        self._sent: Optional[Color] = None
        self._force = False
        self._wake = asyncio.Event()
        self._last_write = float("-inf")

    # -- state ---------------------------------------------------------------
    @property
    def target(self) -> Optional[Color]:
        """Last color requested (before calibration)."""
        return self._target

    @property
    def sent(self) -> Optional[Color]:
        """Last color the speaker actually accepted (after calibration)."""
        return self._sent

    @property
    def calibration(self) -> Calibration:
        return self._calibration

    def output(self) -> Optional[Color]:
        if self._target is None:
            return None
        r, g, b, brightness = self._target
        return (*self._calibration.apply(r, g, b), brightness)

    # -- inputs (synchronous, safe to call from HTTP handlers) ----------------
    def set_target(self, r: int, g: int, b: int, brightness: int) -> None:
        self._target = (_clamp(r, 0, 255), _clamp(g, 0, 255), _clamp(b, 0, 255), _clamp(brightness, 0, 100))
        self._wake.set()

    def set_calibration(self, calibration: Calibration) -> None:
        self._calibration = calibration
        self.force_resend()

    def force_resend(self) -> None:
        """Send the current color again even if unchanged (after reconnect / calibration change)."""
        self._force = True
        self._wake.set()

    # -- loop -----------------------------------------------------------------
    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await self._wake.wait()
            self._wake.clear()
            if self._target is None:
                self._force = False
                continue

            wait = self._last_write + self._min_interval - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)   # newer targets arriving meanwhile simply replace the old one
                self._wake.clear()          # ...and are covered by the send below

            out = self.output()
            if out == self._sent and not self._force:
                continue
            self._force = False
            try:
                await self._write(build_set_color(*out))
            except Exception as exc:        # not connected / write failed: wait for force_resend()
                log.debug("write failed (%s); waiting for reconnect", exc)
                continue
            finally:
                self._last_write = loop.time()
            self._sent = out
