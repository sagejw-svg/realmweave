"""Live time-control (speed ladder) behavior."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realmweave.server import step_speed

STEPS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]


class TestSpeedLadder(unittest.TestCase):
    def test_step_up_and_down(self):
        self.assertEqual(step_speed(STEPS, 1.0, 1), 2.0)
        self.assertEqual(step_speed(STEPS, 1.0, -1), 0.5)

    def test_clamped_at_ends(self):
        self.assertEqual(step_speed(STEPS, 4.0, 1), 4.0)     # cannot exceed max
        self.assertEqual(step_speed(STEPS, 0.0, -1), 0.0)    # cannot go below pause

    def test_snaps_offladder_value(self):
        # an arbitrary scale (e.g. from an absolute 'scale' set) snaps to nearest
        self.assertEqual(step_speed(STEPS, 1.7, 1), 4.0)     # nearest is 2.0 -> up
        self.assertEqual(step_speed(STEPS, 0.3, -1), 0.0)    # nearest is 0.25 -> down

    def test_zero_delta_snaps_only(self):
        self.assertEqual(step_speed(STEPS, 0.9, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
