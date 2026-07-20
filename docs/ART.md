# Art direction & how to drop in real tiles

Target look: classic tabletop-fantasy, early-history, medieval villages and
wilds, readable top-down 2D. See `RESOURCES.md` for vetted CC0/public-domain
sources and `ASSETS.md` for the license ledger.

## What ships today (Phase 9)

Real CC0 sprite tiles now drive both renderers:

- **Kenney Roguelike/RPG tiles (CC0)** - the base sheet
  (`roguelikeSheet_transparent.png`) and character sheet
  (`roguelikeChar_transparent.png`) render the ground, stone paths, crop fields,
  pond, tree/rock props, building roofs, and per-role villager sprites.
- **Live rendered map** at `docs/map.html` (also on GitHub Pages) - draws
  Oakhollow from the live world with the tiles above: grass, paths radiating from
  the square, roofed buildings by kind, trees and rocks, agents as character
  sprites with nameplates and wanted/alias markers.
- **Godot client** (`Main.gd`) blits the same tiles in immediate mode via
  `draw_texture_rect_region` (nearest-neighbour filtering), so the two clients
  agree tile-for-tile. No `TileSet`/`TileMapLayer` needed for the current 2D view.
- **Dynamic day/night lighting + ambience** - both views ease a *continuous*
  ambient colour across the day (soft dawn, clear noon, golden dusk, deep-blue
  night) and, after dark, punch warm light pools through it at the forge, tavern,
  well, square and gate, with gentle flicker. Chimney smoke rises from the smithy
  and tavern roofs; fireflies drift near the treeline at night.
- **Weather (rain and snow)** - a client-only cosmetic layer with an Auto cycle
  and manual Clear / Rain / Snow controls (header buttons on the web map, the
  R key in the Godot client). By design it never touches the sim, saves, or
  protocol.
- **Decorative props** - trees, rocks, and a pond are authored in the world
  (`world.props`) and streamed to every client.

Assets live in `godot_client/assets/{tiles,sprites}/` (loaded by Godot) and are
mirrored under `docs/assets/{tiles,sprites}/` (served by GitHub Pages for the web
map). All are logged in `ASSETS.md`.

## Tile-index reference (base sheet, col,row)

16x16 tiles, 1px margin => 17px pitch. Both renderers share these:

| Use | (col,row) | | Use | (col,row) |
|-----|-----------|-|-----|-----------|
| grass | (5,0) | | tree (round) | (13,10) |
| stone path | (8,0) | | tree (pine) | (16,10) |
| crop field | (2,7) | | rock/shrub | (6,15) |
| water | (3,2) | | | |

Building roofs by kind: tavern (16,26), home (13,25), stable (18,28),
smithy (19,29), shop (15,26), gate (14,25), well (17,27), square (13,25).
Character sprites (character sheet, col,row): Blacksmith (0,5), Herbalist (1,5),
Tavernkeeper (0,10), Farmer (0,3), Stable hand (1,3), Gate guard (0,11),
Errand child (0,9), Street sweeper (1,6); player = silver knight (1,11).

## Swapping in a different tileset

The renderers key off the constants above (`T_GRASS`, `ROOF`, `ROLE_TILE`, etc.
in `Main.gd`, and the matching block in `docs/map.html`). To try another CC0 set:

1. Drop the new sheet(s) under `godot_client/assets/{tiles,sprites}/` (and mirror
   to `docs/assets/...` for the web map).
2. Update the tile-index constants in `Main.gd` and `map.html` to point at the new
   sheet's cells (and the pitch, if it is not 17px).
3. For a larger world you may prefer a real Godot `TileSet` + `TileMapLayer` for
   the ground/paths instead of immediate-mode blits; the data model does not
   change (the server streams positions, kinds, and time-of-day).
4. **Log every asset in `ASSETS.md`** with its source and license before it ships.

## Direction notes

- One coherent tileset + one character set first, so the world reads
  consistently; extend afterward.
- Early/medieval palette: greens, browns, stone greys, warm lamplight at night.
- Keep the god/overseer UI (dashboards) separate from the in-world art.
- Original art can replace placeholders over time without changing the data: the
  server streams positions, kinds, and time-of-day; the client decides how to
  paint them.

