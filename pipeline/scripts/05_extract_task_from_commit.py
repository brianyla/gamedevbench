"""Extract task starting point and ground truth from Git commits."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, GitOperations, MetadataManager, GodotValidator


def extract_files_from_commit(repo_path: Path, commit_hash: str,
                              target_dir: Path) -> List[str]:
    """Extract files from a specific commit state."""

    # Get list of files that exist at this commit
    godot_patterns = ['.gd', '.tscn', '.tres', '.gdshader', '.gdshaderinc',
                     '.png', '.jpg', '.svg', '.wav', '.ogg', '.mp3',
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
    if (task_dir / "ground_truth").exists() and (task_dir / "starting_point").exists():
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

        # Check if ground truth is valid
        print(f"   Validating ground truth...")
        if not validator.check_project(ground_truth_dir):
            print(f"⚠️  Ground truth has syntax errors")
            # Don't fail - might be fixable

        # Save task metadata
        task_spec = {
            "task_id": task_id,
            "name": candidate["name"],
            "instruction": candidate["instruction"],
            "difficulty": candidate.get("difficulty", "intermediate"),
            "estimated_time_minutes": candidate.get("estimated_time_minutes", 30),
            "tags": candidate.get("tags", []),
            "video_id": candidate["video_id"],
            "repo_name": repo_name,
            "commit_hash": commit_hash,
            "commit_message": candidate.get("commit_message", ""),
            "transcript_segment": candidate.get("transcript_segment", ""),
            "files_changed": len(gt_files),
            "starting_point_files": len(sp_files)
        }

        (task_dir / "task_spec.json").write_text(json.dumps(task_spec, indent=2))

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
