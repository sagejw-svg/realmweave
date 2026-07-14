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
var _agents: Dictionary = {}        # id -> latest agent dict
var _render_pos: Dictionary = {}    # id -> Vector2 (smoothed screen pos)
var _players: Array = []
var _clock: Dictionary = {}
var _events: Array = []             # recent event log (strings)

var _player_id := ""
var _player_pos := Vector2(32, 24)
var _send_accum := 0.0

const KIND_COLORS := {
	"tavern": Color(0.72, 0.45, 0.20),
	"home": Color(0.35, 0.38, 0.55),
	"stable": Color(0.55, 0.42, 0.30),
	"well": Color(0.30, 0.55, 0.65),
	"square": Color(0.40, 0.50, 0.35),
	"smithy": Color(0.55, 0.30, 0.30),
	"field": Color(0.45, 0.60, 0.30),
	"gate": Color(0.50, 0.50, 0.55),
}


func _ready() -> void:
	if ProjectSettings.has_setting("network/realmweave/server_url"):
		_server_url = ProjectSettings.get_setting("network/realmweave/server_url")
	_ws.connect_to_url(_server_url)
	set_process(true)


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
			_log("Entered %s (%d locations)" % [data.get("world", {}).get("name", "?"), _locations.size()])
		"joined":
			_player_id = data.get("id", "")
			_log("You are " + _player_id)
		"snapshot":
			_clock = data.get("clock", {})
			_players = data.get("players", [])
			for a in data.get("agents", []):
				_agents[a["id"]] = a
		"event":
			_on_event(data.get("event", {}))


func _on_event(evt: Dictionary) -> void:
	match evt.get("kind", ""):
		"dialogue":
			_log("%s -> %s: \"%s\"" % [evt.get("speaker_name", "?"), evt.get("listener_name", "?"), evt.get("text", "")])
		"death":
			_log("** %s has died: %s **" % [evt.get("name", "?"), evt.get("cause", "")])


func _handle_input(delta: float) -> void:
	if _player_id == "":
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


func _draw() -> void:
	var font := ThemeDB.fallback_font
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

	_draw_hud(font)


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

	# event log panel (bottom)
	var vp := get_viewport_rect().size
	draw_rect(Rect2(10, vp.y - 130, vp.x - 20, 120), Color(0.05, 0.05, 0.08, 0.8), true)
	var y := vp.y - 116
	for line in _events.slice(max(0, _events.size() - 7), _events.size()):
		draw_string(font, Vector2(20, y), line, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.8, 0.8, 0.85))
		y += 16
	draw_string(font, Vector2(vp.x - 200, 27), "WASD to walk", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.6, 0.6, 0.65))


func _log(msg: String) -> void:
	_events.append(msg)
	if _events.size() > 40:
		_events = _events.slice(_events.size() - 40, _events.size())
	print("[Realmweave] ", msg)
