extends PanelContainer

# Debug overlay panel for displaying runtime information
# Positioned in upper-left corner with styled background

@onready var fps_label: Label = $MarginContainer/VBoxContainer/FPSLabel

var frame_count: int = 0
var fps_timer: float = 0.0
var current_fps: float = 0.0
const FPS_UPDATE_INTERVAL: float = 0.5  # Update FPS display twice per second

func _ready():
	# Setup panel styling
	setup_panel_style()

func _process(delta: float):
	# Calculate FPS
	frame_count += 1
	fps_timer += delta

	if fps_timer >= FPS_UPDATE_INTERVAL:
		current_fps = frame_count / fps_timer
		fps_label.text = "FPS: %d" % round(current_fps)

		# Reset counters
		frame_count = 0
		fps_timer = 0.0

func setup_panel_style():
	# Create a dark semi-transparent background panel
	var style_box = StyleBoxFlat.new()
	style_box.bg_color = Color(0.0, 0.0, 0.0, 0.7)  # Black with 70% opacity
	style_box.border_color = Color(0.3, 0.3, 0.3, 0.9)  # Gray border
	style_box.set_border_width_all(1)
	style_box.set_corner_radius_all(4)
	style_box.content_margin_left = 8
	style_box.content_margin_right = 8
	style_box.content_margin_top = 8
	style_box.content_margin_bottom = 8

	add_theme_stylebox_override("panel", style_box)
