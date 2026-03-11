#!/usr/bin/env python3

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "metadata" / "tutorial_manifest.csv"
YOUTUBE_LINKS = ROOT / "metadata" / "youtube_links.csv"


def extract_video_id(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else ""


def main() -> None:
    with MANIFEST.open(newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
        fieldnames = manifest_rows[0].keys()

    youtube_rows = {}
    with YOUTUBE_LINKS.open(newline="") as handle:
        for row in csv.DictReader(handle):
            youtube_rows[row.get("source_folder", "").strip()] = row

    updated = 0
    for row in manifest_rows:
        youtube = youtube_rows.get(row["source_folder"])
        if not youtube:
            continue

        youtube_url = youtube.get("youtube_url", "").strip()
        channel = youtube.get("channel", "").strip()
        title = youtube.get("title", "").strip()
        video_id = youtube.get("video_id", "").strip() or extract_video_id(youtube_url)

        if youtube_url:
            row["youtube_url"] = youtube_url
        if channel:
            row["channel"] = channel
        if title:
            row["title"] = title
        if video_id:
            row["video_id"] = video_id
        updated += 1

    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Updated manifest rows from {YOUTUBE_LINKS}: {updated}")


if __name__ == "__main__":
    main()
