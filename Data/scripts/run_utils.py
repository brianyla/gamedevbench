import json
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "test_result"
METADATA_DIR = ROOT / "metadata"
TASK_REPORT_PATH = METADATA_DIR / "task_generation_report.json"

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
        "classification": None,
        "task_bundle_health": None,
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
    classification: Optional[Dict] = None,
    task_bundle_health: Optional[Dict] = None,
    artifacts: Optional[Dict] = None,
) -> None:
    path = trajectory_path(run_dir)
    trajectory = load_json(path, default={"events": []})
    if validation is not None:
        trajectory["validation"] = validation
    if solver is not None:
        trajectory["solver"] = solver
    if classification is not None:
        trajectory["classification"] = classification
    if task_bundle_health is not None:
        trajectory["task_bundle_health"] = task_bundle_health
    if artifacts:
        trajectory.setdefault("artifacts", {}).update(artifacts)
    write_json(path, trajectory)


def read_text_if_exists(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def load_task_generation_report() -> Dict[str, Any]:
    return load_json(TASK_REPORT_PATH, default={"tasks": []})


def infer_task_bundle_health(task_name: str) -> Dict[str, Any]:
    report = load_task_generation_report()
    for task_entry in report.get("tasks", []):
        if task_entry.get("task") != task_name:
            continue
        audit = task_entry.get("audit") or {}
        manual_review_required = bool(task_entry.get("manual_review_required"))
        if manual_review_required:
            return {
                "status": "manual_review_required",
                "bundle_failure_label": "task_spec_failure",
                "evidence": ["Task bundle is marked manual_review_required."],
                "audit": audit,
            }
        solution_pass = audit.get("solution_pass")
        start_pass = audit.get("start_pass")
        if solution_pass is True and start_pass is False:
            return {
                "status": "ok",
                "bundle_failure_label": None,
                "evidence": [],
                "audit": audit,
            }
        if solution_pass is False:
            return {
                "status": "audit_failed",
                "bundle_failure_label": "validator_failure",
                "evidence": ["Canonical solution failed task audit validation."],
                "audit": audit,
            }
        if solution_pass is True and start_pass is True:
            return {
                "status": "audit_failed",
                "bundle_failure_label": "validator_failure",
                "evidence": ["Task start state unexpectedly passed task audit validation."],
                "audit": audit,
            }
        return {
            "status": "unknown",
            "bundle_failure_label": None,
            "evidence": ["Task audit information is incomplete."],
            "audit": audit,
        }
    return {
        "status": "unknown",
        "bundle_failure_label": None,
        "evidence": ["No task bundle audit information found."],
        "audit": None,
    }


ENVIRONMENT_ERROR_PATTERNS = [
    r"SCRIPT ERROR: Compile Error",
    r"SCRIPT ERROR: Parse Error",
    r"ERROR: Failed to load script",
    r"Identifier not found:",
    r"Could not find type",
    r"Could not find base class",
    r"autoload",
    r"Invalid project path specified",
    r"Could not resolve Godot binary",
]


def classify_run_failure(
    *,
    validation_payload: Optional[Dict[str, Any]],
    validator_output: str,
    task_bundle_health: Dict[str, Any],
) -> Dict[str, Any]:
    if validation_payload and validation_payload.get("success"):
        return {
            "primary_label": "ok",
            "failure_subtype": None,
            "classification_stage": "validation",
            "classification_confidence": "high",
            "failure_evidence": [],
        }

    for pattern in ENVIRONMENT_ERROR_PATTERNS:
        if re.search(pattern, validator_output, flags=re.IGNORECASE):
            return {
                "primary_label": "environment_failure",
                "failure_subtype": "validator_runtime_error",
                "classification_stage": "validation",
                "classification_confidence": "high",
                "failure_evidence": extract_failure_evidence(validator_output),
            }

    bundle_label = task_bundle_health.get("bundle_failure_label")
    if bundle_label:
        return {
            "primary_label": bundle_label,
            "failure_subtype": task_bundle_health.get("status"),
            "classification_stage": "task_bundle_audit",
            "classification_confidence": "medium",
            "failure_evidence": task_bundle_health.get("evidence", []),
        }

    failure_evidence = extract_failure_evidence(validator_output)
    if failure_evidence:
        return {
            "primary_label": "agent_failure",
            "failure_subtype": "validation_requirements_not_met",
            "classification_stage": "validation",
            "classification_confidence": "high",
            "failure_evidence": failure_evidence,
        }

    return {
        "primary_label": "environment_failure",
        "failure_subtype": "unknown_validation_error",
        "classification_stage": "validation",
        "classification_confidence": "medium",
        "failure_evidence": extract_failure_evidence(validator_output),
    }


def classify_pipeline_failure(message: str) -> Dict[str, Any]:
    return {
        "primary_label": "pipeline_failure",
        "failure_subtype": "pipeline_step_failed",
        "classification_stage": "pipeline",
        "classification_confidence": "high",
        "failure_evidence": [message],
    }


def extract_failure_evidence(output: str) -> List[str]:
    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if "VALIDATION_FAILED:" in stripped or "Compile Error" in stripped or "Parse Error" in stripped or "Failed to load script" in stripped:
            lines.append(stripped)
    return lines[:10]
