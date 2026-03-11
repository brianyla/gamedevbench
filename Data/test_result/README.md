# Agent Runs

This folder stores benchmark-style agent attempts.

Each subdirectory should look like:

```text
<task_dir_name>_<agent>_<timestamp>/
  project.godot
  ... edited Godot project copied from the task start/ state ...
  task_config.json
  provenance.json
  transcript_excerpt.txt
  TASK_PROMPT.txt
  agent_trajectory.log
  result.json
```

Workflow:

1. Create a run directory from a task start state.
2. Start a recorded shell with `script agent_trajectory.log`.
3. Run Claude inside that recorded shell.
4. Paste the task instruction from `TASK_PROMPT.txt`.
5. Exit the recorded shell when the attempt is done.
6. Update `result.json` with outcome metadata.

Helper commands:

```bash
python3 scripts/create_agent_run.py task_0001_crouching --agent claude-code
cd test_result/<run_dir>
./LAUNCH_CLAUDE.sh
python3 scripts/finalize_agent_run.py <run_dir_name> --solver-success --model claude-sonnet-4-5 --message "Task completed"
```
