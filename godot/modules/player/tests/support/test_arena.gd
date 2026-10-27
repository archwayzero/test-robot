## Test geometry for the player module (maze is not a dependency): StaticBody3D boxes on layer 1.
## - floor: 4 m tiles over x,z in [-24, 24], top at y = 0 (tile seams on purpose)
## - ROOM: a closed 4 x 4 m cell (walls 0.6 thick centred on the edges, 3 m tall), interior 3.4 m
## - CROUCH_TUNNEL: ceiling with its underside at 1.3 m; CRAWL_TUNNEL: underside at 0.75 m
extends Node3D

const TILE := 4.0
const HALF_EXTENT := 24.0
const ROOM_CENTER := Vector3(-16.0, 0.0, -16.0)
const ROOM_HALF_INTERIOR := 1.7
const WALL_THICKNESS := 0.6
const WALL_HEIGHT := 3.0
## Low ceilings: x from TUNNEL_X0 to TUNNEL_X1, centred on z, 4 m wide.
const TUNNEL_X0 := 12.0
const TUNNEL_X1 := 20.0
const CROUCH_TUNNEL_Z := 0.0
const CROUCH_CEILING := 1.3
const CRAWL_TUNNEL_Z := 10.0
const CRAWL_CEILING := 0.75

var _material: StandardMaterial3D
var with_meshes := true


func _ready() -> void:
	_material = StandardMaterial3D.new()
	_material.albedo_color = Color(0.62, 0.55, 0.45)
	var n := int(HALF_EXTENT * 2.0 / TILE)
	for i in n:
		for j in n:
			var cx := -HALF_EXTENT + TILE * (i + 0.5)
			var cz := -HALF_EXTENT + TILE * (j + 0.5)
			add_box(Vector3(cx, -0.1, cz), Vector3(TILE, 0.2, TILE),
					Color(0.5, 0.5, 0.48) if (i + j) % 2 == 0 else Color(0.42, 0.42, 0.4))
	# Room walls (on the cell edges, overlapping at the corners).
	var e := ROOM_HALF_INTERIOR + WALL_THICKNESS * 0.5
	var long := (ROOM_HALF_INTERIOR + WALL_THICKNESS) * 2.0
	for side in [-1.0, 1.0]:
		add_box(ROOM_CENTER + Vector3(side * e, WALL_HEIGHT * 0.5, 0.0), Vector3(WALL_THICKNESS, WALL_HEIGHT, long))
		add_box(ROOM_CENTER + Vector3(0.0, WALL_HEIGHT * 0.5, side * e), Vector3(long, WALL_HEIGHT, WALL_THICKNESS))
	add_ceiling(CROUCH_TUNNEL_Z, CROUCH_CEILING)
	add_ceiling(CRAWL_TUNNEL_Z, CRAWL_CEILING)


func add_ceiling(z: float, underside: float) -> void:
	var length := TUNNEL_X1 - TUNNEL_X0
	add_box(Vector3((TUNNEL_X0 + TUNNEL_X1) * 0.5, underside + 0.15, z), Vector3(length, 0.3, 4.0),
			Color(0.55, 0.4, 0.3))


func add_box(center: Vector3, size: Vector3, color := Color(0.62, 0.55, 0.45)) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	body.position = center
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	body.add_child(shape)
	if with_meshes:
		var mesh := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = size
		mesh.mesh = bm
		var mat := StandardMaterial3D.new()
		mat.albedo_color = color
		mesh.material_override = mat
		body.add_child(mesh)
	add_child(body)
	return body


## Distance from `p` to the nearest inner wall plane of the room (negative = inside a wall).
static func room_wall_distance(p: Vector3) -> float:
	var local := p - ROOM_CENTER
	return ROOM_HALF_INTERIOR - maxf(absf(local.x), absf(local.z))
