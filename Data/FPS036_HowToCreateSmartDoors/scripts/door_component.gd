class_name DoorComponent extends Node

enum DoorType {SLIDING, ROTATING}
enum ForwardDirection {X, Y, Z}

@export_group("Door Settings")
@export var door_type : DoorType
@export var forward_direction : ForwardDirection
@export var door_size : Vector3
@export var movement_direction : Vector3
@export var rotation : Vector3 = Vector3(0,1,0)
@export var rotation_amount : float = 90.0
@export_group("Close Settings")
@export var close_time : float = 2.0
@export_group("Tween Settings")
@export var speed : float = 0.5
@export var transition : Tween.TransitionType
@export var easing : Tween.EaseType

var parent
var orig_pos : Vector3
var orig_rot : Vector3
var rotation_adjustment : float
var door_direction : Vector3


func _ready() -> void:
	parent = get_parent()
	orig_pos = parent.position
	orig_rot = parent.rotation
	parent.ready.connect(connect_parent)
	

func connect_parent() -> void:
	parent.connect("interacted", Callable(self, "check_door"))
	
	
func check_door() -> void:
	match forward_direction:
		ForwardDirection.X:
			door_direction = parent.global_transform.basis.x
		ForwardDirection.Y:
			door_direction = parent.global_transform.basis.y
		ForwardDirection.Z:
			door_direction = parent.global_transform.basis.z
	var player_position : Vector3 = Global.player.global_position
	var direction_to_player : Vector3 = parent.global_position.direction_to(player_position)
	var door_dot : float = direction_to_player.dot(door_direction)
	if door_dot < 0:
		rotation_adjustment = -1
	else:
		rotation_adjustment = 1
	
	open_door()


func open_door() -> void:
	var tween = get_tree().create_tween()
	match door_type:
		DoorType.SLIDING:
			tween.tween_property(parent, "position", orig_pos + (movement_direction * door_size), speed).set_trans(transition).set_ease(easing)
		DoorType.ROTATING:
			tween.tween_property(parent, "rotation", orig_rot + (rotation * rotation_adjustment * deg_to_rad(rotation_amount)), speed).set_trans(transition).set_ease(easing)
	tween.tween_interval(close_time)
	tween.tween_callback(close_door)


func close_door() -> void:
	var tween = get_tree().create_tween()
	match door_type:
		DoorType.SLIDING:
			tween.tween_property(parent, "position", orig_pos, speed).set_trans(transition).set_ease(easing)
		DoorType.ROTATING:
			tween.tween_property(parent, "rotation", orig_rot, speed).set_trans(transition).set_ease(easing)
