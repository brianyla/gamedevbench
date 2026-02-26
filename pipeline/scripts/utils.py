"""Shared utilities for the pipeline."""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import anthropic
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Load and manage pipeline configuration."""

    def __init__(self, config_path: str = "pipeline/config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def get(self, key: str, default=None):
        """Get config value by dot notation (e.g., 'llm.model')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default


class LLMClient:
    """Wrapper for LLM API calls with retry logic and rate limiting."""

    def __init__(self, config: Config):
        self.config = config
        api_key = os.environ.get(config.get('llm.api_key_env'))
        if not api_key:
            raise ValueError(f"Missing API key: {config.get('llm.api_key_env')}")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = config.get('llm.model')
        self.max_tokens = config.get('llm.max_tokens', 8000)
        self.temperature = config.get('llm.temperature', 0.3)
        self.max_retries = config.get('processing.max_retries', 3)

    def call(self, prompt: str, system: Optional[str] = None) -> str:
        """Make an LLM API call with retry logic."""
        for attempt in range(self.max_retries):
            try:
                messages = [{"role": "user", "content": prompt}]

                kwargs = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": messages
                }

                if system:
                    kwargs["system"] = system

                response = self.client.messages.create(**kwargs)
                return response.content[0].text

            except anthropic.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⏳ Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"⚠️  API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    time.sleep(2)
                else:
                    raise

        raise Exception("Max retries exceeded")


