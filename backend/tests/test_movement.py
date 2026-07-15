"""Tests for the movement-commitment optimization.

Run from the backend/ directory:  py tests\test_movement.py
An agent commits to its destination and only re-decides on arrival or a real
interrupt (survival need, pursuit), rather than re-evaluating every tick.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter
from realmweave.sim import Simulation, SimConfig


def fresh_sim():
    cfg = load_config(); cfg["force_stub"] = True
    return Simulation(LLMRouter(cfg), SimConfig(**cfg["sim"]))


class TestCommitment(unittest.TestCase):
    def test_keeps_destination_while_en_route(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        a.current_location = "home_toft"
        hx, hy = sim.world.pos("home_toft")
        a.x, a.y = hx, hy
        a.activity, a.target_location = "visit", "gate"   # committed to the gate
        # not arrived yet -> decision is unchanged over several ticks
        for _ in range(5):
            sim._decide(a)
            self.assertEqual(a.target_location, "gate")
            self.assertEqual(a.activity, "visit")

    def test_survival_need_interrupts_the_commitment(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        a.current_location = "home_toft"; a.target_location = "gate"; a.activity = "visit"
        a.energy.value = 0.05          # desperate for sleep
        sim._decide(a)
        self.assertEqual(a.activity, "sleep")
        self.assertEqual(a.target_location, a.home)

    def test_rechooses_on_arrival(self):
        sim = fresh_sim()
        a = sim.agents["toft"]
        # standing at the destination -> free to form a new intent
        a.current_location = "square"; a.target_location = "square"; a.activity = "idle"
        sim._decide(a)
        self.assertTrue(a.target_location)          # a concrete next destination
        self.assertNotEqual(a.activity, "idle")     # chose something to do

    def test_still_reaches_places_and_records_arrival_memory(self):
        # end-to-end: with commitment on, agents still travel and log arrivals
        sim = fresh_sim()
        for _ in range(120):
            sim.tick()
        toft = sim.agents["toft"]
        self.assertTrue(any("Arrived at" in e.text for e in toft.memory.entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
