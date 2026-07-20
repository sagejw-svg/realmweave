extends Node2D
## Realmweave 2D client. (UI/graphics upgrade pass)
##
## Connects to the Python backend over WebSocket, receives the authoritative
## world (locations) and a stream of snapshots (agent positions, state, speech)
## plus discrete events (dialogue, deaths). Renders everything top-down in 2D
## and lets the local player walk around with WASD and broadcast their position.
##
## The world (tiles/sprites/lamps) is drawn on a child CanvasLayer so real 2D
## lighting (CanvasModulate + PointLight2D) can dim it at night while the HUD and
## weather overlays, drawn on this node, stay at full brightness. Press L to A/B
## the real lighting against the immediate-mode fallback glow.

const SCALE := 20.0                 # pixels per world unit (a bit zoomed in for detail)
const ORIGIN := Vector2(60, 90)     # legacy map origin (unused since the camera follows)
const CAM_LERP := 3.0               # how quickly the camera eases toward the player
const AGENT_R := 7.0
const MOVE_SPEED := 12.0            # world units / second for the player
const SEND_INTERVAL := 0.1

var _ws := WebSocketPeer.new()
var _connected := false
var _server_url := "ws://127.0.0.1:8765"

var _locations: Array = []          # [{id,name,x,y,kind}]
var _props: Array = []              # decorative scenery [{kind,x,y}]
var _agents: Dictionary = {}        # id -> latest agent dict
var _render_pos: Dictionary = {}    # id -> Vector2 (smoothed screen pos)
var _facing: Dictionary = {}        # id -> +1 (right) / -1 (left), from movement
var _moving: Dictionary = {}        # id -> bool, walking this frame (drives the bob)
var _players: Array = []
var _clock: Dictionary = {}
var _events: Array = []             # recent event log (strings)

# --- atmosphere: dynamic lighting + weather (client-only cosmetic) ---
var _wx_mode := "auto"              # auto | clear | rain | snow (press R to cycle)
var _wx_type := "clear"            # precip currently rendered
var _wx_target := "clear"          # precip we are easing toward
var _wx_intensity := 0.0           # 0..1
var _wx_next := 0.0                # next auto weather roll (in _wx_time seconds)
var _wx_time := 0.0                # local animation clock
var _rain: Array = []              # [{x,y,l,sp}]
var _snow: Array = []              # [{x,y,r,sp,sw,ph,a}]

# --- real 2D lighting prototype: PointLight2D + CanvasModulate (press L) ---
var _lighting := "lights2d"        # "lights2d" (real Godot lights) or "immediate" (fallback glow)
var _world_layer: CanvasLayer      # holds the modulated world so the HUD stays bright
var _world_node: Node2D            # all world tiles/sprites are drawn here
var _canvas_mod: CanvasModulate    # day/night multiply over the world only
var _light_tex: Texture2D          # runtime radial-gradient light cookie
var _shadow_tex: Texture2D         # soft blob shadow under sprites (depth cue)
var _vignette_tex: Texture2D       # subtle edge darkening for framing
var _player_light: PointLight2D    # soft vision light around the player
var _loc_lights: Array = []        # PointLight2D lamps at buildings
var _loc_lights_built := false

var _player_id := ""
var _player_pos := Vector2(32, 24)
var _player_facing := 1            # +1 right / -1 left, from WASD input
var _cam := Vector2(32, 24)        # camera center in world units (eases toward player)
var _send_accum := 0.0
var _chat_input: LineEdit
var _subjective: Dictionary = {}     # 'through their eyes' view of the observed agent
var _observe_id := ""
var _o_down := false

# live time control (server-authoritative; the client just requests changes)
var _time_scale := 1.0
var _game_min_per_sec := 0.0
var _minutes_per_tick := 0.0
var _paused := false
# edge-detect keys so a held key fires once
var _key_down := {}
# settings menu
var _settings_layer: CanvasLayer
var _settings_open := false
var _url_edit: LineEdit
var _speed_value_label: Label

# --- UI/interface upgrade state ---
var _talk_target := ""              # nearest alive villager the chat box will address
var _show_plates := true           # V toggles floating nameplates + inspect card
var _show_minimap := true          # M toggles the corner minimap
var _join_name := "James"          # player display name (override with -- --player=NAME)
var _force_hour := -1.0            # capture-only: pin the time of day (>=0 overrides clock)
const TALK_RANGE := 6.0            # world units within which "press Enter to speak" shows
const UI_GOLD := Color(0.86, 0.74, 0.42)
const UI_INK := Color(0.05, 0.055, 0.085, 0.86)
const UI_EDGE := Color(0.62, 0.55, 0.35, 0.85)

const KIND_COLORS := {
	"tavern": Color(0.72, 0.45, 0.20),
	"home": Color(0.35, 0.38, 0.55),
	"stable": Color(0.55, 0.42, 0.30),
	"well": Color(0.30, 0.55, 0.65),
	"square": Color(0.40, 0.50, 0.35),
	"smithy": Color(0.55, 0.30, 0.30),
	"field": Color(0.45, 0.60, 0.30),
	"gate": Color(0.50, 0.50, 0.55),
	"shop": Color(0.80, 0.65, 0.25),
}

# --- Kenney Roguelike/RPG tiles (CC0). 16x16 tiles, 1px margin => 17px pitch.
# See ASSETS.md for provenance and docs/ART.md for the tile-index reference.
var _sheet: Texture2D = load("res://assets/tiles/roguelikeSheet_transparent.png")
var _chars: Texture2D = load("res://assets/sprites/roguelikeChar_transparent.png")
const T_GRASS := Vector2i(5, 0)
const T_STONE := Vector2i(8, 0)
const T_FIELD := Vector2i(2, 7)
const T_WATER := Vector2i(3, 2)
const T_TREE := Vector2i(13, 10)
const T_PINE := Vector2i(16, 10)
const T_ROCK := Vector2i(6, 15)
const ROOF := {
	"tavern": Vector2i(16, 26), "home": Vector2i(13, 25), "stable": Vector2i(18, 28),
	"smithy": Vector2i(19, 29), "shop": Vector2i(15, 26), "gate": Vector2i(14, 25),
	"well": Vector2i(17, 27), "square": Vector2i(13, 25), "field": Vector2i(15, 26),
}
# Character-sheet cells (col,row). Every role now maps to a distinct *human*
# figure. NOTE: Farmer and Stable hand previously pointed at (0,3)/(1,3), which
# are green goblin/orc sprites on this sheet - the "green villagers" bug. They
# are remapped to people here, and Farmhand/Miner/Shepherd (previously unmapped,
# so they fell back to a blank tile) now have sprites too.
const ROLE_TILE := {
	"Tavernkeeper": Vector2i(0, 10), "Stable hand": Vector2i(1, 9), "Blacksmith": Vector2i(0, 5),
	"Street sweeper": Vector2i(1, 6), "Farmer": Vector2i(0, 8), "Gate guard": Vector2i(0, 11),
	"Errand child": Vector2i(0, 9), "Herbalist": Vector2i(1, 5),
	"Farmhand": Vector2i(0, 6), "Miner": Vector2i(1, 7), "Shepherd": Vector2i(0, 7),
}
const ROLE_TILE_DEFAULT := Vector2i(1, 0)   # plain villager for any unmapped role