## Graphics roadmap (path forward)

**Enabling fact:** every upgrade below is client-only. The backend streams
positions, kinds, and time-of-day; the client decides how to paint them, so
raising fidelity never touches the simulation, saves, or protocol.

**Shipped (2026-07): lighting, ambience, and weather.** The flat four-step
day/night tint is gone, replaced by a continuous ambient ramp keyed to the world
clock, with warm light pools flickering at the forge, tavern, well, square and
gate after dark, chimney smoke over the smithy and tavern, and fireflies near the
trees at night. Rain and snow ship as a client-only cosmetic layer (Auto cycle
plus manual Clear / Rain / Snow controls: header buttons on the web map, the R key
in Godot).

Where it lives:

- **Web map (`docs/map.html`):** `drawAmbient` (ramp), `drawLights` (additive
  radial-gradient pools), `drawAmbience` (smoke, fireflies), and the `weather`
  module (`updateWeather` / `drawWeather`).
- **Godot (`Main.gd`):** two lighting paths, toggled live with the **L** key:
  - *lights2d (default, prototype):* real `CanvasModulate` + `PointLight2D`. The
    world is drawn on a child `CanvasLayer` (`_world_node`) so the modulate/lights
    dim the world but not the HUD/weather overlays. Warm lamps sit at the forge,
    tavern, well, square, gate and homes; a soft vision `PointLight2D` follows the
    player. The night `CanvasModulate` floors around ~0.5 (never fully black), so
    distant, unlit areas lose visibility while lamplit areas and the player's
    bubble stay readable. The light cookie is a runtime `GradientTexture2D` (no
    art asset). `gl_compatibility` supports 2D lights.
  - *immediate (fallback):* the flat ambient tint + stacked glow circles
    (`_draw_immediate_lighting`), matching the web map tile-for-tile. Kept as a
    guaranteed-render fallback and A/B reference.
  Weather (`_update_weather` / `_draw_weather`) draws on the overlay layer in both
  modes, so it is unaffected by the world modulate.
- Weather is deliberately cosmetic and client-side: no sim, save, or protocol
  changes, consistent with the enabling fact above.

Later tiers, when we want a bigger jump (deferred, not scheduled):

1. **Better-crafted 2D, same style:** real `TileSet` + `TileMapLayer` with
   autotiling (grass/dirt edges, shorelines), `AnimatedSprite2D` 4-direction
   walk cycles, y-sort depth. Biggest look-per-effort after lighting. A coherent
   higher-fidelity pack (Cute Fantasy RPG, Mystic Woods, Epic RPG World, or the
   CC0 Ninja Adventure set) sits on top, ~free to ~$11.
2. **Higher-res / distinct identity:** move to 32-48px or hand-painted HD 2D for
   a recognizable look on the Steam page; realistically a commissioned set.
3. **2.5D / 3D:** billboarded HD-2D or low-poly 3D (the Kenney bundle's 3D
   Fantasy Town Kit is a starting point). Large art/engine effort; `PROJECT_PLAN`
   flags full 3D as a stretch goal, not a phase gate. Parked.

Avoid AI-generated tiles: poor cross-tileset consistency and a licensing/
provenance liability against our CC0/MIT discipline.

## LPC art (step 0, feature/lpc-art-step0)

LPC Revised sheets staged under `godot_client/assets/lpc/` (OGA-BY 3.0, LFS-tracked,
not yet wired into the renderers). Note: LPC is 32px-based (vs the current 16x16 /
17px Kenney sheets) and characters are modular layers (Body/Head/Hair/Clothing),
not pre-composed role sprites - both are wiring decisions for a later step.

Missing structures (well, mill, granary) - resolution playbook:
LPC Revised has no ready well, mill/windmill, or granary/silo sheet. Options, in
preference order:
1. Compose from existing LPC parts (no new license). Granary/silo = tall narrow
   `structure/walls` + `structure/roofing` + `objects/small items/Hay & Straw` /
   `Grains, Grasses`. Well = a stone-wall ring + a bucket prop, or the interim
   `structure/misc/Fountain A.png`.
