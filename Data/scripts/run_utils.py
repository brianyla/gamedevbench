import json
import shlex
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "test_result"

EXCLUDED_RUN_ARTIFACTS = {
    ".DS_Store",
    ".godot",
    "agent_trajectory.log",
    "result.json",
    "trajectory.json",
    "validator_output.txt",
    "VALIDATOR_FEEDBACK.txt",
    "REPAIR_PROMPT.txt",
    "RUN_README.txt",
    "LAUNCH_AGENT.sh",
    "LAUNCH_CLAUDE.sh",
}

FRESH_RUN_EXCLUDES = EXCLUDED_RUN_ARTIFACTS | {"test.gd", "test.gd.uid"}


def next_attempt_index(task_dir_name: str, agent: str) -> int:
    prefix = f"{task_dir_name}_{agent}_"
    count = 0
    if RUNS_DIR.exists():
        for path in RUNS_DIR.iterdir():
            if path.is_dir() and path.name.startswith(prefix):
                count += 1
    return count + 1


def write_launch_script(run_dir: Path, agent: str) -> None:
    launch_script_path = run_dir / "LAUNCH_AGENT.sh"
    launch_script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'cd "$(dirname "$0")"',
                'SCRIPTS_DIR="$(cd ../.. && pwd)/scripts"',
                f'python3 "$SCRIPTS_DIR/launch_agent.py" {shlex.quote(str(run_dir))}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    launch_script_path.chmod(0o755)

    compat_path = run_dir / "LAUNCH_CLAUDE.sh"
    compat_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        "./LAUNCH_AGENT.sh\n",
        encoding="utf-8",
    )
    compat_path.chmod(0o755)


def ignore_by_name(excluded_names):
    def _ignore(_, names):
        ignored = set()
        for name in names:
            if name in excluded_names:
                ignored.add(name)
        return ignored
    return _ignore


def iso_timestamp() -> str:
    return datetime.now().isoformat()


def load_json(path: Path, default: Optional[Dict] = None) -> Dict:
    if path.exists():
        with path.open() as handle:
            return json.load(handle)
    return {} if default is None else default


def write_json(path: Path, payload: Dict) -> None:
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)


def trajectory_path(run_dir: Path) -> Path:
    return run_dir / "trajectory.json"


def build_initial_trajectory(
    *,
    task_id: str,
    task_name: str,
    agent: str,
    model: str,
    timestamp: str,
    run_kind: str,
    attempt_index: int,
    parent_run: Optional[str],
    source_task_dir: str,
    task_prompt: str,
    repair_prompt: Optional[str] = None,
    validator_feedback: Optional[str] = None,
    raw_terminal_log: Optional[str] = "agent_trajectory.log",
) -> Dict:
    return {
        "run": {
            "task_id": task_id,
            "task_name": task_name,
            "agent": agent,
            "model": model,
            "timestamp": timestamp,
            "run_kind": run_kind,
            "attempt_index": attempt_index,
            "parent_run": parent_run,
            "source_task_dir": source_task_dir,
        },
        "inputs": {
            "task_prompt": task_prompt,
            "repair_prompt": repair_prompt,
            "validator_feedback": validator_feedback,
        },
        "events": [],
        "validation": None,
        "solver": None,
        "artifacts": {
            "trajectory_file": "trajectory.json",
            "raw_terminal_log": raw_terminal_log,
            "validator_output": None,
        },
    }


def append_trajectory_event(run_dir: Path, event_type: str, payload: Dict) -> None:
    path = trajectory_path(run_dir)
    trajectory = load_json(path, default={"events": []})
    events = trajectory.setdefault("events", [])
    events.append(
        {
            "type": event_type,
            "timestamp": iso_timestamp(),
            "payload": payload,
        }
    )
    write_json(path, trajectory)


def update_trajectory_sections(
    run_dir: Path,
    *,
    validation: Optional[Dict] = None,
    solver: Optional[Dict] = None,
    artifacts: Optional[Dict] = None,
) -> None:
    path = trajectory_path(run_dir)
    trajectory = load_json(path, default={"events": []})
    if validation is not None:
        trajectory["validation"] = validation
    if solver is not None:
        trajectory["solver"] = solver
    if artifacts:
        trajectory.setdefault("artifacts", {}).update(artifacts)
    write_json(path, trajectory)


def read_text_if_exists(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()