# --- LPC Revised art (OGA-BY 3.0). 32px terrain atlas + assembled 64px villagers.
# See ASSETS.md / docs/ART.md. Terrain tiles are (col,row) in a 16x26 grid.
var _lterrain: Texture2D = load("res://assets/lpc/terrain/terrain_summer.png")
var _ltrees: Texture2D = load("res://assets/lpc/terrain/trees_summer.png")
const L_TILE := 32
const L_GRASS := Vector2i(1, 1)      # solid grass
const L_GRASS2 := Vector2i(1, 4)     # tufted grass (variation)
const L_DIRT := Vector2i(4, 1)       # dirt / worn path
const L_COBBLE := Vector2i(10, 3)    # cobblestone
const L_FLAG := Vector2i(10, 1)      # pale flagstone (plaza)
const L_WATER := Vector2i(14, 16)    # solid water
# Assembled per-role villager sheets (256x64 = 4 frames: up,left,down,right).
const VILLAGER_ROLES := ["Blacksmith", "Herbalist", "Tavernkeeper", "Farmer",
	"Stable hand", "Gate guard", "Street sweeper", "Errand child", "Player"]
const VILLAGER_DEFAULT := "Stable hand"
var _vill: Dictionary = {}           # role -> Texture2D


## Blit one 16x16 tile from a Kenney sheet, centered on `center`, scaled to `size` px.
## Drawn on the world layer so lighting affects it.
func _tile(tex: Texture2D, t: Vector2i, center: Vector2, size: float, mod: Color = Color(1, 1, 1)) -> void:
	if tex == null or _world_node == null:
		return
	_world_node.draw_texture_rect_region(tex,
		Rect2(center - Vector2(size, size) * 0.5, Vector2(size, size)),
		Rect2(t.x * 17, t.y * 17, 16, 16), mod)


## Deterministic 0..1 hash for a world cell, so terrain variation is stable
## frame-to-frame (no shimmering) and identical every run.
func _cell_hash(gx: int, gy: int) -> float:
	return fmod(abs(sin(float(gx) * 12.9898 + float(gy) * 78.233) * 43758.5453), 1.0)


## Blit a sprite tile, optionally mirrored horizontally (to face left).
func _tile_h(tex: Texture2D, t: Vector2i, center: Vector2, size: float, flip: bool, mod: Color = Color(1, 1, 1)) -> void:
	if not flip:
		_tile(tex, t, center, size, mod)
		return
	if tex == null or _world_node == null:
		return
	_world_node.draw_set_transform(center, 0.0, Vector2(-1, 1))
	_world_node.draw_texture_rect_region(tex,
		Rect2(-Vector2(size, size) * 0.5, Vector2(size, size)),
		Rect2(t.x * 17, t.y * 17, 16, 16), mod)
	_world_node.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## Blit one 32px LPC terrain tile (col,row), centered on `center`, scaled to `size` px.
func _ltile(t: Vector2i, center: Vector2, size: float, mod: Color = Color(1, 1, 1)) -> void:
	if _lterrain == null or _world_node == null:
		return
	_world_node.draw_texture_rect_region(_lterrain,
		Rect2(center - Vector2(size, size) * 0.5, Vector2(size, size)),
		Rect2(t.x * L_TILE, t.y * L_TILE, L_TILE, L_TILE), mod)


## Draw an assembled LPC villager. The sheet is 256x64 (frames up,left,down,right).
## `feet` is the ground position; the sprite stands on it. `dir` picks the facing
## column; `h` is the on-screen sprite height in px.
func _villager_draw(role: String, feet: Vector2, dir: int, h: float, mod: Color = Color(1, 1, 1)) -> void:
	if _world_node == null:
		return
	var tex: Texture2D = _vill.get(role, _vill.get(VILLAGER_DEFAULT, null))
	if tex == null:
		return
	var top_left := feet - Vector2(h * 0.5, h * 0.86)
	_world_node.draw_texture_rect_region(tex,
		Rect2(top_left, Vector2(h, h)),
		Rect2(dir * 64, 0, 64, 64), mod)


func _load_villagers() -> void:
	for role in VILLAGER_ROLES:
		var t: Texture2D = load("res://assets/lpc/villagers/%s.png" % role)
		if t != null:
			_vill[role] = t


func _ready() -> void:
	# crisp pixel art (no bilinear blur when the 16px tiles are scaled up)
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_build_world_layer()
	_load_villagers()
	if ProjectSettings.has_setting("network/realmweave/server_url"):
		_server_url = ProjectSettings.get_setting("network/realmweave/server_url")
	_ws.connect_to_url(_server_url)
	# chat box: type a line and press Enter to speak to the nearest villager
	_chat_input = LineEdit.new()
	_chat_input.placeholder_text = "Say something to a nearby villager, then press Enter (Enter to focus)"
	_chat_input.custom_minimum_size = Vector2(560, 30)
	_chat_input.position = Vector2(12, 58)
	_chat_input.text_submitted.connect(_on_chat_submitted)
	add_child(_chat_input)
	get_window().theme = _make_ui_theme()   # nicer chat box + settings menu
	_build_settings_ui()
	set_process(true)
	_maybe_setup_capture()


## A small theme so the Control-based UI (chat box, settings menu) matches the
## in-world HUD: dark rounded panels, gold focus, legible text.
func _make_ui_theme() -> Theme:
	var th := Theme.new()
	var sb_panel := StyleBoxFlat.new()
	sb_panel.bg_color = Color(0.07, 0.075, 0.11, 0.97)
	sb_panel.border_color = UI_EDGE
	sb_panel.set_border_width_all(1)
	sb_panel.set_corner_radius_all(8)
	sb_panel.set_content_margin_all(14)
	th.set_stylebox("panel", "PanelContainer", sb_panel)

	var sb_le := StyleBoxFlat.new()
	sb_le.bg_color = Color(0.10, 0.11, 0.15, 0.97)
	sb_le.border_color = Color(0.40, 0.42, 0.50)
	sb_le.set_border_width_all(1)
	sb_le.set_corner_radius_all(6)
	sb_le.set_content_margin_all(8)
	th.set_stylebox("normal", "LineEdit", sb_le)
	var sb_le_f := sb_le.duplicate() as StyleBoxFlat
	sb_le_f.border_color = UI_GOLD
	th.set_stylebox("focus", "LineEdit", sb_le_f)
	th.set_color("font_color", "LineEdit", Color(0.92, 0.93, 0.97))
	th.set_color("font_placeholder_color", "LineEdit", Color(0.60, 0.63, 0.70))

	var sb_btn := StyleBoxFlat.new()
	sb_btn.bg_color = Color(0.16, 0.17, 0.22)
	sb_btn.border_color = Color(0.40, 0.42, 0.50)
	sb_btn.set_border_width_all(1)
	sb_btn.set_corner_radius_all(6)
	sb_btn.set_content_margin_all(8)
	th.set_stylebox("normal", "Button", sb_btn)
	var sb_bh := sb_btn.duplicate() as StyleBoxFlat
	sb_bh.bg_color = Color(0.22, 0.23, 0.30)
	sb_bh.border_color = UI_GOLD
	th.set_stylebox("hover", "Button", sb_bh)
	var sb_bp := sb_btn.duplicate() as StyleBoxFlat
	sb_bp.bg_color = Color(0.12, 0.13, 0.17)
	th.set_stylebox("pressed", "Button", sb_bp)
	th.set_color("font_color", "Button", Color(0.90, 0.91, 0.96))
	return th


