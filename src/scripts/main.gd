extends Node2D
## SNAKE-50000 —— 吃满 50000 分解锁 FLAG
## 正常游玩几乎不可能达到 50000 分（5000 颗食物，末速 25 格/秒）。

const CELL := 20
const COLS := 40
const ROWS := 30
const GRID_Y := 48

const BASE_STEP := 0.150
const MIN_STEP := 0.040
const ACCEL := 0.0022

const POINTS_PER_FOOD := 10
const TARGET_SCORE := 50000

@onready var flag_manager: Node = $FlagManager

var _body: Array[Vector2i] = []
var _dir: Vector2i = Vector2i.RIGHT
var _dir_queue: Array[Vector2i] = []
var _food: Vector2i = Vector2i.ZERO
var _food_count := 0
var _score := 0
var _step_time := BASE_STEP
var _accum := 0.0
var _alive := false
var _won := false
var _paused := false

var _score_label: Label
var _speed_label: Label
var _overlay: CanvasLayer
var _overlay_title: Label
var _overlay_body: Label


func _ready() -> void:
	_build_hud()
	_build_overlay()
	_reset()


func _process(delta: float) -> void:
	if not _alive or _won or _paused:
		return
	_accum += delta
	while _accum >= _step_time:
		_accum -= _step_time
		_step()
		if not _alive or _won:
			break
	queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		_handle_key(event as InputEventKey)


func _handle_key(event: InputEventKey) -> void:
	if event.physical_keycode == KEY_R:
		_reset()
		return
	if not _alive or _won:
		if event.is_action_pressed("ui_accept"):
			_reset()
		return
	if event.physical_keycode == KEY_P or event.physical_keycode == KEY_ESCAPE:
		_toggle_pause()
		return
	var nd := Vector2i.ZERO
	if event.is_action_pressed("ui_left") or event.physical_keycode == KEY_A:
		nd = Vector2i.LEFT
	elif event.is_action_pressed("ui_right") or event.physical_keycode == KEY_D:
		nd = Vector2i.RIGHT
	elif event.is_action_pressed("ui_up") or event.physical_keycode == KEY_W:
		nd = Vector2i.UP
	elif event.is_action_pressed("ui_down") or event.physical_keycode == KEY_S:
		nd = Vector2i.DOWN
	if nd != Vector2i.ZERO:
		_queue_dir(nd)


func _queue_dir(nd: Vector2i) -> void:
	var last: Vector2i = _dir
	if not _dir_queue.is_empty():
		last = _dir_queue[_dir_queue.size() - 1]
	if nd == last or nd == -last:
		return
	if _dir_queue.size() >= 3:
		return
	_dir_queue.append(nd)


func _toggle_pause() -> void:
	_paused = not _paused
	if _paused:
		_show_overlay("PAUSED", "按 P 继续 · 按 R 重新开始", Color(0.9, 0.9, 0.4))
	else:
		_overlay.visible = false
		_accum = 0.0


func _reset() -> void:
	_body.clear()
	var cy: int = ROWS / 2
	_body.append(Vector2i(COLS / 2, cy))
	_body.append(Vector2i(COLS / 2 - 1, cy))
	_body.append(Vector2i(COLS / 2 - 2, cy))
	_dir = Vector2i.RIGHT
	_dir_queue.clear()
	_food_count = 0
	_score = 0
	_step_time = BASE_STEP
	_accum = 0.0
	_alive = true
	_won = false
	_paused = false
	flag_manager.reset()
	_spawn_food()
	_overlay.visible = false
	_update_hud()
	queue_redraw()


func _step() -> void:
	if not _dir_queue.is_empty():
		_dir = _dir_queue.pop_front()
	var new_head: Vector2i = _body[0] + _dir
	if new_head.x < 0 or new_head.x >= COLS or new_head.y < 0 or new_head.y >= ROWS:
		_die()
		return
	var will_grow: bool = new_head == _food
	var check_len: int = _body.size() if will_grow else _body.size() - 1
	for i in range(check_len):
		if _body[i] == new_head:
			_die()
			return
	_body.push_front(new_head)
	if will_grow:
		_score += POINTS_PER_FOOD
		_food_count += 1
		flag_manager.register_food()
		_step_time = max(MIN_STEP, BASE_STEP - _food_count * ACCEL)
		_update_hud()
		if _score >= TARGET_SCORE:
			_win()
			return
		_spawn_food()
	else:
		_body.pop_back()


func _spawn_food() -> void:
	var free_cells: Array[Vector2i] = []
	for x in COLS:
		for y in ROWS:
			var c := Vector2i(x, y)
			if not _body.has(c):
				free_cells.append(c)
	if free_cells.is_empty():
		return
	_food = free_cells[randi() % free_cells.size()]


