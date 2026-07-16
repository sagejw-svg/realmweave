extends Node2D
## Realmweave 2D client.
##
## Connects to the Python backend over WebSocket, receives the authoritative
## world (locations) and a stream of snapshots (agent positions, state, speech)
## plus discrete events (dialogue, deaths). Renders everything top-down in 2D
## and lets the local player walk around with WASD and broadcast their position.
##
## Rendering is done immediately in _draw() using the fallback font so the whole
## client is a single self-contained script - easy to read, easy to replace with
## real sprites/tilemaps later.

const SCALE := 16.0                 # pixels per world unit
const ORIGIN := Vector2(60, 90)     # screen offset for the map origin
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
var _players: Array = []
var _clock: Dictionary = {}
var _events: Array = []             # recent event log (strings)

var _player_id := ""
var _player_pos := Vector2(32, 24)
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


func _ready() -> void:
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
	_build_settings_ui()
	set_process(true)


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
	return ORIGIN + Vector2(x, y) * SCALE


func _process(delta: float) -> void:
	_poll_socket()
	_handle_input(delta)
	# smooth agent positions toward their latest reported location
	for id in _agents.keys():
		var a: Dictionary = _agents[id]
		var target := world_to_screen(a.get("x", 0.0), a.get("y", 0.0))
		if not _render_pos.has(id):
			_render_pos[id] = target
		_render_pos[id] = (_render_pos[id] as Vector2).lerp(target, clamp(delta * 8.0, 0, 1))
	queue_redraw()


func _poll_socket() -> void:
	_ws.poll()
	var state := _ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _connected:
			_connected = true
			_log("Connected to " + _server_url)
			_send({"type": "player_join", "name": "James"})
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


func _observe_nearest() -> void:
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
	if best_id == "":
		return
	if _observe_id == best_id:
		_observe_id = ""
		_subjective = {}
		_send({"type": "stop_observe"})
	else:
		_observe_id = best_id
		_send({"type": "observe", "agent_id": best_id})


func _draw() -> void:
	var font := ThemeDB.fallback_font
	# decorative scenery behind everything
	_draw_props()
	# locations
	for loc in _locations:
		var p := world_to_screen(loc["x"], loc["y"])
		var col: Color = KIND_COLORS.get(loc.get("kind", ""), Color(0.4, 0.4, 0.4))
		draw_rect(Rect2(p - Vector2(18, 12), Vector2(36, 24)), col.darkened(0.2), true)
		draw_rect(Rect2(p - Vector2(18, 12), Vector2(36, 24)), col, false, 1.5)
		draw_string(font, p + Vector2(-16, 20), loc.get("name", ""), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.75, 0.75, 0.8))

	# NPCs
	for id in _agents.keys():
		var a: Dictionary = _agents[id]
		var p: Vector2 = _render_pos.get(id, world_to_screen(a.get("x", 0), a.get("y", 0)))
		var alive: bool = a.get("alive", true)
		var col := Color(0.85, 0.80, 0.55) if alive else Color(0.35, 0.30, 0.30)
		draw_circle(p, AGENT_R, col)
		draw_arc(p, AGENT_R, 0, TAU, 20, Color(0.1, 0.1, 0.1), 1.5)
		draw_string(font, p + Vector2(-20, -12), a.get("name", ""), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
		if not alive:
			draw_string(font, p + Vector2(-6, 4), "x", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.BLACK)
		var say: String = a.get("say", "")
		if say != "":
			_draw_bubble(font, p, say)

	# players
	for pl in _players:
		var p := world_to_screen(pl.get("x", 0), pl.get("y", 0))
		draw_circle(p, AGENT_R + 1, Color(0.35, 0.75, 0.95))
		draw_arc(p, AGENT_R + 1, 0, TAU, 20, Color.WHITE, 1.5)
		draw_string(font, p + Vector2(-20, -12), pl.get("name", "You"), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.6, 0.9, 1.0))

	_draw_daynight()
	_draw_subjective(font)
	_draw_hud(font)


func _draw_props() -> void:
	for pr in _props:
		var p := world_to_screen(pr.get("x", 0), pr.get("y", 0))
		match pr.get("kind", ""):
			"tree":
				draw_rect(Rect2(p + Vector2(-2, -2), Vector2(4, 14)), Color(0.35, 0.25, 0.13), true)
				draw_circle(p + Vector2(0, -10), 13.0, Color(0.24, 0.42, 0.20))
				draw_circle(p + Vector2(-4, -14), 8.0, Color(0.30, 0.50, 0.25))
			"rock":
				draw_circle(p, 8.0, Color(0.42, 0.44, 0.48))
			"pond":
				draw_circle(p, 34.0, Color(0.18, 0.35, 0.44))


func _draw_daynight() -> void:
	var pod := "afternoon"
	if not _clock.is_empty():
		pod = _clock.get("part_of_day", "afternoon")
	var tint := Color(0, 0, 0, 0)
	match pod:
		"night": tint = Color(0.05, 0.09, 0.24, 0.50)
		"evening": tint = Color(0.47, 0.24, 0.08, 0.24)
		"morning": tint = Color(0.78, 0.67, 0.47, 0.10)
	if tint.a > 0.0:
		draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size), tint, true)


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
	var t := text.substr(0, 42)
	var w := float(t.length()) * 6.0 + 10.0
	var box := Rect2(p + Vector2(10, -28), Vector2(w, 18))
	draw_rect(box, Color(0.05, 0.05, 0.07, 0.85), true)
	draw_rect(box, Color(0.6, 0.6, 0.65), false, 1.0)
	draw_string(font, box.position + Vector2(5, 13), t, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.9, 0.9, 0.95))


func _draw_hud(font: Font) -> void:
	# clock panel
	draw_rect(Rect2(10, 10, 300, 40), Color(0.05, 0.05, 0.08, 0.85), true)
	var stamp := "Connecting..."
	if not _clock.is_empty():
		stamp = "Day %d  %s  %s  (%s)" % [_clock.get("day_index", 0), _clock.get("day_name", ""), _clock.get("hhmm", ""), _clock.get("part_of_day", "")]
	draw_string(font, Vector2(20, 27), "Realmweave - Oakhollow", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.9, 0.85, 0.6))
	draw_string(font, Vector2(20, 44), stamp, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.75, 0.8, 0.85))
	# speed readout
	var spd := "PAUSED" if _paused else "%sx  (%.0f min/s)" % [str(_time_scale), _game_min_per_sec]
	var spd_col := Color(0.95, 0.6, 0.5) if _paused else Color(0.6, 0.85, 0.7)
	draw_string(font, Vector2(230, 27), spd, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, spd_col)

	# event log panel (bottom)
	var vp := get_viewport_rect().size
	draw_rect(Rect2(10, vp.y - 130, vp.x - 20, 120), Color(0.05, 0.05, 0.08, 0.8), true)
	var y := vp.y - 116
	for line in _events.slice(max(0, _events.size() - 7), _events.size()):
		draw_string(font, Vector2(20, y), line, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.8, 0.8, 0.85))
		y += 16
	draw_string(font, Vector2(vp.x - 360, 27), "WASD walk · O: eyes · -/+ speed · Space pause · Esc settings",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.6, 0.6, 0.65))


func _log(msg: String) -> void:
	_events.append(msg)
	if _events.size() > 40:
		_events = _events.slice(_events.size() - 40, _events.size())
	print("[Realmweave] ", msg)
