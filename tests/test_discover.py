import unittest
from types import SimpleNamespace

from qr65_discover import EDIFIER_COMPANY_ID, EDIFIER_SERVICE_UUID, find_speakers, looks_like_edifier


def adv(manufacturer=None, uuids=None, rssi=-60):
    return SimpleNamespace(manufacturer_data=manufacturer or {}, service_uuids=uuids or [], rssi=rssi)


def dev(address):
    return SimpleNamespace(address=address)


class LooksLikeEdifierTest(unittest.TestCase):
    def test_edifier_manufacturer_id_matches(self):
        self.assertTrue(looks_like_edifier(adv(manufacturer={EDIFIER_COMPANY_ID: b"\x00"})))

    def test_edifier_service_uuid_matches_case_insensitively(self):
        self.assertTrue(looks_like_edifier(adv(uuids=[EDIFIER_SERVICE_UUID.upper()])))

    def test_other_devices_do_not_match(self):
        self.assertFalse(looks_like_edifier(adv(manufacturer={0x004C: b"\x12"}, uuids=["0000fe2c-0000-1000-8000-00805f9b34fb"])))
        self.assertFalse(looks_like_edifier(adv()))


class FindSpeakersTest(unittest.IsolatedAsyncioTestCase):
    async def test_only_verified_edifier_devices_are_returned_qr65_first(self):
        results = [
            (dev("11:11:11:11:11:11"), adv(manufacturer={0x004C: b""})),                    # Apple, ignored
            (dev("22:22:22:22:22:22"), adv(manufacturer={EDIFIER_COMPANY_ID: b""}, rssi=-40)),  # Edifier headphones
            (dev("33:33:33:33:33:33"), adv(uuids=[EDIFIER_SERVICE_UUID], rssi=-80)),           # the QR65
            (dev("44:44:44:44:44:44"), adv(manufacturer={EDIFIER_COMPANY_ID: b""})),          # no lighting char
        ]
        probed = []

        async def scan(timeout):
            return results

        async def probe(device):
            probed.append(device.address)
            return {"22:22:22:22:22:22": "EDIFIER W820NB",
                    "33:33:33:33:33:33": "EDIFIER QR65"}.get(device.address)

        found = await find_speakers(scan=scan, probe=probe)
        self.assertNotIn("11:11:11:11:11:11", probed, "non-Edifier devices are never connected to")
        self.assertEqual([(d.address, name) for d, name in found],
                         [("33:33:33:33:33:33", "EDIFIER QR65"), ("22:22:22:22:22:22", "EDIFIER W820NB")])

    async def test_probe_errors_are_skipped(self):
        async def scan(timeout):
            return [(dev("55:55:55:55:55:55"), adv(manufacturer={EDIFIER_COMPANY_ID: b""}))]

        async def probe(device):
            raise OSError("connect failed")

        self.assertEqual(await find_speakers(scan=scan, probe=probe), [])


if __name__ == "__main__":
    unittest.main()
