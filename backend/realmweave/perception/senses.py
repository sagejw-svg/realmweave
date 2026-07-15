"""Perception: agents only know what they could plausibly sense.

Sight is limited by distance and by light (night halves it); a keen Perception
skill extends it. Loud events (a scream, a death) also carry to anyone within
hearing range even if they cannot see. This is the foundation for the
"through their eyes" view and for fair crime detection: an act nobody perceives
is not known until it is witnessed by evidence or spread by word of mouth.

Deliberately simple for now: no wall occlusion yet, just range and light. The
interface (`witnesses`) stays the same when line-of-sight is added later.
"""
from __future__ import annotations
import math

DAY_SIGHT = 14.0     # world units an agent can see in daylight
NIGHT_SIGHT = 6.0    # ... and at night
HEAR_RANGE = 11.0    # loud events carry this far regardless of sight


def sight_range(observer, is_night: bool) -> float:
    base = NIGHT_SIGHT if is_night else DAY_SIGHT
    sheet = getattr(observer, "sheet", None)
    if sheet is not None:
        # a sharp eye (Perception) extends the range; a dull one shortens it
        base += (sheet.skill("Perception") - 50) / 8.0
    return max(3.0, base)


def distance(observer, x: float, y: float) -> float:
    return math.hypot(observer.x - x, observer.y - y)


def can_see(observer, x: float, y: float, is_night: bool) -> bool:
    return distance(observer, x, y) <= sight_range(observer, is_night)


def can_hear(observer, x: float, y: float) -> bool:
    return distance(observer, x, y) <= HEAR_RANGE


def can_perceive(observer, x: float, y: float, is_night: bool, loud: bool = False) -> bool:
    if can_see(observer, x, y, is_night):
        return True
    return loud and can_hear(observer, x, y)
