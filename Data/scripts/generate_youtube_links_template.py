#!/usr/bin/env python3

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "metadata" / "tutorial_manifest.csv"
OUTPUT = ROOT / "metadata" / "youtube_links.csv"


def main() -> None:
    with MANIFEST.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    fieldnames = ["order_index", "source_folder", "title", "youtube_url", "channel", "video_id"]
    existing = {}
    if OUTPUT.exists():
        with OUTPUT.open(newline="") as handle:
            for row in csv.DictReader(handle):
                existing[row.get("source_folder", "")] = row

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            current = existing.get(row["source_folder"], {})
            writer.writerow(
                {
                    "order_index": row["order_index"],
                    "source_folder": row["source_folder"],
                    "title": current.get("title", "") or row["title"],
                    "youtube_url": current.get("youtube_url", ""),
                    "channel": current.get("channel", ""),
                    "video_id": current.get("video_id", ""),
                }
            )

    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
