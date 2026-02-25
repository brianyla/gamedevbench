"""Validate tasks by running tests on ground truth and starting point."""

import argparse
import json
from pathlib import Path
from typing import Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, GodotValidator, MetadataManager


def validate_single_task(task_dir: Path, validator: GodotValidator) -> Dict[str, Any]:
    """Validate a single task."""

    task_id = task_dir.name
    ground_truth_dir = task_dir / "ground_truth"
    starting_point_dir = task_dir / "starting_point"

    results = {
        "task_id": task_id,
        "ground_truth": {"valid": False, "test_passed": False},
        "starting_point": {"valid": False, "test_passed": False},
        "errors": []
    }

    # Check ground truth
    print(f"🔍 Validating {task_id}")
    print(f"   Checking ground truth...")

    if not ground_truth_dir.exists():
        results["errors"].append("Ground truth directory missing")
        return results

    # Check syntax
    results["ground_truth"]["valid"] = validator.check_project(ground_truth_dir)

    if not results["ground_truth"]["valid"]:
        results["errors"].append("Ground truth has syntax errors")

    # Run test on ground truth (should pass)
    test_file = ground_truth_dir / "scripts" / "test.gd"
    if test_file.exists():
        test_result = validator.run_test(ground_truth_dir)
        results["ground_truth"]["test_passed"] = test_result["passed"]
        results["ground_truth"]["test_output"] = test_result["output"]

        if not test_result["passed"]:
            results["errors"].append(f"Ground truth test failed: {test_result['output'][:200]}")
    else:
        results["errors"].append("No test file found")

    # Check starting point
    print(f"   Checking starting point...")

    if not starting_point_dir.exists():
        results["errors"].append("Starting point directory missing")
        return results

    results["starting_point"]["valid"] = validator.check_project(starting_point_dir)

    # Run test on starting point (should fail)
    if test_file.exists():
        # Copy test to starting point
        import shutil
        sp_test_file = starting_point_dir / "scripts" / "test.gd"
        sp_test_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(test_file, sp_test_file)

        test_result = validator.run_test(starting_point_dir)
        results["starting_point"]["test_passed"] = test_result["passed"]
        results["starting_point"]["test_output"] = test_result["output"]

        if test_result["passed"]:
            results["errors"].append("Starting point test passed (should fail!)")

    # Determine overall status
    if results["ground_truth"]["test_passed"] and not results["starting_point"]["test_passed"]:
        status = "✅ VALID"
    elif not results["ground_truth"]["test_passed"]:
        status = "❌ INVALID - Ground truth test failed"
    elif results["starting_point"]["test_passed"]:
        status = "⚠️  WARNING - Starting point already passes"
    else:
        status = "❌ INVALID"

    print(f"   {status}")

    results["status"] = status
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate tasks")
    parser.add_argument("--tasks", nargs="+",
                       help="Specific task IDs to validate")
    parser.add_argument("--output", default="pipeline/validation_report.json",
                       help="Output report file")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    tasks_dir = Path(config.get('output.tasks'))

    # Initialize validator
    validator = GodotValidator(config)

    # Get task directories
    if args.tasks:
        task_dirs = [tasks_dir / tid for tid in args.tasks
                    if (tasks_dir / tid).exists()]
    else:
        task_dirs = [d for d in tasks_dir.iterdir()
                    if d.is_dir() and (d / "ground_truth").exists()]

    print(f"📊 Validating {len(task_dirs)} tasks")
    print("\n🚀 Starting validation...\n")

    # Validate tasks
    all_results = []
    stats = {
        "total": len(task_dirs),
        "valid": 0,
        "invalid": 0,
        "warnings": 0
    }

    for task_dir in task_dirs:
        try:
            results = validate_single_task(task_dir, validator)
            all_results.append(results)

            # Update stats
            if "✅" in results["status"]:
                stats["valid"] += 1
                MetadataManager.update_stage_status(task_dir, "validation", "passed")
            elif "⚠️" in results["status"]:
                stats["warnings"] += 1
                MetadataManager.update_stage_status(task_dir, "validation", "warning")
            else:
                stats["invalid"] += 1
                MetadataManager.update_stage_status(
                    task_dir, "validation", "failed",
                    error="; ".join(results["errors"])
                )

        except Exception as e:
            print(f"❌ Exception validating {task_dir.name}: {e}")
            stats["invalid"] += 1

    # Save report
    report = {
        "stats": stats,
        "results": all_results
    }

    output_file = Path(args.output)
    output_file.write_text(json.dumps(report, indent=2))

    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"📊 Total tasks: {stats['total']}")
    print(f"✅ Valid: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")
    print(f"⚠️  Warnings: {stats['warnings']}")
    print(f"❌ Invalid: {stats['invalid']}")
    print(f"\n📄 Full report: {output_file}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
