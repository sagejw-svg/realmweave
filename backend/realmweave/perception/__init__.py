"""Realmweave perception: agents only learn what they can sense."""
from .senses import (
    can_see, can_hear, can_perceive, sight_range,
    DAY_SIGHT, NIGHT_SIGHT, HEAR_RANGE,
)

__all__ = ["can_see", "can_hear", "can_perceive", "sight_range",
           "DAY_SIGHT", "NIGHT_SIGHT", "HEAR_RANGE"]
