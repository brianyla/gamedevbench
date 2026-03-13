# Agent Runs

This folder stores benchmark-style agent attempts and is the source of trajectory data.

Each run directory should contain:

```text
<task_dir_name>_<agent>_<timestamp>/
  project.godot
  ... edited Godot project copied from the task start state or prior failed run ...
  task_config.json
  transcript_excerpt.txt
  TASK_PROMPT.txt
  REPAIR_PROMPT.txt                # repair runs only
  VALIDATOR_FEEDBACK.txt           # repair runs only
  LAUNCH_AGENT.sh
  LAUNCH_CLAUDE.sh                 # compatibility wrapper
  agent_trajectory.log
  validator_output.txt             # after validation
  result.json
  trajectory.json
```

`result.json` is the structured metadata record for the run. `agent_trajectory.log` is the raw terminal capture.
`trajectory.json` is the canonical machine-readable trajectory artifact for dataset use.

Fresh runs intentionally do not expose `test.gd` to the agent workspace. Validation injects the canonical validator into a separate temporary clone.

## Fresh Run Workflow

```bash
python3 scripts/create_agent_run.py task_0003_add_debug_info_panel --agent claude-code
cd test_result/<run_dir>
./LAUNCH_AGENT.sh
python3 ../scripts/validate_agent_run.py <run_dir_name>
python3 ../scripts/finalize_agent_run.py <run_dir_name> \
  --solver-message "First attempt completed" \
  --model claude-sonnet-4-5
```

`LAUNCH_AGENT.sh` now calls a Python launcher, which resolves the configured agent command, records `agent_launch_started` and `agent_launch_finished` events, and captures the raw terminal session with `script`.

## Repair Run Workflow

```bash
python3 scripts/create_repair_run.py <failed_run_dir_name>
cd test_result/<repair_run_dir>
./LAUNCH_AGENT.sh
python3 ../scripts/validate_agent_run.py <repair_run_dir_name>
python3 ../scripts/finalize_agent_run.py <repair_run_dir_name> \
  --solver-success \
  --solver-message "Repair attempt completed" \
  --model claude-sonnet-4-5
```

## Environment Notes

- The Python launcher resolves the agent command from `AGENT_CMD`, an agent-specific env var such as `CLAUDE_CODE_CMD`, or the executable on `PATH`.
- For `claude-code`, the default launch path is the SDK runner via `uv run`.
- `validate_agent_run.py` resolves Godot from `--godot-bin`, `GODOT_BIN`, `GODOT_EXEC_PATH`, standard macOS app paths, or `PATH`.
- Validation runs with `HOME` redirected into `Data/.godot-home` so Godot can run headless without depending on the host user's Library directory.
- Validation runs in a temporary isolated copy of the run directory and injects the canonical validator there, rather than validating in-place.

## Canonical Export

Use:

```bash
python3 scripts/export_canonical_run.py <run_dir_name>
```

This writes a cleaned export under `Data/canonical_runs/` with:
- `trajectory.json`
- `result.json`
- prompt and validator artifacts
- project files with common junk removed
