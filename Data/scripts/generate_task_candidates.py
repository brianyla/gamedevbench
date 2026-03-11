#!/usr/bin/env python3

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "metadata" / "tutorial_manifest.csv"
PAIR_DIFFS = ROOT / "metadata" / "pair_diff_summary.csv"
OUTPUT = ROOT / "metadata" / "task_candidates.csv"


def to_int(order_index: str) -> int:
    return int(float(order_index))


def priority_for(total_changes: int) -> tuple[str, str]:
    if total_changes <= 8:
        return ("high", "1")
    if total_changes <= 14:
        return ("medium", "1-2")
    return ("low", "2-3")


def build_row(
    manifest: dict[str, str],
    *,
    task_source_type: str,
    title: str,
    youtube_urls: list[str],
    video_ids: list[str],
    transcript_paths: list[str],
    start_source_folder: str,
    gt_source_folder: str,
    added_files: int,
    deleted_files: int,
    changed_files: int,
    candidate_files: str,
    notes: str = "",
) -> dict[str, str]:
    total_changes = added_files + deleted_files + changed_files
    extraction_priority, suggested_task_count = priority_for(total_changes)
    return {
        "tutorial_id": manifest["tutorial_id"],
        "order_index": manifest["order_index"],
        "title": title,
        "task_source_type": task_source_type,
        "youtube_urls": "|".join(url for url in youtube_urls if url),
        "video_ids": "|".join(video_id for video_id in video_ids if video_id),
        "transcript_paths": "|".join(path for path in transcript_paths if path),
        "start_source_folder": start_source_folder,
        "gt_source_folder": gt_source_folder,
        "added_files": added_files,
        "deleted_files": deleted_files,
        "changed_files": changed_files,
        "total_changes": total_changes,
        "candidate_files": candidate_files,
        "extraction_priority": extraction_priority,
        "suggested_task_count": suggested_task_count,
        "task_generation_status": "pending_review",
        "notes": notes,
    }


def split_pipe(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split("|")) if item]


def join_unique(values: list[str]) -> str:
    seen = set()
    ordered = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return "|".join(ordered)


def main() -> None:
    with MANIFEST.open(newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    with PAIR_DIFFS.open(newline="") as handle:
        diff_rows = list(csv.DictReader(handle))

    manifest_rows.sort(key=lambda row: to_int(row["order_index"]))
    manifest_by_tutorial_id = {row["tutorial_id"]: row for row in manifest_rows}
    diff_by_tutorial_id = {row["tutorial_id"]: row for row in diff_rows}

    output_rows: list[dict[str, str]] = []

    # Keep the first tutorial as a standalone bootstrap task even without a predecessor pair.
    first_manifest = manifest_rows[0]
    output_rows.append(
        build_row(
            first_manifest,
            task_source_type="bootstrap",
            title=first_manifest["title"],
            youtube_urls=[first_manifest["youtube_url"]],
            video_ids=[first_manifest["video_id"]],
            transcript_paths=[first_manifest["transcript_path"]],
            start_source_folder=first_manifest["source_folder"],
            gt_source_folder=first_manifest["source_folder"],
            added_files=0,
            deleted_files=0,
            changed_files=0,
            candidate_files="",
            notes="Bootstrap tutorial with no predecessor snapshot; start and solution both point to the tutorial snapshot."
        )
    )

    previous_non_duplicate_manifest = first_manifest
    previous_non_duplicate_diff = None
    previous_non_duplicate_output_row = None

    for manifest in manifest_rows[1:]:
        tutorial_id = manifest["tutorial_id"]
        diff = diff_by_tutorial_id.get(tutorial_id)
        if diff is None:
            continue

        status = manifest["status"].strip()
        added = int(diff["added_files"])
        deleted = int(diff["deleted_files"])
        changed = int(diff["changed_files"])
        total_changes = added + deleted + changed

        if status == "duplicate_snapshot":
            if previous_non_duplicate_diff is None:
                continue
            if previous_non_duplicate_output_row is None:
                continue
            previous_non_duplicate_output_row["task_source_type"] = "pair_merged_duplicate"
            previous_non_duplicate_output_row["title"] = (
                f"{previous_non_duplicate_output_row['title']} + {manifest['title']}"
            )
            previous_non_duplicate_output_row["youtube_urls"] = join_unique(
                split_pipe(previous_non_duplicate_output_row["youtube_urls"]) + [manifest["youtube_url"]]
            )
            previous_non_duplicate_output_row["video_ids"] = join_unique(
                split_pipe(previous_non_duplicate_output_row["video_ids"]) + [manifest["video_id"]]
            )
            previous_non_duplicate_output_row["transcript_paths"] = join_unique(
                split_pipe(previous_non_duplicate_output_row["transcript_paths"]) + [manifest["transcript_path"]]
            )
            existing_notes = previous_non_duplicate_output_row["notes"].strip()
            merge_note = (
                f"Merged duplicate-snapshot tutorial {manifest['source_folder']} into this task and combined transcript/video provenance."
            )
            previous_non_duplicate_output_row["notes"] = (
                f"{existing_notes} {merge_note}".strip() if existing_notes else merge_note
            )
            continue

        if total_changes == 0:
            continue

        row = build_row(
            manifest,
            task_source_type="pair",
            title=manifest["title"],
            youtube_urls=[manifest["youtube_url"]],
            video_ids=[manifest["video_id"]],
            transcript_paths=[manifest["transcript_path"]],
            start_source_folder=diff["start_source_folder"],
            gt_source_folder=diff["gt_source_folder"],
            added_files=added,
            deleted_files=deleted,
            changed_files=changed,
            candidate_files=diff["candidate_files"],
        )
        output_rows.append(row)
        previous_non_duplicate_manifest = manifest
        previous_non_duplicate_diff = diff
        previous_non_duplicate_output_row = row

    output_rows.sort(key=lambda row: (to_int(row["order_index"]), row["task_source_type"]))

    fieldnames = [
        "tutorial_id",
        "order_index",
        "title",
        "task_source_type",
        "youtube_urls",
        "video_ids",
        "transcript_paths",
        "start_source_folder",
        "gt_source_folder",
        "added_files",
        "deleted_files",
        "changed_files",
        "total_changes",
        "candidate_files",
        "extraction_priority",
        "suggested_task_count",
        "task_generation_status",
        "notes",
    ]

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
