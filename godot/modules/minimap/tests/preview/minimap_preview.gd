## Visual check scene (tests only, not shipped): the game maze, a scripted walk of ~30 cells revealed one per frame
## on the small map, then the large map opened at frame 40. Drives Core.player_moved directly (no player).
extends Control

const WALK_CELLS := 30
const OPEN_FRAME := 40

var _layout: MazeLayout
var _exploration: Exploration
var _minimap: Minimap
var _path: Array[Vector2i] = []
var _frame := 0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.22, 0.24, 0.28)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	_layout = MazeFactory.create().make_layout()
	Core.state.set_value(StateKeys.MAZE_SEED, _layout.get_seed())
	_exploration = ExplorationFactory.create()
	add_child(_exploration)
	_exploration.setup(_layout)
	_minimap = MinimapFactory.create()
	add_child(_minimap)
	_minimap.setup(_layout, _exploration)
	_path = _dfs_walk(_layout.start_cell(), WALK_CELLS)


func _process(_delta: float) -> void:
	_frame += 1
	if _frame <= _path.size():
		var cell := _path[_frame - 1]
		Core.player_moved.emit(_layout.cell_to_world(cell))
	elif _frame == OPEN_FRAME:
		_minimap.open_large_map()


## Depth-first walk through open edges (backtracking counts as steps, so the marker stays on a real route).
func _dfs_walk(start: Vector2i, steps: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = [start]
	var seen := {start: true}
	var stack: Array[Vector2i] = [start]
	var dirs := [[MazeLayout.Dir.NORTH, Vector2i(0, -1)], [MazeLayout.Dir.EAST, Vector2i(1, 0)],
			[MazeLayout.Dir.SOUTH, Vector2i(0, 1)], [MazeLayout.Dir.WEST, Vector2i(-1, 0)]]
	while not stack.is_empty() and out.size() < steps:
		var c: Vector2i = stack.back()
		var moved := false
		for d in dirs:
			var n: Vector2i = c + d[1]
			if not _layout.has_wall(c, d[0]) and _layout.in_bounds(n) and not seen.has(n):
				seen[n] = true
				stack.append(n)
				out.append(n)
				moved = true
				break
		if not moved:
			stack.pop_back()
			if not stack.is_empty():
				out.append(stack.back())
	return out
