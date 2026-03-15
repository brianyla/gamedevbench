#!/usr/bin/env python3
"""Run the full one-attempt task pipeline: create a run, launch the agent,
validate the result, classify the outcome, finalize metadata, and export the
canonical artifact."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from run_utils import (
    ROOT,
    RUNS_DIR,
    classify_pipeline_failure,
    load_json,
    update_trajectory_sections,
    write_json,
)


SCRIPTS_DIR = Path(__file__).resolve().parent


def run_command(cmd: List[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_created_run_dir(stdout: str) -> Path:
    first_line = stdout.strip().splitlines()[0].strip()
    run_dir = Path(first_line)
    if not run_dir.is_absolute():
        run_dir = (ROOT / first_line).resolve()
    return run_dir


def persist_pipeline_failure(run_dir: Optional[Path], message: str) -> None:
    if run_dir is None or not run_dir.exists():
        return
    result_path = run_dir / "result.json"
    if not result_path.exists():
        return
    result = load_json(result_path)
    classification = classify_pipeline_failure(message)
    result["classification"] = classification
    write_json(result_path, result)
    update_trajectory_sections(
        run_dir,
        classification=classification,
        task_bundle_health=result.get("task_bundle_health"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full one-attempt agent pipeline for a task.")
    parser.add_argument("task", help="Task directory name under tasks/ or absolute path")
    parser.add_argument("--agent", required=True, help="Agent label, e.g. claude-code")
    parser.add_argument("--timestamp", help="Optional timestamp override in YYYYMMDD_HHMMSS")
    parser.add_argument("--model", default="", help="Optional model label to persist during finalization")
    parser.add_argument("--godot-bin", help="Optional explicit Godot binary path")
    parser.add_argument("--skip-export", action="store_true", help="Do not export a canonical run")
    parser.add_argument("--include-raw-log", action="store_true", help="Include raw terminal log in export")
    args = parser.parse_args()

    run_dir: Optional[Path] = None
    try:
        create_cmd = [sys.executable, str(SCRIPTS_DIR / "create_agent_run.py"), args.task, "--agent", args.agent]
        if args.timestamp:
            create_cmd.extend(["--timestamp", args.timestamp])
        created = run_command(create_cmd, cwd=ROOT)
        if created.returncode != 0:
            raise SystemExit(created.stderr.strip() or created.stdout.strip() or "Failed to create run directory.")
        run_dir = parse_created_run_dir(created.stdout)

        launch_cmd = [sys.executable, str(SCRIPTS_DIR / "launch_agent.py"), str(run_dir)]
        launched = subprocess.run(launch_cmd, cwd=ROOT, check=False)
        if launched.returncode != 0:
            persist_pipeline_failure(run_dir, f"Agent launch failed with exit code {launched.returncode}.")
            raise SystemExit(launched.returncode)

        validate_cmd = [sys.executable, str(SCRIPTS_DIR / "validate_agent_run.py"), str(run_dir)]
        if args.godot_bin:
            validate_cmd.extend(["--godot-bin", args.godot_bin])
        validated = run_command(validate_cmd, cwd=ROOT)
        if validated.stdout:
            print(validated.stdout.strip())
        if validated.stderr:
            print(validated.stderr.strip(), file=sys.stderr)

        result = load_json(run_dir / "result.json")
        solver = result.get("solver") or {}
        finalize_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "finalize_agent_run.py"),
            str(run_dir),
            "--solver-message",
            solver.get("message", "Attempt completed"),
            "--model",
            args.model or solver.get("model", ""),
        ]
        if solver.get("success"):
            finalize_cmd.append("--solver-success")
        finalized = run_command(finalize_cmd, cwd=ROOT)
        if finalized.returncode != 0:
            persist_pipeline_failure(run_dir, finalized.stderr.strip() or finalized.stdout.strip() or "Finalization failed.")
            raise SystemExit(finalized.returncode)

        export_path = None
        if not args.skip_export:
            export_cmd = [sys.executable, str(SCRIPTS_DIR / "export_canonical_run.py"), str(run_dir)]
            if args.include_raw_log:
                export_cmd.append("--include-raw-log")
            exported = run_command(export_cmd, cwd=ROOT)
            if exported.returncode != 0:
                persist_pipeline_failure(run_dir, exported.stderr.strip() or exported.stdout.strip() or "Export failed.")
                raise SystemExit(exported.returncode)
            export_path = exported.stdout.strip().splitlines()[-1].strip()

        result = load_json(run_dir / "result.json")
        classification = result.get("classification", {})
        validation = result.get("validation", {})
        print(f"run_dir={run_dir}")
        print(f"validation_success={validation.get('success')}")
        print(f"classification={classification.get('primary_label')}")
        if export_path:
            print(f"export_dir={export_path}")

        raise SystemExit(0 if validation.get("success") else 1)
    except SystemExit:
        raise
    except Exception as exc:
        persist_pipeline_failure(run_dir, str(exc))
        raise


if __name__ == "__main__":
    main()
