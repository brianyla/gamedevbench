"""Discover task candidates by matching transcripts to commits using LLM."""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, LLMClient, MetadataManager


def load_transcript(video_dir: Path) -> str:
    """Load transcript from video directory."""
    transcript_file = video_dir / "transcript.txt"
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_file}")
    return transcript_file.read_text()


def load_commits(repo_dir: Path) -> List[Dict[str, Any]]:
    """Load commit history from repository directory."""
    commits_file = repo_dir / "commits.json"
    if not commits_file.exists():
        raise FileNotFoundError(f"Commits not found: {commits_file}")
    return json.loads(commits_file.read_text())


def get_commit_diff(repo_dir: Path, commit_hash: str) -> str:
    """Get the actual code diff for a commit (only .gd and .tscn files)."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "show", commit_hash, "--", "*.gd", "*.tscn"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except Exception as e:
        print(f"⚠️  Failed to get diff for {commit_hash[:8]}: {e}")
        return ""


def create_commit_summaries(commits: List[Dict[str, Any]], repo_dir: Path,
                           include_diffs: bool = True) -> str:
    """Create detailed commit summaries with actual code diffs for LLM prompt."""
    summaries = []
    for commit in commits:
        files = [f["path"] for f in commit["files_changed"][:5]]
        file_str = ", ".join(files)
        if len(commit["files_changed"]) > 5:
            file_str += f" (+ {len(commit['files_changed']) - 5} more)"

        summary = f"• {commit['hash'][:8]}: {commit['message']}\n"
        summary += f"  Files: {file_str}"

        # Include actual code diff for better context
        if include_diffs:
            diff = get_commit_diff(repo_dir, commit['hash'])
            if diff:
                summary += f"\n  Diff:\n{diff}\n"
            elif commit.get('diff_stats'):
                # Fallback to stats if diff is unavailable
                summary += f"\n  Stats:\n{commit['diff_stats']}"

        summaries.append(summary)

    return "\n\n".join(summaries)


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)."""
    return len(text) // 4


def filter_commits_by_range(commits: List[Dict[str, Any]], commit_range: Dict) -> List[Dict[str, Any]]:
    """Filter commits to only include those in the specified range.

    Commits are in reverse chronological order (newest first).
    start = older commit, end = newer commit
    """
    if not commit_range:
        return commits

    start_hash = commit_range.get("start")  # Older commit
    end_hash = commit_range.get("end")      # Newer commit

    if not start_hash or not end_hash:
        return commits

    # Find indices of start and end commits
    start_idx = None  # Index of older commit (higher index)
    end_idx = None    # Index of newer commit (lower index)

    for i, commit in enumerate(commits):
        if commit["hash"].startswith(start_hash):
            start_idx = i  # Older commit
        if commit["hash"].startswith(end_hash):
            end_idx = i    # Newer commit

    if start_idx is None or end_idx is None:
        print(f"⚠️  Could not find commit range {start_hash[:8]}..{end_hash[:8]}")
        return commits

    # Return commits in the range (inclusive)
    # Since commits are reverse chronological, end_idx should be <= start_idx
    filtered = commits[end_idx:start_idx+1]
    print(f"📎 Filtered to {len(filtered)} commits in range {start_hash[:8]}..{end_hash[:8]}")
    return filtered


def match_transcript_to_commits(video_dir: Path, repo_dir: Path,
                               llm_client: LLMClient, commit_range: Dict = None) -> List[Dict[str, Any]]:
    """Use LLM to match transcript segments to specific commits.

    Automatically batches commits if context window would be exceeded.
    """

    video_id = video_dir.name
    repo_name = repo_dir.name

    print(f"🤖 Matching {video_id} to {repo_name}...")

    # Load data
    transcript = load_transcript(video_dir)
    commits = load_commits(repo_dir)

    if not commits:
        print(f"⚠️  No commits found for {repo_name}")
        return []

    # Filter commits by range if specified
    if commit_range:
        commits = filter_commits_by_range(commits, commit_range)

    # Estimate tokens for transcript
    transcript_tokens = estimate_tokens(transcript)
    print(f"📊 Transcript: ~{transcript_tokens:,} tokens")

    # Context window limit (leave 20k for response + safety margin)
    MAX_CONTEXT_TOKENS = 180_000
    available_tokens = MAX_CONTEXT_TOKENS - transcript_tokens

    # Create commit summaries with diffs and check size
    commit_summaries = create_commit_summaries(commits, repo_dir, include_diffs=True)
    commit_tokens = estimate_tokens(commit_summaries)

    print(f"📊 Commits ({len(commits)} total): ~{commit_tokens:,} tokens")
    print(f"📊 Total: ~{transcript_tokens + commit_tokens:,} tokens")

    # Check if we need to batch
    if transcript_tokens + commit_tokens > MAX_CONTEXT_TOKENS:
        print(f"⚠️  Context would be {transcript_tokens + commit_tokens:,} tokens (exceeds {MAX_CONTEXT_TOKENS:,})")
        print(f"🔄 Batching commits into multiple API calls...")
        return match_with_batching(video_dir, repo_dir, transcript, commits, llm_client, available_tokens)

    # Single API call - everything fits
    print(f"✅ Context fits in single API call")
    return match_single_batch(video_dir, repo_dir, transcript, commits, commit_summaries, llm_client)


