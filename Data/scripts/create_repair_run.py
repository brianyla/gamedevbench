#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

from run_utils import (
    EXCLUDED_RUN_ARTIFACTS,
    ROOT,
    RUNS_DIR,
    TASKS_DIR,
    append_trajectory_event,
    build_initial_trajectory,
    load_json,
    next_attempt_index,
    read_text_if_exists,
    write_json,
    write_launch_script,
)


def load_run(run_ref: str) -> Tuple[Path, Dict]:
    run_dir = Path(run_ref)
    if not run_dir.is_absolute():
        run_dir = RUNS_DIR / run_ref
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_ref}")
    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise SystemExit(f"Missing result.json in {run_dir}")
    with result_path.open() as handle:
        result = json.load(handle)
    return run_dir, result


def resolve_task_dir(task_name: str) -> Path:
    task_dir = TASKS_DIR / task_name
    if not task_dir.exists():
        raise SystemExit(f"Task directory not found for repair run: {task_dir}")
    return task_dir


def load_task_id(task_dir: Path) -> str:
    config_path = task_dir / "task_config.json"
    if not config_path.exists():
        return ""
    with config_path.open() as handle:
        config = json.load(handle)
    return config.get("task_id", "")


def should_ignore(_: str, names: List[str]) -> Set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_RUN_ARTIFACTS:
            ignored.add(name)
    return ignored


def extract_repair_feedback(raw_feedback: str) -> str:
    lines = []
    for line in raw_feedback.splitlines():
        stripped = line.strip()
        if stripped.startswith("VALIDATION_FAILED:"):
            lines.append(stripped)
    return "\n".join(lines).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a repair-attempt run directory from an existing run."
    )
    parser.add_argument("source_run", help="Run directory name under test_result/ or absolute path")
    parser.add_argument("--timestamp", help="Optional timestamp override in YYYYMMDD_HHMMSS")
    parser.add_argument(
        "--feedback-file",
        default="validator_output.txt",
        help="Feedback file to carry into the repair run, relative to the source run",
    )
    args = parser.parse_args()

    source_run_dir, source_result = load_run(args.source_run)
    agent = source_result.get("agent")
    task_name = source_result.get("task_name")
    if not agent or not task_name:
        raise SystemExit("Source run result.json is missing agent or task_name")
    validation = source_result.get("validation")
    if not validation:
        raise SystemExit("Source run must be validated before creating a repair run")
    if validation.get("success"):
        raise SystemExit("Cannot create a repair run from a passing run")

    task_dir = resolve_task_dir(task_name)
    task_id = source_result.get("task_id") or load_task_id(task_dir)
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{task_name}_{agent}_{timestamp}"
    run_dir = RUNS_DIR / run_name
    if run_dir.exists():
        raise SystemExit(f"Run directory already exists: {run_dir}")

    shutil.copytree(source_run_dir, run_dir, ignore=should_ignore)
    if (task_dir / "test.gd").exists():
        shutil.copy2(task_dir / "test.gd", run_dir / "test.gd")

    feedback_path = source_run_dir / args.feedback_file
    feedback_text = ""
    if feedback_path.exists():
        raw_feedback = feedback_path.read_text(encoding="utf-8").strip()
        feedback_text = extract_repair_feedback(raw_feedback) or raw_feedback
        (run_dir / "VALIDATOR_FEEDBACK.txt").write_text(feedback_text + "\n", encoding="utf-8")

    task_prompt = read_text_if_exists(run_dir / "TASK_PROMPT.txt") or ""
    repair_prompt_parts = [
        "This is a repair attempt for a previously failed benchmark run.",
        "Use the existing workspace state as your starting point.",
        "Make only the changes needed to satisfy the task and validator.",
    ]
    if task_prompt:
        repair_prompt_parts.extend(["", "Original task instruction:", task_prompt])
    if feedback_text:
        repair_prompt_parts.extend(["", "Validator feedback from the previous attempt:", feedback_text])
    (run_dir / "REPAIR_PROMPT.txt").write_text("\n".join(repair_prompt_parts) + "\n", encoding="utf-8")

    write_launch_script(run_dir, agent)
    attempt_index = next_attempt_index(task_name, agent)

    result = {
        "task_id": task_id,
        "task_name": task_name,
        "agent": agent,
        "timestamp": timestamp,
        "status": "prepared",
        "run_kind": "repair",
        "attempt_index": attempt_index,
        "lineage": {
            "parent_run": source_run_dir.name,
            "source_task_dir": str(task_dir),
        },
        "artifacts": {
            "task_prompt": "TASK_PROMPT.txt",
            "repair_prompt": "REPAIR_PROMPT.txt",
            "validator_feedback": "VALIDATOR_FEEDBACK.txt" if feedback_text else None,
            "trajectory_file": "trajectory.json",
            "raw_terminal_log": "agent_trajectory.log",
            "trajectory_log": "agent_trajectory.log",
            "validator_output": None,
        },
        "validation": None,
        "solver": None,
    }
    write_json(run_dir / "result.json", result)

    trajectory = build_initial_trajectory(
        task_id=task_id,
        task_name=task_name,
        agent=agent,
        model="",
        timestamp=timestamp,
        run_kind="repair",
        attempt_index=attempt_index,
        parent_run=source_run_dir.name,
        source_task_dir=str(task_dir),
        task_prompt=task_prompt,
        repair_prompt=read_text_if_exists(run_dir / "REPAIR_PROMPT.txt"),
        validator_feedback=feedback_text or None,
    )
    write_json(run_dir / "trajectory.json", trajectory)
    append_trajectory_event(
        run_dir,
        "repair_run_created",
        {
            "run_dir": run_name,
            "parent_run": source_run_dir.name,
        },
    )
    append_trajectory_event(
        run_dir,
        "validator_feedback_attached",
        {
            "feedback_file": args.feedback_file,
            "has_feedback": bool(feedback_text),
        },
    )
    append_trajectory_event(
        run_dir,
        "prompt_written",
        {
            "prompt_file": "REPAIR_PROMPT.txt",
            "prompt_kind": "repair",
        },
    )

    (run_dir / "RUN_README.txt").write_text(
        "\n".join(
            [
                f"Repair run directory: {run_name}",
                f"Parent run: {source_run_dir.name}",
                "",
                "What to do:",
                "1. Open this directory as the agent workspace.",
                "2. Launch the agent with ./LAUNCH_AGENT.sh.",
                "3. Paste REPAIR_PROMPT.txt into the agent.",
                "4. Let the agent repair the current workspace state.",
                "5. Exit the recorded shell to finish agent_trajectory.log.",
                "6. Validate with python3 ../scripts/validate_agent_run.py <run_dir_name>.",
                "7. Finalize with python3 ../scripts/finalize_agent_run.py <run_dir_name> ...",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(run_dir)
    print(f"Next: cd {run_dir} && ./LAUNCH_AGENT.sh")


if __name__ == "__main__":
    main()
