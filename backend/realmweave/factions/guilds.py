"""Guilds and factions: organizations an agent can belong to and rise within.

Slice C layers real organizations on top of the per-faction reputation from
Phase 7. A guild has a domain, a hall (a place in the village), a roster of
members, a coffer fed by dues, and ranks that rise with tenure. Membership is
not just a label: it carries benefits. A merchant-guild member buys scarce
materials from the outside supplier more cheaply (trade connections); a
fighters-guild member is deputized and joins the guard in running down the
wanted. Guards are the lawful faction, seeded with the town's gate guard.

Ranks are derived from how long an agent has belonged (a clean, single source of
truth that needs no separate bookkeeping): every `PROMOTE_INTERVAL` days of
membership lifts a member one rank, up to `MAX_RANK`. Dues run once per day and
are forgiving - a member pays only what they can, so no one is expelled for a
bad week. Every dues payment flows through the ledger like all other coin.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Guild:
    id: str
    name: str
    domain: str
    hall: str            # an existing location id where the guild gathers
    dues: int            # coin owed per day by each member


GUILDS: Dict[str, Guild] = {
    "fighters":  Guild("fighters",  "the Iron Watch",   "combat",  "gate",   3),
    "thieves":   Guild("thieves",   "the Shadow Hand",  "stealth", "tavern", 2),
    "mages":     Guild("mages",     "the Hollow Circle", "arcana", "well",   4),
    "merchants": Guild("merchants", "the Coin League",  "trade",   "square", 3),
}

RANK_TITLES = {
    "combat":  ["Recruit", "Soldier", "Veteran", "Champion"],
    "stealth": ["Footpad", "Prowler", "Shadow", "Master Thief"],
    "arcana":  ["Novice", "Adept", "Magus", "Archmage"],
    "trade":   ["Peddler", "Trader", "Merchant", "Magnate"],
}

MAX_RANK = 4
PROMOTE_INTERVAL = 3        # days of membership per rank gained
MERCHANT_DISCOUNT = 0.85    # merchants pay 85% of the supplier's premium


def rank_at(join_day: int, day: int) -> int:
    """Rank (1..MAX_RANK) for a member who joined on `join_day`, as of `day`."""
    return min(MAX_RANK, 1 + max(0, day - join_day) // PROMOTE_INTERVAL)


def best_guild_for(agent) -> str:
    """The guild that best fits an agent's nature (a pure, deterministic pick)."""
    p = agent.personality or {}
    role = (agent.role or "").lower()
    guard_bonus = 0.6 if ("guard" in role or agent.id == "guard") else 0.0
    scores = {
        "fighters":  p.get("ambition", 0.5) * 0.5 + (1.0 - p.get("caution", 0.5)) * 0.5 + guard_bonus,
        "merchants": p.get("greed", 0.5) * 0.7 + p.get("industry", 0.5) * 0.3,
        "mages":     p.get("curiosity", 0.5) * 0.8,
        "thieves":   p.get("greed", 0.5) * 0.4 + (1.0 - p.get("loyalty", 0.5)) * 0.6,
    }
    return max(scores, key=lambda k: scores[k])


def guild_join_description(guild_id: str) -> str:
    g = GUILDS.get(guild_id)
    return f"earn a place in {g.name}" if g else "seek a guild to belong to"


