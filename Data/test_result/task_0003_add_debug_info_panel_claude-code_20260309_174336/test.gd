extends SceneTree

const SCENE_PATH := "res://controllers/fps_controller.tscn"
const EXPECTED_SCRIPT_PATH := "res://scripts/debug.gd"
const EXPECTED_THEME_PATH := "res://ui/themes/debug.tres"

var failures: Array[String] = []

func _init() -> void:
	validate_project_settings()
	var instance: Node = load_and_instantiate_scene()
	if instance:
		validate_scene_structure(instance)
		await process_frame
		validate_runtime_behavior(instance)
		instance.queue_free()
	finish()


func validate_project_settings() -> void:
	if not InputMap.has_action("debug"):
		failures.append("Missing InputMap action 'debug'.")
		return

	var events := InputMap.action_get_events("debug")
	if events.is_empty():
		failures.append("InputMap action 'debug' has no events assigned.")


func load_and_instantiate_scene() -> Node:
	var scene: PackedScene = load(SCENE_PATH) as PackedScene
	if scene == null:
		failures.append("Could not load %s." % SCENE_PATH)
		return null

	var instance: Node = scene.instantiate()
	if instance == null:
		failures.append("Could not instantiate %s." % SCENE_PATH)
		return null

	root.add_child(instance)
	return instance


func validate_scene_structure(instance: Node) -> void:
	var ui: Node = instance.get_node_or_null("UserInterface")
	if ui == null:
		failures.append("FPSController is missing the UserInterface root.")
		return

	var debug_panel: PanelContainer = ui.get_node_or_null("DebugPanel") as PanelContainer
	if debug_panel == null:
		failures.append("UserInterface is missing a DebugPanel node.")
		return

	if debug_panel.position.x > 20.0 or debug_panel.position.y > 20.0:
		failures.append("DebugPanel should be placed in the upper-left corner.")

	var theme: Theme = debug_panel.theme
	if theme == null:
		failures.append("DebugPanel is missing a Theme resource.")
	elif theme.resource_path != EXPECTED_THEME_PATH:
		failures.append("DebugPanel should use %s." % EXPECTED_THEME_PATH)

	var script: Script = debug_panel.get_script() as Script
	if script == null:
		failures.append("DebugPanel is missing its script.")
	elif script.resource_path != EXPECTED_SCRIPT_PATH:
		failures.append("DebugPanel should use %s." % EXPECTED_SCRIPT_PATH)

	if debug_panel.get_node_or_null("MarginContainer") == null:
		failures.append("DebugPanel is missing a MarginContainer child.")
		return

	var vbox: VBoxContainer = debug_panel.get_node_or_null("MarginContainer/VBoxContainer") as VBoxContainer
	if vbox == null:
		failures.append("DebugPanel is missing a VBoxContainer for debug labels.")


func validate_runtime_behavior(instance: Node) -> void:
	var debug_panel: PanelContainer = instance.get_node_or_null("UserInterface/DebugPanel") as PanelContainer
	if debug_panel == null:
		return

	if debug_panel.visible:
		failures.append("DebugPanel should start hidden.")

	var vbox: VBoxContainer = debug_panel.get_node_or_null("MarginContainer/VBoxContainer") as VBoxContainer
	if vbox == null:
		return

	if vbox.get_child_count() < 1:
		failures.append("DebugPanel should create at least one debug label.")
		return

	var first_label: Label = vbox.get_child(0) as Label
	if first_label == null:
		failures.append("First debug entry should be a Label.")
		return

	if first_label.name != "FPS":
		failures.append("Expected the first debug label to be named 'FPS'.")

	var toggle_event := InputEventAction.new()
	toggle_event.action = "debug"
	toggle_event.pressed = true
	debug_panel._input(toggle_event)

	if not debug_panel.visible:
		failures.append("DebugPanel did not toggle visible on the debug action.")
		return

	debug_panel._process(0.25)
	var text: String = first_label.text
	if not text.begins_with("FPS"):
		failures.append("FPS label text was not updated after processing.")


func finish() -> void:
	if failures.is_empty():
		print("VALIDATION_PASSED")
		quit(0)
		return

	for failure in failures:
		print("VALIDATION_FAILED: %s" % failure)
	quit(1)