## Dev/CI screenshot mode: run the client with `-- --capture=PATH [--capture-delay=SECONDS]`
## and it renders for a few seconds (long enough to connect and populate the world),
## saves a PNG of the viewport to PATH, and quits. Used to verify graphics changes.
func _maybe_setup_capture() -> void:
	var path := ""
	var delay := 6.0
	# these can be set outside capture too, to override name/conditions
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--capture="):
			path = a.substr("--capture=".length())
		elif a.begins_with("--capture-delay="):
			delay = float(a.substr("--capture-delay=".length()))
		elif a.begins_with("--player="):
			_join_name = a.substr("--player=".length())
		elif a.begins_with("--weather="):
			_wx_mode = a.substr("--weather=".length())
		elif a.begins_with("--hour="):
			_force_hour = clamp(float(a.substr("--hour=".length())), 0.0, 24.0)
	if path == "":
		return
	get_tree().create_timer(delay).timeout.connect(func() -> void:
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var err := img.save_png(path)
		print("[Realmweave] capture ", "ok" if err == OK else "FAILED", " -> ", path)
		get_tree().quit())


func _build_settings_ui() -> void:
	_settings_layer = CanvasLayer.new()
	_settings_layer.layer = 10
	_settings_layer.visible = false
	add_child(_settings_layer)

	# dim backdrop
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_settings_layer.add_child(dim)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.position = Vector2(-190, -140)
	panel.custom_minimum_size = Vector2(380, 0)
	_settings_layer.add_child(panel)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 12)
	panel.add_child(vb)

	var title := Label.new()
	title.text = "Settings"
	title.add_theme_font_size_override("font_size", 20)
	vb.add_child(title)

	# --- server ---
	vb.add_child(_row_label("Server"))
	var srow := HBoxContainer.new()
	_url_edit = LineEdit.new()
	_url_edit.text = _server_url
	_url_edit.custom_minimum_size = Vector2(240, 0)
	srow.add_child(_url_edit)
	var reconnect := Button.new()
	reconnect.text = "Reconnect"
	reconnect.pressed.connect(_on_reconnect_pressed)
	srow.add_child(reconnect)
	vb.add_child(srow)

	# --- speed ---
	vb.add_child(_row_label("World speed"))
	var prow := HBoxContainer.new()
	prow.add_theme_constant_override("separation", 8)
	var slower := Button.new()
	slower.text = "  -  "
	slower.pressed.connect(func(): _change_speed(-1))
	prow.add_child(slower)
	_speed_value_label = Label.new()
	_speed_value_label.custom_minimum_size = Vector2(150, 0)
	_speed_value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prow.add_child(_speed_value_label)
	var faster := Button.new()
	faster.text = "  +  "
	faster.pressed.connect(func(): _change_speed(1))
	prow.add_child(faster)
	var pause := Button.new()
	pause.text = "Pause / Resume"
	pause.pressed.connect(_toggle_pause)
	prow.add_child(pause)
	vb.add_child(prow)

	var hint := Label.new()
	hint.text = "Tip: press - / + anytime to change speed, Space to pause, Esc to close."
	hint.add_theme_font_size_override("font_size", 11)
	hint.modulate = Color(0.7, 0.7, 0.75)
	vb.add_child(hint)

	var close := Button.new()
	close.text = "Close"
	close.pressed.connect(_toggle_settings)
	vb.add_child(close)
	_refresh_speed_label()


func _row_label(t: String) -> Label:
	var l := Label.new()
	l.text = t
	l.modulate = Color(0.65, 0.7, 0.8)
	return l


func _toggle_settings() -> void:
	_settings_open = not _settings_open
	_settings_layer.visible = _settings_open


func _on_reconnect_pressed() -> void:
	var url := _url_edit.text.strip_edges()
	if url == "":
		return
	_server_url = url
	_connected = false
	_player_id = ""
	_agents.clear()
	_render_pos.clear()
	_ws.close()
	_ws = WebSocketPeer.new()
	_ws.connect_to_url(_server_url)
	_log("Reconnecting to " + _server_url + " ...")


func _change_speed(delta: int) -> void:
	_send({"type": "set_speed", "delta": delta})


func _toggle_pause() -> void:
	# ask the server to pause (scale 0) or resume (scale 1)
	_send({"type": "set_speed", "scale": 0.0 if not _paused else 1.0})


func _refresh_speed_label() -> void:
	if _speed_value_label == null:
		return
	if _paused:
		_speed_value_label.text = "PAUSED"
	else:
		_speed_value_label.text = "%sx  (%.0f min/s)" % [str(_time_scale), _game_min_per_sec]


func _on_chat_submitted(text: String) -> void:
	var line := text.strip_edges()
	if line != "" and _player_id != "":
		_send({"type": "player_say", "id": _player_id, "text": line})
		_log("You: \"" + line + "\"")
	_chat_input.clear()
	_chat_input.release_focus()


func world_to_screen(x: float, y: float) -> Vector2:
	return get_viewport_rect().size * 0.5 + (Vector2(x, y) - _cam) * SCALE


func _process(delta: float) -> void:
	_poll_socket()
	_handle_input(delta)
	# the camera eases toward the player so movement feels smooth, not snapped
	_cam = _cam.lerp(_player_pos, clamp(delta * CAM_LERP, 0.0, 1.0))
	# smooth agent positions toward their latest reported location
	for id in _agents.keys():
		var a: Dictionary = _agents[id]
		var target := world_to_screen(a.get("x", 0.0), a.get("y", 0.0))
		if not _render_pos.has(id):
			_render_pos[id] = target
		var prev: Vector2 = _render_pos[id]
		var now: Vector2 = prev.lerp(target, clamp(delta * 8.0, 0, 1))
		_render_pos[id] = now
		var d := now - prev
		if abs(d.x) > 0.04:
			_facing[id] = -1 if d.x < 0.0 else 1
		_moving[id] = d.length() > 0.05
	_talk_target = _nearest_alive_agent()
	_wx_time += delta
	_update_weather(delta)
	if not _loc_lights_built and not _locations.is_empty():
		_build_loc_lights()
	_update_lighting(delta)
	queue_redraw()
	if _world_node:
		_world_node.queue_redraw()


func _poll_socket() -> void:
	_ws.poll()
	var state := _ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _connected:
			_connected = true
			_log("Connected to " + _server_url)
			_send({"type": "player_join", "name": _join_name})
		while _ws.get_available_packet_count() > 0:
			var pkt := _ws.get_packet().get_string_from_utf8()
			_on_message(pkt)
	elif state == WebSocketPeer.STATE_CLOSED:
		if _connected:
			_connected = false
			_log("Disconnected.")


func _send(obj: Dictionary) -> void:
	if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_ws.send_text(JSON.stringify(obj))


func _on_message(text: String) -> void:
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		return
	match data.get("type", ""):
		"hello":
			_locations = data.get("world", {}).get("locations", [])
			_props = data.get("world", {}).get("props", [])
			var cfg: Dictionary = data.get("config", {})
			_minutes_per_tick = float(cfg.get("minutes_per_tick", 0.0))
			_time_scale = float(cfg.get("time_scale", 1.0))
			_game_min_per_sec = float(cfg.get("game_min_per_sec", 0.0))
			_paused = _time_scale <= 0.0
			_refresh_speed_label()
			_log("Entered %s (%d locations)" % [data.get("world", {}).get("name", "?"), _locations.size()])
		"joined":
			_player_id = data.get("id", "")
			_log("You are " + _player_id)
		"snapshot":
			_clock = data.get("clock", {})
			_players = data.get("players", [])
			if data.has("time_scale"):
				_time_scale = float(data.get("time_scale", _time_scale))
				_game_min_per_sec = float(data.get("game_min_per_sec", _game_min_per_sec))
				_paused = _time_scale <= 0.0
				_refresh_speed_label()
			for a in data.get("agents", []):
				_agents[a["id"]] = a
		"speed":
			_time_scale = float(data.get("time_scale", _time_scale))
			_game_min_per_sec = float(data.get("game_min_per_sec", _game_min_per_sec))
			_paused = bool(data.get("paused", _time_scale <= 0.0))
			_refresh_speed_label()
			_log("World speed: %s" % ("PAUSED" if _paused else "%sx" % str(_time_scale)))
		"event":
			_on_event(data.get("event", {}))
		"npc_reply":
			var who: String = data.get("agent_name", "")
			if who == "":
				_log(data.get("text", ""))
			else:
				_log("%s (to you): \"%s\"" % [who, data.get("text", "")])
		"divine_result":
			var nm: String = data.get("agent_name", "")
			if nm == "":
				_log(data.get("reaction", "(the whisper fades)"))
			else:
				_log("%s [%s]: \"%s\"" % [nm, data.get("outcome", "?"), data.get("reaction", "")])
		"subjective":
			_subjective = data


