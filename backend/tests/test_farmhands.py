"""Tests for the farmhand cast (a shepherd and a farmhand who work the land).

Run from the backend/ directory:  py tests\test_farmhands.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.world import World
from realmweave.agents import default_agents


class TestFarmhands(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.cast = {a.id: a for a in default_agents()}

    def test_shepherd_and_farmhand_exist(self):
        self.assertIn("shep", self.cast)
        self.assertIn("hollis", self.cast)
        self.assertEqual(self.cast["shep"].role, "Shepherd")
        self.assertEqual(self.cast["hollis"].role, "Farmhand")

    def test_homes_and_workplaces_are_real_locations(self):
        for aid in ("shep", "hollis"):
            a = self.cast[aid]
            self.assertIn(a.home, self.w.locations, f"{aid} home missing")
            self.assertIn(a.workplace, self.w.locations, f"{aid} workplace missing")

    def test_schedules_only_reference_real_locations(self):
        for aid in ("shep", "hollis"):
            for block in self.cast[aid].schedule:
                self.assertIn(block.location, self.w.locations,
                              f"{aid} scheduled at unknown {block.location}")

    def test_farmhands_work_the_farmland(self):
        # the shepherd tends the pasture; the farmhand works farm/field ground
        shep_spots = {b.location for b in self.cast["shep"].schedule if b.activity == "work"}
        self.assertIn("south_pasture", shep_spots)
        hollis_spots = {b.location for b in self.cast["hollis"].schedule if b.activity == "work"}
        kinds = {self.w.loc(s).kind for s in hollis_spots}
        self.assertTrue(kinds & {"farm", "field"}, "farmhand should work farm/field ground")


if __name__ == "__main__":
    unittest.main(verbosity=2)
