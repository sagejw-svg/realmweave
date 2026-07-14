"""World clock and calendar for Realmweave.

Time is tracked in whole in-game minutes since world epoch. One simulation
tick advances the clock by `minutes_per_tick` (default 10). A day is 1440
minutes. This module is intentionally dependency-free.
"""
from __future__ import annotations
from dataclasses import dataclass

MINUTES_PER_DAY = 24 * 60
DAY_NAMES = ["Sunday", "Moonday", "Tarsday", "Wodensday", "Thunresday", "Freyasday", "Satursday"]
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
DAYS_PER_SEASON = 28  # 4 seasons * 28 = 112-day year


@dataclass
class WorldClock:
    minutes: int = 6 * 60  # start at 06:00 on day 0

    def advance(self, minutes: int) -> None:
        self.minutes += minutes

    @property
    def day_index(self) -> int:
        return self.minutes // MINUTES_PER_DAY

    @property
    def minute_of_day(self) -> int:
        return self.minutes % MINUTES_PER_DAY

    @property
    def hour(self) -> int:
        return self.minute_of_day // 60

    @property
    def minute(self) -> int:
        return self.minute_of_day % 60

    @property
    def day_name(self) -> str:
        return DAY_NAMES[self.day_index % len(DAY_NAMES)]

    @property
    def season(self) -> str:
        return SEASONS[(self.day_index // DAYS_PER_SEASON) % len(SEASONS)]

    @property
    def is_night(self) -> bool:
        return self.hour < 6 or self.hour >= 21

    @property
    def part_of_day(self) -> str:
        h = self.hour
        if h < 6:
            return "night"
        if h < 12:
            return "morning"
        if h < 17:
            return "afternoon"
        if h < 21:
            return "evening"
        return "night"

    def hhmm(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def stamp(self) -> str:
        return f"Day {self.day_index} ({self.day_name}), {self.hhmm()}, {self.part_of_day}"

    def to_dict(self) -> dict:
        return {
            "minutes": self.minutes,
            "day_index": self.day_index,
            "day_name": self.day_name,
            "season": self.season,
            "hhmm": self.hhmm(),
            "part_of_day": self.part_of_day,
            "is_night": self.is_night,
        }