func _on_event(evt: Dictionary) -> void:
	match evt.get("kind", ""):
		"dialogue":
			_log("%s -> %s: \"%s\"" % [evt.get("speaker_name", "?"), evt.get("listener_name", "?"), evt.get("text", "")])
		"death":
			_log("** %s has died: %s **" % [evt.get("name", "?"), evt.get("cause", "")])


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	# while typing in any text field, keys belong to it (Esc just unfocuses)
	var focused := get_viewport().gui_get_focus_owner()
	if focused is LineEdit:
		if event.keycode == KEY_ESCAPE:
			focused.release_focus()
		return
	match event.keycode:
		KEY_ESCAPE:
			_toggle_settings()
		KEY_EQUAL, KEY_KP_ADD:          # '=' shares the physical '+' key
			_change_speed(1)
		KEY_MINUS, KEY_KP_SUBTRACT:
			_change_speed(-1)
		KEY_SPACE:
			_toggle_pause()
		KEY_R:
			_cycle_weather()
		KEY_L:
			_toggle_lighting()
		KEY_V:
			_show_plates = not _show_plates
			_log("Nameplates: " + ("on" if _show_plates else "off"))
		KEY_M:
			_show_minimap = not _show_minimap
			_log("Minimap: " + ("on" if _show_minimap else "off"))


func _handle_input(delta: float) -> void:
	if _player_id == "" or _settings_open:
		return
	# don't drive the character while typing in the chat box
	if _chat_input and _chat_input.has_focus():
		return
	var dir := Vector2.ZERO
	if Input.is_key_pressed(KEY_W): dir.y -= 1
	if Input.is_key_pressed(KEY_S): dir.y += 1
	if Input.is_key_pressed(KEY_A): dir.x -= 1
	if Input.is_key_pressed(KEY_D): dir.x += 1
	if dir.x != 0.0:
		_player_facing = -1 if dir.x < 0.0 else 1
	if dir != Vector2.ZERO:
		_player_pos += dir.normalized() * MOVE_SPEED * delta
	_send_accum += delta
	if _send_accum >= SEND_INTERVAL:
		_send_accum = 0.0
		_send({"type": "player_move", "id": _player_id, "x": _player_pos.x, "y": _player_pos.y})
	# press O to see through the eyes of the nearest villager (toggle)
	var o := Input.is_key_pressed(KEY_O)
	if o and not _o_down:
		_observe_nearest()
	_o_down = o


## Id of the closest living villager to the player (any range), or "".
func _nearest_alive_agent() -> String:
	var best_id := ""
	var best_d := 1.0e9
	for id in _agents.keys():
		var a: Dictionary = _agents[id]
		if not a.get("alive", true):
			continue
		var d: float = Vector2(a.get("x", 0.0) - _player_pos.x, a.get("y", 0.0) - _player_pos.y).length()
		if d < best_d:
			best_d = d
			best_id = id
	return best_id


func _observe_nearest() -> void:
	var best_id := _nearest_alive_agent()
	if best_id == "":
		return
	if _observe_id == best_id:
		_observe_id = ""
		_subjective = {}
		_send({"type": "stop_observe"})
	else:
		_observe_id = best_id
		_send({"type": "observe", "agent_id": best_id})


## Overlays only. The world (tiles, sprites, lamps) is drawn on _world_node in a
## CanvasLayer below, so CanvasModulate / PointLight2D dim the world but not these.
func _draw() -> void:
	var font := ThemeDB.fallback_font
	_draw_vignette()
	_draw_weather()
	if _subjective.is_empty():
		if _show_minimap:
			_draw_minimap(font)
		if _show_plates:
			_draw_inspect_card(font)
	_draw_subjective(font)
	_draw_hud(font)


## A soft panel with a thin edge and top highlight, used across the HUD.
func _panel(r: Rect2, fill: Color = UI_INK, edge: Color = UI_EDGE) -> void:
	draw_rect(r, fill, true)
	draw_rect(r, edge, false, 1.0)
	draw_rect(Rect2(r.position + Vector2(1, 1), Vector2(r.size.x - 2, 1)), Color(1, 1, 1, 0.06), true)


## A soft edge-darkening frame over the world (above tiles, below HUD text).
func _draw_vignette() -> void:
	if _vignette_tex == null:
		return
	draw_texture_rect(_vignette_tex, Rect2(Vector2.ZERO, get_viewport_rect().size), false)


