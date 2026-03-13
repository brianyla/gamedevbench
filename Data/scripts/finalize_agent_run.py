#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from run_utils import RUNS_DIR, append_trajectory_event, load_json, update_trajectory_sections, write_json


def load_result(run_ref: str) -> Tuple[Path, Dict]:
    run_dir = Path(run_ref)
    if not run_dir.is_absolute():
        run_dir = RUNS_DIR / run_ref
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    result_path = run_dir / "result.json"
    result = load_json(result_path)
    return run_dir, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize a benchmark-style agent run directory.")
    parser.add_argument("run_dir", help="Run directory name under test_result/ or absolute path")
    parser.add_argument("--solver-success", action="store_true", help="Mark solver as successful")
    parser.add_argument("--solver-message", default="", help="Solver outcome summary")
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--model", default="")
    parser.add_argument("--cost-usd", type=float, default=0.0)
    parser.add_argument("--input-tokens", type=int, default=0)
    parser.add_argument("--output-tokens", type=int, default=0)
    parser.add_argument("--cache-read-tokens", type=int, default=0)
    parser.add_argument("--cache-write-tokens", type=int, default=0)
    parser.add_argument("--rate-limited", action="store_true", help="Mark the run as rate-limited")
    args = parser.parse_args()

    run_dir, result = load_result(args.run_dir)

    result["status"] = "completed"
    result["completed_at"] = datetime.now().isoformat()
    solver_payload = {
        "success": bool(args.solver_success),
        "message": args.solver_message,
        "duration_seconds": args.duration_seconds,
        "is_rate_limited": bool(args.rate_limited),
        "model": args.model,
        "cost_usd": args.cost_usd,
        "token_usage": {
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "total_tokens": args.input_tokens + args.output_tokens,
            "cache_read_tokens": args.cache_read_tokens,
            "cache_write_tokens": args.cache_write_tokens,
        },
    }
    result["solver"] = solver_payload

    result_path = run_dir / "result.json"
    write_json(result_path, result)
    update_trajectory_sections(run_dir, solver=solver_payload)
    append_trajectory_event(
        run_dir,
        "run_finalized",
        {
            "solver_success": bool(args.solver_success),
            "model": args.model,
            "duration_seconds": args.duration_seconds,
        },
    )

    print(result_path)


if __name__ == "__main__":
    main()
