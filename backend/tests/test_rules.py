"""Unit tests for the Realmweave rules system (Phase 1).

Run from the backend/ directory:  py tests\test_rules.py
Covers the pure dice math, advantage, use-based progression, and the core
acceptance claim: higher skill yields better outcomes on average.
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realmweave.rules.checks import resolve, roll_d100, check, opposed, Outcome
from realmweave.rules.skills import CharacterSheet, role_sheet


class TestResolve(unittest.TestCase):
    def test_thresholds(self):
        # effective 50: crit<=10, success<=50, partial<=70, fail 71-95, fumble 96+
        self.assertEqual(resolve(50, 1), Outcome.CRIT_SUCCESS)
        self.assertEqual(resolve(50, 10), Outcome.CRIT_SUCCESS)
        self.assertEqual(resolve(50, 11), Outcome.SUCCESS)
        self.assertEqual(resolve(50, 50), Outcome.SUCCESS)
        self.assertEqual(resolve(50, 51), Outcome.PARTIAL)
        self.assertEqual(resolve(50, 70), Outcome.PARTIAL)
        self.assertEqual(resolve(50, 71), Outcome.FAILURE)
        self.assertEqual(resolve(50, 95), Outcome.FAILURE)
        self.assertEqual(resolve(50, 96), Outcome.FUMBLE)
        self.assertEqual(resolve(50, 100), Outcome.FUMBLE)

    def test_fumble_beats_everything(self):
        # even a master fumbles on a 96-100
        self.assertEqual(resolve(100, 97), Outcome.FUMBLE)

    def test_low_skill_still_can_crit(self):
        self.assertEqual(resolve(4, 1), Outcome.CRIT_SUCCESS)  # crit threshold floors at 1


class TestAdvantage(unittest.TestCase):
    def test_advantage_averages_lower(self):
        rng = random.Random(1)
        n = 4000
        plain = sum(roll_d100(rng, 0) for _ in range(n)) / n
        adv = sum(roll_d100(rng, +1) for _ in range(n)) / n
        dis = sum(roll_d100(rng, -1) for _ in range(n)) / n
        # roll-under: advantage should lower the average roll, disadvantage raise it
        self.assertLess(adv, plain)
        self.assertGreater(dis, plain)

    def test_determinism(self):
        a = [roll_d100(random.Random(42)) for _ in range(1)]
        b = [roll_d100(random.Random(42)) for _ in range(1)]
        self.assertEqual(a, b)


class TestSkillOutcomes(unittest.TestCase):
    def _success_rate(self, skill_value, trials=6000, seed=7):
        rng = random.Random(seed)
        sheet = CharacterSheet(skills={"Smithing": skill_value})
        wins = sum(1 for _ in range(trials) if sheet.check("Smithing", rng).success)
        return wins / trials

    def test_higher_skill_higher_success(self):
        low = self._success_rate(30)
        mid = self._success_rate(60)
        high = self._success_rate(90)
        self.assertLess(low, mid)
        self.assertLess(mid, high)

    def test_craft_quality_scales_with_skill(self):
        rng = random.Random(11)

        # fresh sheet per trial so use-based training doesn't drift the skill
        def avg_quality(skill_value, n=3000):
            total = 0
            for _ in range(n):
                total += CharacterSheet(skills={"Smithing": skill_value}).craft("Smithing", rng)[0]
            return total / n

        nq = avg_quality(30)
        mq = avg_quality(85)
        self.assertGreater(mq, nq + 30)  # masters make clearly better armor


class TestProgression(unittest.TestCase):
    def test_use_based_growth_with_diminishing_returns(self):
        rng = random.Random(3)
        sheet = CharacterSheet(skills={"Smithing": 20})
        for _ in range(2000):
            sheet.train("Smithing", rng)
        # a novice practicing hard should improve, but not trivially hit 100
        self.assertGreater(sheet.skill("Smithing"), 20)
        self.assertLessEqual(sheet.skill("Smithing"), 100)


class TestRoleSeeding(unittest.TestCase):
    def test_roles_have_expected_strengths(self):
        smith = role_sheet("Blacksmith")
        keeper = role_sheet("Tavernkeeper")
        self.assertGreater(smith.skill("Smithing"), keeper.skill("Smithing"))
        self.assertGreater(keeper.skill("Bargaining"), smith.skill("Bargaining"))
        self.assertEqual(smith.emergent_class(), "Artisan")

    def test_opposed_haggle_favors_the_better_bargainer(self):
        rng = random.Random(5)
        keeper = role_sheet("Tavernkeeper")   # high Bargaining
        child = role_sheet("Errand child")    # untrained bargainer
        keeper_wins = 0
        for _ in range(2000):
            winner, _, _ = opposed(keeper.effective("Bargaining"), child.effective("Bargaining"), rng)
            if winner == "a":
                keeper_wins += 1
        self.assertGreater(keeper_wins, 1200)  # clearly favored, not guaranteed


if __name__ == "__main__":
    unittest.main(verbosity=2)