## The world, drawn on the modulated/lit layer.
func _draw_world() -> void:
	if _world_node == null:
		return
	var font := ThemeDB.fallback_font
	# grass ground covering the viewport (one tile per 2 world units), with
	# per-cell mottling and scattered tufts so it stops reading as a flat grid
	var gt := 2
	var cx := int(round(_cam.x / gt)) * gt
	var cy := int(round(_cam.y / gt)) * gt
	for gx in range(cx - 40, cx + 42, gt):
		for gy in range(cy - 30, cy + 32, gt):
			var h := _cell_hash(gx, gy)
			var g := 0.98 + h * 0.04                       # very subtle mottling (no checkerboard)
			_ltile(L_GRASS, world_to_screen(gx, gy), SCALE * 2 + 2, Color(g, g, g))
			if h > 0.82:                                    # a tuft of taller grass here and there
				_ltile(L_GRASS2, world_to_screen(gx + 0.6, gy + 0.5), SCALE * 2 + 2)
	# stone paths radiating from the square hub
	var sq := _find_loc("square")
	if not sq.is_empty():
		for loc in _locations:
			if loc.get("id", "") == "square" or loc.get("kind", "") == "home":
				continue
			var ax: float = sq.get("x", 0.0)
			var ay: float = sq.get("y", 0.0)
			var bx: float = loc.get("x", 0.0)
			var by: float = loc.get("y", 0.0)
			var n := int(Vector2(bx - ax, by - ay).length() / 1.4) + 1
			for k in range(n + 1):
				var t := float(k) / float(n)
				_ltile(L_DIRT, world_to_screen(ax + (bx - ax) * t, ay + (by - ay) * t), SCALE * 2.0, Color(1, 1, 1).lerp(Color(0.88, 0.82, 0.72), _cell_hash(int((ax + (bx - ax) * t) * 2.0), int((ay + (by - ay) * t) * 2.0)) * 0.35))
	# crop field patches, then buildings (top-down = roofs)
	for loc in _locations:
		var p := world_to_screen(loc["x"], loc["y"])
		var kind: String = loc.get("kind", "")
		match kind:
			"field":
				for dx in [-2, 0, 2]:
					for dy in [-2, 0, 2]:
						_tile(_sheet, T_FIELD, world_to_screen(loc["x"] + dx, loc["y"] + dy), SCALE * 2 + 2)
			"well":
				_tile(_sheet, T_STONE, p, SCALE * 1.7)
				_tile(_sheet, T_WATER, p, SCALE * 0.9)
			"square":
				for dx in [-1.5, 0.0, 1.5]:
					for dy in [-1.0, 1.0]:
						_tile(_sheet, T_STONE, world_to_screen(loc["x"] + dx, loc["y"] + dy), SCALE * 1.6)
			"gate":
				_tile(_sheet, T_ROCK, p, SCALE * 1.8)
			_:
				var r: Vector2i = ROOF.get(kind, ROOF["home"])
				_shadow(world_to_screen(loc["x"], loc["y"] + 1.15), SCALE * 4.6, SCALE * 1.4)
				for dx in [-1.2, 0.0, 1.2]:
					for dy in [-0.9, 0.9]:
						# front (lower) row sits in the building's own shadow -> darker,
						# giving a flat roof cluster a bit of solid, 3D weight
						var sh := 1.0 if dy < 0.0 else 0.68
						_tile(_sheet, r, world_to_screen(loc["x"] + dx, loc["y"] + dy), SCALE * 1.5 + 2, Color(sh, sh, sh))
		if kind != "field":
			_label(_world_node, font, p + Vector2(-40, 28), loc.get("name", ""), 9, Color(0.9, 0.88, 0.78), HORIZONTAL_ALIGNMENT_CENTER, 80)
	# decorative scenery
	_draw_props()

	# NPCs (character sprites), drawn back-to-front by screen-y so nearer
	# villagers overlap farther ones (a cheap but effective depth cue).
	var order: Array = _agents.keys()
	order.sort_custom(func(i, j):
		var pi: Vector2 = _render_pos.get(i, world_to_screen(_agents[i].get("x", 0), _agents[i].get("y", 0)))
		var pj: Vector2 = _render_pos.get(j, world_to_screen(_agents[j].get("x", 0), _agents[j].get("y", 0)))
		return pi.y < pj.y)
	var bubbles: Array = []
	for id in order:
		var a: Dictionary = _agents[id]
		var p: Vector2 = _render_pos.get(id, world_to_screen(a.get("x", 0), a.get("y", 0)))
		var alive: bool = a.get("alive", true)
		if alive:
			_shadow(p + Vector2(0, SCALE * 0.55), SCALE * 1.5, SCALE * 0.55)
		if a.get("wanted", false):
			_world_node.draw_arc(p - Vector2(0, SCALE * 0.3), SCALE * 1.4, 0, TAU, 20, Color(0.85, 0.3, 0.3), 2.0)
		# pulsing golden ring under the villager the chat box will address
		if alive and id == _talk_target:
			var pulse := 0.5 + 0.5 * sin(_wx_time * 4.0)
			_world_node.draw_set_transform(p + Vector2(0, SCALE * 0.5), 0.0, Vector2(1.0, 0.5))
			_world_node.draw_arc(Vector2.ZERO, SCALE * (0.9 + 0.12 * pulse), 0, TAU, 28,
				Color(UI_GOLD.r, UI_GOLD.g, UI_GOLD.b, 0.35 + 0.45 * pulse), 2.5)
			_world_node.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		var vrole: String = a.get("role", "")
		var vdir := 2                                   # front/down when idle
		if _moving.get(id, false):
			vdir = 1 if int(_facing.get(id, 1)) < 0 else 3
		var bob := (sin(_wx_time * 9.0 + p.x * 0.05) * SCALE * 0.08) if _moving.get(id, false) else 0.0
		if alive:
			_villager_draw(vrole, p - Vector2(0, bob), vdir, SCALE * 3.0)
		else:
			_villager_draw(vrole, p, 2, SCALE * 3.0, Color(1, 1, 1, 0.45))
		var nm: String = a.get("name", "") if alive else str(a.get("name", "")) + " +"
		_label(_world_node, font, p + Vector2(-40, -SCALE * 1.5), nm, 10, Color(0.96, 0.96, 1.0), HORIZONTAL_ALIGNMENT_CENTER, 80)
		var say: String = a.get("say", "")
		if say != "":
			bubbles.append([p, say])
	# speech bubbles last so they sit above every sprite
	for b in bubbles:
		_draw_bubble(font, b[0], b[1])

	# players (silver knight sprite)
	for pl in _players:
		var p := world_to_screen(pl.get("x", 0), pl.get("y", 0))
		_shadow(p + Vector2(0, SCALE * 0.55), SCALE * 1.6, SCALE * 0.6)
		var pdir := 2
		if pl.get("id", "") == _player_id:
			pdir = 1 if _player_facing < 0 else 3
		_villager_draw("Player", p, pdir, SCALE * 3.1)
		_label(_world_node, font, p + Vector2(-40, -SCALE * 1.5), pl.get("name", "You"), 10, Color(0.6, 0.92, 1.0), HORIZONTAL_ALIGNMENT_CENTER, 80)

	# In immediate mode, the flat tint + glow fallback is drawn here on the world layer.
	if _lighting == "immediate":
		_draw_immediate_lighting()


func _find_loc(id: String) -> Dictionary:
	for loc in _locations:
		if loc.get("id", "") == id:
			return loc
	return {}


func _draw_props() -> void:
	var i := 0
	for pr in _props:
		var p := world_to_screen(pr.get("x", 0), pr.get("y", 0))
		match pr.get("kind", ""):
			"tree":
				_shadow(p + Vector2(0, SCALE * 0.7), SCALE * 1.7, SCALE * 0.6)
				_tile(_sheet, T_TREE if i % 2 == 0 else T_PINE, p - Vector2(0, SCALE * 0.4), SCALE * 2.6)
			"rock":
				_tile(_sheet, T_ROCK, p, SCALE * 1.4)
			"pond":
				for dx in [-3, -1, 1, 3]:
					for dy in [-2, 0, 2]:
						_tile(_sheet, T_WATER, world_to_screen(pr.get("x", 0) + dx, pr.get("y", 0) + dy), SCALE * 2 + 2)
		i += 1


## Immediate-mode fallback lighting (press L to compare): a flat ambient tint plus
## stacked translucent glow circles, drawn on the world layer.
func _draw_immediate_lighting() -> void:
	if _world_node == null:
		return
	var amb := _ambient_at(_clock_hours())
	if amb.a > 0.003:
		_world_node.draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size), amb, true)
	var nightness: float = clamp((amb.a - 0.05) / 0.5, 0.0, 1.0)
	if nightness <= 0.01:
		return
	var t := _wx_time
	for L in _light_sources():
		var amp: float = L["amp"]
		var sp: float = L["sp"]
		var fl: float = max(0.4, float(L["base"]) * (1.0 + amp * sin(t * sp + float(L["x"])) + amp * 0.5 * sin(t * sp * 2.3 + float(L["y"]))))
		var center := world_to_screen(L["x"], L["y"])
		var R: float = float(L["r"]) * SCALE * fl
		var col: Color = L["c"]
		var peak: float = 0.5 * nightness * fl
		var rings := 6
		for i in range(rings):
			var f: float = float(i) / float(rings)
			var rr: float = R * (1.0 - f * 0.85)
			var a: float = peak * (0.10 + 0.9 * f) * 0.42
			_world_node.draw_circle(center, rr, Color(col.r, col.g, col.b, a))


# --- real 2D lighting prototype ---------------------------------------------

