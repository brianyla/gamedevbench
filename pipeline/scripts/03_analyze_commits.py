"""Analyze commit history from cloned repositories."""

import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, GitOperations, MetadataManager


def analyze_single_repo(repo_dir: Path, max_commits: int = 100) -> bool:
    """Analyze commit history for a single repository."""

    repo_name = repo_dir.name
    code_dir = repo_dir / "code"

    # Check if repo is cloned
    if not (code_dir / ".git").exists():
        print(f"⏭️  Skipping {repo_name}: not cloned")
        return False

    # Check if already analyzed
    commits_file = repo_dir / "commits.json"
    if commits_file.exists():
        print(f"✓ Already analyzed: {repo_name}")
        MetadataManager.update_stage_status(repo_dir, "analyze_commits", "completed")
        return True

    print(f"🔍 Analyzing {repo_name}...")

    try:
        # Extract commit history
        commits = GitOperations.get_commit_history(code_dir, max_commits)

        if not commits:
            print(f"⚠️  No Godot commits found in {repo_name}")
            MetadataManager.update_stage_status(
                repo_dir, "analyze_commits", "completed",
                error="No Godot-relevant commits found"
            )
            return False

        # Save commits
        commits_file.write_text(json.dumps(commits, indent=2))

        # Update metadata
        MetadataManager.update_stage_status(repo_dir, "analyze_commits", "completed")

        print(f"✅ Analyzed {repo_name}: {len(commits)} commits")
        return True

    except Exception as e:
        MetadataManager.update_stage_status(
            repo_dir, "analyze_commits", "failed",
            error=str(e)
        )
        print(f"❌ Error analyzing {repo_name}: {e}")
        return False


def analyze_repos_parallel(repos_dir: Path, max_workers: int = 20,
                          max_commits: int = 100) -> dict:
    """Analyze multiple repositories in parallel."""

    repo_dirs = [d for d in repos_dir.iterdir() if d.is_dir()]
    results = {"success": 0, "failed": 0, "skipped": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(analyze_single_repo, repo_dir, max_commits): repo_dir
            for repo_dir in repo_dirs
        }

        for future in as_completed(futures):
            repo_dir = futures[future]
            try:
                success = future.result()
                if success:
                    results["success"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                print(f"❌ Exception for {repo_dir.name}: {e}")
                results["failed"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Analyze commit history")
    parser.add_argument("--repos", nargs="+",
                       help="Specific repo names to analyze")
    parser.add_argument("--max-commits", type=int, default=100,
                       help="Maximum commits to analyze per repo")
    parser.add_argument("--workers", type=int, default=20,
                       help="Number of parallel workers")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    repos_dir = Path(config.get('sources.repos'))

    print(f"📂 Analyzing repositories in {repos_dir}")

    # Filter specific repos if requested
    if args.repos:
        repo_dirs = [repos_dir / name for name in args.repos if (repos_dir / name).exists()]
        if not repo_dirs:
            print("❌ No matching repositories found")
            return
        print(f"📊 Analyzing {len(repo_dirs)} specific repositories")
    else:
        repo_dirs = [d for d in repos_dir.iterdir() if d.is_dir()]
        print(f"📊 Found {len(repo_dirs)} repositories")

    # Analyze repositories
    print(f"\n🚀 Starting analysis with {args.workers} workers...\n")

    if args.repos:
        # Single-threaded for specific repos
        results = {"success": 0, "failed": 0, "skipped": 0}
        for repo_dir in repo_dirs:
            success = analyze_single_repo(repo_dir, args.max_commits)
            if success:
                results["success"] += 1
            else:
                results["skipped"] += 1
    else:
        results = analyze_repos_parallel(repos_dir, args.workers, args.max_commits)

    # Print summary
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    print(f"✅ Success: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