class Guilds:
    """Owns all guild rosters and coffers and runs the daily guild cycle."""

    def __init__(self, sim):
        self.sim = sim
        self.rosters: Dict[str, Dict[str, int]] = {gid: {} for gid in GUILDS}  # gid -> {member: join_day}
        self.coffers: Dict[str, int] = {gid: 0 for gid in GUILDS}
        self.last_day = sim.clock.day_index

    # ---- seeding -------------------------------------------------------
    def seed(self) -> None:
        """The gate guard is a charter member of the fighters' guild, so the
        lawful faction exists from the world's first tick."""
        guard = self.sim.agents.get("guard")
        if guard is not None and not self.guild_of("guard"):
            self.join(guard, "fighters", announce=False)

    # ---- membership ----------------------------------------------------
    def guild_of(self, agent_id: str) -> str:
        for gid, roster in self.rosters.items():
            if agent_id in roster:
                return gid
        return ""

    def is_member(self, agent, guild_id: Optional[str] = None) -> bool:
        gid = self.guild_of(agent.id if hasattr(agent, "id") else agent)
        if not gid:
            return False
        return gid == guild_id if guild_id else True

    def join(self, agent, guild_id: str, announce: bool = True) -> bool:
        if guild_id not in GUILDS:
            return False
        current = self.guild_of(agent.id)
        if current == guild_id:
            return False
        if current:
            self.leave(agent)
        self.rosters[guild_id][agent.id] = self.sim.clock.day_index
        # membership registers as renown with that faction
        agent.reputation[guild_id] = agent.reputation.get(guild_id, 0.0) + 10.0
        if announce:
            g = GUILDS[guild_id]
            self.sim.emit("guild_join", agent=agent.id, agent_name=agent.name,
                          guild=guild_id, guild_name=g.name, rank=1,
                          title=self.title_of(agent.id))
            self.sim._observe(agent, f"I was admitted to {g.name} as a {self.title_of(agent.id)}.",
                              7.0, "reflection")
        return True

    def leave(self, agent) -> None:
        gid = self.guild_of(agent.id)
        if gid:
            self.rosters[gid].pop(agent.id, None)

    def rank_of(self, agent_id: str) -> int:
        gid = self.guild_of(agent_id)
        if not gid:
            return 0
        return rank_at(self.rosters[gid][agent_id], self.sim.clock.day_index)

    def title_of(self, agent_id: str) -> str:
        gid = self.guild_of(agent_id)
        if not gid:
            return ""
        rank = self.rank_of(agent_id)
        return RANK_TITLES[GUILDS[gid].domain][rank - 1]

    def members(self, guild_id: str):
        return list(self.rosters.get(guild_id, {}).keys())

    # ---- benefits ------------------------------------------------------
    def supplier_price(self, agent, price: int) -> int:
        """The premium a given agent pays the outside supplier: merchant-guild
        members get a discount from their trade connections."""
        if self.is_member(agent, "merchants"):
            return max(1, int(price * MERCHANT_DISCOUNT))
        return price

    def assists_justice(self, agent) -> bool:
        """Fighters' guild members are deputized to help run down the wanted."""
        return self.is_member(agent, "fighters")

    # ---- daily cycle ---------------------------------------------------
    def step(self) -> None:
        day = self.sim.clock.day_index
        if day <= self.last_day:
            return
        prev_day = self.last_day
        self.last_day = day
        for gid, guild in GUILDS.items():
            for member_id, join_day in list(self.rosters[gid].items()):
                member = self.sim.agents.get(member_id)
                if member is None or not member.alive:
                    continue
                # dues (forgiving: only what they can pay) flow to the coffer
                paid = self.sim.economy.transfer(member, f"guild:{gid}", guild.dues,
                                                 "dues", note=guild.name)
                self.coffers[gid] += paid
                # announce a promotion when tenure crosses a rank boundary
                new_rank = rank_at(join_day, day)
                if new_rank > rank_at(join_day, prev_day):
                    self.sim.emit("guild_rank", agent=member_id,
                                  agent_name=member.name, guild=gid,
                                  rank=new_rank, title=RANK_TITLES[guild.domain][new_rank - 1])

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"rosters": {gid: dict(r) for gid, r in self.rosters.items()},
                "coffers": dict(self.coffers), "last_day": self.last_day}

    def load(self, data: dict) -> None:
        rosters = data.get("rosters")
        if rosters:
            self.rosters = {gid: {m: int(d) for m, d in rosters.get(gid, {}).items()}
                            for gid in GUILDS}
        coffers = data.get("coffers", {})
        self.coffers = {gid: int(coffers.get(gid, 0)) for gid in GUILDS}
        self.last_day = int(data.get("last_day", self.last_day))
