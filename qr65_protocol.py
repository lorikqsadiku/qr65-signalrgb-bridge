"""Edifier QR65 BLE packet format (reverse-engineered from Edifier ConneX 1.0.26).

Packet: [0xAA] [0xEC] [cmd] [len_hi] [len_lo] [payload...] [checksum]
checksum = sum of all preceding bytes & 0xFF
"""

HEADER = 0xAA
APP_CODE = 0xEC

CMD_SET_AMBIENT_LIGHT = 0x6B
SLOT_STATIC = 7          # light-effect slot for a fixed color
SPEED_DEFAULT = 0xFF     # speed byte the static slot was proven to work with


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def build_packet(cmd: int, payload: bytes) -> bytes:
    plen = len(payload)
    packet = bytearray([HEADER, APP_CODE, cmd & 0xFF, (plen >> 8) & 0xFF, plen & 0xFF])
    packet.extend(payload)
    packet.append(sum(packet) & 0xFF)
    return bytes(packet)


def build_set_color(r: int, g: int, b: int, brightness: int = 100) -> bytes:
    """Static color command: payload [0x00, slot 7, R, G, B, brightness 0-100, speed]."""
    payload = bytes([
        0x00, SLOT_STATIC,
        _clamp(r, 0, 255), _clamp(g, 0, 255), _clamp(b, 0, 255),
        _clamp(brightness, 0, 100),
        SPEED_DEFAULT,
    ])
    return build_packet(CMD_SET_AMBIENT_LIGHT, payload)