def match_single_batch(video_dir: Path, repo_dir: Path, transcript: str,
                      commits: List[Dict[str, Any]], commit_summaries: str,
                      llm_client: LLMClient) -> List[Dict[str, Any]]:
    """Match transcript to commits in a single API call."""

    prompt = f"""Match this Godot tutorial transcript to specific Git commits.

VIDEO TRANSCRIPT:
{transcript}

GIT COMMITS:
{commit_summaries}

For each distinct feature/task taught in the transcript:
1. Identify the tutorial segment (with approximate timestamp/section)
2. Find the matching Git commit(s) that implement that feature
3. Extract a clear, specific task instruction

Requirements:
- Only include commits that implement complete, testable features
- Task instruction should be implementable by a student
- Focus on gameplay mechanics, UI systems, or visual effects
- Exclude trivial changes (typo fixes, formatting, etc.)

Output a JSON array with this exact structure:
[
  {{
    "name": "Quest HUD System",
    "instruction": "Create a CanvasLayer-based quest HUD that displays active quests and updates when quest state changes. Connect signals from QuestManager to update UI labels in real-time.",
    "transcript_segment": "Section 2: UI Implementation",
    "transcript_excerpt": "Now we'll connect the signals from QuestManager...",
    "commit_hash": "a1b2c3d4",
    "commit_message": "Add quest UI with signal connections",
    "difficulty": "intermediate",
    "estimated_time_minutes": 30,
    "tags": ["ui", "signals", "canvas_layer"]
  }}
]

Output ONLY the JSON array, no additional text."""

    try:
        response = llm_client.call(prompt)
        return parse_and_validate_candidates(response, commits, video_dir.name, repo_dir.name)

    except Exception as e:
        print(f"❌ Error matching transcript: {e}")
        return []


