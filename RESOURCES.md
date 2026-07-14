# Free and Public-Domain Asset Resources

Vetted sources for art, music, sound, and fonts we can use to give Realmweave a
classic tabletop-fantasy, early-history look without paying for or building
everything up front. Target feel: medieval villages, trades, wilds, and dungeons.
No science-fiction assets for now.

**Golden rule:** anything we actually ship gets logged in `ASSETS.md` with its
license and a link, first. This file is the shortlist of *where to look*;
`ASSETS.md` is the record of *what we used*.

## License primer (read once)

| License | Attribution required | Commercial use | Notes |
|---------|----------------------|----------------|-------|
| **CC0 / Public Domain** | No | Yes | Best case. Use, modify, ship freely, no credit needed. Prefer this. |
| **CC-BY** | Yes | Yes | Fine to use; must credit the author (keep a credits screen / `THIRD_PARTY_NOTICES`). |
| **OGA-BY** | Yes | Yes | OpenGameArt's attribution license; treat like CC-BY. |
| **OFL** (fonts) | Keep license, no selling font alone | Yes | Standard for open fonts. |
| CC-BY-SA | Yes + share-alike | Yes | Share-alike can force your derived assets open; use with care. |
| CC-NC / CC-ND | - | **No / limited** | Avoid: non-commercial or no-derivatives block a paid release. |

Packs can be **mixed-license**: always check the individual asset, not just the
page or bundle title.

## Art (2D sprites, tilesets, icons)

- **Kenney** (https://kenney.nl) - thousands of assets, all **CC0**, no
  attribution. Great for tiles, characters, UI, and prototyping. Start here.
- **OpenGameArt.org** - large library; filter to CC0 or CC-BY. Useful collections:
  [All CC0 by Kenney](https://opengameart.org/content/all-cc0-uploader-kenney),
  [CC0 Tiles & Tilesets](https://opengameart.org/content/cc0-tiles-tilesets),
  [CC0 resources hub](https://opengameart.org/content/cc0-resources). Search for
  medieval, dungeon, town, forest, and overworld tilesets.
- **itch.io CC0 art** (https://itch.io/game-assets/tag-cc0) - many free
  medieval/fantasy tile and character packs; confirm each pack's license.
- **Game-icons.net** (https://game-icons.net) - 4000+ clean fantasy icons
  (weapons, armor, spells, items) under **CC-BY 3.0**. Ideal for a D&D-style
  inventory, skills, and spellbook UI. Needs attribution.

*Direction:* pick one coherent tileset + character set first (Kenney or a single
OpenGameArt pack) so the world reads consistently, then extend.

## Music (ambient, exploration, tavern, tension)

- **Musopen** (https://musopen.org) - **public-domain** recordings of classical
  and early music. Good for a courtly, pre-industrial, "old world" atmosphere.
  Verify each recording's specific license (compositions are PD; some
  performances carry their own terms).
- **OpenGameArt CC0 music** (https://opengameart.org/content/cc0-music-0) and
  [CC0 fantasy music & sounds](https://opengameart.org/content/cc0-fantasy-music-sounds)
  - loops and tracks purpose-made for fantasy RPGs.
- **itch.io CC0 music** (https://itch.io/game-assets/tag-cc0/tag-music) -
  fantasy music mega-packs and ambient sets released CC0/public domain.
- **IMSLP** (https://imslp.org) - vast public-domain **sheet music** of medieval,
  Renaissance, and Baroque works. Compositions are PD; recordings vary, so we may
  need to record/render performances ourselves for a fully clean track.

*Direction:* early/medieval-adjacent instrumentation (lute, harp, recorder,
strings) sells the setting. A little goes a long way; a few loops per biome/mood.

## Sound effects (footsteps, forge, market, combat, UI)

- **Kenney audio** (https://kenney.nl) - **CC0** impact, UI, and effect packs, no
  attribution.
- **Sonniss GDC Game Audio bundles** (https://sonniss.com/gameaudiogdc) -
  professional, royalty-free, commercially usable SFX; tens of thousands of
  sounds, no attribution required. Excellent for ambience and foley.
- **Freesound** (https://freesound.org) - huge library; **filter to CC0** for the
  cleanest use (other clips may be CC-BY and need credit).
- **gamesounds.xyz** (https://gamesounds.xyz) - curated royalty-free/PD game
  audio, including Kenney's packs.

## Fonts

- **Google Fonts** (https://fonts.google.com) - open-licensed (mostly OFL). Look
  for readable serif/blackletter-adjacent faces that fit a medieval tone while
  staying legible in-game.

## Workflow

1. Find a candidate asset from a source above.
2. Confirm its exact license (CC0 preferred; CC-BY acceptable with credit).
3. Download and add it to the project.
4. **Record it in `ASSETS.md`** with source link, license, and attribution text.
5. Keep any required license files in the repo.

Replacing placeholders with original or commissioned art later does not change
the pipeline, so starting with CC0 costs us nothing long-term.