class GitOperations:
    """Git operations for repository management."""

    @staticmethod
    def clone_repo(url: str, target_dir: Path) -> bool:
        """Clone a git repository."""
        try:
            subprocess.run(
                ["git", "clone", url, str(target_dir)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300
            )
            return True
        except subprocess.TimeoutExpired:
            print(f"⏱️  Timeout cloning {url}")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to clone {url}: {e.stderr}")
            return False

    @staticmethod
    def get_commit_history(repo_path: Path, max_commits: int = 100) -> List[Dict[str, Any]]:
        """Extract commit history from repository."""
        try:
            # Get commit metadata
            result = subprocess.run(
                ["git", "log", f"-{max_commits}", "--all",
                 "--pretty=format:%H|%s|%an|%ad|%P"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('|')
                if len(parts) < 4:
                    continue

                commit_hash = parts[0]

                # Get files changed in this commit
                files_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", commit_hash],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )

                files_changed = []
                for file_line in files_result.stdout.strip().split('\n'):
                    if not file_line:
                        continue
                    file_parts = file_line.split('\t', 1)
                    if len(file_parts) == 2:
                        status, file_path = file_parts
                        # Only include Godot-relevant files
                        if file_path.endswith(('.gd', '.tscn', '.tres', '.gdshader',
                                             '.gdshaderinc', '.gdextension', '.png',
                                             '.jpg', '.svg', '.wav', '.ogg', 'project.godot')):
                            files_changed.append({
                                "status": status,
                                "path": file_path
                            })

                # Only include commits that changed Godot files
                if files_changed:
                    commits.append({
                        "hash": commit_hash,
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                        "parents": parts[4].split() if len(parts) > 4 else [],
                        "files_changed": files_changed
                    })

            return commits

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to get commit history: {e.stderr}")
            return []

    @staticmethod
    def checkout(repo_path: Path, ref: str) -> bool:
        """Checkout a specific commit or branch."""
        try:
            subprocess.run(
                ["git", "checkout", ref],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to checkout {ref}: {e.stderr}")
            return False

    @staticmethod
    def get_files_at_commit(repo_path: Path, commit_hash: str,
                           file_patterns: Optional[List[str]] = None) -> List[str]:
        """Get list of files at a specific commit."""
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit_hash],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            files = result.stdout.strip().split('\n')

            if file_patterns:
                filtered_files = []
                for file in files:
                    for pattern in file_patterns:
                        if file.endswith(pattern):
                            filtered_files.append(file)
                            break
                return filtered_files

            return files

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to list files: {e.stderr}")
            return []


class MetadataManager:
    """Manage metadata files for videos, repos, and tasks."""

    @staticmethod
    def load_metadata(item_path: Path) -> Dict[str, Any]:
        """Load metadata.json from item directory."""
        metadata_file = item_path / "metadata.json"
        if metadata_file.exists():
            return json.loads(metadata_file.read_text())
        return {"stages": {}, "errors": []}

    @staticmethod
    def save_metadata(item_path: Path, metadata: Dict[str, Any]):
        """Save metadata.json to item directory."""
        metadata_file = item_path / "metadata.json"
        metadata["last_updated"] = datetime.now().isoformat()
        metadata_file.write_text(json.dumps(metadata, indent=2))

    @staticmethod
    def update_stage_status(item_path: Path, stage: str, status: str,
                          error: Optional[str] = None):
        """Update the status of a specific stage."""
        metadata = MetadataManager.load_metadata(item_path)

        if "stages" not in metadata:
            metadata["stages"] = {}

        metadata["stages"][stage] = status

        if error:
            if "errors" not in metadata:
                metadata["errors"] = []
            metadata["errors"].append({
                "stage": stage,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })

        MetadataManager.save_metadata(item_path, metadata)

    @staticmethod
    def get_stage_status(item_path: Path, stage: str) -> str:
        """Get the status of a specific stage."""
        metadata = MetadataManager.load_metadata(item_path)
        return metadata.get("stages", {}).get(stage, "pending")


class GodotValidator:
    """Run Godot validation tests."""

    def __init__(self, config: Config):
        self.godot_executable = config.get('godot.executable', 'godot')
        self.timeout = config.get('godot.validation_timeout', 30)

    def check_project(self, project_path: Path) -> bool:
        """Check if a Godot project has valid syntax."""
        try:
            result = subprocess.run(
                [self.godot_executable, "--path", str(project_path),
                 "--check-only", "--headless"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False

    def run_test(self, project_path: Path, test_script: str = "scripts/test.gd") -> Dict[str, Any]:
        """Run a validation test script."""
        try:
            result = subprocess.run(
                [self.godot_executable, "--path", str(project_path),
                 "--headless", "-s", test_script],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            output = result.stdout + result.stderr

            return {
                "passed": "VALIDATION_PASSED" in output,
                "output": output,
                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "output": "Test timed out",
                "return_code": -1
            }
        except Exception as e:
            return {
                "passed": False,
                "output": str(e),
                "return_code": -1
            }


def print_stats(data_dir: Path = Path("pipeline/data")):
    """Print pipeline statistics."""

    videos_dir = data_dir / "videos"
    repos_dir = data_dir / "repos"
    tasks_dir = data_dir / "tasks"

    print("\n" + "="*60)
    print("PIPELINE STATISTICS")
    print("="*60 + "\n")

    # Videos
    if videos_dir.exists():
        video_count = len(list(videos_dir.iterdir()))
        completed_downloads = sum(1 for v in videos_dir.iterdir()
                                 if (v / "transcript.txt").exists())
        print(f"Videos: {video_count}")
        print(f"  - Downloaded: {completed_downloads}")
        print(f"  - Pending: {video_count - completed_downloads}")

    # Repos
    if repos_dir.exists():
        repo_count = len(list(repos_dir.iterdir()))
        cloned_repos = sum(1 for r in repos_dir.iterdir()
                          if (r / "code" / ".git").exists())
        print(f"\nRepositories: {repo_count}")
        print(f"  - Cloned: {cloned_repos}")
        print(f"  - Pending: {repo_count - cloned_repos}")

    # Tasks
    if tasks_dir.exists():
        task_count = len(list(tasks_dir.iterdir()))
        extracted_tasks = sum(1 for t in tasks_dir.iterdir()
                            if (t / "ground_truth").exists())
        print(f"\nTasks: {task_count}")
        print(f"  - Extracted: {extracted_tasks}")
        print(f"  - Pending: {task_count - extracted_tasks}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true", help="Print pipeline statistics")
    args = parser.parse_args()

    if args.stats:
        print_stats()
