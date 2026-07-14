"""Shops, pricing, and trade: how an agent's ambition becomes a livelihood.

When an agent completes a "build a livelihood" goal, it founds a Shop: a real
location in the world, stocked from what the agent has made, with prices set by
the owner's greed. Other agents (and, later, players) can buy from it. Prices
flex with an opposed Bargaining check, tying trade back to the Phase 1 rules.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .goods import Item, make_item, SKILL_OUTPUT
from ..rules.checks import opposed


@dataclass
class Shop:
    owner_id: str
    location_id: str
    name: str
    margin: float                       # markup over item value (0.2 = +20%)
    x: float = 0.0
    y: float = 0.0
    is_open: bool = True
    stock: List[Item] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"owner_id": self.owner_id, "location_id": self.location_id, "name": self.name,
                "margin": self.margin, "x": self.x, "y": self.y, "is_open": self.is_open,
                "stock": [it.to_dict() for it in self.stock]}

    @classmethod
    def from_dict(cls, d: dict) -> "Shop":
        s = cls(owner_id=d["owner_id"], location_id=d["location_id"], name=d["name"],
                margin=float(d["margin"]), x=float(d.get("x", 0)), y=float(d.get("y", 0)),
                is_open=bool(d.get("is_open", True)))
        s.stock = [Item.from_dict(it) for it in d.get("stock", [])]
        return s


class Economy:
    """Owns all shops and mediates trade. Held by the Simulation (duck-typed)."""

    def __init__(self, sim):
        self.sim = sim
        self.shops: Dict[str, Shop] = {}     # keyed by owner id (one shop per owner for now)

    # ---- founding ------------------------------------------------------
    def found_shop(self, agent) -> Optional[Shop]:
        if agent.id in self.shops:
            return self.shops[agent.id]
        from ..world import Location
        # place shops just off the village square so they get real foot traffic
        idx = len(self.shops)
        lx, ly = 26.0 + idx * 3.0, 27.0
        loc_id = f"shop_{agent.id}"
        first = agent.name.split()[0]
        name = f"{first}'s Shop"
        self.sim.world.locations[loc_id] = Location(loc_id, name, lx, ly, "shop")
        margin = 0.2 + agent.personality.get("greed", 0.5) * 0.4
        shop = Shop(owner_id=agent.id, location_id=loc_id, name=name, margin=margin, x=lx, y=ly)
        # stock the shop from whatever the owner has made so far
        shop.stock.extend(agent.inventory)
        agent.inventory.clear()
        # if they had nothing on hand, they open with a small starter stock made
        # from their best craft (represents the goods they prepared to open)
        if not shop.stock and agent.sheet is not None:
            best_skill = max(SKILL_OUTPUT, key=lambda sk: agent.sheet.skill(sk))
            base_q = agent.sheet.skill(best_skill)
            for _ in range(3):
                q = max(1, min(100, base_q + self.sim.rng.randint(-8, 8)))
                shop.stock.append(make_item(best_skill, q))
        self.shops[agent.id] = shop
        self.sim.emit("shop_founded", agent=agent.id, agent_name=agent.name,
                      shop=name, location=loc_id, stock=len(shop.stock))
        self.sim._observe(agent, f"I opened {name}. My own trade at last.", 8.0, "event")
        return shop

    # ---- pricing -------------------------------------------------------
    def price_of(self, shop: Shop, item: Item, buyer=None) -> int:
        base = int(item.value() * (1.0 + shop.margin))
        owner = self.sim.agents.get(shop.owner_id)
        if buyer is not None and owner is not None and buyer.sheet and owner.sheet:
            winner, _, _ = opposed(buyer.sheet.effective("Bargaining"),
                                   owner.sheet.effective("Bargaining"), self.sim.rng)
            if winner == "a":
                base = int(base * 0.85)      # buyer haggled a discount
            elif winner == "b":
                base = int(base * 1.05)      # owner held firm / upsold
        return max(1, base)

    def nearest_open_shop_location(self, agent) -> Optional[str]:
        best, best_d = None, 1e9
        for oid, shop in self.shops.items():
            if oid == agent.id or not shop.is_open or not shop.stock:
                continue
            d = abs(shop.x - agent.x) + abs(shop.y - agent.y)
            if d < best_d:
                best_d, best = d, shop.location_id
        return best

    def shop_at(self, location_id: str) -> Optional[Shop]:
        for shop in self.shops.values():
            if shop.location_id == location_id:
                return shop
        return None

    # ---- trade ---------------------------------------------------------
    def buy(self, buyer, shop: Shop, item: Item) -> Optional[int]:
        if item not in shop.stock:
            return None
        price = self.price_of(shop, item, buyer)
        if buyer.coin < price:
            return None
        shop.stock.remove(item)
        buyer.coin -= price
        owner = self.sim.agents.get(shop.owner_id)
        if owner is not None:
            owner.coin += price
        buyer.inventory.append(item)
        self.sim.emit("trade", shop=shop.name, seller=shop.owner_id,
                      seller_name=(owner.name if owner else "?"), buyer=buyer.id,
                      buyer_name=buyer.name, item=item.name, quality=item.quality, price=price)
        self.sim._observe(buyer, f"Bought {item.name} (q{item.quality}) at {shop.name} for {price} coin.", 3.0, "event")
        if owner is not None:
            self.sim._observe(owner, f"Sold {item.name} to {buyer.name} for {price} coin.", 3.0, "event")
        return price

    def maybe_trade(self) -> None:
        """Each tick, resolve opportunistic purchases at shops with foot traffic."""
        for shop in list(self.shops.values()):
            if not shop.is_open or not shop.stock:
                continue
            buyers = [a for a in self.sim.living()
                      if a.current_location == shop.location_id and a.id != shop.owner_id and a.coin > 0]
            if not buyers:
                continue
            buyer = self.sim.rng.choice(buyers)
            affordable = [it for it in shop.stock if self.price_of(shop, it) <= buyer.coin]
            if not affordable:
                continue
            item = max(affordable, key=lambda it: it.quality)   # buy the best they can afford
            self.buy(buyer, shop, item)

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"shops": [s.to_dict() for s in self.shops.values()]}

    def load(self, data: dict) -> None:
        from ..world import Location
        self.shops = {}
        for sd in data.get("shops", []):
            shop = Shop.from_dict(sd)
            self.shops[shop.owner_id] = shop
            self.sim.world.locations[shop.location_id] = Location(
                shop.location_id, shop.name, shop.x, shop.y, "shop")
