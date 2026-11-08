import asyncio
import unittest

from qr65_color import Calibration
from qr65_protocol import build_set_color
from qr65_sender import ColorSender


class FakeSpeaker:
    """Collects packets; can be told to fail the next N writes."""

    def __init__(self):
        self.packets = []
        self.fail_next = 0
        self.attempts = 0
        self._changed = asyncio.Event()

    async def write(self, packet: bytes):
        self.attempts += 1
        if self.fail_next:
            self.fail_next -= 1
            self._changed.set()
            raise ConnectionError("not connected")
        self.packets.append(packet)
        self._changed.set()

    async def wait_for(self, n_attempts: int, timeout: float = 2.0):
        async def _wait():
            while self.attempts < n_attempts:
                self._changed.clear()
                await self._changed.wait()
        await asyncio.wait_for(_wait(), timeout)


class ColorSenderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.speaker = FakeSpeaker()
        self.sender = ColorSender(self.speaker.write, min_interval=0.0)
        self.task = asyncio.create_task(self.sender.run())

    async def asyncTearDown(self):
        self.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.task

    async def test_sends_the_target_color(self):
        self.sender.set_target(10, 20, 30, 100)
        await self.speaker.wait_for(1)
        self.assertEqual(self.speaker.packets, [build_set_color(10, 20, 30, 100)])
        self.assertEqual(self.sender.sent, (10, 20, 30, 100))

    async def test_identical_color_is_not_sent_twice(self):
        self.sender.set_target(10, 20, 30, 100)
        await self.speaker.wait_for(1)
        self.sender.set_target(10, 20, 30, 100)
        await asyncio.sleep(0.05)
        self.assertEqual(len(self.speaker.packets), 1)

    async def test_only_latest_color_is_sent_while_rate_limited(self):
        sender = ColorSender(self.speaker.write, min_interval=0.2)
        task = asyncio.create_task(sender.run())
        try:
            sender.set_target(1, 1, 1, 100)
            await self.speaker.wait_for(1)
            for v in (2, 3, 4):          # arrive inside the 0.2 s window
                sender.set_target(v, v, v, 100)
            await self.speaker.wait_for(2)
            await asyncio.sleep(0.3)     # nothing else should follow
            self.assertEqual(self.speaker.packets,
                             [build_set_color(1, 1, 1, 100), build_set_color(4, 4, 4, 100)])
        finally:
            task.cancel()

    async def test_calibration_is_applied_and_change_resends(self):
        self.sender.set_target(200, 200, 200, 100)
        await self.speaker.wait_for(1)
        self.sender.set_calibration(Calibration(gain=(1.0, 0.5, 1.0)))
        await self.speaker.wait_for(2)
        self.assertEqual(self.speaker.packets[-1], build_set_color(200, 100, 200, 100))
        self.assertEqual(self.sender.target, (200, 200, 200, 100))

    async def test_failed_write_is_retried_after_force_resend(self):
        self.speaker.fail_next = 1
        self.sender.set_target(5, 6, 7, 100)
        await self.speaker.wait_for(1)
        await asyncio.sleep(0.05)
        self.assertEqual(self.speaker.attempts, 1, "must not hammer a disconnected speaker")
        self.assertIsNone(self.sender.sent)
        self.sender.force_resend()      # e.g. called when the link reconnects
        await self.speaker.wait_for(2)
        self.assertEqual(self.speaker.packets, [build_set_color(5, 6, 7, 100)])

    async def test_force_resend_repeats_last_color_after_reconnect(self):
        self.sender.set_target(5, 6, 7, 100)
        await self.speaker.wait_for(1)
        self.sender.force_resend()
        await self.speaker.wait_for(2)
        self.assertEqual(len(self.speaker.packets), 2)

    async def test_nothing_is_sent_before_any_target(self):
        self.sender.force_resend()
        await asyncio.sleep(0.05)
        self.assertEqual(self.speaker.attempts, 0)


if __name__ == "__main__":
    unittest.main()