def match_with_batching(video_dir: Path, repo_dir: Path, transcript: str,
                       commits: List[Dict[str, Any]], llm_client: LLMClient,
                       available_tokens: int) -> List[Dict[str, Any]]:
    """Match transcript to commits using multiple batched API calls."""

    all_candidates = []
    batch_size = 1
    total_batches = (len(commits) + batch_size - 1) // batch_size

    # Try to fit as many commits as possible per batch
    test_summaries = create_commit_summaries(commits[:batch_size], repo_dir, include_diffs=True)
    test_tokens = estimate_tokens(test_summaries)

    if test_tokens < available_tokens:
        # Calculate optimal batch size
        batch_size = min(len(commits), max(1, int(available_tokens / test_tokens)))
        total_batches = (len(commits) + batch_size - 1) // batch_size

    print(f"📦 Processing {len(commits)} commits in {total_batches} batch(es) of ~{batch_size} commits each")

    for i in range(0, len(commits), batch_size):
        batch = commits[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        print(f"\n🔄 Batch {batch_num}/{total_batches}: {len(batch)} commits")

        commit_summaries = create_commit_summaries(batch, repo_dir, include_diffs=True)
        candidates = match_single_batch(video_dir, repo_dir, transcript, batch,
                                       commit_summaries, llm_client)

        all_candidates.extend(candidates)
        print(f"   Found {len(candidates)} candidates in this batch")

    return all_candidates


def parse_and_validate_candidates(response: str, commits: List[Dict[str, Any]],
                                 video_id: str, repo_name: str) -> List[Dict[str, Any]]:
    """Parse LLM response and validate commit references."""

    try:
        # Parse JSON response
        # Handle potential markdown code blocks
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        candidates = json.loads(response)

        # Validate and enrich candidates
        valid_candidates = []
        commit_hashes = {c["hash"]: c for c in commits}

        for candidate in candidates:
            # Verify commit exists
            commit_hash = candidate.get("commit_hash", "")
            if not any(commit_hash.startswith(h[:8]) for h in commit_hashes.keys()):
                print(f"⚠️  Skipping candidate: commit {commit_hash} not found")
                continue

            # Find full commit hash
            full_hash = next(h for h in commit_hashes.keys()
                           if h.startswith(commit_hash[:8]))
            candidate["commit_hash"] = full_hash

            # Add video and repo info
            candidate["video_id"] = video_id
            candidate["repo_name"] = repo_name

            valid_candidates.append(candidate)

        print(f"✅ Found {len(valid_candidates)} task candidates")
        return valid_candidates

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        print(f"Response preview: {response[:500]}")
        return []

    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        return []


def discover_tasks_for_video(video_dir: Path, repos_dir: Path,
                            llm_client: LLMClient,
                            repo_name: str = None,
                            commit_range: Dict = None) -> List[Dict[str, Any]]:
    """Discover tasks for a single video."""

    candidates_file = video_dir / "candidates.json"

    # Check if already processed
    if candidates_file.exists():
        print(f"✓ Already discovered: {video_dir.name}")
        MetadataManager.update_stage_status(video_dir, "discovery", "completed")
        return json.loads(candidates_file.read_text())

    try:
        # Check transcript exists
        if not (video_dir / "transcript.txt").exists():
            print(f"⏭️  Skipping {video_dir.name}: no transcript")
            return []

        # Find matching repository
        # Check sources mapping (passed from main)
        if not repo_name and hasattr(llm_client, '_sources_mapping'):
            repo_name = llm_client._sources_mapping.get(video_dir.name)
            if repo_name:
                print(f"📎 Using repo from sources.json: {repo_name}")

        if repo_name:
            repo_dir = repos_dir / repo_name
            if not repo_dir.exists():
                print(f"❌ Repository not found: {repo_name}")
                return []
            repo_dirs = [repo_dir]
        else:
            # Fallback: try all repos (less efficient)
            print(f"⚠️  No repo specified for {video_dir.name}, trying all repos")
            repo_dirs = [d for d in repos_dir.iterdir()
                        if d.is_dir() and (d / "commits.json").exists()]

        all_candidates = []
        for repo_dir in repo_dirs:
            candidates = match_transcript_to_commits(video_dir, repo_dir, llm_client, commit_range)
            all_candidates.extend(candidates)

        if all_candidates:
            # Save candidates
            candidates_file.write_text(json.dumps(all_candidates, indent=2))
            MetadataManager.update_stage_status(video_dir, "discovery", "completed")
        else:
            MetadataManager.update_stage_status(
                video_dir, "discovery", "completed",
                error="No candidates found"
            )

        return all_candidates

    except Exception as e:
        MetadataManager.update_stage_status(
            video_dir, "discovery", "failed",
            error=str(e)
        )
        print(f"❌ Error discovering tasks for {video_dir.name}: {e}")
        return []


def load_sources_mapping(sources_file: Path) -> Dict[str, Dict]:
    """Load video_id -> source data mapping from sources.json."""
    if not sources_file.exists():
        return {}

    with open(sources_file) as f:
        data = json.load(f)

    mapping = {}
    for source in data.get("sources", []):
        mapping[source["video_id"]] = {
            "repo_name": source["repo_name"],
            "commit_range": source.get("commit_range")
        }

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Discover task candidates")
    parser.add_argument("--videos", nargs="+",
                       help="Specific video IDs to process")
    parser.add_argument("--repo",
                       help="Specific repo name to match against")
    parser.add_argument("--sources", default="pipeline/sources.json",
                       help="Sources JSON file")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    videos_dir = Path(config.get('sources.videos'))
    repos_dir = Path(config.get('sources.repos'))

    # Load video -> repo mapping from sources.json
    sources_mapping = load_sources_mapping(Path(args.sources))

    # Initialize LLM client
    llm_client = LLMClient(config)

    # Get video directories
    if args.videos:
        video_dirs = [videos_dir / vid for vid in args.videos
                     if (videos_dir / vid).exists()]
    else:
        video_dirs = [d for d in videos_dir.iterdir() if d.is_dir()]

    print(f"📊 Processing {len(video_dirs)} videos")

    # Store sources mapping in llm_client for access in discover_tasks_for_video
    llm_client._sources_mapping = sources_mapping

    # Process videos
    print("\n🚀 Starting discovery...\n")

    total_candidates = 0
    for video_dir in video_dirs:
        # Get repo and commit_range from command line or sources mapping
        repo = args.repo
        commit_range = None

        if not repo:
            source_data = sources_mapping.get(video_dir.name)
            if source_data:
                repo = source_data.get("repo_name")
                commit_range = source_data.get("commit_range")

        candidates = discover_tasks_for_video(
            video_dir, repos_dir, llm_client, repo, commit_range
        )
        total_candidates += len(candidates)

    # Print summary
    print("\n" + "="*60)
    print("DISCOVERY SUMMARY")
    print("="*60)
    print(f"📹 Videos processed: {len(video_dirs)}")
    print(f"✅ Task candidates found: {total_candidates}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
