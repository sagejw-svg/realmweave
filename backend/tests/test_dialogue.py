"""Tests for the context-aware dialogue database (GPU-free stub voice).

Run from the backend/ directory:  py tests\test_dialogue.py
"""
import os
import sys
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realmweave.llm import dialogue


def prompt(place="The Gilded Stag", role="Blacksmith", mood="warmly",
           pod="morning", mem="none"):
    return (f"It is {pod} at {place}. You are working. "
            f"You see Toft Bellow ({role}) and feel {mood} toward them. "
            f"Recent memories: {mem}. Say one line to Toft Bellow.")


class TestDialogue(unittest.TestCase):
    def test_lines_are_filled_and_nonempty(self):
        for seed in range(120):
            out = dialogue.compose(prompt(), other="Toft Bellow", rng=random.Random(seed))
            self.assertTrue(out.strip())
            self.assertNotIn("{", out)           # no unfilled template slots
            self.assertNotIn("}", out)

    def test_gossip_names_the_dead(self):
        p = prompt(mood="coldly", mem="[Isla Fenn has died]")
        said = {dialogue.compose(p, other="Wren Pallet", rng=random.Random(s)) for s in range(40)}
        self.assertTrue(any("Isla Fenn" in s for s in said), "grief/gossip should name the dead")

    def test_role_flavoured_lines_appear(self):
        said = {dialogue.compose(prompt(role="Blacksmith"), other="Toft Bellow",
                                 rng=random.Random(s)) for s in range(120)}
        self.assertTrue(any("forge" in s or "blade" in s for s in said))

    def test_place_flavoured_lines_appear(self):
        # a role the TO_ROLE table doesn't cover, so place remarks show through
        said = {dialogue.compose(prompt(place="Old Well", role="Traveler"),
                                 other="Ada", rng=random.Random(s)) for s in range(120)}
        self.assertTrue(any("water" in s.lower() or "well" in s.lower() for s in said))

    def test_divine_stances(self):
        rng = random.Random(0)
        self.assertIn(dialogue.divine("the gods ask you to refuse", rng), dialogue.DIVINE["refuse"])
        self.assertIn(dialogue.divine("the gods, you bargain", rng), dialogue.DIVINE["bargain"])
        self.assertIn(dialogue.divine("the gods, half-accept", rng), dialogue.DIVINE["partial"])
        self.assertIn(dialogue.divine("the gods speak", rng), dialogue.DIVINE["accept"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
