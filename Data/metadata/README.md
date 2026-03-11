# Dataset Metadata

`tutorial_manifest.csv` is the control file for the raw Godot project folders in this workspace.

Column notes:

- `tutorial_id`: Stable canonical ID for dataset tooling. Keep this fixed after tasks start referencing it.
- `source_folder`: Existing raw folder on disk. Do not rename this unless you intentionally migrate the raw source.
- `source_type`: Either `checkpoint` or `version_snapshot`.
- `order_index`: Sequence value used to infer the previous folder in a series.
- `youtube_url`, `video_id`, `channel`, `title`: Fill these in once you collect the source tutorial metadata.
- `transcript_path`: Where the transcript file should live if you add one later.
- `repo_root`: Absolute path to the raw Godot project.
- `godot_version`: Parsed from `project.godot`.
- `start_source_folder`: Proposed predecessor folder to use as the starting point for task extraction.
- `gt_source_folder`: The current folder, treated as the candidate ground truth.
- `status`: Workflow status. Suggested values are `needs_metadata`, `ready_for_diff`, `tasked`, `validated`.
- `notes`: Free-form remarks for edge cases or linkage issues.

Recommended workflow:

1. Fill in video metadata.
2. Verify `start_source_folder` pairings.
3. Diff each `start_source_folder` -> `gt_source_folder` pair.
4. Create task bundles under `tasks/`.
