"""Justice: witnessed crime, wanted status, bounties, pursuit, and redemption.

Crime only 'counts' when perceived. A perpetrator within a witness's senses is
still only noticed if the witness wins a Perception check against the perp's
Stealth, so a skilled thief can work unseen. A witnessed crime makes the perp
wanted, drops their standing, posts a bounty, and lets the witnesses (and the
guard they report to) recognize them by their true face. The guard and lawful
villagers then pursue the wanted; a capture ends it with restitution, and
standing recovers over time. The same rules apply to NPCs and to a human's
character.
"""
from __future__ import annotations
import math
from typing import List

from ..rules.checks import opposed
from ..perception import senses as perception
from .model import CrimeRecord, SEVERITY

CAPTURE_RANGE = 2.5
PURSUE_LOYALTY = 0.6      # how law-abiding an NPC must be to join a chase


class Justice:
    def __init__(self, sim):
        self.sim = sim
        self.crimes: List[CrimeRecord] = []

    # ---- committing a crime -------------------------------------------
    def commit_crime(self, perp_id: str, kind: str, victim_id: str = "") -> dict:
        perp = self.sim.agents.get(perp_id)
        if perp is None or not perp.alive:
            return {"detected": False, "error": "no perp"}
        severity = SEVERITY.get(kind, 1)
        victim = self.sim.agents.get(victim_id) if victim_id else None
        x, y = perp.x, perp.y

        # who actually notices? within senses AND wins Perception vs Stealth
        witnesses = []
        for a in self.sim.witnesses(x, y, loud=(severity >= 2), exclude=perp_id):
            if a.sheet is None or perp.sheet is None:
                witnesses.append(a); continue
            winner, _, _ = opposed(a.sheet.effective("Perception"),
                                   perp.sheet.effective("Stealth"), self.sim.rng)
            if winner != "b":       # the perp only slips by on a clear Stealth win
                witnesses.append(a)

        # the deed itself (theft moves coin)
        stolen = 0
        if kind == "theft" and victim is not None:
            stolen = min(victim.coin, 20 + severity * 10)
            victim.coin -= stolen
            perp.coin += stolen

        if not witnesses:
            self.sim._observe(perp, f"I committed {kind} unseen. No one is the wiser.", 5.0, "event")
            self.sim.emit("crime", perp=perp_id, perp_name=perp.name, crime=kind,
                          detected=False, stolen=stolen)
            return {"detected": False, "stolen": stolen, "witnesses": 0}

        # witnessed: record it and make the perp wanted
        rec = CrimeRecord(perp_id=perp_id, kind=kind, severity=severity,
                          victim_id=victim_id, witnesses=[w.id for w in witnesses],
                          location=perp.current_location, at=self.sim.clock.minutes)
        self.crimes.append(rec)
        perp.wanted += severity
        perp.bounty += severity * 40
        perp.notoriety = min(100.0, perp.notoriety + severity * 20)
        perp.reputation["village"] = perp.reputation.get("village", 0.0) - severity * 15

        for w in witnesses:
            w.known_facts.add(f"wanted:{perp_id}")
            perp.recognized_by.add(w.id)     # they saw the true face behind any alias
            self.sim._observe(w, f"I saw {perp.name} commit {kind}! They are wanted now.", 7.0, "event")
        # the witnesses report to the guard, who joins the hunt
        guard = self.sim.agents.get("guard")
        if guard is not None and guard.alive:
            guard.known_facts.add(f"wanted:{perp_id}")
            perp.recognized_by.add("guard")

        self.sim.emit("crime", perp=perp_id, perp_name=perp.name, crime=kind, detected=True,
                      severity=severity, bounty=perp.bounty, witnesses=len(witnesses), stolen=stolen)
        self.sim.emit("bounty", perp=perp_id, perp_name=perp.name, amount=perp.bounty)
        return {"detected": True, "stolen": stolen, "witnesses": len(witnesses),
                "wanted": perp.wanted, "bounty": perp.bounty}

    # ---- who is hunting whom ------------------------------------------
    def pursuers_of(self, perp) -> List:
        out = []
        for a in self.sim.living():
            if a.id == perp.id:
                continue
            if f"wanted:{perp.id}" not in a.known_facts:
                continue
            if a.id == "guard" or a.personality.get("loyalty", 0.5) >= PURSUE_LOYALTY:
                out.append(a)
        return out

    # ---- per-tick step -------------------------------------------------
    def step(self) -> None:
        wanted = [a for a in self.sim.living() if a.wanted > 0]
        for perp in wanted:
            for p in self.pursuers_of(perp):
                if perception.can_perceive(p, perp.x, perp.y, self.sim.clock.is_night):
                    p._pursuing = perp.id     # chase next decision
                if math.hypot(p.x - perp.x, p.y - perp.y) <= CAPTURE_RANGE:
                    self._resolve_capture(p, perp)
                    break
        self._recover()

    def _resolve_capture(self, captor, perp) -> None:
        c_skill = (captor.sheet.effective("Blades") if captor.sheet else 40) + (10 if captor.id == "guard" else 0)
        p_skill = perp.sheet.effective("Athletics") if perp.sheet else 40
        winner, _, _ = opposed(c_skill, p_skill, self.sim.rng)
        if winner == "b":
            self.sim.emit("escape", perp=perp.id, perp_name=perp.name, from_agent=captor.id)
            self.sim._observe(perp, f"I slipped away from {captor.name}.", 6.0, "event")
            return
        bounty = perp.bounty
        captor.coin += bounty
        restitution = min(perp.coin, bounty)
        perp.coin -= restitution
        for rec in self.crimes:
            if rec.perp_id == perp.id and not rec.resolved:
                rec.resolved = True
        perp.wanted = 0
        perp.bounty = 0
        setattr(perp, "_pursuing", "")
        setattr(captor, "_pursuing", "")
        self.sim.emit("arrest", perp=perp.id, perp_name=perp.name, by=captor.id,
                      by_name=captor.name, bounty=bounty, restitution=restitution)
        self.sim._observe(perp, f"{captor.name} caught me. I answered for my crimes ({restitution} coin).", 8.0, "reflection")
        self.sim._observe(captor, f"I brought {perp.name} to justice and claimed the {bounty} bounty.", 6.0, "event")

    def _recover(self) -> None:
        # redemption over time: notoriety fades and standing drifts back to neutral
        for a in self.sim.agents.values():
            if a.notoriety > 0:
                a.notoriety = max(0.0, a.notoriety - 0.05)
            v = a.reputation.get("village", 0.0)
            if v < 0:
                a.reputation["village"] = min(0.0, v + 0.05)

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"crimes": [c.to_dict() for c in self.crimes]}

    def load(self, data: dict) -> None:
        self.crimes = [CrimeRecord.from_dict(c) for c in data.get("crimes", [])]
