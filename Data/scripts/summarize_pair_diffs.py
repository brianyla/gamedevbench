#!/usr/bin/env python3

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "metadata" / "tutorial_manifest.csv"
OUTPUT = ROOT / "metadata" / "pair_diff_summary.csv"
IGNORE_PARTS = {".godot", ".git", ".import"}
IGNORE_NAMES = {".DS_Store", ".gitattributes", ".gitignore"}


def should_ignore(path: Path) -> bool:
    if any(part in IGNORE_PARTS for part in path.parts):
        return True
    if path.name in IGNORE_NAMES:
        return True
    if path.suffix == ".import":
        return True
    return any(part.startswith(".") for part in path.parts)


def iter_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or should_ignore(path):
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha1(path.read_bytes()).hexdigest()
        result[rel] = digest
    return result


def main() -> None:
    with MANIFEST.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    output_rows = []
    for row in rows:
        start_folder = row["start_source_folder"].strip()
        gt_folder = row["gt_source_folder"].strip()
        if not start_folder:
            continue

        start_root = ROOT / start_folder
        gt_root = ROOT / gt_folder
        start_files = iter_files(start_root)
        gt_files = iter_files(gt_root)

        start_names = set(start_files)
        gt_names = set(gt_files)

        added = sorted(gt_names - start_names)
        deleted = sorted(start_names - gt_names)
        common = start_names & gt_names
        changed = sorted(name for name in common if start_files[name] != gt_files[name])

        output_rows.append(
            {
                "tutorial_id": row["tutorial_id"],
                "start_source_folder": start_folder,
                "gt_source_folder": gt_folder,
                "source_type": row["source_type"],
                "added_files": len(added),
                "deleted_files": len(deleted),
                "changed_files": len(changed),
                "candidate_files": " | ".join((changed + added)[:12]),
            }
        )

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "tutorial_id",
                "start_source_folder",
                "gt_source_folder",
                "source_type",
                "added_files",
                "deleted_files",
                "changed_files",
                "candidate_files",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
