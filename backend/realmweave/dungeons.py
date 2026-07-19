"""Dungeons of the realm around Oakhollow.

Phase 1: the entrances and their lore exist as world data (marked on the maps,
carried in the snapshot). Making them delvable - parties, encounters, and loot
resolved through the combat system - is Phase 2 (see docs/BACKLOG.md).

`x`/`y` are a local-map entrance position when the way in lies in or under the
village (the Welldeep); wilderness dungeons leave them None and are placed on
the regional map instead.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Dungeon:
    id: str
    name: str
    theme: str
    region: str
    danger: int                 # 1 (a nuisance) .. 5 (a grave)
    entrance: str
    levels: List[dict]          # [{name, denizens, hazard}]
    mystery: str
    x: Optional[float] = None
    y: Optional[float] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "theme": self.theme,
                "region": self.region, "danger": self.danger,
                "entrance": self.entrance, "levels": self.levels,
                "mystery": self.mystery, "x": self.x, "y": self.y}


DUNGEONS: List[Dungeon] = [
    Dungeon(
        id="kobold_warren", name="The Kobold Warren", theme="kobold stronghold",
        region="the Ironbark Hills, east past the mine", danger=3,
        entrance="A timber-shored adit gouged into a hillside, its lintel scratched "
                 "with warning-glyphs no villager can read. Smoke leaks from cracks above it.",
        levels=[
            {"name": "The Guard Burrows",
             "denizens": "kobold skirmishers and trap-slingers",
             "hazard": "spring-spike pits and rockfall snares, each one tripped from hiding"},
            {"name": "The Warren Deeps",
             "denizens": "kobold packs and a half-grown drakeling on a chain",
             "hazard": "tunnels that narrow until a tall folk must crawl"},
            {"name": "Skarn's Throne",
             "denizens": "Skarn the Underking and his shield-guard",
             "hazard": "a hoard-hall trapped six ways over"},
        ],
        mystery="Skarn hoards more than coin: a warm clutch of drake eggs, kept alive by a "
                "forge-heart the kobolds stole from somewhere they will not name."),
    Dungeon(
        id="hollow_barrow", name="The Hollow Barrow", theme="undead barrow",
        region="the Highmoor, north beyond the fields", danger=4,
        entrance="A sunken barrow-mound out on the cold moor, its capstone split as if "
                 "something pushed it aside from below. The grass will not grow within a spear's throw.",
        levels=[
            {"name": "The Antechamber",
             "denizens": "restless shades and grave-fed rats",
             "hazard": "a grief-cold that saps the will to go on"},
            {"name": "The Ossuary",
             "denizens": "bone-knit wights that rise as you pass",
             "hazard": "floors of loose skulls and a ceiling that comes down"},
            {"name": "The Kingsbarrow",
             "denizens": "the Hollow King, crowned in rime",
             "hazard": "a curse that follows whatever you carry out"},
        ],
        mystery="The Hollow King still wears his crown and still gives orders, for he does not "
                "believe the war he died in was ever lost."),
    Dungeon(
        id="weeping_caverns", name="The Weeping Caverns", theme="flooded caverns",
        region="deep in Whisperwood, west of the village", danger=2,
        entrance="A dripping cave-mouth curtained in grey web, far back in the old forest "
                 "where the trees lean inward and the birds go quiet.",
        levels=[
            {"name": "The Dripstone Halls",
             "denizens": "cave-spiders and a slow, patient ooze",
             "hazard": "slick stone, blind drops, and web underfoot"},
            {"name": "The Sunless Pool",
             "denizens": "a great pale spider and the blind fish it feeds on",
             "hazard": "water that rises while you are down there"},
        ],
        mystery="Something older than the spiders taught these caves to weep. The water hums a "
                "name when it is still, and the name is almost one you know."),
    Dungeon(
        id="welldeep", name="The Welldeep", theme="rats, then far worse",
        region="beneath Oakhollow itself", danger=3, x=32, y=30,
        entrance="Down the trap-door in the Gilded Stag's cellar, past the ale-casks and a "
                 "bold nest of rats, an old drain lets into the shaft of the Old Well - and the "
                 "well, it turns out, goes far, far deeper than any bucket has ever sounded.",
        levels=[
            {"name": "The Stag's Cellar",
             "denizens": "a bold nest of cellar rats",
             "hazard": "a cluttered, lightless larder and Bram's temper if you spill the ale"},
            {"name": "The Well Shaft",
             "denizens": "drowned rats and a rat the size of a hound",
             "hazard": "a long wet climb with no easy way back up"},
            {"name": "The Cistern",
             "denizens": "pale swimming things and a toll-keeper that was once a man",
             "hazard": "black water in every direction and no shore in sight"},
            {"name": "The Sounding Deep",
             "denizens": "unknown - nothing that has come back up has said",
             "hazard": "dressed stone no villager ever laid, and a hum that answers when you speak"},
        ],
        mystery="Who cut a cistern of worked stone a hundred fathoms under a farming village, and "
                "why does the Welldeep hum back your own words in a voice that is not yours? What "
                "mysteries await, indeed."),
]
