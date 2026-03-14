#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rewrite_task_instructions import INSTRUCTIONS as BASE_INSTRUCTIONS


ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
METADATA_DIR = ROOT / "metadata"
TASK_CANDIDATES = METADATA_DIR / "task_candidates.csv"
OVERRIDES_PATH = METADATA_DIR / "task_spec_overrides.json"
REPORT_PATH = METADATA_DIR / "task_generation_report.json"

DEFAULT_GODOT_CANDIDATES = [
    Path("/Applications/Godot.app/Contents/MacOS/godot"),
    Path("/Applications/Godot.app/Contents/MacOS/Godot"),
]


def read_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {} if default is None else default


def load_candidate_rows() -> Dict[str, Dict[str, str]]:
    with TASK_CANDIDATES.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["tutorial_id"]: row for row in rows}


def load_overrides() -> Dict[str, Dict[str, Any]]:
    return read_json(OVERRIDES_PATH, default={})


def task_dirs(selected: List[str]) -> List[Path]:
    selected_set = set(selected)
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        if selected_set and task_dir.name not in selected_set and task_dir.name.split("_", 2)[0] + "_" + task_dir.name.split("_", 2)[1] not in selected_set:
            if task_dir.name.split("_", 2)[0] + "_" + task_dir.name.split("_", 2)[1] != task_dir.name:
                pass
        if selected_set and task_dir.name not in selected_set:
            task_id = task_dir.name.split("_", 2)
            short_id = "_".join(task_id[:2]) if len(task_id) >= 2 else task_dir.name
            if short_id not in selected_set:
                continue
        tasks.append(task_dir)
    return tasks


def relative_files(root: Path) -> List[str]:
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and ".godot" not in path.parts and path.name != ".DS_Store"
    )


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def parse_project_sections(path: Path) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    text = read_text(path) or ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("[") and line.endswith("]"):
            current = line.strip("[]")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def parse_input_actions(path: Path) -> List[str]:
    sections = parse_project_sections(path)
    actions = []
    for line in sections.get("input", []):
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            actions.append(key)
    return sorted(set(actions))


def parse_autoloads(path: Path) -> Dict[str, str]:
    sections = parse_project_sections(path)
    autoloads = {}
    for line in sections.get("autoload", []):
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        autoloads[key.strip()] = value.strip().strip('"')
    return autoloads


def parse_gd_contract(path: Path) -> Dict[str, Any]:
    text = read_text(path) or ""
    class_names = re.findall(r"^\s*class_name\s+([A-Za-z0-9_]+)", text, re.MULTILINE)
    signals = re.findall(r"^\s*signal\s+([A-Za-z0-9_]+)", text, re.MULTILINE)
    functions = re.findall(r"^\s*func\s+([A-Za-z0-9_]+)\s*\(", text, re.MULTILINE)
    return {
        "class_names": sorted(set(class_names)),
        "signals": sorted(set(signals)),
        "functions": sorted(set(functions)),
    }


def parse_scene(path: Path) -> Dict[str, Any]:
    text = read_text(path) or ""
    ext_resources: Dict[str, str] = {}
    nodes: Dict[str, Dict[str, Any]] = {}
    current_path: Optional[str] = None

    for line in text.splitlines():
        ext_match = re.match(r'\[ext_resource .* path="([^"]+)" id="([^"]+)"\]', line)
        if ext_match:
            ext_resources[ext_match.group(2)] = ext_match.group(1)
            continue

        node_match = re.match(r'\[node name="([^"]+)" type="([^"]+)"(?: parent="([^"]*)")?.*\]', line)
        if node_match:
            name = node_match.group(1)
            node_type = node_match.group(2)
            parent = node_match.group(3) or ""
            node_path = name if not parent or parent == "." else f"{parent}/{name}"
            current_path = node_path
            nodes[current_path] = {
                "name": name,
                "type": node_type,
                "parent": parent,
                "script_path": None,
                "theme_path": None,
                "visible": None,
                "offset_left": None,
                "offset_top": None,
                "offset_right": None,
                "offset_bottom": None,
                "custom_minimum_size": None,
            }
            continue

        if current_path is None or current_path not in nodes:
            continue

        script_match = re.match(r'script = ExtResource\("([^"]+)"\)', line)
        if script_match:
            nodes[current_path]["script_path"] = ext_resources.get(script_match.group(1))
            continue

        theme_match = re.match(r'theme = ExtResource\("([^"]+)"\)', line)
        if theme_match:
            nodes[current_path]["theme_path"] = ext_resources.get(theme_match.group(1))
            continue

        visible_match = re.match(r"visible = (true|false)", line)
        if visible_match:
            nodes[current_path]["visible"] = visible_match.group(1) == "true"
            continue

        for key in ("offset_left", "offset_top", "offset_right", "offset_bottom"):
            prop_match = re.match(rf"{key} = (-?[0-9.]+)", line)
            if prop_match:
                nodes[current_path][key] = float(prop_match.group(1))
                break

        min_size_match = re.match(r"custom_minimum_size = Vector2\(([^,]+), ([^)]+)\)", line)
        if min_size_match:
            nodes[current_path]["custom_minimum_size"] = {
                "x": float(min_size_match.group(1)),
                "y": float(min_size_match.group(2)),
            }

    return {"nodes": nodes}