## Build the world CanvasLayer, its CanvasModulate, and the player's vision light.
func _build_world_layer() -> void:
	_world_layer = CanvasLayer.new()
	_world_layer.layer = -1
	add_child(_world_layer)
	_canvas_mod = CanvasModulate.new()
	_canvas_mod.color = Color(1, 1, 1)
	_world_layer.add_child(_canvas_mod)
	_world_node = Node2D.new()
	_world_node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_world_node.draw.connect(_draw_world)
	_world_layer.add_child(_world_node)
	_light_tex = _make_light_texture()
	_shadow_tex = _make_blob_texture(Color(0, 0, 0, 0.42), Color(0, 0, 0, 0))
	_vignette_tex = _make_vignette_texture()
	_player_light = PointLight2D.new()
	_player_light.texture = _light_tex
	_player_light.color = Color(1.0, 0.96, 0.86)
	_player_light.energy = 0.0
	_player_light.texture_scale = 1.5   # soft vision bubble around the player
	_world_node.add_child(_player_light)


## A soft round light cookie built at runtime, so no art asset is needed.
func _make_light_texture() -> Texture2D:
	var g := Gradient.new()
	g.set_offset(0, 0.0)
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_offset(1, 1.0)
	g.set_color(1, Color(1, 1, 1, 0))
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 256
	tex.height = 256
	return tex


## A soft radial blob fading `inner` -> `outer`, used for drop shadows.
func _make_blob_texture(inner: Color, outer: Color) -> Texture2D:
	var g := Gradient.new()
	g.set_offset(0, 0.0); g.set_color(0, inner)
	g.set_offset(1, 1.0); g.set_color(1, outer)
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 128
	tex.height = 128
	return tex


## Transparent center darkening toward the corners, for a gentle vignette frame.
func _make_vignette_texture() -> Texture2D:
	var g := Gradient.new()
	g.set_offset(0, 0.0); g.set_color(0, Color(0, 0, 0, 0))
	g.set_offset(1, 0.62); g.set_color(1, Color(0, 0, 0, 0))
	g.add_point(0.86, Color(0, 0, 0, 0.16))
	g.add_point(1.0, Color(0.02, 0.02, 0.05, 0.42))
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 1.0)
	tex.width = 512
	tex.height = 512
	return tex


## Blit a squashed blob shadow on the ground under a sprite at `center`.
func _shadow(center: Vector2, w: float, h: float) -> void:
	if _world_node == null or _shadow_tex == null:
		return
	_world_node.draw_texture_rect(_shadow_tex, Rect2(center - Vector2(w, h) * 0.5, Vector2(w, h)), false)


## Draw text with a dark outline so labels stay legible over any ground tile.
func _label(node: CanvasItem, font: Font, pos: Vector2, text: String, size: int,
		col: Color, halign: int = HORIZONTAL_ALIGNMENT_LEFT, width: float = -1) -> void:
	var o := Color(0, 0, 0, 0.75)
	for d in [Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1)]:
		node.draw_string(font, pos + d, text, halign, width, size, o)
	node.draw_string(font, pos, text, halign, width, size, col)


## One warm lamp per light source; energy is driven by _update_lighting.
func _build_loc_lights() -> void:
	for src in _light_sources():
		var pl := PointLight2D.new()
		pl.texture = _light_tex
		pl.color = src["c"]
		pl.energy = 0.0
		pl.texture_scale = max(0.25, (float(src["r"]) * SCALE * 2.0) / 256.0)
		pl.position = world_to_screen(src["x"], src["y"])
		pl.set_meta("src", src)
		_world_node.add_child(pl)
		_loc_lights.append(pl)
	_loc_lights_built = true


func _toggle_lighting() -> void:
	_lighting = "immediate" if _lighting == "lights2d" else "lights2d"
	_log("Lighting: " + _lighting + ("  (real Light2D)" if _lighting == "lights2d" else "  (immediate glow)"))


## 0 = full day, 1 = deep night; smooth dawn/dusk shoulders.
func _night_amount(h: float) -> float:
	if h >= 21.0 or h < 5.0:
		return 1.0
	if h >= 8.0 and h <= 17.5:
		return 0.0
	if h < 8.0:
		return clamp((8.0 - h) / 3.0, 0.0, 1.0)
	return clamp((h - 17.5) / 3.5, 0.0, 1.0)


## Day/night multiply for the world: a warm midday, golden dusk, and cool blue
## night, so time-of-day reads at a glance. Never floors fully dark (village stays
## legible); lamps + the player light do the rest at night.
func _sky_modulate(h: float) -> Color:
	var ramp := [
		[0.0, Color(0.34, 0.38, 0.58)],    # deep night
		[5.0, Color(0.38, 0.42, 0.60)],
		[6.6, Color(0.86, 0.64, 0.56)],    # dawn, warm
		[8.0, Color(1.00, 0.98, 0.93)],    # morning
		[12.0, Color(1.03, 1.01, 0.95)],   # midday, bright and slightly warm
		[16.5, Color(1.01, 0.95, 0.85)],   # afternoon gold
		[18.6, Color(0.96, 0.62, 0.44)],   # dusk, golden
		[20.0, Color(0.54, 0.44, 0.56)],   # twilight
		[21.6, Color(0.36, 0.40, 0.58)],   # night
		[24.0, Color(0.34, 0.38, 0.58)],
	]
	for i in range(ramp.size() - 1):
		var a: Array = ramp[i]
		var b: Array = ramp[i + 1]
		if h >= float(a[0]) and h <= float(b[0]):
			var t: float = (h - float(a[0])) / max(0.0001, float(b[0]) - float(a[0]))
			return (a[1] as Color).lerp(b[1] as Color, t)
	return ramp[0][1]


func _update_lighting(_delta: float) -> void:
	if _world_layer == null:
		return
	var on := _lighting == "lights2d"
	var h := _clock_hours()
	var n := _night_amount(h)
	_canvas_mod.color = _sky_modulate(h) if on else Color(1, 1, 1)
	var t := _wx_time
	for pl in _loc_lights:
		var src: Dictionary = pl.get_meta("src")
		pl.position = world_to_screen(src["x"], src["y"])   # follow the camera
		if not on:
			pl.energy = 0.0
			continue
		var amp: float = src["amp"]
		var sp: float = src["sp"]
		var fl: float = 1.0 + amp * sin(t * sp + float(src["x"])) + amp * 0.5 * sin(t * sp * 2.3 + float(src["y"]))
		pl.energy = n * float(src["base"]) * 1.25 * max(0.3, fl)
	if _player_light:
		_player_light.position = world_to_screen(_player_pos.x, _player_pos.y)
		_player_light.energy = lerp(0.0, 0.7, n) if on else 0.0


func _clock_hours() -> float:
	if _force_hour >= 0.0:
		return _force_hour
	if not _clock.is_empty():
		var s := str(_clock.get("hhmm", ""))
		if ":" in s:
			var parts := s.split(":")
			return float(parts[0]) + float(parts[1]) / 60.0
		match _clock.get("part_of_day", ""):
			"night": return 1.0
			"morning": return 6.5
			"evening": return 19.0
	return 13.0


func _ambient_at(h: float) -> Color:
	var pts := [
		[0.0, Color(0.031, 0.055, 0.180, 0.62)],
		[5.0, Color(0.063, 0.086, 0.227, 0.52)],
		[6.3, Color(0.470, 0.306, 0.212, 0.34)],
		[7.2, Color(0.824, 0.647, 0.439, 0.13)],
		[8.5, Color(0.0, 0.0, 0.0, 0.03)],
		[11.0, Color(0.0, 0.0, 0.0, 0.0)],
		[16.0, Color(0.0, 0.0, 0.0, 0.0)],
		[17.8, Color(0.588, 0.361, 0.173, 0.16)],
		[19.0, Color(0.494, 0.227, 0.086, 0.30)],
		[20.0, Color(0.180, 0.149, 0.290, 0.45)],
		[21.2, Color(0.055, 0.078, 0.220, 0.56)],
		[24.0, Color(0.031, 0.055, 0.180, 0.62)],
	]
	for i in range(pts.size() - 1):
		var a: Array = pts[i]
		var b: Array = pts[i + 1]
		if h >= float(a[0]) and h <= float(b[0]):
			var t: float = (h - float(a[0])) / max(0.0001, float(b[0]) - float(a[0]))
			return (a[1] as Color).lerp(b[1] as Color, t)
	return pts[0][1]


