"""Clone GitHub repositories in parallel."""

import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, GitOperations, MetadataManager


def load_repo_list(file_path: str) -> List[Dict[str, str]]:
    """Load repository list from JSON file.

    Supports two formats:
    1. Direct repo list: [{"name": "...", "url": "..."}, ...]
    2. Sources file: {"sources": [{"repo_name": "...", "repo_url": "..."}, ...]}
    """
    with open(file_path) as f:
        data = json.load(f)

    # Check if it's a sources file
    if isinstance(data, dict) and "sources" in data:
        # Extract unique repos from sources
        repos = {}
        for source in data["sources"]:
            repo_name = source["repo_name"]
            if repo_name not in repos:
                repos[repo_name] = {
                    "name": repo_name,
                    "url": source["repo_url"]
                }
        return list(repos.values())

    # Otherwise assume it's a direct repo list
    return data


def clone_single_repo(repo_info: Dict[str, str], data_dir: Path) -> bool:
    """Clone a single repository."""
    repo_name = repo_info["name"]
    repo_url = repo_info["url"]

    repo_dir = data_dir / "repos" / repo_name
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Check if already cloned
    code_dir = repo_dir / "code"
    if (code_dir / ".git").exists():
        print(f"✓ Already cloned: {repo_name}")
        MetadataManager.update_stage_status(repo_dir, "clone", "completed")
        return True

    print(f"📥 Cloning {repo_name}...")

    try:
        # Clone repository
        success = GitOperations.clone_repo(repo_url, code_dir)

        if success:
            # Save metadata
            metadata = {
                "name": repo_name,
                "url": repo_url,
                "stages": {
                    "clone": "completed"
                }
            }
            MetadataManager.save_metadata(repo_dir, metadata)

            print(f"✅ Cloned: {repo_name}")
            return True
        else:
            MetadataManager.update_stage_status(
                repo_dir, "clone", "failed",
                error="Git clone failed"
            )
            print(f"❌ Failed: {repo_name}")
            return False

    except Exception as e:
        MetadataManager.update_stage_status(
            repo_dir, "clone", "failed",
            error=str(e)
        )
        print(f"❌ Error cloning {repo_name}: {e}")
        return False


def clone_repos_parallel(repo_list: List[Dict[str, str]],
                        data_dir: Path,
                        max_workers: int = 10) -> Dict[str, int]:
    """Clone multiple repositories in parallel."""

    results = {"success": 0, "failed": 0, "skipped": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(clone_single_repo, repo, data_dir): repo
            for repo in repo_list
        }

        for future in as_completed(futures):
            repo = futures[future]
            try:
                success = future.result()
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                print(f"❌ Exception for {repo['name']}: {e}")
                results["failed"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Clone GitHub repositories")
    parser.add_argument("--sources",
                       help="Sources JSON file (extracts repos from sources)")
    parser.add_argument("--repos",
                       help="Direct repos JSON file (legacy format)")
    parser.add_argument("--workers", type=int, default=10,
                       help="Number of parallel workers")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    if not args.sources and not args.repos:
        parser.error("Must provide either --sources or --repos")

    # Load config
    config = Config(args.config)
    data_dir = Path(config.get('sources.videos')).parent

    # Load repository list
    repo_file = args.sources or args.repos
    print(f"📋 Loading repository list from {repo_file}")
    repo_list = load_repo_list(repo_file)
    print(f"📊 Found {len(repo_list)} unique repositories")

    # Clone repositories
    print(f"\n🚀 Starting clone with {args.workers} workers...\n")
    results = clone_repos_parallel(repo_list, data_dir, args.workers)

    # Print summary
    print("\n" + "="*60)
    print("CLONE SUMMARY")
    print("="*60)
    print(f"✅ Success: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
