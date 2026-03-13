#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_ROOT = SCRIPT_DIR.parent
REPO_ROOT = DATA_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from claude_code_sdk import ClaudeCodeOptions, query

from gamedevbench.src.utils.prompts import create_system_prompt
from gamedevbench.src.utils.data_types import TokenUsage

from run_utils import (
    append_trajectory_event,
    load_json,
    read_text_if_exists,
    update_trajectory_sections,
    write_json,
)


def resolve_run_dir(arg: str) -> Path:
    run_dir = Path(arg).resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")
    return run_dir


def select_prompt(run_dir: Path) -> Tuple[str, str]:
    repair_prompt = run_dir / "REPAIR_PROMPT.txt"
    if repair_prompt.exists():
        return "repair", repair_prompt.read_text(encoding="utf-8").strip()
    task_prompt = run_dir / "TASK_PROMPT.txt"
    if task_prompt.exists():
        return "task", task_prompt.read_text(encoding="utf-8").strip()
    raise SystemExit(f"No prompt file found in {run_dir}")


def block_to_dict(block: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": block.__class__.__name__}
    if is_dataclass(block):
        payload.update(asdict(block))
        return payload
    payload.update(getattr(block, "__dict__", {}))
    return payload


def message_to_event_payload(message: Any) -> Tuple[str, Dict[str, Any]]:
    message_type = message.__class__.__name__
    if message_type in {"AssistantMessage", "UserMessage"}:
        content = getattr(message, "content", None)
        if isinstance(content, list):
            blocks = [block_to_dict(block) for block in content]
        else:
            blocks = content
        return (
            "sdk_message",
            {
                "message_type": message_type,
                "model": getattr(message, "model", None),
                "parent_tool_use_id": getattr(message, "parent_tool_use_id", None),
                "content": blocks,
            },
        )
    if message_type == "SystemMessage":
        return (
            "sdk_system",
            {
                "subtype": getattr(message, "subtype", None),
                "data": getattr(message, "data", None),
            },
        )
    if message_type == "ResultMessage":
        return (
            "sdk_result",
            {
                "subtype": getattr(message, "subtype", None),
                "duration_ms": getattr(message, "duration_ms", None),
                "duration_api_ms": getattr(message, "duration_api_ms", None),
                "is_error": getattr(message, "is_error", None),
                "num_turns": getattr(message, "num_turns", None),
                "session_id": getattr(message, "session_id", None),
                "total_cost_usd": getattr(message, "total_cost_usd", None),
                "usage": getattr(message, "usage", None),
                "result": getattr(message, "result", None),
            },
        )
    return (
        "sdk_raw_message",
        {
            "message_type": message_type,
            "repr": repr(message),
        },
    )


async def run_claude_sdk(run_dir: Path) -> int:
    prompt_kind, prompt = select_prompt(run_dir)
    model = os.environ.get("CLAUDE_MODEL", "").strip() or None
    options_kwargs: Dict[str, Any] = {
        "system_prompt": create_system_prompt(False),
        "permission_mode": "bypassPermissions",
        "cwd": str(run_dir),
    }
    if model:
        options_kwargs["model"] = model
    options = ClaudeCodeOptions(**options_kwargs)

    append_trajectory_event(
        run_dir,
        "sdk_query_started",
        {
            "prompt_kind": prompt_kind,
            "model": model or "",
        },
    )

    start_time = time.time()
    token_usage = TokenUsage()
    total_cost = 0.0
    model_used = model or ""
    final_result: Dict[str, Any] = {}
    stdout_parts: List[str] = []

    try:
        async for message in query(prompt=prompt, options=options):
            event_type, payload = message_to_event_payload(message)
            append_trajectory_event(run_dir, event_type, payload)

            rendered = str(message)
            stdout_parts.append(rendered)
            print(rendered, flush=True)

            usage = getattr(message, "usage", None)
            if usage:
                token_usage.input_tokens += usage.get("input_tokens", 0)
                token_usage.output_tokens += usage.get("output_tokens", 0)
                token_usage.total_tokens = token_usage.input_tokens + token_usage.output_tokens
                token_usage.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                token_usage.cache_write_tokens += usage.get("cache_creation_input_tokens", 0)

            total_cost_usd = getattr(message, "total_cost_usd", None)
            if total_cost_usd:
                total_cost += total_cost_usd

            message_model = getattr(message, "model", None)
            if message_model:
                model_used = message_model

            if message.__class__.__name__ == "ResultMessage":
                final_result = {
                    "subtype": getattr(message, "subtype", None),
                    "is_error": getattr(message, "is_error", None),
                    "result": getattr(message, "result", None),
                    "session_id": getattr(message, "session_id", None),
                }

        duration = time.time() - start_time
        solver_payload = {
            "success": not final_result.get("is_error", False),
            "message": final_result.get("result") or "Task completed",
            "duration_seconds": duration,
            "is_rate_limited": False,
            "model": model_used,
            "cost_usd": total_cost,
            "token_usage": token_usage.to_dict(),
        }
        update_trajectory_sections(run_dir, solver=solver_payload)
        append_trajectory_event(
            run_dir,
            "sdk_query_finished",
            {
                "success": solver_payload["success"],
                "model": model_used,
                "duration_seconds": duration,
                "total_cost_usd": total_cost,
            },
        )

        result_path = run_dir / "result.json"
        result = load_json(result_path)
        result["solver"] = solver_payload
        result.setdefault("artifacts", {})["sdk_stdout_file"] = "sdk_stdout.txt"
        write_json(result_path, result)
        (run_dir / "sdk_stdout.txt").write_text("".join(stdout_parts), encoding="utf-8")
        update_trajectory_sections(run_dir, artifacts={"sdk_stdout_file": "sdk_stdout.txt"})
        return 0 if solver_payload["success"] else 1
    except Exception as exc:
        duration = time.time() - start_time
        error_message = str(exc)
        append_trajectory_event(
            run_dir,
            "sdk_query_finished",
            {
                "success": False,
                "model": model_used,
                "duration_seconds": duration,
                "error": error_message,
            },
        )
        solver_payload = {
            "success": False,
            "message": f"Error invoking Claude Code SDK: {error_message}",
            "duration_seconds": duration,
            "is_rate_limited": False,
            "model": model_used,
            "cost_usd": total_cost,
            "token_usage": token_usage.to_dict(),
        }
        update_trajectory_sections(run_dir, solver=solver_payload)
        result_path = run_dir / "result.json"
        result = load_json(result_path)
        result["solver"] = solver_payload
        write_json(result_path, result)
        print(error_message, file=sys.stderr)
        return 1


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: run_agent_with_sdk.py <run_dir>")
    run_dir = resolve_run_dir(sys.argv[1])
    raise SystemExit(asyncio.run(run_claude_sdk(run_dir)))


if __name__ == "__main__":
    main()