func _light_sources() -> Array:
	var out: Array = []
	for l in _locations:
		match l.get("kind", ""):
			"smithy": out.append({"x": l["x"], "y": l["y"] - 0.3, "r": 5.5, "c": Color(1.0, 0.55, 0.18), "amp": 0.35, "sp": 9.0, "base": 1.0})
			"tavern": out.append({"x": l["x"], "y": l["y"], "r": 5.0, "c": Color(1.0, 0.77, 0.38), "amp": 0.14, "sp": 5.0, "base": 0.9})
			"square": out.append({"x": l["x"], "y": l["y"], "r": 4.6, "c": Color(1.0, 0.82, 0.59), "amp": 0.10, "sp": 4.0, "base": 0.85})
			"well": out.append({"x": l["x"], "y": l["y"], "r": 3.6, "c": Color(1.0, 0.80, 0.55), "amp": 0.10, "sp": 4.0, "base": 0.7})
			"gate": out.append({"x": l["x"], "y": l["y"], "r": 3.6, "c": Color(1.0, 0.78, 0.55), "amp": 0.12, "sp": 4.0, "base": 0.7})
			"shop": out.append({"x": l["x"], "y": l["y"], "r": 3.8, "c": Color(1.0, 0.78, 0.47), "amp": 0.12, "sp": 5.0, "base": 0.7})
			"home": out.append({"x": l["x"], "y": l["y"], "r": 3.0, "c": Color(1.0, 0.71, 0.43), "amp": 0.10, "sp": 3.0, "base": 0.55})
	return out


func _ensure_wx(size: Vector2) -> void:
	if _rain.is_empty():
		for i in range(320):
			_rain.append({"x": randf() * size.x, "y": randf() * size.y, "l": 10.0 + randf() * 12.0, "sp": 9.0 + randf() * 7.0})
	if _snow.is_empty():
		for i in range(220):
			_snow.append({"x": randf() * size.x, "y": randf() * size.y, "r": 1.0 + randf() * 2.2, "sp": 0.7 + randf() * 1.3, "sw": 0.6 + randf() * 1.2, "ph": randf() * TAU, "a": 0.5 + randf() * 0.5})


func _update_weather(delta: float) -> void:
	if _wx_mode == "auto":
		if _wx_time > _wx_next:
			var r := randf()
			_wx_target = "clear" if r < 0.55 else ("rain" if r < 0.85 else "snow")
			_wx_next = _wx_time + 22.0 + randf() * 40.0
	else:
		_wx_target = _wx_mode
	if _wx_type != _wx_target:
		_wx_intensity -= delta * 0.45
		if _wx_intensity <= 0.0:
			_wx_intensity = 0.0
			_wx_type = _wx_target
	else:
		var tgt := 0.0 if _wx_type == "clear" else 1.0
		var dir := 1.0 if tgt > _wx_intensity else -1.0
		_wx_intensity = clamp(_wx_intensity + dir * delta * 0.45, 0.0, 1.0)


func _cycle_weather() -> void:
	var order := ["auto", "clear", "rain", "snow"]
	var idx := order.find(_wx_mode)
	_wx_mode = order[(idx + 1) % order.size()]
	_wx_next = 0.0
	_log("Weather: " + _wx_mode)


func _draw_weather() -> void:
	var size := get_viewport_rect().size
	_ensure_wx(size)
	var intensity := _wx_intensity
	if intensity <= 0.01 or _wx_type == "clear":
		return
	var dt := get_process_delta_time()
	var step := dt * 60.0
	if _wx_type == "rain":
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.21, 0.25, 0.34, 0.16 * intensity), true)
		var wind := 2.6
		var n := int(_rain.size() * intensity)
		for i in range(n):
			var d: Dictionary = _rain[i]
			var x: float = d["x"]
			var y: float = d["y"]
			draw_line(Vector2(x, y), Vector2(x - wind * 1.2, y - float(d["l"])), Color(0.75, 0.80, 0.90, 0.5 * intensity), 1.1)
			d["y"] = y + float(d["sp"]) * step
			d["x"] = x + wind * step
			if float(d["y"]) > size.y:
				d["y"] = -10.0
				d["x"] = randf() * size.x
			if float(d["x"]) > size.x:
				d["x"] = float(d["x"]) - size.x
	elif _wx_type == "snow":
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.84, 0.88, 0.94, 0.10 * intensity), true)
		var n := int(_snow.size() * intensity)
		for i in range(n):
			var f: Dictionary = _snow[i]
			var sway: float = sin(_wx_time * float(f["sw"]) + float(f["ph"])) * 8.0
			draw_circle(Vector2(float(f["x"]) + sway, float(f["y"])), float(f["r"]), Color(0.93, 0.95, 0.98, float(f["a"]) * intensity))
			f["y"] = float(f["y"]) + float(f["sp"]) * step
			f["x"] = float(f["x"]) + 0.3 * step
			if float(f["y"]) > size.y:
				f["y"] = -6.0
				f["x"] = randf() * size.x
			if float(f["x"]) > size.x:
				f["x"] = float(f["x"]) - size.x


func _draw_subjective(font: Font) -> void:
	if _subjective.is_empty():
		return
	var v := _subjective
	var vp := get_viewport_rect().size
	var w := 300.0
	var x := vp.x - w - 10.0
	var y := 60.0
	draw_rect(Rect2(x, y, w, 280), Color(0.05, 0.05, 0.08, 0.9), true)
	draw_rect(Rect2(x, y, w, 280), Color(0.6, 0.55, 0.35), false, 1.0)
	var ag: Dictionary = v.get("agent", {})
	draw_string(font, Vector2(x + 10, y + 20), "Through the eyes of " + str(ag.get("name", "?")),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.9, 0.85, 0.6))
	draw_string(font, Vector2(x + 10, y + 38), str(v.get("where", "")) + " - " + str(v.get("mood", "")),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.75, 0.8, 0.85))
	draw_string(font, Vector2(x + 10, y + 56), "Aim: " + str(v.get("goal", "")).substr(0, 40),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.8, 0.8, 0.85))
	var yy := y + 78.0
	draw_string(font, Vector2(x + 10, yy), "I see:", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.6, 0.6, 0.65))
	yy += 15
	for s in v.get("seen", []):
		draw_string(font, Vector2(x + 16, yy), "- %s (%s), %s" % [s.get("name", "?"), s.get("role", ""), s.get("feel", "")],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.85, 0.85, 0.9))
		yy += 14
	yy += 6
	draw_string(font, Vector2(x + 10, yy), "On my mind:", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.6, 0.6, 0.65))
	yy += 15
	for m in v.get("memories", []):
		draw_string(font, Vector2(x + 16, yy), "- " + str(m.get("text", "")).substr(0, 40),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.8, 0.8, 0.85))
		yy += 13


func _draw_bubble(font: Font, p: Vector2, text: String) -> void:
	if _world_node == null:
		return
	var t := text.substr(0, 42)
	var w := float(t.length()) * 6.0 + 10.0
	var box := Rect2(p + Vector2(10, -28), Vector2(w, 18))
	_world_node.draw_rect(box, Color(0.05, 0.05, 0.07, 0.85), true)
	_world_node.draw_rect(box, Color(0.6, 0.6, 0.65), false, 1.0)
	_world_node.draw_string(font, box.position + Vector2(5, 13), t, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.9, 0.9, 0.95))


