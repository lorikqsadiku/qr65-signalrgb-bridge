import json
import os
import tempfile
import unittest

from aiohttp.test_utils import TestClient, TestServer

from qr65_bridge import ConfigStore, create_app
from qr65_color import Calibration
from qr65_sender import ColorSender


class FakeLink:
    def __init__(self, state="searching"):
        self.state = state
        self.address = "AA:BB:CC:DD:EE:FF"
        self.seconds_since_seen = 12.0

    @property
    def connected(self):
        return self.state == "connected"

    async def write(self, packet):
        raise ConnectionError("not connected")


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp.name, "qr65_config.json")
        with open(self.config_path, "w") as f:
            json.dump({"device_address": "AA:BB:CC:DD:EE:FF", "write_uuid": "w"}, f)
        self.store = ConfigStore(self.config_path)
        self.link = FakeLink()
        self.sender = ColorSender(self.link.write)
        app = create_app(self.link, self.sender, self.store, default_brightness=80)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.tmp.cleanup()

    async def test_ping(self):
        resp = await self.client.get("/ping")
        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.json(), {"ok": True})

    async def test_color_is_accepted_even_while_speaker_is_disconnected(self):
        resp = await self.client.get("/color?r=1&g=2&b=3&brightness=50")
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["connected"])
        self.assertEqual(self.sender.target, (1, 2, 3, 50))

    async def test_color_without_brightness_uses_default(self):
        await self.client.get("/color?r=9&g=9&b=9")
        self.assertEqual(self.sender.target, (9, 9, 9, 80))

    async def test_color_values_are_clamped(self):
        await self.client.get("/color?r=999&g=-4&b=10&brightness=300")
        self.assertEqual(self.sender.target, (255, 0, 10, 100))

    async def test_color_rejects_non_numbers(self):
        resp = await self.client.get("/color?r=red&g=0&b=0")
        self.assertEqual(resp.status, 400)
        self.assertIsNone(self.sender.target)

    async def test_status_reports_state_colors_and_calibration(self):
        self.link.state = "asleep"
        await self.client.get("/color?r=1&g=2&b=3&brightness=50")
        body = await (await self.client.get("/status")).json()
        self.assertFalse(body["connected"])
        self.assertEqual(body["state"], "asleep")
        self.assertEqual(body["address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(body["last_color"], {"r": 1, "g": 2, "b": 3, "brightness": 50})
        self.assertIsNone(body["sent_color"])
        self.assertEqual(body["calibration"], Calibration().to_dict())
        self.assertEqual(body["seconds_since_seen"], 12.0)

    async def test_status_before_any_color(self):
        body = await (await self.client.get("/status")).json()
        self.assertIsNone(body["last_color"])

    async def test_post_calibration_updates_sender_and_persists(self):
        new = {"gain": [1.0, 0.5, 0.9], "gamma": [1.0, 1.2, 1.0]}
        resp = await self.client.post("/calibration", json=new)
        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.json(), new)
        self.assertEqual(self.sender.calibration, Calibration.from_dict(new))
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertEqual(saved["calibration"], new)
        self.assertEqual(saved["device_address"], "AA:BB:CC:DD:EE:FF", "other settings kept")

    async def test_get_calibration(self):
        body = await (await self.client.get("/calibration")).json()
        self.assertEqual(body, Calibration().to_dict())

    async def test_invalid_calibration_is_rejected_and_nothing_changes(self):
        resp = await self.client.post("/calibration", json={"gain": [2, 1, 1]})
        self.assertEqual(resp.status, 400)
        self.assertEqual(self.sender.calibration, Calibration())
        with open(self.config_path) as f:
            self.assertNotIn("calibration", json.load(f))

    async def test_calibration_post_must_be_json(self):
        resp = await self.client.post("/calibration", data="gain=1",
                                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(resp.status, 415)

    async def test_requests_for_other_host_names_are_refused(self):
        # DNS-rebinding defence: a web page on evil.example must not be able to drive the bridge.
        for path in ("/status", "/color?r=1&g=1&b=1", "/calibrate"):
            resp = await self.client.get(path, headers={"Host": "evil.example:5297"})
            self.assertEqual(resp.status, 403, path)
        self.assertIsNone(self.sender.target)

    async def test_localhost_host_name_is_allowed(self):
        resp = await self.client.get("/ping", headers={"Host": "localhost:5297"})
        self.assertEqual(resp.status, 200)

    async def test_calibrate_page_is_served(self):
        resp = await self.client.get("/calibrate")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertIn("QR65", await resp.text())


class ConfigStoreTest(unittest.TestCase):
    def test_missing_file_gives_defaults_with_no_speaker_address(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = ConfigStore(os.path.join(d, "nope.json")).load()
            self.assertEqual(cfg["device_address"], "", "empty = find the speaker automatically")
            self.assertIn("write_uuid", cfg)

    def test_save_address_keeps_other_settings(self):
        with tempfile.TemporaryDirectory() as d:
            store = ConfigStore(os.path.join(d, "c.json"))
            store.save_calibration(Calibration(gain=(1.0, 0.5, 0.5)))
            store.save_address("AA:BB:CC:DD:EE:FF")
            cfg = store.load()
            self.assertEqual(cfg["device_address"], "AA:BB:CC:DD:EE:FF")
            self.assertEqual(cfg["calibration"]["gain"], [1.0, 0.5, 0.5])

    def test_saved_calibration_is_loaded_back(self):
        with tempfile.TemporaryDirectory() as d:
            store = ConfigStore(os.path.join(d, "c.json"))
            cal = Calibration(gain=(0.9, 0.9, 0.8))
            store.save_calibration(cal)
            self.assertEqual(Calibration.from_dict(store.load()["calibration"]), cal)


if __name__ == "__main__":
    unittest.main()
