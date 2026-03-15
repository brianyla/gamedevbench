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
    existing_solver = result.get("solver") or {}
    existing_tokens = existing_solver.get("token_usage") or {}
    solver_payload = {
        "success": bool(args.solver_success or existing_solver.get("success")),
        "message": args.solver_message or existing_solver.get("message", ""),
        "duration_seconds": args.duration_seconds if args.duration_seconds else existing_solver.get("duration_seconds", 0.0),
        "is_rate_limited": bool(args.rate_limited or existing_solver.get("is_rate_limited")),
        "model": args.model or existing_solver.get("model", ""),
        "cost_usd": args.cost_usd if args.cost_usd else existing_solver.get("cost_usd", 0.0),
        "token_usage": {
            "input_tokens": args.input_tokens if args.input_tokens else existing_tokens.get("input_tokens", 0),
            "output_tokens": args.output_tokens if args.output_tokens else existing_tokens.get("output_tokens", 0),
            "total_tokens": 0,
            "cache_read_tokens": args.cache_read_tokens if args.cache_read_tokens else existing_tokens.get("cache_read_tokens", 0),
            "cache_write_tokens": args.cache_write_tokens if args.cache_write_tokens else existing_tokens.get("cache_write_tokens", 0),
        },
    }
    solver_payload["token_usage"]["total_tokens"] = (
        solver_payload["token_usage"]["input_tokens"] + solver_payload["token_usage"]["output_tokens"]
    )
    result["solver"] = solver_payload

    result_path = run_dir / "result.json"
    write_json(result_path, result)
    update_trajectory_sections(
        run_dir,
        solver=solver_payload,
        classification=result.get("classification"),
        task_bundle_health=result.get("task_bundle_health"),
    )
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
