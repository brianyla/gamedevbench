"""Download YouTube transcripts from sources file."""

import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import ssl
import sys

# Fix SSL certificate verification on macOS
ssl._create_default_https_context = ssl._create_unverified_context

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("❌ youtube-transcript-api not installed")
    print("Install with: pip install youtube-transcript-api")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.utils import Config, MetadataManager


def format_timestamp(seconds):
    """Format seconds into MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def download_transcript(video_id: str) -> str:
    """Download transcript for a video ID."""
    try:
        # Get transcript using youtube-transcript-api (correct API)
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id, languages=['en'])
        raw_data = fetched_transcript.to_raw_data()

        # Format with timestamps
        lines = []
        for entry in raw_data:
            timestamp = format_timestamp(entry["start"])
            text = entry["text"].strip()
            lines.append(f"[{timestamp}] {text}")

        return "\n".join(lines)
    except Exception as e:
        raise Exception(f"Failed to download: {e}")


def download_single_transcript(video_id: str, video_dir: Path) -> bool:
    """Download transcript for a single video."""

    transcript_file = video_dir / "transcript.txt"

    # Check if already downloaded
    if transcript_file.exists():
        print(f"✓ Already downloaded: {video_id}")
        MetadataManager.update_stage_status(video_dir, "download", "completed")
        return True

    print(f"📥 Downloading {video_id}...")

    try:
        # Download transcript
        transcript = download_transcript(video_id)

        # Save transcript to file
        transcript_file.write_text(transcript)

        # Update metadata
        MetadataManager.update_stage_status(video_dir, "download", "completed")

        print(f"✅ Downloaded {video_id}: {len(transcript)} chars")
        return True

    except Exception as e:
        MetadataManager.update_stage_status(
            video_dir, "download", "failed",
            error=str(e)
        )
        print(f"❌ Failed {video_id}: {e}")
        return False


def download_transcripts_parallel(sources: list, data_dir: Path,
                                  max_workers: int = 5) -> dict:
    """Download transcripts in parallel."""

    results = {"success": 0, "failed": 0, "skipped": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for source in sources:
            video_id = source["video_id"]
            video_dir = data_dir / "videos" / video_id
            video_dir.mkdir(parents=True, exist_ok=True)

            future = executor.submit(download_single_transcript, video_id, video_dir)
            futures[future] = video_id

        for future in as_completed(futures):
            video_id = futures[future]
            try:
                success = future.result()
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                print(f"❌ Exception for {video_id}: {e}")
                results["failed"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Download YouTube transcripts")
    parser.add_argument("--sources", default="pipeline/sources.json",
                       help="Sources JSON file")
    parser.add_argument("--videos", nargs="+",
                       help="Specific video IDs to download")
    parser.add_argument("--workers", type=int, default=5,
                       help="Number of parallel workers")
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")

    args = parser.parse_args()

    # Load config
    config = Config(args.config)
    data_dir = Path(config.get('sources.videos')).parent

    # Load sources
    sources_file = Path(args.sources)
    if not sources_file.exists():
        print(f"❌ Sources file not found: {sources_file}")
        print("Run: uv run python pipeline/scripts/00_process_sources.py --sources pipeline/sources.json")
        return 1

    with open(sources_file) as f:
        data = json.load(f)

    sources = data.get("sources", [])

    # Filter by specific video IDs if requested
    if args.videos:
        sources = [s for s in sources if s["video_id"] in args.videos]

    if not sources:
        print("❌ No videos to download")
        return 1

    print(f"📊 Downloading transcripts for {len(sources)} videos")
    print(f"🔧 Using {args.workers} parallel workers\n")

    # Download transcripts
    results = download_transcripts_parallel(sources, data_dir, args.workers)

    # Print summary
    print("\n" + "="*60)
    print("DOWNLOAD SUMMARY")
    print("="*60)
    print(f"✅ Success: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
