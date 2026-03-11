#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / 'test_result'


def main():
    parser = argparse.ArgumentParser(description='Finalize a benchmark-style agent run directory.')
    parser.add_argument('run_dir', help='Run directory name under test_result/ or absolute path')
    parser.add_argument('--solver-success', action='store_true', help='Mark solver as successful')
    parser.add_argument('--validation-success', action='store_true', help='Mark validation as successful')
    parser.add_argument('--duration-seconds', type=float, default=0.0)
    parser.add_argument('--model', default='')
    parser.add_argument('--message', default='')
    parser.add_argument('--cost-usd', type=float, default=0.0)
    parser.add_argument('--input-tokens', type=int, default=0)
    parser.add_argument('--output-tokens', type=int, default=0)
    parser.add_argument('--cache-read-tokens', type=int, default=0)
    parser.add_argument('--cache-write-tokens', type=int, default=0)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = RUNS_DIR / args.run_dir
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f'Run directory not found: {run_dir}')

    result_path = run_dir / 'result.json'
    if result_path.exists():
        with open(result_path) as f:
            result = json.load(f)
    else:
        result = {}

    result['status'] = 'completed'
    result['completed_at'] = datetime.now().isoformat()
    result['validation'] = {
        'success': bool(args.validation_success),
        'message': args.message,
        'timestamp': datetime.now().isoformat(),
    }
    result['solver'] = {
        'success': bool(args.solver_success),
        'message': args.message,
        'duration_seconds': args.duration_seconds,
        'is_rate_limited': False,
        'model': args.model,
        'cost_usd': args.cost_usd,
        'token_usage': {
            'input_tokens': args.input_tokens,
            'output_tokens': args.output_tokens,
            'total_tokens': args.input_tokens + args.output_tokens,
            'cache_read_tokens': args.cache_read_tokens,
            'cache_write_tokens': args.cache_write_tokens,
        },
    }

    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(result_path)


if __name__ == '__main__':
    main()
