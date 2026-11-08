import unittest

from qr65_color import Calibration


class ApplyTest(unittest.TestCase):
    def test_default_calibration_leaves_colors_unchanged(self):
        cal = Calibration()
        for rgb in [(0, 0, 0), (255, 255, 255), (12, 200, 99), (1, 2, 3)]:
            self.assertEqual(cal.apply(*rgb), rgb)

    def test_gain_scales_each_channel(self):
        cal = Calibration(gain=(1.0, 0.5, 0.8))
        self.assertEqual(cal.apply(200, 200, 200), (200, 100, 160))

    def test_gamma_bends_midtones_per_channel(self):
        cal = Calibration(gamma=(2.0, 1.0, 1.0))
        # 255 * (128/255)^2 = 64.25 -> 64
        self.assertEqual(cal.apply(128, 128, 128), (64, 128, 128))

    def test_black_and_full_white_survive_gamma(self):
        cal = Calibration(gamma=(2.2, 0.6, 1.5))
        self.assertEqual(cal.apply(0, 0, 0), (0, 0, 0))
        self.assertEqual(cal.apply(255, 255, 255), (255, 255, 255))

    def test_out_of_range_input_is_clamped(self):
        self.assertEqual(Calibration().apply(300, -5, 255), (255, 0, 255))


class ValidationTest(unittest.TestCase):
    def test_gain_above_one_is_rejected(self):
        with self.assertRaises(ValueError):
            Calibration(gain=(1.2, 1.0, 1.0))

    def test_negative_gain_is_rejected(self):
        with self.assertRaises(ValueError):
            Calibration(gain=(-0.1, 1.0, 1.0))

    def test_gamma_outside_range_is_rejected(self):
        with self.assertRaises(ValueError):
            Calibration(gamma=(0.1, 1.0, 1.0))
        with self.assertRaises(ValueError):
            Calibration(gamma=(1.0, 6.0, 1.0))

    def test_wrong_channel_count_is_rejected(self):
        with self.assertRaises(ValueError):
            Calibration(gain=(1.0, 1.0))


class SerialisationTest(unittest.TestCase):
    def test_round_trip_through_dict(self):
        cal = Calibration(gain=(0.9, 0.8, 0.7), gamma=(1.1, 1.2, 1.3))
        self.assertEqual(Calibration.from_dict(cal.to_dict()), cal)

    def test_missing_or_empty_dict_gives_default(self):
        self.assertEqual(Calibration.from_dict(None), Calibration())
        self.assertEqual(Calibration.from_dict({}), Calibration())

    def test_partial_dict_keeps_defaults_for_missing_keys(self):
        cal = Calibration.from_dict({"gain": [1.0, 0.5, 0.5]})
        self.assertEqual(cal.gamma, (1.0, 1.0, 1.0))
        self.assertEqual(cal.gain, (1.0, 0.5, 0.5))

    def test_bad_dict_values_raise_value_error(self):
        with self.assertRaises(ValueError):
            Calibration.from_dict({"gain": ["x", 1, 1]})


if __name__ == "__main__":
    unittest.main()
