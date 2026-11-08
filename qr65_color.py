"""Color calibration so the speaker's LEDs can be matched to other RGB components.

For each channel c:  out = 255 * gain_c * (in / 255) ** gamma_c
  gain  0.0-1.0  : white balance (LEDs can only be dimmed, never pushed past 255)
  gamma 0.2-5.0  : midtone curve (>1 = deeper/darker midtones, <1 = brighter)
"""

from dataclasses import dataclass

GAIN_RANGE = (0.0, 1.0)
GAMMA_RANGE = (0.2, 5.0)


def _triple(values, name: str, lo: float, hi: float) -> tuple:
    try:
        vals = tuple(float(v) for v in values)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be three numbers")
    if len(vals) != 3:
        raise ValueError(f"{name} must have exactly 3 values (r, g, b)")
    for v in vals:
        if not lo <= v <= hi:
            raise ValueError(f"{name} values must be between {lo} and {hi}, got {v}")
    return vals


def _clamp255(v) -> int:
    return max(0, min(255, int(v)))


@dataclass(frozen=True)
class Calibration:
    gain: tuple = (1.0, 1.0, 1.0)
    gamma: tuple = (1.0, 1.0, 1.0)

    def __post_init__(self):
        object.__setattr__(self, "gain", _triple(self.gain, "gain", *GAIN_RANGE))
        object.__setattr__(self, "gamma", _triple(self.gamma, "gamma", *GAMMA_RANGE))

    def apply(self, r: int, g: int, b: int) -> tuple:
        out = []
        for value, gain, gamma in zip((r, g, b), self.gain, self.gamma):
            x = _clamp255(value) / 255.0
            out.append(_clamp255(round(255.0 * gain * (x ** gamma))))
        return tuple(out)

    def to_dict(self) -> dict:
        return {"gain": list(self.gain), "gamma": list(self.gamma)}

    @classmethod
    def from_dict(cls, data) -> "Calibration":
        if not data:
            return cls()
        default = cls()
        return cls(gain=data.get("gain", default.gain), gamma=data.get("gamma", default.gamma))