func _die() -> void:
	_alive = false
	_show_overlay("GAME OVER", "最终得分 %d / %d\n按 R 重新开始" % [_score, TARGET_SCORE], Color(0.95, 0.3, 0.3))


func _win() -> void:
	_alive = false
	_won = true
	var flag_text: String = flag_manager.reveal(_score)
	DisplayServer.clipboard_set(flag_text)
	_show_overlay("*** UNLOCKED ***", "恭喜通关！FLAG:\n%s\n\n(已复制到剪贴板)" % flag_text, Color(0.35, 1.0, 0.45))


func _update_hud() -> void:
	_score_label.text = "SCORE %d / %d" % [_score, TARGET_SCORE]
	var pct: int = int(round(BASE_STEP / _step_time * 100.0))
	_speed_label.text = "SPD %d%%" % pct


func _build_hud() -> void:
	var hud := CanvasLayer.new()
	hud.layer = 5
	add_child(hud)

	var title := Label.new()
	title.text = "SNAKE-50000"
	title.position = Vector2(16, 6)
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color(0.3, 0.9, 0.4))
	hud.add_child(title)

	var hint := Label.new()
	hint.text = "方向键 / WASD 移动 · P 暂停 · R 重开"
	hint.position = Vector2(0, 30)
	hint.size = Vector2(COLS * CELL, 16)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_font_size_override("font_size", 12)
	hint.add_theme_color_override("font_color", Color(0.6, 0.65, 0.7))
	hud.add_child(hint)

	_score_label = Label.new()
	_score_label.position = Vector2(584, 6)
	_score_label.size = Vector2(200, 26)
	_score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_score_label.add_theme_font_size_override("font_size", 20)
	_score_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
	hud.add_child(_score_label)

	_speed_label = Label.new()
	_speed_label.position = Vector2(584, 30)
	_speed_label.size = Vector2(200, 16)
	_speed_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_speed_label.add_theme_font_size_override("font_size", 12)
	_speed_label.add_theme_color_override("font_color", Color(0.6, 0.65, 0.7))
	hud.add_child(_speed_label)


func _build_overlay() -> void:
	_overlay = CanvasLayer.new()
	_overlay.layer = 10
	add_child(_overlay)

	var w: float = COLS * CELL
	var h: float = GRID_Y + ROWS * CELL

	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.78)
	dim.position = Vector2(0, 0)
	dim.size = Vector2(w, h)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(dim)

	_overlay_title = Label.new()
	_overlay_title.position = Vector2(0, h * 0.36)
	_overlay_title.size = Vector2(w, 48)
	_overlay_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_title.add_theme_font_size_override("font_size", 36)
	_overlay.add_child(_overlay_title)

	_overlay_body = Label.new()
	_overlay_body.position = Vector2(60, h * 0.36 + 70)
	_overlay_body.size = Vector2(w - 120, 200)
	_overlay_body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_body.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_overlay_body.add_theme_font_size_override("font_size", 18)
	_overlay.add_child(_overlay_body)

	_overlay.visible = false


func _show_overlay(title_text: String, body_text: String, color: Color) -> void:
	_overlay_title.text = title_text
	_overlay_title.add_theme_color_override("font_color", color)
	_overlay_body.text = body_text
	_overlay.visible = true


func _draw() -> void:
	var w: float = COLS * CELL
	var h: float = ROWS * CELL

	# 棋盘背景与网格
	draw_rect(Rect2(0, GRID_Y, w, h), Color(0.08, 0.09, 0.12))
	var line := Color(1, 1, 1, 0.03)
	for x in COLS + 1:
		var px: float = x * CELL
		draw_line(Vector2(px, GRID_Y), Vector2(px, GRID_Y + h), line)
	for y in ROWS + 1:
		var py: float = GRID_Y + y * CELL
		draw_line(Vector2(0, py), Vector2(w, py), line)

	# 食物
	var fc := Vector2(
		_food.x * CELL + CELL * 0.5,
		GRID_Y + _food.y * CELL + CELL * 0.5
	)
	draw_circle(fc, CELL * 0.36, Color(0.92, 0.28, 0.28))

	# 蛇（蛇头更亮，向尾部渐暗）
	for i in _body.size():
		var seg: Vector2i = _body[i]
		var c: Color
		if i == 0:
			c = Color(0.32, 1.0, 0.42)
		else:
			c = Color(0.18, 0.72, 0.28).darkened(float(i) / float(_body.size()) * 0.55)
		draw_rect(
			Rect2(seg.x * CELL + 1, GRID_Y + seg.y * CELL + 1, CELL - 2, CELL - 2),
			c
		)
