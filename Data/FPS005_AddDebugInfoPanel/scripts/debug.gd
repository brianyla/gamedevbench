extends PanelContainer

@onready var property_container = %VBoxContainer

var property
var frames_per_second : String

# Called when the node enters the scene tree for the first time.
func _ready():
	# Hide Debug Panel on load
	visible = false
	
	add_debug_property("FPS",frames_per_second)
	
func _process(delta):
	
	if visible:
		# Use delta time to get approx frames per second and round to two decimal places !Disable VSync if fps is stuck at 60!
			frames_per_second = "%.2f" % (1.0/delta) # Gets frames per second every frame
		#	frames_per_second = Engine.get_frames_per_second() # Gets frames per second every second
			property.text = property.name + ": " + frames_per_second
	
func _input(event):
	# Toggle debug panel
	if event.is_action_pressed("debug"):
		visible = !visible

# Callable function to add new debug property
func add_debug_property(title : String,value):
	property = Label.new() # Create new Label node
	property_container.add_child(property) # Add new node as child to VBox container
	property.name = title # Set name to title
	property.text = property.name + value
