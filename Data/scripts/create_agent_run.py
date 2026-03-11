#!/usr/bin/env python3
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / 'tasks'
RUNS_DIR = ROOT / 'test_result'


def load_task(task_ref: str):
    task_dir = Path(task_ref)
    if not task_dir.is_absolute():
        task_dir = TASKS_DIR / task_ref
    task_dir = task_dir.resolve()
    if not task_dir.exists():
        raise SystemExit(f'Task not found: {task_ref}')
    config_path = task_dir / 'task_config.json'
    if not config_path.exists():
        raise SystemExit(f'Missing task_config.json in {task_dir}')
    with open(config_path) as f:
        config = json.load(f)
    return task_dir, config


def main():
    parser = argparse.ArgumentParser(description='Create a benchmark-style agent run directory from a task start state.')
    parser.add_argument('task', help='Task directory name under tasks/ or absolute path')
    parser.add_argument('--agent', required=True, help='Agent label, e.g. claude-code or codex')
    parser.add_argument('--timestamp', help='Optional timestamp override in YYYYMMDD_HHMMSS')
    args = parser.parse_args()

    task_dir, config = load_task(args.task)
    start_dir = task_dir / 'start'
    if not start_dir.exists():
        raise SystemExit(f'Missing start directory in {task_dir}')

    timestamp = args.timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
    run_name = f"{task_dir.name}_{args.agent}_{timestamp}"
    run_dir = RUNS_DIR / run_name
    if run_dir.exists():
        raise SystemExit(f'Run directory already exists: {run_dir}')

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(start_dir, run_dir)

    public_task_config = {
        'task_id': config.get('task_id'),
        'task_name': config.get('task_name'),
        'instruction': config.get('instruction'),
        'difficulty': config.get('difficulty'),
        'skill_category': config.get('skill_category'),
        'editor_type': config.get('editor_type'),
        'requires_multimodal': config.get('requires_multimodal'),
        'files_to_edit': config.get('files_to_edit', []),
    }
    with open(run_dir / 'task_config.json', 'w') as f:
        json.dump(public_task_config, f, indent=2)

    if (task_dir / 'transcript_excerpt.txt').exists():
        shutil.copy2(task_dir / 'transcript_excerpt.txt', run_dir / 'transcript_excerpt.txt')

    prompt_path = run_dir / 'TASK_PROMPT.txt'
    prompt_path.write_text(config.get('instruction', '').strip() + '\n', encoding='utf-8')

    claude_entry = "node /Users/sejoonchang/.npm-global/lib/node_modules/@anthropic-ai/.claude-code-InSDvR7a/cli.js"
    launch_script_path = run_dir / 'LAUNCH_CLAUDE.sh'
    launch_script_path.write_text(
        "\n".join([
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "cd \"$(dirname \"$0\")\"",
            "script agent_trajectory.log",
            f"{claude_entry}",
        ]) + "\n",
        encoding='utf-8',
    )
    launch_script_path.chmod(0o755)

    result = {
        'task_name': task_dir.name,
        'agent': args.agent,
        'timestamp': timestamp,
        'status': 'prepared',
        'validation': None,
        'solver': None,
    }
    with open(run_dir / 'result.json', 'w') as f:
        json.dump(result, f, indent=2)

    readme = run_dir / 'RUN_README.txt'
    readme.write_text(
        '\n'.join([
            f'Run directory: {run_name}',
            f'Task source: {task_dir}',
            '',
            'What to do:',
            '1. Open this directory as the agent workspace.',
            '2. Start recording and launch Claude with: ./LAUNCH_CLAUDE.sh',
            '3. Inside Claude, paste the contents of TASK_PROMPT.txt.',
            '4. Let the agent edit files in this directory.',
            '5. When Claude is done, exit the recorded shell to finish agent_trajectory.log.',
            '6. Run scripts/finalize_agent_run.py after the attempt.',
            '',
            'This directory starts from the task start/ state.',
            'Using script(1) automatically records the terminal session to agent_trajectory.log.',
        ]) + '\n',
        encoding='utf-8',
    )

    print(run_dir)
    print(f"Next: cd {run_dir} && ./LAUNCH_CLAUDE.sh")


if __name__ == '__main__':
    main()