2. Pull LPC-compatible sheets from OpenGameArt (the wider LPC ecosystem has well,
   windmill, and watermill art). Filter to CC0 / CC-BY / OGA-BY; avoid CC-BY-SA
   (share-alike) to keep the release flexible. Log each in ASSETS.md with its own
   license and attribution before it ships.
3. Original art (MIT, no attribution) for a distinct identity - best long term,
   most effort.
Avoid AI-generated tiles (provenance + style consistency, per this doc).
Interim: `structure/misc/Fountain A.png` stands in for the well until replaced.

## The LPC render path (step 1)

The Godot client now renders Oakhollow entirely from LPC Revised art (OGA-BY 3.0),
replacing the Kenney sheets. This is still client-only: the backend streams the
same positions, kinds, and time-of-day; only how the client paints them changed.
All of the code lives in `godot_client/scripts/Main.gd`.

### What draws what

- **Terrain** comes from `assets/lpc/terrain/terrain_summer.png`, a 32px atlas laid
  out as a 16x26 tile grid. The renderer keys off named cells:

  | Use | (col,row) | | Use | (col,row) |
  |-----|-----------|-|-----|-----------|
  | grass | (1,1) | | cobblestone | (10,3) |
  | tufted grass | (1,4) | | flagstone (plaza) | (10,1) |
  | dirt path | (4,1) | | water | (14,16) |

  Crop fields use `tilled_soil.png` cell (1,1); trees are cropped regions of
  `trees_summer.png` (round tree at px (160,0,64,128), conifer at (160,352,64,160)).

- **Villagers** are assembled sheets under `assets/lpc/villagers/<Role>.png`. LPC
  Revised characters are *modular* - Body, Head (separate from the body), Hair, and
  Clothing (Torso/Legs/Feet slots) are individual 512x256 animation sheets. A build
  script composites the down/left/right/up standing frame of each layer, in
  z-order Body -> Head -> Legs -> Feet -> Torso -> Hair, into a 256x64 four-frame
  sheet (columns: up, left, down, right). To add or restyle a role, re-composite
  its layers and drop the sheet in `villagers/`. The renderer picks the front frame
  when idle and the side frame when the agent is moving.

- **Buildings** use LPC prefab houses copied into `assets/lpc/buildings/`
  (`house_brick_a/b`, `house_paneled_a` from `Structure/Structures`, `fountain`
  from `Structure/Misc`). These are 3/4-elevation sprites, which matches the LPC
  character perspective, so a top-down ground with elevation buildings reads
  correctly. `_building_tex(kind)` maps a location kind to a prefab (homes vary by
  position hash) and `_building_w(kind)` sets its on-screen width in world units;
  `_building_draw` blits it with its base on the ground. Wells use the fountain;
  the square and gate use flagstone/cobble ground.

### Helpers (Main.gd)

`_gtile(tex, col, row, center, size)` blits one 32px atlas tile; `_ltile` is the
terrain shortcut. `_villager_draw(role, feet, dir, h)` draws an assembled villager
standing on `feet`. `_building_draw(tex, feet, world_w)` and `_tree_draw(region,
feet, h)` place elevation sprites by their base. There is no Kenney blit path left.

### Import discipline (important)

The full LPC character tree is ~64k files. Godot must not import it, or the editor
and CI hang. `assets/lpc/characters/`, `structure/`, and `objects/` each carry a
`.gdignore` so Godot skips them; the renderer only uses the assembled `villagers/`
sheets, the copied `buildings/` prefabs, and `terrain/`. Keep new raw-layer drops
under a `.gdignore`d directory.

### Verifying renders headless (no GPU)

`tools/screenshot.sh` renders the client against the stub server under `xvfb` with
software GL. In a plain Linux sandbox: download Godot 4.3, `pip install websockets`,
ensure the `.gdignore`s above are present (so import is a few dozen textures, not
64k), then run the script. It writes a PNG you can eyeball. This is how the terrain
and villager passes were verified.

### Open items

- Buildings/props pass is parse-validated but wants an on-GPU render confirm (F5).
- The Errand child renders under-dressed (this LPC subset has no child-fit clothing).
- Well/mill/granary have no dedicated LPC sheet: the fountain is the well stand-in;
  mill and granary are still an open sourcing/compose task (see the step-0 playbook).
