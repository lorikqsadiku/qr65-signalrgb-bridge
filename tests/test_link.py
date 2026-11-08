import asyncio
import unittest
from types import SimpleNamespace

from qr65_link import AsleepTracker, SpeakerLink

WRITE_UUID = "48090002-1a48-11e9-ab14-d663bd873d93"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class AsleepTrackerTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.tracker = AsleepTracker(threshold=60, clock=self.clock)

    def test_not_asleep_before_threshold(self):
        self.clock.now = 59
        self.assertFalse(self.tracker.check())
        self.assertFalse(self.tracker.asleep)

    def test_fires_exactly_once_per_episode(self):
        self.clock.now = 60
        self.assertTrue(self.tracker.check())
        self.assertTrue(self.tracker.asleep)
        self.clock.now = 500
        self.assertFalse(self.tracker.check())
        self.assertTrue(self.tracker.asleep)

    def test_seen_starts_a_new_episode(self):
        self.clock.now = 60
        self.tracker.check()
        self.tracker.seen()
        self.assertFalse(self.tracker.asleep)
        self.clock.now = 119
        self.assertFalse(self.tracker.check())
        self.clock.now = 121
        self.assertTrue(self.tracker.check())

    def test_seconds_since_seen(self):
        self.clock.now = 42.5
        self.assertAlmostEqual(self.tracker.seconds_since_seen, 42.5)


# ---------------------------------------------------------------------------
class FakeServices:
    def __init__(self, has_char=True):
        self.has_char = has_char

    def get_characteristic(self, uuid):
        return object() if self.has_char and uuid == WRITE_UUID else None


class FakeClient:
    def __init__(self, device, on_disconnect, *, fail_connect=False, fail_write=False, has_char=True):
        self.device = device
        self._on_disconnect = on_disconnect
        self.fail_connect = fail_connect
        self.fail_write = fail_write
        self.services = FakeServices(has_char)
        self.is_connected = False
        self.writes = []

    async def connect(self):
        if self.fail_connect:
            raise OSError("connect failed")
        self.is_connected = True

    async def disconnect(self):
        if self.is_connected:
            self.is_connected = False
            self._on_disconnect(self)

    async def write_gatt_char(self, uuid, data, response):
        if self.fail_write:
            raise OSError("write failed")
        self.writes.append((uuid, bytes(data), response))

    def drop(self):  # simulate the speaker going away
        self.is_connected = False
        self._on_disconnect(self)


class Harness:
    """Scripted scanner + client factory for SpeakerLink."""

    def __init__(self, found=True, client_kwargs=None):
        self.found = found
        self.client_kwargs = client_kwargs or {}
        self.clients = []
        self.finds = 0

    async def find_device(self, address, timeout):
        self.finds += 1
        await asyncio.sleep(0)
        return "device" if self.found else None

    def client_factory(self, device, on_disconnect):
        client = FakeClient(device, on_disconnect, **self.client_kwargs)
        self.clients.append(client)
        return client


async def until(predicate, timeout=2.0):
    async def _poll():
        while not predicate():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(_poll(), timeout)


class SpeakerLinkTest(unittest.IsolatedAsyncioTestCase):
    def make_link(self, harness, **kw):
        self.connected_calls = 0
        self.asleep_calls = 0

        def on_connected():
            self.connected_calls += 1

        def on_asleep():
            self.asleep_calls += 1

        link = SpeakerLink("AA:BB:CC:DD:EE:FF", WRITE_UUID,
                           on_connected=on_connected, on_asleep=on_asleep,
                           find_device=harness.find_device, client_factory=harness.client_factory,
                           retry_delay=0.01, **kw)
        self.task = asyncio.create_task(link.run())
        return link

    async def asyncTearDown(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass

    async def test_connects_when_found_and_writes_reach_the_speaker(self):
        h = Harness()
        link = self.make_link(h)
        await until(lambda: link.connected)
        self.assertEqual(link.state, "connected")
        self.assertEqual(self.connected_calls, 1)
        await link.write(b"\x01\x02")
        self.assertEqual(h.clients[0].writes, [(WRITE_UUID, b"\x01\x02", False)])

    async def test_reconnects_after_the_speaker_drops(self):
        h = Harness()
        link = self.make_link(h)
        await until(lambda: link.connected)
        h.clients[0].drop()
        await until(lambda: len(h.clients) == 2 and link.connected)
        self.assertEqual(self.connected_calls, 2)

    async def test_write_while_disconnected_raises(self):
        h = Harness(found=False)
        link = self.make_link(h)
        with self.assertRaises(ConnectionError):
            await link.write(b"\x00")

    async def test_failed_write_drops_link_so_it_reconnects(self):
        h = Harness(client_kwargs={"fail_write": True})
        link = self.make_link(h)
        await until(lambda: link.connected)
        with self.assertRaises(ConnectionError):
            await link.write(b"\x00")
        await until(lambda: len(h.clients) >= 2)

    async def test_connect_failure_is_retried(self):
        h = Harness(client_kwargs={"fail_connect": True})
        link = self.make_link(h)
        await until(lambda: len(h.clients) >= 3)
        self.assertFalse(link.connected)
        self.assertEqual(link.state, "searching")

    async def test_missing_write_characteristic_is_treated_as_failed_connect(self):
        h = Harness(client_kwargs={"has_char": False})
        link = self.make_link(h)
        await until(lambda: len(h.clients) >= 2)
        self.assertFalse(link.connected)
        self.assertEqual(self.connected_calls, 0)

    async def test_asleep_reported_once_when_speaker_never_found(self):
        h = Harness(found=False)
        link = self.make_link(h, asleep_after=0.05)
        await until(lambda: self.asleep_calls == 1)
        await asyncio.sleep(0.1)
        self.assertEqual(self.asleep_calls, 1)
        self.assertEqual(link.state, "asleep")

    async def test_unknown_address_is_discovered_then_used(self):
        h = Harness()
        found_addresses = []

        async def discover():
            return [(SimpleNamespace(address="AA:BB:CC:DD:EE:FF"), "EDIFIER QR65")]

        link = SpeakerLink(None, WRITE_UUID, discover=discover, on_address_found=found_addresses.append,
                           find_device=h.find_device, client_factory=h.client_factory, retry_delay=0.01)
        self.task = asyncio.create_task(link.run())
        await until(lambda: link.connected)
        self.assertEqual(link.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(found_addresses, ["AA:BB:CC:DD:EE:FF"])

    async def test_discovery_that_finds_nothing_reports_asleep(self):
        h = Harness()
        asleep = []

        async def discover():
            return []

        link = SpeakerLink(None, WRITE_UUID, discover=discover, on_asleep=lambda: asleep.append(1),
                           find_device=h.find_device, client_factory=h.client_factory,
                           retry_delay=0.01, asleep_after=0.05)
        self.task = asyncio.create_task(link.run())
        await until(lambda: asleep == [1])
        self.assertFalse(link.connected)
        self.assertIsNone(link.address)

    async def test_asleep_episode_ends_when_speaker_reappears(self):
        h = Harness(found=False)
        link = self.make_link(h, asleep_after=0.05)
        await until(lambda: link.state == "asleep")
        h.found = True
        await until(lambda: link.connected)
        self.assertEqual(link.state, "connected")


if __name__ == "__main__":
    unittest.main()
