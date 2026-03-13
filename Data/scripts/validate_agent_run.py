#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from run_utils import (
    ROOT,
    RUNS_DIR,
    append_trajectory_event,
    load_json,
    update_trajectory_sections,
    write_json,
)

DEFAULT_GODOT_CANDIDATES = [
    Path("/Applications/Godot.app/Contents/MacOS/godot"),
    Path("/Applications/Godot.app/Contents/MacOS/Godot"),
]


def resolve_run_dir(run_ref: str) -> Path:
    run_dir = Path(run_ref)
    if not run_dir.is_absolute():
        run_dir = RUNS_DIR / run_ref
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_ref}")
    return run_dir


def resolve_godot_explicit_or_path(explicit_path: Optional[str]) -> str:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.exists():
            raise SystemExit(f"Godot binary not found: {path}")
        return str(path)

    env_path = os.environ.get("GODOT_BIN") or os.environ.get("GODOT_EXEC_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return str(path)

    for candidate in DEFAULT_GODOT_CANDIDATES:
        if candidate.exists():
            return str(candidate)

    found = shutil_which("godot") or shutil_which("Godot")
    if found:
        return found

    raise SystemExit("Could not resolve Godot binary. Set GODOT_BIN or pass --godot-bin.")


def shutil_which(binary: str) -> Optional[str]:
    for path_part in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_part) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def update_result_json(run_dir: Path, validation_payload: Dict) -> None:
    result_path = run_dir / "result.json"
    result = load_json(result_path)

    task_config_path = run_dir / "task_config.json"
    if task_config_path.exists():
        with task_config_path.open() as handle:
            task_config = json.load(handle)
        result.setdefault("task_id", task_config.get("task_id"))
        result.setdefault("task_name", task_config.get("task_name"))

    artifacts = result.setdefault("artifacts", {})
    artifacts["validator_output"] = "validator_output.txt"
    if result.get("status") == "prepared":
        result["status"] = "validated"
    result["validation"] = validation_payload

    write_json(result_path, result)


def copy_run_for_validation(run_dir: Path) -> Path:
    validation_dir = Path(tempfile.mkdtemp(prefix="gdb_validation_"))
    for item in run_dir.iterdir():
        if item.name in {"agent_trajectory.log", "validator_output.txt", "result.json"}:
            continue
        dst = validation_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)
    return validation_dir


def inject_validator(run_dir: Path, validation_dir: Path) -> None:
    source_test = run_dir / "test.gd"
    if source_test.exists():
        shutil.copy2(source_test, validation_dir / "test.gd")
        return

    task_config_path = run_dir / "task_config.json"
    if not task_config_path.exists():
        raise SystemExit("Missing task_config.json and no local test.gd to use for validation")

    with task_config_path.open() as handle:
        task_config = json.load(handle)
    task_id = task_config.get("task_id")
    if not task_id:
        raise SystemExit("task_config.json is missing task_id and no local test.gd is present")

    matches = sorted(ROOT.glob(f"tasks/{task_id}_*/test.gd"))
    if not matches:
        raise SystemExit(f"Could not locate canonical validator for {task_id}")
    shutil.copy2(matches[0], validation_dir / "test.gd")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a task validator against an agent run directory.")
    parser.add_argument("run_dir", help="Run directory name under test_result/ or absolute path")
    parser.add_argument("--godot-bin", help="Explicit Godot binary path")
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_dir)
    godot_bin = resolve_godot_explicit_or_path(args.godot_bin)
    workspace_home = ROOT / ".godot-home"
    workspace_home.mkdir(parents=True, exist_ok=True)
    validation_dir = copy_run_for_validation(run_dir)
    inject_validator(run_dir, validation_dir)
    append_trajectory_event(
        run_dir,
        "validator_started",
        {
            "run_dir": str(run_dir),
        },
    )

    cmd = [godot_bin, "--headless", "--path", str(validation_dir), "-s", "test.gd"]
    env = os.environ.copy()
    env["HOME"] = str(workspace_home)
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(validation_dir, ignore_errors=True)

    combined_output = completed.stdout
    if completed.stderr:
        if combined_output and not combined_output.endswith("\n"):
            combined_output += "\n"
        combined_output += completed.stderr

    validator_output_path = run_dir / "validator_output.txt"
    validator_output_path.write_text(combined_output, encoding="utf-8")

    success = completed.returncode == 0 and "VALIDATION_PASSED" in combined_output and "VALIDATION_FAILED:" not in combined_output
    failure_lines = [
        line.strip()
        for line in combined_output.splitlines()
        if "VALIDATION_FAILED:" in line
    ]
    message = "Validation passed" if success else (
        failure_lines[0] if failure_lines else f"Validation failed with exit code {completed.returncode}"
    )

    validation_payload = {
        "success": success,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "command": cmd,
        "exit_code": completed.returncode,
        "output_file": "validator_output.txt",
        "failure_count": len(failure_lines),
        "failure_messages": failure_lines,
        "validated_in_isolation": True,
    }
    update_result_json(run_dir, validation_payload)
    update_trajectory_sections(
        run_dir,
        validation=validation_payload,
        artifacts={"validator_output": "validator_output.txt"},
    )
    append_trajectory_event(
        run_dir,
        "validator_finished",
        {
            "success": success,
            "message": message,
            "failure_messages": failure_lines,
            "exit_code": completed.returncode,
            "validated_in_isolation": True,
        },
    )

    print(validator_output_path)
    print(message)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
