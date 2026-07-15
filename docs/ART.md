# Art direction & how to drop in real tiles

Target look: classic tabletop-fantasy, early-history, medieval villages and
wilds, readable top-down 2D. See `RESOURCES.md` for vetted CC0/public-domain
sources and `ASSETS.md` for the license ledger.

## What ships today (Phase 9, first pass)

World feel without any binary asset dependency yet:

- **Live rendered map** at `docs/map.html` (also on GitHub Pages) - draws
  Oakhollow from the live world: grass, a pond, paths radiating from the square,
  buildings colored by kind, trees and rocks, and agents as little figures with
  nameplates and wanted/alias markers.
- **Day/night lighting** - both the map view and the Godot client tint the scene
  by the world clock: soft morning, clear afternoon, warm dusk, deep-blue night.
- **Decorative props** - trees, rocks, and a pond are authored in the world
  (`world.props`) and streamed to every client, so the map and the game agree.

All of the above is drawn procedurally (original, MIT with the project). It is a
placeholder that already reads as a village; real sprite tiles slot in on top.

## Dropping in real CC0 tiles (Godot)

1. Pick a coherent top-down set from a source in `RESOURCES.md` (Kenney's tiny
   town / roguelike packs are CC0 and a great start).
2. Put the images under `godot_client/assets/tiles/` and
   `godot_client/assets/sprites/`.
3. In Godot 4: create a `TileSet` from the tile image, add a `TileMapLayer` to
   `Main.tscn`, and paint the ground/paths. Map the world's `locations` and
   `props` coordinates (same 0..64 grid the map view uses) to tile cells.
4. Replace the drawn circles in `Main.gd` (`_draw_props`, the agent circles) with
   `Sprite2D`/`AnimatedSprite2D` nodes per agent, keyed by role. Keep the
   day/night `_draw_daynight` tint on top.
5. **Log every asset in `ASSETS.md`** with its source and license before it ships.

## Direction notes

- One coherent tileset + one character set first, so the world reads
  consistently; extend afterward.
- Early/medieval palette: greens, browns, stone greys, warm lamplight at night.
- Keep the god/overseer UI (dashboards) separate from the in-world art.
- Original art can replace placeholders over time without changing the data: the
  server streams positions, kinds, and time-of-day; the client decides how to
  paint them.
