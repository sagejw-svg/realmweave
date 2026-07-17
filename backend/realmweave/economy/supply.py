"""The supply system: how an agent gets the raw materials a recipe needs.

When a refiner is short an input, it acquires it here. The rule is local-first,
supplier-fallback:

  1. If a neighbour is holding surplus of the material, buy it from them at base
     value (coin flows to the neighbour). This is the real supply chain: a cook
     buys grain from the farmer who grew it.
  2. Otherwise, buy from the NPC supplier at a premium. The supplier is an
     abstraction of the wider world outside the village, so its coin leaves
     circulation (paid to WORLD) and its goods appear from outside. This is the
     forgiving backstop: no agent who can pay is ever hard-stalled for want of a
     material, they just pay more when the local market is dry.

Every purchase, local or premium, is recorded in the ledger as a `supply` entry,
so the flow of materials and coin is fully auditable.
"""
from __future__ import annotations

from .ledger import WORLD
from .recipes import RAW_MATERIALS, premium_price


class Supply:
    """Sources raw materials for refiners, preferring local sellers."""

    def __init__(self, sim):
        self.sim = sim

    def _local_seller(self, buyer, material: str):
        """A living neighbour holding at least one unit of `material` to spare."""
        for a in self.sim.living():
            if a.id == buyer.id:
                continue
            if a.materials.get(material, 0) > 0:
                return a
        return None

    def acquire(self, buyer, material: str, qty: int = 1) -> int:
        """Get up to `qty` units of `material` for `buyer`, crediting the source
        and debiting the buyer's coin. Returns how many units were secured (which
        are added to the buyer's material stock)."""
        secured = 0
        base = RAW_MATERIALS.get(material, 10)
        premium = premium_price(material)
        for _ in range(int(qty)):
            seller = self._local_seller(buyer, material)
            if seller is not None and buyer.coin >= base:
                # buy locally at base value; the material moves neighbour -> buyer
                paid = self.sim.economy.transfer(buyer, seller, base, "supply",
                                                 note=f"{material} (local)")
                if paid <= 0:
                    break
                seller.materials[material] = seller.materials.get(material, 0) - 1
                buyer.materials[material] = buyer.materials.get(material, 0) + 1
                secured += 1
                continue
            # a merchant-guild member's trade connections cut the supplier premium
            guilds = getattr(self.sim, "guilds", None)
            price = guilds.supplier_price(buyer, premium) if guilds is not None else premium
            if buyer.coin >= price:
                # fall back to the NPC supplier at a premium (coin leaves the
                # village; the good arrives from outside)
                paid = self.sim.economy.transfer(buyer, WORLD, price, "supply",
                                                 note=f"{material} (supplier)")
                if paid <= 0:
                    break
                buyer.materials[material] = buyer.materials.get(material, 0) + 1
                secured += 1
                continue
            break   # cannot afford even the premium: production waits
        return secured
