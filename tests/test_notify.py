import os
import unittest

import qr65_notify


class NotifyTest(unittest.TestCase):
    def test_runs_the_toast_script_with_title_and_message_as_separate_args(self):
        calls = []
        qr65_notify.notify("QR65 lights", "press the button", runner=lambda args, **kw: calls.append(args))
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertIsInstance(args, list, "must not go through a shell")
        script = args[args.index("-File") + 1]
        self.assertTrue(os.path.isfile(script), script)
        self.assertEqual(args[args.index("-Title") + 1], "QR65 lights")
        self.assertEqual(args[args.index("-Message") + 1], "press the button")

    def test_never_raises_when_launching_fails(self):
        def broken(args, **kw):
            raise OSError("no powershell")
        qr65_notify.notify("t", "m", runner=broken)  # must not raise


if __name__ == "__main__":
    unittest.main()
