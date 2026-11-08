"""Find Edifier QR65 speakers nearby.

1. Scan BLE advertisements and keep Edifier devices (manufacturer ID 0x07E0 or service 0x5D00).
2. Connect to each candidate and keep it only if it has Edifier's command characteristic.
   Its GAP device name is read too (the QR65 reports "EDIFIER BLE"); a name containing "QR65"
   would be preferred, otherwise the strongest signal wins.

The speaker only advertises while its Bluetooth radio is awake: switch it to Bluetooth mode
(or USB -> Bluetooth -> USB) before searching.
"""

import logging

log = logging.getLogger("qr65.discover")

EDIFIER_COMPANY_ID = 0x07E0
EDIFIER_SERVICE_UUID = "00005d00-0000-1000-8000-00805f9b34fb"
COMMAND_CHAR_UUID = "48090002-1a48-11e9-ab14-d663bd873d93"
DEVICE_NAME_CHAR_UUID = "00002a00-0000-1000-8000-00805f9b34fb"


def looks_like_edifier(adv) -> bool:
    if EDIFIER_COMPANY_ID in (adv.manufacturer_data or {}):
        return True
    return EDIFIER_SERVICE_UUID in [u.lower() for u in (adv.service_uuids or [])]


async def _bleak_scan(timeout: float):
    from bleak import BleakScanner
    return list((await BleakScanner.discover(timeout=timeout, return_adv=True)).values())


async def _bleak_probe(device):
    """Device name if the device has the Edifier command characteristic, else None."""
    from bleak import BleakClient
    async with BleakClient(device, timeout=20.0, winrt={"use_cached_services": False}) as client:
        if client.services.get_characteristic(COMMAND_CHAR_UUID) is None:
            return None
        try:
            return bytes(await client.read_gatt_char(DEVICE_NAME_CHAR_UUID)).decode("utf-8", "replace").strip("\x00 ")
        except Exception:
            return "Edifier device"


async def find_speakers(scan_timeout: float = 15.0, scan=_bleak_scan, probe=_bleak_probe) -> list:
    """List of (device, name) for verified Edifier devices, QR65s first, then by signal strength."""
    candidates = [(d, a) for d, a in await scan(scan_timeout) if looks_like_edifier(a)]
    candidates.sort(key=lambda da: -(da[1].rssi if da[1].rssi is not None else -999))
    found = []
    for device, _adv in candidates:
        try:
            name = await probe(device)
        except Exception as exc:
            log.info("could not check %s: %s", device.address, exc)
            continue
        if name:
            log.info("found %s at %s", name, device.address)
            found.append((device, name))
    found.sort(key=lambda dn: 0 if "QR65" in dn[1].upper() else 1)  # stable: keeps RSSI order within groups
    return found
