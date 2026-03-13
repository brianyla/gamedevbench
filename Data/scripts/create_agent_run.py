#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from run_utils import (
    FRESH_RUN_EXCLUDES,
    ROOT,
    RUNS_DIR,
    TASKS_DIR,
    append_trajectory_event,
    build_initial_trajectory,
    ignore_by_name,
    next_attempt_index,
    read_text_if_exists,
    write_json,
    write_launch_script,
)


def load_task(task_ref: str) -> Tuple[Path, Dict]:
    task_dir = Path(task_ref)
    if not task_dir.is_absolute():
        task_dir = TASKS_DIR / task_ref
    task_dir = task_dir.resolve()
    if not task_dir.exists():
        raise SystemExit(f"Task not found: {task_ref}")
    config_path = task_dir / "task_config.json"
    if not config_path.exists():
        raise SystemExit(f"Missing task_config.json in {task_dir}")
    with config_path.open() as handle:
        config = json.load(handle)
    return task_dir, config


def build_public_task_config(config: Dict) -> Dict:
    return {
        "task_id": config.get("task_id"),
        "task_name": config.get("task_name"),
        "instruction": config.get("instruction"),
        "difficulty": config.get("difficulty"),
        "skill_category": config.get("skill_category"),
        "editor_type": config.get("editor_type"),
        "requires_multimodal": config.get("requires_multimodal"),
        "files_to_edit": config.get("files_to_edit", []),
    }


def write_run_readme(run_dir: Path, run_name: str, task_dir: Path, agent: str) -> None:
    readme = run_dir / "RUN_README.txt"
    readme.write_text(
        "\n".join(
            [
                f"Run directory: {run_name}",
                f"Task source: {task_dir}",
                "",
                "What to do:",
                "1. Open this directory as the agent workspace.",
                f"2. Launch the agent with: ./{'LAUNCH_CLAUDE.sh' if agent == 'claude-code' else 'LAUNCH_AGENT.sh'}",
                "3. Inside the agent, paste the contents of TASK_PROMPT.txt.",
                "4. Let the agent edit files in this directory.",
                "5. Exit the recorded shell to finish agent_trajectory.log.",
                "6. Validate with: python3 ../scripts/validate_agent_run.py <run_dir_name>",
                "7. Finalize with: python3 ../scripts/finalize_agent_run.py <run_dir_name> ...",
                "",
                "This directory starts from the task start/ state.",
                "LAUNCH_AGENT.sh records the whole terminal session to agent_trajectory.log.",
                "Validator files are intentionally not present in the agent workspace for fresh runs.",
                "Set AGENT_CMD or an agent-specific env var such as CLAUDE_CODE_CMD if the CLI is not on PATH.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a benchmark-style agent run directory from a task start state."
    )
    parser.add_argument("task", help="Task directory name under tasks/ or absolute path")
    parser.add_argument("--agent", required=True, help="Agent label, e.g. claude-code or codex")
    parser.add_argument("--timestamp", help="Optional timestamp override in YYYYMMDD_HHMMSS")
    args = parser.parse_args()

    task_dir, config = load_task(args.task)
    start_dir = task_dir / "start"
    if not start_dir.exists():
        raise SystemExit(f"Missing start directory in {task_dir}")

    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{task_dir.name}_{args.agent}_{timestamp}"
    run_dir = RUNS_DIR / run_name
    if run_dir.exists():
        raise SystemExit(f"Run directory already exists: {run_dir}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(start_dir, run_dir, ignore=ignore_by_name(FRESH_RUN_EXCLUDES))

    with (run_dir / "task_config.json").open("w") as handle:
        json.dump(build_public_task_config(config), handle, indent=2)

    if (task_dir / "transcript_excerpt.txt").exists():
        shutil.copy2(task_dir / "transcript_excerpt.txt", run_dir / "transcript_excerpt.txt")

    (run_dir / "TASK_PROMPT.txt").write_text(
        config.get("instruction", "").strip() + "\n",
        encoding="utf-8",
    )

    write_launch_script(run_dir, args.agent)
    write_run_readme(run_dir, run_name, task_dir, args.agent)
    task_prompt = read_text_if_exists(run_dir / "TASK_PROMPT.txt") or ""
    attempt_index = next_attempt_index(task_dir.name, args.agent)

    result = {
        "task_id": config.get("task_id"),
        "task_name": task_dir.name,
        "agent": args.agent,
        "timestamp": timestamp,
        "status": "prepared",
        "run_kind": "fresh",
        "attempt_index": attempt_index,
        "lineage": {
            "parent_run": None,
            "source_task_dir": str(task_dir),
        },
        "artifacts": {
            "task_prompt": "TASK_PROMPT.txt",
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
        task_id=config.get("task_id", ""),
        task_name=task_dir.name,
        agent=args.agent,
        model="",
        timestamp=timestamp,
        run_kind="fresh",
        attempt_index=attempt_index,
        parent_run=None,
        source_task_dir=str(task_dir),
        task_prompt=task_prompt,
    )
    write_json(run_dir / "trajectory.json", trajectory)
    append_trajectory_event(
        run_dir,
        "run_created",
        {
            "run_dir": run_name,
            "source": "start_state",
        },
    )
    append_trajectory_event(
        run_dir,
        "prompt_written",
        {
            "prompt_file": "TASK_PROMPT.txt",
            "prompt_kind": "task",
        },
    )

    print(run_dir)
    print(f"Next: cd {run_dir} && ./LAUNCH_AGENT.sh")


if __name__ == "__main__":
    main()
