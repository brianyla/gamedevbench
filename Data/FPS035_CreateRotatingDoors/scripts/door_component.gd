class_name DoorComponent extends Node

enum DoorType {SLIDING, ROTATING}

@export_group("Door Settings")
@export var door_type : DoorType
@export var movement_direction : Vector3
@export var rotation : Vector3 = Vector3(0,1,0)
@export var rotation_amount : float = 90.0
@export var door_size : Vector3
@export_group("Close Settings")
@export var close_time : float = 2.0
@export_group("Tween Settings")
@export var speed : float = 0.5
@export var transition : Tween.TransitionType
@export var easing : Tween.EaseType

var parent
var orig_pos : Vector3
var orig_rot : Vector3


func _ready() -> void:
	parent = get_parent()
	orig_pos = parent.position
	orig_rot = parent.rotation
	parent.ready.connect(connect_parent)
	

func connect_parent() -> void:
	parent.connect("interacted", Callable(self, "open_door"))


func open_door() -> void:
	var tween = get_tree().create_tween()
	match door_type:
		DoorType.SLIDING:
			tween.tween_property(parent, "position", orig_pos + (movement_direction * door_size), speed).set_trans(transition).set_ease(easing)
		DoorType.ROTATING:
			tween.tween_property(parent, "rotation", orig_rot + (rotation * deg_to_rad(rotation_amount)), speed).set_trans(transition).set_ease(easing)
	tween.tween_interval(close_time)
	tween.tween_callback(close_door)


func close_door() -> void:
	var tween = get_tree().create_tween()
	match door_type:
		DoorType.SLIDING:
			tween.tween_property(parent, "position", orig_pos, speed).set_trans(transition).set_ease(easing)
		DoorType.ROTATING:
			tween.tween_property(parent, "rotation", orig_rot, speed).set_trans(transition).set_ease(easing)
