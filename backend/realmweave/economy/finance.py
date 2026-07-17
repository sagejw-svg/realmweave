"""Recurring money flows and the forgiving floor.

A living economy needs coin to move on its own, not just at the moment of a sale.
Finance runs once per in-game day and does three things:

  * Rent  - each shop owner pays a daily rent into the village coffer (a sink).
  * Wages - each working agent earns a daily wage from the coffer (a source).
  * Relief- any agent below the poverty floor is topped back up to it, so no one
            is ever destitute enough to spiral into a needs-death they cannot buy
            their way out of. This is the "forgiving" half of a deep economy.

The coffer (treasury) is a real balance: rent and fines flow in, wages and relief
flow out. When it cannot cover what it owes, the world subsidizes it (an unbacked
top-up, logged as `subsidy`) so wages and relief never silently fail. Every move
goes through `economy.transfer`, so all of it lands in the ledger.

Tuning lives here as module constants, matching the codebase style (cf. justice).
"""
from __future__ import annotations

from .ledger import TREASURY, WORLD

STARTING_TREASURY = 500     # the village begins with a modest coffer
DAILY_WAGE = 5              # paid to each working agent per day
DAILY_RENT = 8             # paid by each shop owner per day
RELIEF_FLOOR = 10          # no agent is left below this many coin


class Finance:
    """Owns the village coffer and runs the daily economic cycle."""

    def __init__(self, sim, treasury: int = STARTING_TREASURY):
        self.sim = sim
        self.treasury = int(treasury)
        self.last_day = sim.clock.day_index

    # ---- per-tick entry point -----------------------------------------
    def step(self) -> None:
        """Called every tick; the real work happens once, on each day rollover."""
        day = self.sim.clock.day_index
        if day <= self.last_day:
            return
        self.last_day = day
        self._run_day(day)

    def _run_day(self, day: int) -> None:
        rent = self._collect_rent()
        wages = self._pay_wages()
        relief = self._pay_relief()
        self.sim.emit("economy_day", day=day, treasury=self.treasury,
                      rent=rent, wages=wages, relief=relief)

    # ---- the three flows ----------------------------------------------
    def _collect_rent(self) -> int:
        total = 0
        for owner_id in list(self.sim.economy.shops.keys()):
            owner = self.sim.agents.get(owner_id)
            if owner is None or not owner.alive:
                continue
            paid = self.sim.economy.transfer(owner, TREASURY, DAILY_RENT, "rent",
                                             note="shop rent")
            self.treasury += paid
            total += paid
        return total

    def _pay_wages(self) -> int:
        total = 0
        for a in self.sim.living():
            if not a.workplace:
                continue
            total += self._pay(a, DAILY_WAGE, "wage", note="day's labor")
        return total

    def _pay_relief(self) -> int:
        total = 0
        for a in self.sim.living():
            if a.coin < RELIEF_FLOOR:
                total += self._pay(a, RELIEF_FLOOR - a.coin, "relief", note="subsistence")
        return total

    # ---- paying out of the coffer (with the world as backstop) --------
    def _pay(self, agent, amount: int, kind: str, note: str = "") -> int:
        amount = int(amount)
        if amount <= 0:
            return 0
        if self.treasury < amount:
            short = amount - self.treasury
            self.sim.economy.ledger.record(
                self.sim.clock.minutes, self.sim.clock.day_index,
                "subsidy", WORLD, TREASURY, short, "coffer top-up")
            self.treasury += short
        moved = self.sim.economy.transfer(TREASURY, agent, amount, kind, note=note)
        self.treasury -= moved
        return moved

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"treasury": self.treasury, "last_day": self.last_day}

    def load(self, data: dict) -> None:
        self.treasury = int(data.get("treasury", self.treasury))
        self.last_day = int(data.get("last_day", self.last_day))
