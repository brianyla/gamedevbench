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


def create_commit_summaries(commits: List[Dict[str, Any]], max_commits: int = 50) -> str:
    """Create concise commit summaries for LLM prompt."""
    summaries = []
    for commit in commits[:max_commits]:
        files = [f["path"] for f in commit["files_changed"][:5]]
        file_str = ", ".join(files)
        if len(commit["files_changed"]) > 5:
            file_str += f" (+ {len(commit['files_changed']) - 5} more)"

        summaries.append(
            f"• {commit['hash'][:8]}: {commit['message']}\n"
            f"  Files: {file_str}"
        )

    return "\n".join(summaries)


def match_transcript_to_commits(video_dir: Path, repo_dir: Path,
                               llm_client: LLMClient) -> List[Dict[str, Any]]:
    """Use LLM to match transcript segments to specific commits."""

    video_id = video_dir.name
    repo_name = repo_dir.name

    print(f"🤖 Matching {video_id} to {repo_name}...")

    # Load data
    transcript = load_transcript(video_dir)
    commits = load_commits(repo_dir)

    if not commits:
        print(f"⚠️  No commits found for {repo_name}")
        return []

    # Create prompt
    commit_summaries = create_commit_summaries(commits, max_commits=50)

    prompt = f"""Match this Godot tutorial transcript to specific Git commits.

VIDEO TRANSCRIPT:
{transcript[:15000]}  # Limit to ~15k chars

GIT COMMITS (most recent 50):
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
        print(f"❌ Error matching transcript: {e}")
        return []


def discover_tasks_for_video(video_dir: Path, repos_dir: Path,
                            llm_client: LLMClient,
                            repo_name: str = None) -> List[Dict[str, Any]]:
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
        if repo_name:
            repo_dir = repos_dir / repo_name
            if not repo_dir.exists():
                print(f"❌ Repository not found: {repo_name}")
                return []
            repo_dirs = [repo_dir]
        else:
            # Try all repos (can be refined with metadata)
            repo_dirs = [d for d in repos_dir.iterdir()
                        if d.is_dir() and (d / "commits.json").exists()]

        all_candidates = []
        for repo_dir in repo_dirs:
            candidates = match_transcript_to_commits(video_dir, repo_dir, llm_client)
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


def main():
    parser = argparse.ArgumentParser(description="Discover task candidates")
    parser.add_argument("--videos", nargs="+",
                       help="Specific video IDs to process")
    parser.add_argument("--repo",
                       help="Specific repo name to match against")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    videos_dir = Path(config.get('sources.videos'))
    repos_dir = Path(config.get('sources.repos'))

    # Initialize LLM client
    llm_client = LLMClient(config)

    # Get video directories
    if args.videos:
        video_dirs = [videos_dir / vid for vid in args.videos
                     if (videos_dir / vid).exists()]
    else:
        video_dirs = [d for d in videos_dir.iterdir() if d.is_dir()]

    print(f"📊 Processing {len(video_dirs)} videos")

    # Process videos
    print("\n🚀 Starting discovery...\n")

    total_candidates = 0
    for video_dir in video_dirs:
        candidates = discover_tasks_for_video(
            video_dir, repos_dir, llm_client, args.repo
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
