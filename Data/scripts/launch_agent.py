#!/usr/bin/env python3
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from run_utils import append_trajectory_event, load_json


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_ROOT = SCRIPT_DIR.parent


def resolve_run_dir(arg: str) -> Path:
    run_dir = Path(arg).resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")
    return run_dir


def load_agent_label(run_dir: Path) -> str:
    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise SystemExit(f"Missing result.json in {run_dir}")
    result = load_json(result_path)
    agent = result.get("agent")
    if not agent:
        raise SystemExit(f"result.json in {run_dir} is missing 'agent'")
    return str(agent)


def resolve_agent_command(agent: str) -> str:
    agent_env_var = agent.upper().replace("-", "_") + "_CMD"

    if os.environ.get("AGENT_CMD"):
        return os.environ["AGENT_CMD"]

    if agent == "claude-code":
        cache_dir = os.environ.get("UV_CACHE_DIR", str(DATA_ROOT / ".uv-cache"))
        return (
            f"UV_CACHE_DIR={shlex.quote(cache_dir)} "
            f"uv run python {shlex.quote(str(SCRIPT_DIR / 'run_agent_with_sdk.py'))} ."
        )

    if os.environ.get(agent_env_var):
        return os.environ[agent_env_var]

    if shutil_which(agent):
        return agent

    raise SystemExit(
        f"Could not resolve an agent command for {agent}. "
        f"Set AGENT_CMD or {agent_env_var} before launching."
    )


def shutil_which(binary: str) -> Optional[str]:
    for path_part in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_part) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: launch_agent.py <run_dir>")

    run_dir = resolve_run_dir(sys.argv[1])
    agent = load_agent_label(run_dir)
    command = resolve_agent_command(agent)

    print("Recording trajectory to agent_trajectory.log")
    print(f"Launching: {command}")
    append_trajectory_event(
        run_dir,
        "agent_launch_started",
        {
            "agent": agent,
            "command": command,
        },
    )

    completed = subprocess.run(
        ["script", "-q", "agent_trajectory.log", "bash", "-lc", command],
        cwd=run_dir,
        check=False,
    )

    append_trajectory_event(
        run_dir,
        "agent_launch_finished",
        {
            "agent": agent,
            "command": command,
            "exit_code": completed.returncode,
        },
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