## Corner minimap: locations coloured by kind, living villagers as dots, the
## player highlighted. Toggle with M.
func _draw_minimap(font: Font) -> void:
	if _locations.is_empty():
		return
	var vp := get_viewport_rect().size
	var sz := 156.0
	var rect := Rect2(vp.x - sz - 10.0, 10.0, sz, sz)
	_panel(rect)
	draw_string(font, rect.position + Vector2(8, 14), "Oakhollow", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, UI_GOLD)
	var minx := 1.0e9
	var miny := 1.0e9
	var maxx := -1.0e9
	var maxy := -1.0e9
	for loc in _locations:
		minx = min(minx, float(loc.get("x", 0.0)))
		maxx = max(maxx, float(loc.get("x", 0.0)))
		miny = min(miny, float(loc.get("y", 0.0)))
		maxy = max(maxy, float(loc.get("y", 0.0)))
	minx -= 4.0; miny -= 4.0; maxx += 4.0; maxy += 4.0
	var spanx := maxf(1.0, maxx - minx)
	var spany := maxf(1.0, maxy - miny)
	var inner := Rect2(rect.position + Vector2(8.0, 22.0), rect.size - Vector2(16.0, 30.0))
	for loc in _locations:
		var c: Color = KIND_COLORS.get(loc.get("kind", ""), Color(0.6, 0.6, 0.65))
		var mx := inner.position.x + (float(loc.get("x", 0.0)) - minx) / spanx * inner.size.x
		var my := inner.position.y + (float(loc.get("y", 0.0)) - miny) / spany * inner.size.y
		draw_rect(Rect2(mx - 1.5, my - 1.5, 3.0, 3.0), c, true)
	for id in _agents.keys():
		var a: Dictionary = _agents[id]
		if not a.get("alive", true):
			continue
		var mx := inner.position.x + (float(a.get("x", 0.0)) - minx) / spanx * inner.size.x
		var my := inner.position.y + (float(a.get("y", 0.0)) - miny) / spany * inner.size.y
		var col := Color(0.80, 0.82, 0.88)
		if a.get("wanted", false):
			col = Color(0.9, 0.35, 0.35)
		if id == _talk_target:
			col = UI_GOLD
		draw_circle(Vector2(mx, my), 1.7, col)
	var px := inner.position.x + (_player_pos.x - minx) / spanx * inner.size.x
	var py := inner.position.y + (_player_pos.y - miny) / spany * inner.size.y
	draw_circle(Vector2(px, py), 2.6, Color(0.55, 0.92, 1.0))
	draw_arc(Vector2(px, py), 4.2, 0.0, TAU, 16, Color(0.55, 0.92, 1.0, 0.6), 1.0)


## Inspect card for the nearest villager (name, role, activity, health, coin)
## plus a floating "press Enter to speak" tag when in range. Toggle with V.
func _draw_inspect_card(font: Font) -> void:
	if _talk_target == "" or not _agents.has(_talk_target):
		return
	var a: Dictionary = _agents[_talk_target]
	if not a.get("alive", true):
		return
	var vp := get_viewport_rect().size
	var dist := Vector2(float(a.get("x", 0.0)) - _player_pos.x, float(a.get("y", 0.0)) - _player_pos.y).length()
	if dist <= TALK_RANGE:
		var sp: Vector2 = _render_pos.get(_talk_target, world_to_screen(a.get("x", 0), a.get("y", 0)))
		var tag := "Press Enter to speak"
		var tw := float(tag.length()) * 6.0 + 14.0
		var tr := Rect2(sp + Vector2(-tw * 0.5, -SCALE * 2.3), Vector2(tw, 18.0))
		_panel(tr, Color(0.06, 0.06, 0.09, 0.92))
		draw_string(font, tr.position + Vector2(7, 13), tag, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, UI_GOLD)
	var w := 196.0
	var x := vp.x - w - 10.0
	var y := 176.0 if _show_minimap else 10.0
	var h := 92.0
	_panel(Rect2(x, y, w, h))
	var nm := str(a.get("name", "?"))
	draw_string(font, Vector2(x + 10, y + 18), nm, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.96, 0.96, 1.0))
	var sub_t := "%s  -  %s" % [str(a.get("role", "")), str(a.get("activity", ""))]
	draw_string(font, Vector2(x + 10, y + 34), sub_t, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.72, 0.78, 0.85))
	var hp := clampf(float(a.get("health", 1.0)), 0.0, 1.0)
	var bx := x + 10.0
	var by := y + 44.0
	var bw := w - 20.0
	draw_rect(Rect2(bx, by, bw, 7.0), Color(0, 0, 0, 0.45), true)
	draw_rect(Rect2(bx, by, bw * hp, 7.0), Color(0.85, 0.3, 0.3).lerp(Color(0.45, 0.8, 0.4), hp), true)
	draw_rect(Rect2(bx, by, bw, 7.0), Color(0, 0, 0, 0.5), false, 1.0)
	draw_string(font, Vector2(bx, by + 20), "Health %d%%" % int(round(hp * 100.0)), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.8, 0.82, 0.88))
	draw_string(font, Vector2(bx + 96, by + 20), "%d coin" % int(a.get("coin", 0)), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, UI_GOLD)
	if a.get("wanted", false):
		draw_string(font, Vector2(x + w - 58, y + 18), "WANTED", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.92, 0.36, 0.36))


func _draw_hud(font: Font) -> void:
	var vp := get_viewport_rect().size
	_panel(Rect2(10, 10, 320, 46))
	draw_circle(Vector2(24, 24), 4.0, Color(0.45, 0.82, 0.5) if _connected else Color(0.85, 0.45, 0.4))
	draw_string(font, Vector2(36, 27), "Realmweave - Oakhollow", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, UI_GOLD)
	var stamp := "Connecting..."
	if not _clock.is_empty():
		stamp = "Day %d  %s  %s  (%s)" % [_clock.get("day_index", 0), _clock.get("day_name", ""), _clock.get("hhmm", ""), _clock.get("part_of_day", "")]
	draw_string(font, Vector2(20, 47), stamp, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.75, 0.8, 0.85))
	var spd := "PAUSED" if _paused else "%sx  (%.0f min/s)" % [str(_time_scale), _game_min_per_sec]
	var spd_col := Color(0.95, 0.6, 0.5) if _paused else Color(0.6, 0.85, 0.7)
	draw_string(font, Vector2(234, 47), spd, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, spd_col)
	var hint := "WASD move   Enter talk   O eyes   V plates   M map   R weather   L light   -/+ speed   Space pause   Esc menu"
	var hy := vp.y - 150.0
	_panel(Rect2(10, hy, vp.x - 20, 20))
	draw_string(font, Vector2(18, hy + 14), hint, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.62, 0.66, 0.74))
	_panel(Rect2(10, vp.y - 126, vp.x - 20, 116))
	var lines := _events.slice(max(0, _events.size() - 7), _events.size())
	var n := lines.size()
	var y := vp.y - 112.0
	for i in range(n):
		var fade := 0.5 + 0.5 * (float(i + 1) / float(max(1, n)))
		draw_string(font, Vector2(20, y), lines[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.82, 0.83, 0.88, fade))
		y += 16


func _log(msg: String) -> void:
	_events.append(msg)
	if _events.size() > 40:
		_events = _events.slice(_events.size() - 40, _events.size())
	print("[Realmweave] ", msg)
