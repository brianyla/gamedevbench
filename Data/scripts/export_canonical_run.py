#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path
from typing import Set

from run_utils import ROOT, RUNS_DIR


EXPORTS_DIR = ROOT / "canonical_runs"
CANONICAL_FILES = {
    "TASK_PROMPT.txt",
    "REPAIR_PROMPT.txt",
    "VALIDATOR_FEEDBACK.txt",
    "validator_output.txt",
    "result.json",
    "trajectory.json",
}


def resolve_run_dir(run_ref: str) -> Path:
    run_dir = Path(run_ref)
    if not run_dir.is_absolute():
        run_dir = RUNS_DIR / run_ref
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_ref}")
    return run_dir


def should_copy_project_file(path: Path) -> bool:
    if any(part == ".godot" for part in path.parts):
        return False
    if path.name in {
        ".DS_Store",
        "LAUNCH_AGENT.sh",
        "LAUNCH_CLAUDE.sh",
        "RUN_README.txt",
        "agent_trajectory.log",
        "test.gd",
        "test.gd.uid",
    }:
        return False
    if path.suffix == ".uid":
        return False
    return True


def copy_project_tree(src_dir: Path, dst_dir: Path) -> None:
    for item in src_dir.iterdir():
        if item.name in CANONICAL_FILES:
            continue
        if not should_copy_project_file(item):
            continue
        dst = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                dst,
                ignore=shutil.ignore_patterns(".DS_Store", ".godot", "*.uid"),
            )
        else:
            shutil.copy2(item, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a canonicalized run directory for dataset use.")
    parser.add_argument("run_dir", help="Run directory name under test_result/ or absolute path")
    parser.add_argument("--output-dir", help="Optional output directory root")
    parser.add_argument("--include-raw-log", action="store_true", help="Include raw agent_trajectory.log in the export")
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_dir)
    output_root = Path(args.output_dir).resolve() if args.output_dir else EXPORTS_DIR
    export_dir = output_root / run_dir.name
    if export_dir.exists():
        raise SystemExit(f"Export directory already exists: {export_dir}")

    export_dir.mkdir(parents=True, exist_ok=False)
    copy_project_tree(run_dir, export_dir)

    for name in CANONICAL_FILES:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, export_dir / name)

    if args.include_raw_log and (run_dir / "agent_trajectory.log").exists():
        raw_dir = export_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / "agent_trajectory.log", raw_dir / "agent_trajectory.log")

    print(export_dir)


if __name__ == "__main__":
    main()
