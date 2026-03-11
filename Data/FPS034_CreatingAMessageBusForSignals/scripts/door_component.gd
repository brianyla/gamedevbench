class_name DoorComponent extends Node

@export_group("Door Settings")
@export var direction : Vector3
@export var rotation : Vector3
@export var rotation_amount : float
@export var door_size : Vector3
@export var forward_direction : Vector3
@export_group("Close Settings")
@export var close_automatically : bool
@export var close_time : float = 2.0
@export_group("Tween Settings")
@export var speed : float = 0.5
@export var transition : Tween.TransitionType
@export var easing : Tween.EaseType

@export var interaction_component : InteractionComponent

var parent
var orig_pos : Vector3
var orig_rot : Vector3
var rotation_adjustment : float
var door_open : bool = false


func _ready() -> void:
	parent = get_parent()
	orig_pos = parent.position
	orig_rot = parent.rotation
	parent.ready.connect(connect_parent)
	

func connect_parent() -> void:
	parent.connect("interacted", Callable(self, "check_door"))


func check_door() -> void:
	match door_open:
		false:
			door_open = true
			interaction_component.context = "Close Door"
			MessageBus.interaction_focused.emit("Close Door")
			var door_direction : Vector3 = parent.global_transform.basis.x
			var player_position : Vector3 = Global.player.global_position
			var direction_to_player = parent.global_position.direction_to(player_position)
			var door_dot : float = direction_to_player.dot(door_direction)
			
			if door_dot < 0:
				rotation_adjustment = -1
			else:
				rotation_adjustment = 1
			
			var tween = get_tree().create_tween()
			
			if direction != Vector3.ZERO:
				tween.tween_property(parent, "position", orig_pos + (direction * door_size), speed).set_trans(transition).set_ease(easing)
			else:
				tween.tween_property(parent, "rotation", orig_rot + (rotation * rotation_adjustment * deg_to_rad(rotation_amount)), speed).set_trans(transition).set_ease(easing)
			
			if close_automatically:
				tween.tween_interval(close_time)
				tween.tween_callback(close_door)
		true:
			close_door()


func close_door() -> void:
	door_open = false
	var tween = get_tree().create_tween()
	
	if direction != Vector3.ZERO:
		tween.tween_property(parent, "position", orig_pos, speed).set_trans(transition).set_ease(easing)
	else:
		tween.tween_property(parent, "rotation", orig_rot, speed).set_trans(transition).set_ease(easing)
	interaction_component.context = "Open Door"
	MessageBus.interaction_focused.emit("Open Door")
