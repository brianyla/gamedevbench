@tool

extends Node3D

@export var WEAPON_TYPE : Weapons:
	set(value):
		WEAPON_TYPE = value
		if Engine.is_editor_hint():
			load_weapon()
@export var sway_noise : NoiseTexture2D
@export var sway_speed : float = 1.2
@export var reset : bool = false:
	set(value):
		reset = value
		if Engine.is_editor_hint():
			load_weapon()

@onready var weapon_mesh : MeshInstance3D = %WeaponMesh
@onready var weapon_shadow : MeshInstance3D = %WeaponShadow

var mouse_movement : Vector2
var random_sway_x
var random_sway_y
var random_sway_amount : float
var time : float = 0.0
var idle_sway_adjustment
var idle_sway_rotation_strength

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	await owner.ready
	load_weapon()
	
func _input(event):
	if event.is_action_pressed("weapon1"):
		WEAPON_TYPE = load("res://meshes/weapons/crowbar/crowbar.tres")
		load_weapon()
	if event.is_action_pressed("weapon2"):
		WEAPON_TYPE = load("res://meshes/weapons/gun_rifle/scifi_rifle.tres")
		load_weapon()
	if event is InputEventMouseMotion:
		mouse_movement = event.relative
	
func load_weapon() -> void:
	weapon_mesh.mesh = WEAPON_TYPE.mesh # Set weapon mesh
	position = WEAPON_TYPE.position # Set weapon position
	rotation_degrees = WEAPON_TYPE.rotation	# Set weapon rotation
	scale = WEAPON_TYPE.scale	# Set weapon scale
	weapon_shadow.visible = WEAPON_TYPE.shadow # Turn shadow on/off
	idle_sway_adjustment = WEAPON_TYPE.idle_sway_adjustment
	idle_sway_rotation_strength = WEAPON_TYPE.idle_sway_rotation_strength
	random_sway_amount = WEAPON_TYPE.random_sway_amount
	
func sway_weapon(delta) -> void:
	# Get random sway value from 2D noise
	var sway_random : float = get_sway_noise()
	var sway_random_adjusted : float = sway_random * idle_sway_adjustment # Adjust sway strength
	
	# Create time with delta and set two sine values for x and y sway movement
	time += delta * (sway_speed + sway_random)
	random_sway_x = sin(time * 1.5 + sway_random_adjusted) / random_sway_amount
	random_sway_y = sin(time - sway_random_adjusted) / random_sway_amount
	
	# Clamp mouse movement
	mouse_movement = mouse_movement.clamp(WEAPON_TYPE.sway_min,WEAPON_TYPE.sway_max)
	
	# Lerp weapon position based on mouse movement
	position.x = lerp(position.x, WEAPON_TYPE.position.x - (mouse_movement.x * WEAPON_TYPE.sway_amount_position + random_sway_x) * delta, WEAPON_TYPE.sway_speed_position)
	position.y = lerp(position.y, WEAPON_TYPE.position.y + (mouse_movement.y * WEAPON_TYPE.sway_amount_position + random_sway_y) * delta, WEAPON_TYPE.sway_speed_position) 
	
	# Lerp weapon rotation based on mouse movement
	rotation_degrees.y = lerp(rotation_degrees.y, WEAPON_TYPE.rotation.y + (mouse_movement.x * WEAPON_TYPE.sway_amount_rotation + (random_sway_y * idle_sway_rotation_strength)) * delta, WEAPON_TYPE.sway_speed_rotation)
	rotation_degrees.x = lerp(rotation_degrees.x, WEAPON_TYPE.rotation.x - (mouse_movement.y * WEAPON_TYPE.sway_amount_rotation + (random_sway_x * idle_sway_rotation_strength)) * delta, WEAPON_TYPE.sway_speed_rotation)
	
func get_sway_noise() -> float:
	var player_position : Vector3 = Vector3(0,0,0)
	
	# Only access global variable when in-game to avoid constant errors
	if not Engine.is_editor_hint():
		player_position = Global.player.global_position
	
	var noise_location : float = sway_noise.noise.get_noise_2d(player_position.x,player_position.y)
	return noise_location

func _physics_process(delta: float) -> void:
	sway_weapon(delta)
