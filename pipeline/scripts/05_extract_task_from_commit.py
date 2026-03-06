"""Extract task starting point and ground truth from Git commits."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, GitOperations, MetadataManager, GodotValidator


def import_godot_project(project_dir: Path, validator: GodotValidator) -> bool:
    """Run Godot to import/parse project (generates .godot folder)."""
    import subprocess
    import time

    if not (project_dir / "project.godot").exists():
        print(f"⚠️  No project.godot found in {project_dir}")
        return False

    try:
        # Run Godot with --import flag to import all assets
        # This is the proper way to reimport a project
        cmd = [
            validator.godot_executable,
            "--headless",
            "--import",
            "--path", str(project_dir)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # Longer timeout for importing
        )

        # Give it a moment to finish writing files
        time.sleep(1)

        # Check if .godot/imported folder has files
        imported_dir = project_dir / ".godot" / "imported"
        if imported_dir.exists():
            # Count imported files
            imported_files = list(imported_dir.iterdir())
            if len(imported_files) > 0:
                return True
            else:
                print(f"⚠️  .godot/imported folder is empty")
                return False
        else:
            print(f"⚠️  .godot/imported folder not created")
            return False

    except subprocess.TimeoutExpired:
        print(f"⚠️  Godot import timed out (>60s)")
        return False
    except Exception as e:
        print(f"⚠️  Failed to import project: {e}")
        return False


def extract_files_from_commit(repo_path: Path, commit_hash: str,
                              target_dir: Path) -> List[str]:
    """Extract files from a specific commit state."""

    # Get list of files that exist at this commit
    godot_patterns = ['.gd', '.tscn', '.tres', '.gdshader', '.gdshaderinc',
                     '.png', '.jpg', '.jpeg', '.svg', '.webp',
                     '.wav', '.ogg', '.mp3',
                     '.ttf', '.otf', '.woff', '.woff2', '.fnt',
                     'project.godot', '.import', '.godot']

    files = GitOperations.get_files_at_commit(repo_path, commit_hash, godot_patterns)

    extracted_files = []
    for file_path in files:
        src = repo_path / file_path
        if src.exists() and src.is_file():
            dst = target_dir / file_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                extracted_files.append(file_path)
            except Exception as e:
                print(f"⚠️  Failed to copy {file_path}: {e}")

    return extracted_files


def extract_task_from_commit(candidate: Dict[str, Any], repos_dir: Path,
                            tasks_dir: Path, validator: GodotValidator) -> bool:
    """Extract starting point and ground truth from a git commit."""

    repo_name = candidate["repo_name"]
    commit_hash = candidate["commit_hash"]
    task_name = candidate["name"]

    print(f"📦 Extracting task: {task_name}")
    print(f"   Repo: {repo_name}, Commit: {commit_hash[:8]}")

    # Setup directories
    repo_path = repos_dir / repo_name / "code"
    if not (repo_path / ".git").exists():
        print(f"❌ Repository not found: {repo_path}")
        return False

    # Generate task ID
    task_id = f"task_{abs(hash(f'{repo_name}_{commit_hash}')) % 100000:05d}"
    task_dir = tasks_dir / task_id

    # Check if already extracted
    if (task_dir / "task_config.json").exists():
        print(f"✓ Already extracted: {task_id}")
        return True

    task_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_dir = task_dir / "ground_truth"
    starting_point_dir = task_dir / "starting_point"
    ground_truth_dir.mkdir(exist_ok=True)
    starting_point_dir.mkdir(exist_ok=True)

    try:
        # Save original branch/commit
        import subprocess
        original_ref = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        ).stdout.strip()

        # Extract GROUND TRUTH (after commit)
        print(f"   Extracting ground truth...")
        if not GitOperations.checkout(repo_path, commit_hash):
            raise Exception("Failed to checkout commit")

        gt_files = extract_files_from_commit(repo_path, commit_hash, ground_truth_dir)

        # Extract STARTING POINT (before commit - commit^)
        print(f"   Extracting starting point...")
        parent_hash = f"{commit_hash}^"
        if not GitOperations.checkout(repo_path, parent_hash):
            raise Exception("Failed to checkout parent commit")

        sp_files = extract_files_from_commit(repo_path, parent_hash, starting_point_dir)

        # Restore original state
        GitOperations.checkout(repo_path, original_ref)

        # Validate extraction
        if not gt_files:
            print(f"⚠️  No files extracted for ground truth")
            return False

        # Import the ground truth project (generates .godot folder)
        print(f"   Importing ground truth project...")
        if not import_godot_project(ground_truth_dir, validator):
            print(f"⚠️  Failed to import ground truth project")
            # Don't fail - might still work

        # Import the starting point project
        print(f"   Importing starting point project...")
        if not import_godot_project(starting_point_dir, validator):
            print(f"⚠️  Failed to import starting point project")
            # Don't fail - might still work

        # Check if ground truth is valid
        print(f"   Validating ground truth...")
        if not validator.check_project(ground_truth_dir):
            print(f"⚠️  Ground truth has syntax errors")
            # Don't fail - might be fixable

        # Save task metadata in format matching existing tasks
        task_id_number = abs(hash(f'{repo_name}_{commit_hash}')) % 100000

        # Build repo URL from repo name
        repo_url = f"https://github.com/{repo_name}" if not repo_name.startswith('http') else repo_name

        task_config = {
            "task_id": task_id_number,
            "name": candidate["name"],
            "instruction": candidate["instruction"],
            "metadata": {
                "tutorial_source": f"YouTube: {candidate.get('video_id', 'unknown')}",
                "video_id": candidate.get("video_id", ""),
                "github_repo": repo_url,
                "transcript_excerpt": candidate.get("transcript_excerpt", "")[:200],  # Limit length
                "transcript_segment": candidate.get("transcript_segment", ""),
                "difficulty": candidate.get("difficulty", "intermediate"),
                "estimated_time_minutes": candidate.get("estimated_time_minutes", 30),
                "tags": candidate.get("tags", []),
                "commit_hash": commit_hash,
                "commit_message": candidate.get("commit_message", ""),
                "files_changed": len(gt_files),
                "starting_point_files": len(sp_files),
                "expected_nodes": [],  # TODO: Extract from ground truth analysis
                "key_properties": {}   # TODO: Extract from ground truth analysis
            }
        }

        (task_dir / "task_config.json").write_text(json.dumps(task_config, indent=2))

        # Update metadata
        MetadataManager.update_stage_status(task_dir, "extraction", "completed")

        print(f"✅ Extracted {task_id}: {len(gt_files)} files")
        return True

    except Exception as e:
        # Cleanup on failure
        if ground_truth_dir.exists():
            shutil.rmtree(ground_truth_dir)
        if starting_point_dir.exists():
            shutil.rmtree(starting_point_dir)

        # Restore original state
        try:
            GitOperations.checkout(repo_path, original_ref)
        except:
            pass

        MetadataManager.update_stage_status(
            task_dir, "extraction", "failed",
            error=str(e)
        )
        print(f"❌ Failed to extract: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Extract tasks from commits")
    parser.add_argument("--videos", nargs="+",
                       help="Specific video IDs to process")
    parser.add_argument("--tasks", nargs="+",
                       help="Specific task IDs to re-extract")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    videos_dir = Path(config.get('sources.videos'))
    repos_dir = Path(config.get('sources.repos'))
    tasks_dir = Path(config.get('output.tasks'))

    # Initialize validator
    validator = GodotValidator(config)

    # Collect all candidates
    all_candidates = []

    if args.videos:
        video_dirs = [videos_dir / vid for vid in args.videos]
    else:
        video_dirs = [d for d in videos_dir.iterdir() if d.is_dir()]

    for video_dir in video_dirs:
        candidates_file = video_dir / "candidates.json"
        if candidates_file.exists():
            candidates = json.loads(candidates_file.read_text())
            all_candidates.extend(candidates)

    if not all_candidates:
        print("❌ No candidates found to extract")
        return

    print(f"📊 Found {len(all_candidates)} task candidates")
    print("\n🚀 Starting extraction...\n")

    # Extract tasks
    success_count = 0
    failed_count = 0

    for candidate in all_candidates:
        success = extract_task_from_commit(candidate, repos_dir, tasks_dir, validator)
        if success:
            success_count += 1
        else:
            failed_count += 1

    # Print summary
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📁 Tasks directory: {tasks_dir}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
