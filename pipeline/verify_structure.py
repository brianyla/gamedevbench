"""Verify pipeline structure is correctly set up."""

from pathlib import Path
import sys


def verify_structure():
    """Verify all required files and directories exist."""

    print("="*60)
    print("PIPELINE STRUCTURE VERIFICATION")
    print("="*60 + "\n")

    errors = []
    warnings = []

    # Check directories
    required_dirs = [
        "pipeline/scripts",
        "pipeline/data/videos",
        "pipeline/data/repos",
        "pipeline/data/tasks",
    ]

    print("Checking directories...")
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} (missing)")
            errors.append(f"Missing directory: {dir_path}")

    # Check core scripts
    print("\nChecking scripts...")
    required_scripts = [
        "pipeline/scripts/utils.py",
        "pipeline/scripts/01_download_transcripts.py",
        "pipeline/scripts/02_clone_repos.py",
        "pipeline/scripts/03_analyze_commits.py",
        "pipeline/scripts/04_discover_tasks.py",
        "pipeline/scripts/05_extract_task_from_commit.py",
        "pipeline/scripts/06_generate_tests.py",
        "pipeline/scripts/07_validate_tasks.py",
    ]

    for script_path in required_scripts:
        path = Path(script_path)
        if path.exists():
            print(f"  ✅ {script_path}")
        else:
            print(f"  ❌ {script_path} (missing)")
            errors.append(f"Missing script: {script_path}")

    # Check configuration files
    print("\nChecking configuration...")
    config_files = [
        ("pipeline/config.yaml", True),
        ("pipeline/requirements.txt", True),
        ("pipeline/run_pipeline.py", True),
        ("pipeline/README.md", True),
        ("pipeline/QUICKSTART.md", True),
    ]

    for file_path, required in config_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path}")
        elif required:
            print(f"  ❌ {file_path} (missing)")
            errors.append(f"Missing file: {file_path}")
        else:
            print(f"  ⚠️  {file_path} (optional, not found)")
            warnings.append(f"Optional file missing: {file_path}")

    # Check Python syntax
    print("\nChecking Python syntax...")
    for script_path in required_scripts + ["pipeline/run_pipeline.py"]:
        path = Path(script_path)
        if path.exists():
            try:
                with open(path) as f:
                    compile(f.read(), path, 'exec')
                print(f"  ✅ {script_path} - valid syntax")
            except SyntaxError as e:
                print(f"  ❌ {script_path} - syntax error: {e}")
                errors.append(f"Syntax error in {script_path}: {e}")

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)

    if not errors:
        print("✅ All checks passed!")
        print("\nPipeline is ready to use.")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r pipeline/requirements.txt")
        print("  2. Set API key: export ANTHROPIC_API_KEY='...'")
        print("  3. See QUICKSTART.md for usage")
        return True
    else:
        print(f"❌ Found {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")

        if warnings:
            print(f"\n⚠️  Found {len(warnings)} warning(s):")
            for warning in warnings:
                print(f"  - {warning}")

        return False


if __name__ == "__main__":
    success = verify_structure()
    sys.exit(0 if success else 1)
