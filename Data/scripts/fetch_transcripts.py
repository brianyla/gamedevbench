#!/usr/bin/env python3

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "metadata" / "tutorial_manifest.csv"
TRANSCRIPTS_DIR = ROOT / "metadata" / "transcripts"


def main() -> None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise SystemExit(
            "Missing dependency: youtube-transcript-api\n"
            "Install with: pip install youtube-transcript-api"
        )

    api = YouTubeTranscriptApi()
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    with MANIFEST.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    written = 0
    skipped = 0
    failed = 0

    for row in rows:
        video_id = row["video_id"].strip()
        transcript_path = ROOT / row["transcript_path"]
        source_folder = row["source_folder"]

        if not video_id:
            print(f"SKIP {source_folder}: missing video_id")
            skipped += 1
            continue

        if transcript_path.exists() and transcript_path.read_text().strip():
            print(f"SKIP {source_folder}: transcript already exists")
            skipped += 1
            continue

        try:
            fetched = api.fetch(video_id)
            raw_entries = fetched.to_raw_data()
            text = "\n".join(
                f"[{entry['start']:.2f}] {entry['text']}" for entry in raw_entries if entry.get("text")
            )
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(text)
            print(f"WROTE {source_folder} -> {transcript_path}")
            written += 1
        except Exception as exc:
            print(f"FAIL {source_folder}: {exc}")
            failed += 1

    print(f"written={written} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
