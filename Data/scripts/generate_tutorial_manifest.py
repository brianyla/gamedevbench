#!/usr/bin/env python3

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "metadata" / "tutorial_manifest.csv"

CHECKPOINT_RE = re.compile(r"^FPS(?P<num>\d{3})_(?P<slug>.+)$")
VERSION_RE = re.compile(r"^FPS-Project-VC-(?P<major>\d+)\.(?P<minor>\d+)$")
YOUTUBE_LINKS = ROOT / "metadata" / "youtube_links.csv"


@dataclass
class TutorialRow:
    tutorial_id: str
    source_folder: str
    source_type: str
    series_name: str
    order_index: str
    youtube_url: str
    video_id: str
    channel: str
    title: str
    transcript_path: str
    repo_root: str
    godot_version: str
    start_source_folder: str
    gt_source_folder: str
    status: str
    notes: str


def slugify(text: str) -> str:
    return "_".join(word.lower() for word in split_words(text))


def split_words(text: str) -> list[str]:
    text = text.replace("//", " ")
    text = text.replace("_", " ")
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    parts = []
    for chunk in text.split():
        parts.extend(
            re.findall(
                r"[A-Z]+(?=[A-Z][a-z]|\d+[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+[A-Z]+(?![a-z])|\d+|[A-Z]+",
                chunk,
            )
        )
    return [part for part in parts if part]


def infer_title_from_folder(folder_name: str) -> str:
    checkpoint_match = CHECKPOINT_RE.match(folder_name)
    if checkpoint_match:
        return " ".join(split_words(checkpoint_match.group("slug")))
    return " ".join(split_words(folder_name))


def load_youtube_links() -> dict[str, dict[str, str]]:
    if not YOUTUBE_LINKS.exists():
        return {}

    by_source_folder: dict[str, dict[str, str]] = {}
    with YOUTUBE_LINKS.open(newline="") as handle:
        for row in csv.DictReader(handle):
            source_folder = row.get("source_folder", "").strip()
            if source_folder:
                by_source_folder[source_folder] = row
    return by_source_folder


def extract_video_id(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else ""


def detect_godot_version(project_file: Path) -> str:
    for line in project_file.read_text().splitlines():
        if "config/features=" not in line:
            continue
        match = re.search(r'"(\d+\.\d+)"', line)
        if match:
            return match.group(1)
    return ""


def classify_folder(folder: Path) -> tuple[str, str, str]:
    name = folder.name
    checkpoint_match = CHECKPOINT_RE.match(name)
    if checkpoint_match:
        order_index = str(int(checkpoint_match.group("num")))
        slug = slugify(checkpoint_match.group("slug"))
        return (
            f"fps_{checkpoint_match.group('num').lower()}_{slug}",
            "checkpoint",
            order_index,
        )

    version_match = VERSION_RE.match(name)
    if version_match:
        major = version_match.group("major")
        minor = version_match.group("minor")
        order_index = f"{major}.{minor}"
        return (f"fps_vc_{major}_{minor}", "version_snapshot", order_index)

    return (slugify(name), "unknown", "")


def build_rows() -> list[TutorialRow]:
    existing_by_tutorial_id = {}
    existing_by_source_folder = {}
    youtube_links = load_youtube_links()
    if OUTPUT.exists():
        with OUTPUT.open(newline="") as handle:
            for row in csv.DictReader(handle):
                existing_by_tutorial_id[row.get("tutorial_id", "")] = row
                existing_by_source_folder[row.get("source_folder", "")] = row

    folders = sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / "project.godot").exists())
    rows: list[TutorialRow] = []

    checkpoint_rows: list[TutorialRow] = []
    version_rows: list[TutorialRow] = []

    for folder in folders:
        tutorial_id, source_type, order_index = classify_folder(folder)
        existing = existing_by_tutorial_id.get(tutorial_id) or existing_by_source_folder.get(folder.name) or {}
        youtube = youtube_links.get(folder.name, {})
        title = existing.get("title", "").strip() or youtube.get("title", "").strip() or infer_title_from_folder(folder.name)
        youtube_url = youtube.get("youtube_url", "").strip() or existing.get("youtube_url", "").strip()
        video_id = youtube.get("video_id", "").strip() or extract_video_id(youtube_url) or existing.get("video_id", "").strip()
        channel = youtube.get("channel", "").strip() or existing.get("channel", "").strip()
        row = TutorialRow(
            tutorial_id=tutorial_id,
            source_folder=folder.name,
            source_type=source_type,
            series_name="the_godot_fps_project",
            order_index=order_index,
            youtube_url=youtube_url,
            video_id=video_id,
            channel=channel,
            title=title,
            transcript_path=(
                f"metadata/transcripts/{tutorial_id}.txt"
                if existing.get("transcript_path", "").startswith("metadata/transcripts/")
                or not existing.get("transcript_path", "").strip()
                else existing.get("transcript_path", "")
            ),
            repo_root=str(folder.resolve()),
            godot_version=detect_godot_version(folder / "project.godot"),
            start_source_folder="",
            gt_source_folder=folder.name,
            status=existing.get("status", "needs_metadata"),
            notes=existing.get("notes", ""),
        )
        rows.append(row)
        if source_type == "checkpoint":
            checkpoint_rows.append(row)
        elif source_type == "version_snapshot":
            version_rows.append(row)

    for series_rows in (checkpoint_rows, version_rows):
        series_rows.sort(key=lambda row: [int(part) for part in row.order_index.split(".") if part])
        previous = None
        for row in series_rows:
            row.start_source_folder = previous.source_folder if previous else ""
            previous = row

    rows.sort(
        key=lambda row: (
            0 if row.source_type == "checkpoint" else 1 if row.source_type == "version_snapshot" else 2,
            [int(part) for part in row.order_index.split(".") if part] if row.order_index else [9999],
            row.source_folder,
        )
    )
    return rows


def write_csv(rows: list[TutorialRow]) -> None:
    fieldnames = list(TutorialRow.__annotations__.keys())
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
