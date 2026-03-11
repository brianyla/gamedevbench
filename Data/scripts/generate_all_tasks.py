#!/usr/bin/env python3

import csv
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TASK_CANDIDATES = ROOT / "metadata" / "task_candidates.csv"
TASKS_DIR = ROOT / "tasks"
IGNORE_NAMES = shutil.ignore_patterns(".DS_Store", ".gitignore", ".gitattributes", ".godot")


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text


def infer_skill_category(title: str, candidate_files: list[str]) -> str:
    title_lower = title.lower()
    joined = " ".join(candidate_files).lower()
    if any(word in title_lower for word in ["ui", "hud", "menu", "panel", "label"]):
        return "user_interface"
    if any(token in joined for token in ["textures/", ".png", ".material", ".tres", ".glb", "mesh", "weapon"]):
        return "3d_graphics"
    if any(token in joined for token in ["sprite", "tilemap", "2d"]):
        return "2d_graphics"
    return "gameplay_logic"


def infer_editor_type(candidate_files: list[str]) -> str:
    has_script = any(path.endswith(".gd") for path in candidate_files)
    has_scene = any(path.endswith(".tscn") for path in candidate_files)
    has_context = any(path.endswith((".tres", ".png", ".glb", ".res")) for path in candidate_files)
    if has_script and (has_scene or has_context):
        return "scene_editor+script_editor"
    if has_script:
        return "script_editor"
    if has_scene or has_context:
        return "scene_editor"
    return "script_editor"


def infer_multimodal(candidate_files: list[str]) -> bool:
    return any(path.endswith((".tscn", ".tres", ".png", ".glb", ".res")) for path in candidate_files)


def infer_difficulty(total_changes: int) -> str:
    if total_changes <= 8:
        return "easy"
    if total_changes <= 16:
        return "medium"
    return "hard"


def build_instruction(title: str, candidate_files: list[str]) -> str:
    if not candidate_files:
        return (
            f"Implement the `{title}` tutorial step in this Godot project. "
            f"Use the tutorial transcript and the existing project files to preserve the intended scene, "
            f"script, and resource setup for this feature."
        )
    files_str = ", ".join(f"`res://{path}`" for path in candidate_files[:6])
    suffix = ""
    if len(candidate_files) > 6:
        suffix = ", and any directly related scene or resource wiring"
    return (
        f"Implement the `{title}` tutorial step in this Godot project. "
        f"Update {files_str}{suffix} so the project includes the scene, script, "
        f"and resource changes required for this feature."
    )


def extract_excerpt(transcript_paths: list[Path], title: str) -> str:
    lines: list[str] = []
    for transcript_path in transcript_paths:
        if transcript_path.exists():
            current = transcript_path.read_text().splitlines()
            if current:
                if lines:
                    lines.append("")
                lines.extend(current)
    if not lines:
        return ""

    keywords = [word.lower() for word in re.findall(r"[A-Za-z0-9]+", title) if len(word) >= 4]
    match_index = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            match_index = index
            break

    if match_index is None:
        excerpt = lines[:40]
    else:
        start = max(0, match_index - 8)
        end = min(len(lines), match_index + 24)
        excerpt = lines[start:end]
    return "\n".join(excerpt).strip() + "\n"


def copy_project(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=IGNORE_NAMES)


def main() -> None:
    with TASK_CANDIDATES.open(newline="") as handle:
        candidates = list(csv.DictReader(handle))

    for existing in TASKS_DIR.iterdir():
        if existing.is_dir() and existing.name.startswith("task_"):
            shutil.rmtree(existing)

    for index, row in enumerate(candidates, start=1):
        task_id = f"task_{index:04d}"
        task_slug = slugify(row["title"])
        task_dir = TASKS_DIR / f"{task_id}_{task_slug}"
        start_src = ROOT / row["start_source_folder"]
        solution_src = ROOT / row["gt_source_folder"]
        transcript_paths = [ROOT / item.strip() for item in row["transcript_paths"].split("|") if item.strip()]
        candidate_files = [item.strip() for item in row["candidate_files"].split("|") if item.strip()]
        total_changes = int(row["total_changes"])

        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)

        copy_project(start_src, task_dir / "start")
        copy_project(solution_src, task_dir / "solution")

        task_config = {
            "task_id": task_id,
            "task_name": task_slug,
            "tutorial_id": row["tutorial_id"],
            "task_source_type": row["task_source_type"],
            "instruction": build_instruction(row["title"], candidate_files),
            "difficulty": infer_difficulty(total_changes),
            "skill_category": infer_skill_category(row["title"], candidate_files),
            "editor_type": infer_editor_type(candidate_files),
            "requires_multimodal": infer_multimodal(candidate_files),
            "files_to_edit": candidate_files,
            "start_source_folder": row["start_source_folder"],
            "solution_source_folder": row["gt_source_folder"]
        }
        (task_dir / "task_config.json").write_text(json.dumps(task_config, indent=2) + "\n")

        provenance = {
            "source_type": "youtube_tutorial",
            "tutorial_title": row["title"],
            "task_source_type": row["task_source_type"],
            "youtube_urls": [item.strip() for item in row["youtube_urls"].split("|") if item.strip()],
            "video_ids": [item.strip() for item in row["video_ids"].split("|") if item.strip()],
            "transcript_paths": [str(path) for path in transcript_paths],
            "start_project_path": str(start_src),
            "solution_project_path": str(solution_src),
            "derived_from": "GameDevBench-style tutorial-to-task distillation without local validation.",
            "notes": row["notes"],
        }
        (task_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")

        excerpt = extract_excerpt(transcript_paths, row["title"])
        (task_dir / "transcript_excerpt.txt").write_text(excerpt)

    print(f"Wrote {len(candidates)} task bundles to {TASKS_DIR}")


if __name__ == "__main__":
    main()
