import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nodes.detector_service.rules import (ILLEGAL_OPEN, SAFE, SECURE, TAMPER_ALERT, BoxRules)
from shared.messages import Telemetry
from shared.processing import LidDetector, motion_rms
from shared.sensors import SensorSample


def tele(rms=0.0, lid_open=False, seq=1):
    return Telemetry.make("box1", "boot", seq, rms, lid_open)


class ProcessingTests(unittest.TestCase):
    def test_motion_rms(self):
        still = [SensorSample(0, (0, 0, 9.81))] * 5
        shaken = [SensorSample(0, (0, 0, 9.81 + d)) for d in (3, -3, 3, -3, 3)]
        self.assertLess(motion_rms(still), 0.01)
        self.assertGreater(motion_rms(shaken), 0.7)

    def test_lid_hysteresis(self):
        lid = LidDetector("light", open_lux=15, close_lux=5)
        self.assertIsNone(lid.update(1, None))
        self.assertEqual(lid.update(300, None), "OPENED")
        self.assertIsNone(lid.update(10, None))      # zona tengah: status ditahan
        self.assertTrue(lid.is_open)
        self.assertEqual(lid.update(2, None), "CLOSED")

    def test_lid_proximity_and_modes(self):
        p = LidDetector("proximity", near_cm=3)
        self.assertEqual(p.update(None, 5.0), "OPENED")
        self.assertEqual(p.update(None, 0.0), "CLOSED")
        both = LidDetector("both", open_lux=15, close_lux=5, near_cm=3)
        self.assertIsNone(both.update(300, 0.0))     # hanya satu yang sepakat
        self.assertEqual(both.update(300, 5.0), "OPENED")


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.r = BoxRules(0.7, confirm_motion=2, confirm_open=1, tamper_hold=10)

    def test_secure(self):
        self.assertEqual(self.r.evaluate(tele(0.05), now=0).status, SECURE)

    def test_tamper_needs_confirmation_and_expires(self):
        self.assertEqual(self.r.evaluate(tele(2.0), now=0).status, SECURE)
        self.assertEqual(self.r.evaluate(tele(2.0), now=1).status, TAMPER_ALERT)
        self.assertEqual(self.r.evaluate(tele(0.0), now=5).status, TAMPER_ALERT)
        self.assertEqual(self.r.evaluate(tele(0.0), now=12).status, SECURE)

    def test_illegal_open_latches(self):
        self.assertEqual(self.r.evaluate(tele(0, True), now=0).status, ILLEGAL_OPEN)
        self.assertEqual(self.r.evaluate(tele(0, False), now=1).status, ILLEGAL_OPEN)

    def test_disarm_and_rearm(self):
        self.r.evaluate(tele(0, True), now=0)
        self.r.disarm()
        self.assertEqual(self.r.evaluate(tele(0, True), now=1).status, SAFE)
        self.r.arm()
        self.assertEqual(self.r.evaluate(tele(0, False), now=2).status, SECURE)


if __name__ == "__main__":
    unittest.main()
