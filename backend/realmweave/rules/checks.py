"""Dice and check resolution for Realmweave's custom d100 system.

Skills and difficulties live on a 1-100 scale, so a skill value reads directly
as a rough percent chance of success (Bargaining 72 = "usually wins a haggle").
Resolution is roll-under d100 with degrees of success:

    roll <= effective / 5          -> critical success
    roll <= effective              -> success
    roll <= effective + 20         -> partial (success at a cost)
    roll 96-100                    -> fumble (always fails)
    otherwise                      -> failure

Everything here is pure and deterministic given the random source, which makes
the whole simulation reproducible and unit-testable. The LLM never rolls dice;
code does, so outcomes stay fair.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

FUMBLE_MIN = 96          # a roll this high always fails
PARTIAL_BAND = 20        # margin above the skill that still half-succeeds


class Outcome(str, Enum):
    CRIT_SUCCESS = "crit_success"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    FUMBLE = "fumble"


@dataclass
class CheckResult:
    roll: int
    effective: int
    outcome: Outcome

    @property
    def success(self) -> bool:
        """Partial counts as a (costly) success."""
        return self.outcome in (Outcome.CRIT_SUCCESS, Outcome.SUCCESS, Outcome.PARTIAL)

    @property
    def full_success(self) -> bool:
        return self.outcome in (Outcome.CRIT_SUCCESS, Outcome.SUCCESS)

    @property
    def margin(self) -> int:
        """How far under (positive) or over (negative) the threshold the roll landed."""
        return self.effective - self.roll


def resolve(effective: int, roll: int) -> Outcome:
    """Pure mapping from an effective skill and a d100 roll to an Outcome."""
    if roll >= FUMBLE_MIN:
        return Outcome.FUMBLE
    crit_threshold = max(1, effective // 5)
    if roll <= crit_threshold:
        return Outcome.CRIT_SUCCESS
    if roll <= effective:
        return Outcome.SUCCESS
    if roll <= effective + PARTIAL_BAND:
        return Outcome.PARTIAL
    return Outcome.FAILURE


def roll_d100(rng, advantage: int = 0) -> int:
    """Roll a d100. advantage>0 rolls twice and keeps the better (lower) roll;
    advantage<0 keeps the worse (higher). advantage==0 rolls once."""
    r1 = rng.randint(1, 100)
    if advantage == 0:
        return r1
    r2 = rng.randint(1, 100)
    return min(r1, r2) if advantage > 0 else max(r1, r2)


def check(effective: int, rng, advantage: int = 0) -> CheckResult:
    """Roll against an effective skill value and return the full result."""
    effective = max(1, min(120, int(effective)))
    roll = roll_d100(rng, advantage)
    return CheckResult(roll=roll, effective=effective, outcome=resolve(effective, roll))


def opposed(effective_a: int, effective_b: int, rng,
            adv_a: int = 0, adv_b: int = 0):
    """Opposed check between two actors. Returns (winner, result_a, result_b)
    where winner is 'a', 'b', or 'tie'. Compares margins; a full success beats a
    partial of equal margin via a small tiebreak."""
    ra = check(effective_a, rng, adv_a)
    rb = check(effective_b, rng, adv_b)
    score_a = ra.margin + (2 if ra.full_success else 0) - (100 if ra.outcome == Outcome.FUMBLE else 0)
    score_b = rb.margin + (2 if rb.full_success else 0) - (100 if rb.outcome == Outcome.FUMBLE else 0)
    if score_a > score_b:
        return "a", ra, rb
    if score_b > score_a:
        return "b", ra, rb
    return "tie", ra, rb
