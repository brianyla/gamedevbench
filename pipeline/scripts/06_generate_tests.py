"""Generate validation tests for tasks using LLM."""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, LLMClient, MetadataManager


def analyze_ground_truth_structure(ground_truth_dir: Path) -> Dict[str, Any]:
    """Analyze ground truth to extract structure information."""

    structure = {
        "scenes": [],
        "scripts": [],
        "resources": [],
        "main_scene": None
    }

    # Find project.godot to determine main scene
    project_godot = ground_truth_dir / "project.godot"
    if project_godot.exists():
        content = project_godot.read_text()
        for line in content.split('\n'):
            if line.startswith('run/main_scene='):
                structure["main_scene"] = line.split('=')[1].strip('"')
                break

    # List scenes
    for scene_file in ground_truth_dir.rglob("*.tscn"):
        rel_path = scene_file.relative_to(ground_truth_dir)
        structure["scenes"].append(str(rel_path))

    # List scripts
    for script_file in ground_truth_dir.rglob("*.gd"):
        rel_path = script_file.relative_to(ground_truth_dir)
        structure["scripts"].append(str(rel_path))

    # List resources
    for res_file in ground_truth_dir.rglob("*.tres"):
        rel_path = res_file.relative_to(ground_truth_dir)
        structure["resources"].append(str(rel_path))

    return structure


def load_reference_tests(config: Config) -> List[str]:
    """Load reference test examples from existing tasks."""

    reference_tasks = config.get('reference_tasks', [])
    test_examples = []

    for task_path in reference_tasks:
        test_file = Path(task_path) / "scripts" / "test.gd"
        if test_file.exists():
            test_examples.append(test_file.read_text())

    return test_examples


def generate_test_script(task_spec: Dict[str, Any], ground_truth_dir: Path,
                        llm_client: LLMClient, config: Config) -> str:
    """Generate test.gd script using LLM."""

    # Analyze ground truth
    structure = analyze_ground_truth_structure(ground_truth_dir)

    # Load reference tests
    reference_tests = load_reference_tests(config)
    reference_example = reference_tests[0] if reference_tests else ""

    # Create prompt
    prompt = f"""Generate a comprehensive Godot validation test script for this task.

TASK NAME: {task_spec['name']}

TASK INSTRUCTION:
{task_spec['instruction']}

GROUND TRUTH STRUCTURE:
- Main scene: {structure.get('main_scene', 'main.tscn')}
- Scenes: {', '.join(structure['scenes'][:5])}
- Scripts: {', '.join(structure['scripts'][:5])}
- Resources: {', '.join(structure['resources'][:3])}

DIFFICULTY: {task_spec.get('difficulty', 'intermediate')}
TAGS: {', '.join(task_spec.get('tags', []))}

REFERENCE TEST EXAMPLE:
```gdscript
{reference_example[:2000]}
```

Generate a complete test.gd script that:

1. **Extends Node** (required structure)
2. **Instantiates main scene** in _ready() function
3. **Validates node structure** - checks that required nodes exist with correct types
4. **Validates properties** - checks that key properties are set correctly
5. **Validates signals** - checks that required signal connections exist
6. **Tests runtime behavior** (if applicable) - simulates input, checks state changes
7. **Prints clear results**:
   - Print "VALIDATION_PASSED" if all checks pass
   - Print "VALIDATION_FAILED: [reason]" if any check fails
   - Print descriptive messages for each check
8. **Exits properly** with get_tree().quit() and status code

Key validation patterns:
- Use `has_node()` to check node existence
- Use `get_node()` to access nodes
- Use `is_connected()` to verify signals
- Use assertions or conditional checks
- Print specific failure reasons

Important:
- Make the test comprehensive but focused on the task instruction
- Don't test implementation details, test observable behavior
- Assume the student's code structure may differ from ground truth
- Test the REQUIREMENTS, not a specific implementation

Output ONLY the complete test.gd script content, no markdown formatting or explanations."""

    try:
        response = llm_client.call(prompt)

        # Clean up response
        response = response.strip()
        if response.startswith("```gdscript"):
            response = response[11:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        return response.strip()

    except Exception as e:
        print(f"❌ Error generating test: {e}")
        raise


def generate_test_for_task(task_dir: Path, llm_client: LLMClient,
                          config: Config) -> bool:
    """Generate test for a single task."""

    task_id = task_dir.name
    task_spec_file = task_dir / "task_spec.json"
    ground_truth_dir = task_dir / "ground_truth"
    test_file = ground_truth_dir / "scripts" / "test.gd"

    # Check if already generated
    if test_file.exists():
        print(f"✓ Test already exists: {task_id}")
        MetadataManager.update_stage_status(task_dir, "test_generation", "completed")
        return True

    # Load task spec
    if not task_spec_file.exists():
        print(f"⏭️  Skipping {task_id}: no task spec")
        return False

    task_spec = json.loads(task_spec_file.read_text())

    print(f"🧪 Generating test for {task_id}: {task_spec['name']}")

    try:
        # Generate test
        test_content = generate_test_script(task_spec, ground_truth_dir,
                                           llm_client, config)

        # Save test
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(test_content)

        # Update metadata
        MetadataManager.update_stage_status(task_dir, "test_generation", "completed")

        print(f"✅ Generated test for {task_id}")
        return True

    except Exception as e:
        MetadataManager.update_stage_status(
            task_dir, "test_generation", "failed",
            error=str(e)
        )
        print(f"❌ Failed to generate test for {task_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate validation tests")
    parser.add_argument("--tasks", nargs="+",
                       help="Specific task IDs to process")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    tasks_dir = Path(config.get('output.tasks'))

    # Initialize LLM client
    llm_client = LLMClient(config)

    # Get task directories
    if args.tasks:
        task_dirs = [tasks_dir / tid for tid in args.tasks
                    if (tasks_dir / tid).exists()]
    else:
        task_dirs = [d for d in tasks_dir.iterdir()
                    if d.is_dir() and (d / "ground_truth").exists()]

    print(f"📊 Processing {len(task_dirs)} tasks")
    print("\n🚀 Starting test generation...\n")

    # Generate tests
    success_count = 0
    failed_count = 0

    for task_dir in task_dirs:
        success = generate_test_for_task(task_dir, llm_client, config)
        if success:
            success_count += 1
        else:
            failed_count += 1

    # Print summary
    print("\n" + "="*60)
    print("TEST GENERATION SUMMARY")
    print("="*60)
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