def first_relevant_scene(candidate_files: List[str]) -> Optional[str]:
    scene_files = [path for path in candidate_files if path.endswith(".tscn")]
    if not scene_files:
        return None
    for prefix in ("controllers/", "levels/", "ui/"):
        for path in scene_files:
            if path.startswith(prefix):
                return path
    return scene_files[0]


def build_scene_checks(start_path: Path, solution_path: Path, candidate_files: List[str]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    scene_files = [path for path in candidate_files if path.endswith(".tscn")]
    for rel_path in scene_files:
        sol_scene = parse_scene(solution_path / rel_path)
        start_scene = parse_scene(start_path / rel_path) if (start_path / rel_path).exists() else {"nodes": {}}
        added_nodes = []
        for node_path, node_info in sol_scene["nodes"].items():
            if node_path not in start_scene["nodes"]:
                entry = dict(node_info)
                entry["path"] = node_path
                added_nodes.append(entry)
        if added_nodes:
            checks.append(
                {
                    "scene_path": f"res://{rel_path}",
                    "added_nodes": added_nodes,
                }
            )
    return checks


def build_project_settings_spec(start_path: Path, solution_path: Path) -> Dict[str, Any]:
    project_file = "project.godot"
    start_project = start_path / project_file
    solution_project = solution_path / project_file
    input_actions: List[str] = []
    autoloads: List[Dict[str, str]] = []
    if solution_project.exists():
        start_actions = set(parse_input_actions(start_project)) if start_project.exists() else set()
        solution_actions = set(parse_input_actions(solution_project))
        input_actions = sorted(solution_actions - start_actions)

        start_autoloads = parse_autoloads(start_project) if start_project.exists() else {}
        solution_autoloads = parse_autoloads(solution_project)
        for name, value in solution_autoloads.items():
            if start_autoloads.get(name) != value:
                autoloads.append({"name": name, "value": value})
    return {
        "input_actions": input_actions,
        "autoloads": autoloads,
    }


def build_script_checks(start_path: Path, solution_path: Path, candidate_files: List[str]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for rel_path in candidate_files:
        if not rel_path.endswith(".gd"):
            continue
        sol_file = solution_path / rel_path
        if not sol_file.exists():
            continue
        start_file = start_path / rel_path
        start_contract = parse_gd_contract(start_file) if start_file.exists() else {"class_names": [], "signals": [], "functions": []}
        solution_contract = parse_gd_contract(sol_file)
        added_functions = sorted(set(solution_contract["functions"]) - set(start_contract["functions"]))
        added_signals = sorted(set(solution_contract["signals"]) - set(start_contract["signals"]))
        added_classes = sorted(set(solution_contract["class_names"]) - set(start_contract["class_names"]))
        if not start_file.exists() or added_functions or added_signals or added_classes:
            checks.append(
                {
                    "script_path": f"res://{rel_path}",
                    "must_exist": True,
                    "class_names": added_classes,
                    "signals": added_signals,
                    "functions": added_functions,
                }
            )
    return checks


def build_file_presence_spec(start_path: Path, solution_path: Path) -> List[str]:
    start_files = set(relative_files(start_path))
    solution_files = set(relative_files(solution_path))
    return sorted(
        path
        for path in (solution_files - start_files)
        if not path.endswith(".uid")
    )


def build_base_spec(task_dir: Path, metadata_row: Dict[str, str]) -> Dict[str, Any]:
    config = read_json(task_dir / "task_config.json")
    provenance = read_json(task_dir / "provenance.json")
    start_path = task_dir / "start"
    solution_path = task_dir / "solution"
    candidate_files = [item.strip() for item in metadata_row.get("candidate_files", "").split("|") if item.strip()]
    source_type = config.get("task_source_type", metadata_row.get("task_source_type", "pair"))

    project_settings = build_project_settings_spec(start_path, solution_path)
    scene_checks = build_scene_checks(start_path, solution_path, candidate_files)
    script_checks = build_script_checks(start_path, solution_path, candidate_files)
    added_files = build_file_presence_spec(start_path, solution_path)
    target_scene = first_relevant_scene(candidate_files)

    return {
        "task_id": config.get("task_id"),
        "task_name": config.get("task_name"),
        "tutorial_id": config.get("tutorial_id"),
        "task_source_type": source_type,
        "title": provenance.get("tutorial_title", metadata_row.get("title", config.get("task_name", ""))),
        "candidate_files": candidate_files,
        "transcript_excerpt_path": str(task_dir / "transcript_excerpt.txt"),
        "context": {
            "base_instruction": BASE_INSTRUCTIONS.get(config.get("task_name", ""), config.get("instruction", "").strip()),
        },
        "required_project_settings": project_settings,
        "required_files": added_files,
        "required_structure": {
            "target_scene": f"res://{target_scene}" if target_scene else None,
            "scene_checks": scene_checks,
            "script_checks": script_checks,
        },
        "required_runtime_behavior": [],
        "validator_target_scene": f"res://{target_scene}" if target_scene else None,
        "manual_review_required": source_type == "bootstrap",
        "audit_start_should_fail": source_type != "bootstrap",
        "notes": [],
    }


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_instruction(spec: Dict[str, Any]) -> str:
    parts: List[str] = []
    base_instruction = spec.get("context", {}).get("base_instruction", "").strip()
    if base_instruction:
        parts.append(base_instruction.rstrip(".") + ".")

    project_settings = spec.get("required_project_settings", {})
    if project_settings.get("input_actions"):
        actions = ", ".join(f"`{name}`" for name in project_settings["input_actions"])
        parts.append(f"Define the input action(s) {actions} in `project.godot`.")

    if project_settings.get("autoloads"):
        autoloads = ", ".join(
            f"`{item['name']}` from `{item['value']}`" for item in project_settings["autoloads"]
        )
        parts.append(f"Register the required autoload(s): {autoloads}.")

    required_files = spec.get("required_files", [])
    if required_files:
        files_str = ", ".join(f"`res://{path}`" for path in required_files[:6])
        suffix = "" if len(required_files) <= 6 else ", plus the other solution-aligned support files for this task"
        parts.append(f"Add the new file(s) {files_str}{suffix}.")

    scene_checks = spec.get("required_structure", {}).get("scene_checks", [])
    for scene_check in scene_checks[:2]:
        scene_path = scene_check["scene_path"]
        node_bits = []
        for node in scene_check.get("added_nodes", [])[:3]:
            node_bits.append(f"`{node['path']}` ({node['type']})")
        if node_bits:
            parts.append(f"In `{scene_path}`, add the node(s) {', '.join(node_bits)}.")

    script_checks = spec.get("required_structure", {}).get("script_checks", [])
    for script_check in script_checks[:2]:
        requirements: List[str] = []
        if script_check.get("class_names"):
            requirements.append("class_name " + ", ".join(f"`{item}`" for item in script_check["class_names"]))
        if script_check.get("signals"):
            requirements.append("signals " + ", ".join(f"`{item}`" for item in script_check["signals"]))
        if script_check.get("functions"):
            requirements.append("functions " + ", ".join(f"`{item}()`" for item in script_check["functions"][:4]))
        if requirements:
            parts.append(
                f"In `{script_check['script_path']}`, include the required {'; '.join(requirements)}."
            )

    if spec.get("manual_review_required"):
        parts.append("This task uses a manually reviewed contract because it cannot be derived safely from a normal start-to-solution diff.")

    return " ".join(part.strip() for part in parts if part.strip())


def gdscript_string(value: str) -> str:
    return json.dumps(value)


def render_manual_review_validator(spec: Dict[str, Any]) -> str:
    message = f"Task {spec['task_id']} requires manual validator review before automated validation can be trusted."
    return "\n".join(
        [
            "extends SceneTree",
            "",
            "func _init() -> void:",
            f"\tprint(\"VALIDATION_FAILED: {message}\")",
            "\tquit(1)",
            "",
        ]
    )


def render_validator(spec: Dict[str, Any]) -> str:
    if spec.get("manual_review_required"):
        return render_manual_review_validator(spec)

    scene_path = spec.get("validator_target_scene")
    project_settings = spec.get("required_project_settings", {})
    scene_checks = spec.get("required_structure", {}).get("scene_checks", [])
    script_checks = spec.get("required_structure", {}).get("script_checks", [])
    required_files = spec.get("required_files", [])

    lines = [
        "extends SceneTree",
        "",
        f"const SCENE_PATH := {gdscript_string(scene_path or '')}",
        "",
        "var failures: Array[String] = []",
        "",
        "func _init() -> void:",
        "\tvalidate_project_settings()",
        "\tvalidate_required_files()",
        "\tvalidate_scripts()",
        "\tvar instance: Node = load_and_instantiate_scene()",
        "\tif instance != null:",
        "\t\tvalidate_scene_structure(instance)",
        "\t\tinstance.queue_free()",
        "\tfinish()",
        "",
        "func validate_project_settings() -> void:",
    ]

    if not project_settings.get("input_actions") and not project_settings.get("autoloads"):
        lines.append("\tpass")
    else:
        for action in project_settings.get("input_actions", []):
            lines.extend(
                [
                    f"\tif not InputMap.has_action({gdscript_string(action)}):",
                    f"\t\tfailures.append(\"Missing InputMap action '{action}'.\")",
                    "\telse:",
                    f"\t\tvar events_{action}: Array = InputMap.action_get_events({gdscript_string(action)})",
                    f"\t\tif events_{action}.is_empty():",
                    f"\t\t\tfailures.append(\"InputMap action '{action}' has no events assigned.\")",
                ]
            )
        for autoload in project_settings.get("autoloads", []):
            name = autoload["name"]
            value = autoload["value"]
            lines.extend(
                [
                    f"\tvar autoload_{name}: String = ProjectSettings.get_setting(\"autoload/{name}\", \"\")",
                    f"\tif autoload_{name} != {gdscript_string(value)}:",
                    f"\t\tfailures.append(\"Missing autoload '{name}' with value {value}.\")",
                ]
            )

    lines.extend(
        [
            "",
            "func validate_required_files() -> void:",
        ]
    )
    if not required_files:
        lines.append("\tpass")
    else:
        for rel_path in required_files:
            lines.extend(
                [
                    f"\tif not FileAccess.file_exists({gdscript_string('res://' + rel_path)}):",
                    f"\t\tfailures.append(\"Missing required file res://{rel_path}.\")",
                ]
            )

    lines.extend(
        [
            "",
            "func validate_scripts() -> void:",
        ]
    )
    if not script_checks:
        lines.append("\tpass")
    else:
        for index, script_check in enumerate(script_checks):
            var_name = f"script_text_{index}"
            path = script_check["script_path"]
            lines.extend(
                [
                    f"\tif not FileAccess.file_exists({gdscript_string(path)}):",
                    f"\t\tfailures.append(\"Missing script {path}.\")",
                    "\telse:",
                    f"\t\tvar file_{index}: FileAccess = FileAccess.open({gdscript_string(path)}, FileAccess.READ)",
                    f"\t\tvar {var_name}: String = file_{index}.get_as_text() if file_{index} != null else \"\"",
                ]
            )
            for item in script_check.get("class_names", []):
                lines.extend(
                    [
                        f"\t\tif {gdscript_string('class_name ' + item)} not in {var_name}:",
                        f"\t\t\tfailures.append(\"{path} should declare class_name {item}.\")",
                    ]
                )
            for item in script_check.get("signals", []):
                lines.extend(
                    [
                        f"\t\tif {gdscript_string('signal ' + item)} not in {var_name}:",
                        f"\t\t\tfailures.append(\"{path} should declare signal {item}.\")",
                    ]
                )
            for item in script_check.get("functions", []):
                lines.extend(
                    [
                        f"\t\tif {gdscript_string('func ' + item + '(')} not in {var_name}:",
                        f"\t\t\tfailures.append(\"{path} should define function {item}().\")",
                    ]
                )

    lines.extend(
        [
            "",
            "func load_and_instantiate_scene() -> Node:",
            "\tif SCENE_PATH == \"\":",
            "\t\treturn null",
            "\tvar scene: PackedScene = load(SCENE_PATH) as PackedScene",
            "\tif scene == null:",
            "\t\tfailures.append(\"Could not load %s.\" % SCENE_PATH)",
            "\t\treturn null",
            "\tvar instance: Node = scene.instantiate()",
            "\tif instance == null:",
            "\t\tfailures.append(\"Could not instantiate %s.\" % SCENE_PATH)",
            "\t\treturn null",
            "\troot.add_child(instance)",
            "\treturn instance",
            "",
            "func validate_scene_structure(instance: Node) -> void:",
        ]
    )
    if not scene_checks:
        lines.append("\tpass")
    else:
        for scene_check in scene_checks:
            if scene_check["scene_path"] != scene_path:
                continue
            for node in scene_check.get("added_nodes", []):
                node_path = node["path"]
                node_type = node["type"]
                lines.extend(
                    [
                        f"\tvar node_{sanitize_identifier(node_path)}: Node = instance.get_node_or_null({gdscript_string(node_path)})",
                        f"\tif node_{sanitize_identifier(node_path)} == null:",
                        f"\t\tfailures.append(\"Missing node {node_path} in {scene_path}.\")",
                        "\telse:",
                        f"\t\tif not (node_{sanitize_identifier(node_path)} is {node_type}):",
                        f"\t\t\tfailures.append(\"Node {node_path} should be a {node_type}.\")",
                    ]
                )
                if node.get("script_path"):
                    lines.extend(
                        [
                            f"\t\tvar script_{sanitize_identifier(node_path)}: Script = node_{sanitize_identifier(node_path)}.get_script() as Script",
                            f"\t\tif script_{sanitize_identifier(node_path)} == null or script_{sanitize_identifier(node_path)}.resource_path != {gdscript_string(node['script_path'])}:",
                            f"\t\t\tfailures.append(\"Node {node_path} should use {node['script_path']}.\")",
                        ]
                    )
                if node.get("theme_path"):
                    lines.extend(
                        [
                            f"\t\tvar theme_{sanitize_identifier(node_path)}: Theme = node_{sanitize_identifier(node_path)}.theme",
                            f"\t\tif theme_{sanitize_identifier(node_path)} == null or theme_{sanitize_identifier(node_path)}.resource_path != {gdscript_string(node['theme_path'])}:",
                            f"\t\t\tfailures.append(\"Node {node_path} should use {node['theme_path']}.\")",
                        ]
                    )
                if node.get("visible") is False:
                    lines.extend(
                        [
                            f"\t\tif node_{sanitize_identifier(node_path)}.visible:",
                            f"\t\t\tfailures.append(\"Node {node_path} should start hidden.\")",
                        ]
                    )
                if node.get("offset_left") is not None and node.get("offset_top") is not None:
                    lines.extend(
                        [
                            f"\t\tif node_{sanitize_identifier(node_path)}.position.x > {max(node['offset_left'], 20.0)} or node_{sanitize_identifier(node_path)}.position.y > {max(node['offset_top'], 20.0)}:",
                            f"\t\t\tfailures.append(\"Node {node_path} should stay in the upper-left area.\")",
                        ]
                    )

    lines.extend(
        [
            "",
            "func finish() -> void:",
            "\tif failures.is_empty():",
            "\t\tprint(\"VALIDATION_PASSED\")",
            "\t\tquit(0)",
            "\t\treturn",
            "\tfor failure in failures:",
            "\t\tprint(\"VALIDATION_FAILED: %s\" % failure)",
            "\tquit(1)",
            "",
        ]
    )

    return "\n".join(lines)


def sanitize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return cleaned or "node"


def write_task_outputs(task_dir: Path, spec: Dict[str, Any], instruction: str, validator: str, dry_run: bool) -> None:
    if dry_run:
        return
    (task_dir / "task_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    config_path = task_dir / "task_config.json"
    config = read_json(config_path)
    config["instruction"] = instruction
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (task_dir / "test.gd").write_text(validator, encoding="utf-8")


def resolve_godot_bin(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        path = Path(explicit).expanduser()
        return str(path) if path.exists() else None
    env_path = os.environ.get("GODOT_BIN") or os.environ.get("GODOT_EXEC_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return str(path)
    for candidate in DEFAULT_GODOT_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return shutil.which("godot") or shutil.which("Godot")


def audit_task(task_dir: Path, godot_bin: str) -> Dict[str, Any]:
    result = {
        "task": task_dir.name,
        "solution_pass": None,
        "start_pass": None,
        "manual_review_required": read_json(task_dir / "task_spec.json").get("manual_review_required"),
    }
    validator_path = task_dir / "test.gd"
    if not validator_path.exists():
        result["error"] = "Missing test.gd"
        return result

    workspace_home = ROOT / ".godot-home"
    workspace_home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(workspace_home)

    for label in ("solution", "start"):
        project_dir = task_dir / label
        temp_dir = Path(tempfile.mkdtemp(prefix="gdb_task_audit_"))
        try:
            for item in project_dir.iterdir():
                dst = temp_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
            shutil.copy2(validator_path, temp_dir / "test.gd")
            completed = subprocess.run(
                [godot_bin, "--headless", "--path", str(temp_dir), "-s", "test.gd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            success = completed.returncode == 0 and "VALIDATION_PASSED" in (completed.stdout + completed.stderr)
            result[f"{label}_pass"] = success
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate task specs, instructions, and canonical test.gd validators.")
    parser.add_argument("--tasks", nargs="*", default=[], help="Optional task directory names or task ids, e.g. task_0003")
    parser.add_argument("--dry-run", action="store_true", help="Compute specs without writing files")
    parser.add_argument("--audit", action="store_true", help="Run generated validators against start/ and solution/")
    parser.add_argument("--force", action="store_true", help="Overwrite existing task_spec.json and test.gd")
    parser.add_argument("--godot-bin", help="Optional explicit Godot binary path for --audit")
    args = parser.parse_args()

    candidates = load_candidate_rows()
    overrides = load_overrides()
    tasks = task_dirs(args.tasks)
    if not tasks:
        raise SystemExit("No matching task directories found.")

    report: Dict[str, Any] = {"tasks": []}
    godot_bin = resolve_godot_bin(args.godot_bin) if args.audit else None
    if args.audit and not godot_bin:
        raise SystemExit("Could not resolve Godot binary for --audit.")

    for task_dir in tasks:
        config = read_json(task_dir / "task_config.json")
        tutorial_id = config.get("tutorial_id")
        if tutorial_id not in candidates:
            raise SystemExit(f"Missing metadata row for tutorial_id={tutorial_id} in {task_dir}")

        if not args.force and (task_dir / "task_spec.json").exists():
            raise SystemExit(f"{task_dir / 'task_spec.json'} already exists. Use --force to overwrite.")

        base_spec = build_base_spec(task_dir, candidates[tutorial_id])
        override = overrides.get(task_dir.name) or overrides.get(base_spec["task_id"]) or {}
        spec = deep_merge(base_spec, override)
        if spec.get("task_source_type") == "bootstrap":
            spec["manual_review_required"] = True
            spec.setdefault("notes", []).append("Bootstrap task has no start-to-solution diff; override required for a production validator.")

        instruction = build_instruction(spec)
        validator = render_validator(spec)
        write_task_outputs(task_dir, spec, instruction, validator, args.dry_run)

        task_report = {
            "task": task_dir.name,
            "manual_review_required": spec.get("manual_review_required", False),
            "wrote_files": [] if args.dry_run else ["task_spec.json", "task_config.json", "test.gd"],
        }
        if args.audit and godot_bin:
            if args.dry_run:
                raise SystemExit("--audit cannot be used with --dry-run")
            task_report["audit"] = audit_task(task_dir, godot_bin)
        report["tasks"].append(task_report)

    if not args.dry_run:
        REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
