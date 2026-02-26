# Simple Workflow: Single Source of Truth

Use **one file** (`sources.json`) to define all video-repo pairs.

## Configuration: sources.json

**`pipeline/sources.json`:**
```json
{
  "sources": [
    {
      "video_id": "Pa0P1lUoC-M",
      "video_url": "https://www.youtube.com/watch?v=Pa0P1lUoC-M",
      "video_title": "Godot 4 Deck Builder Tutorial",
      "repo_name": "deck_builder_tutorial",
      "repo_url": "https://github.com/guladam/deck_builder_tutorial",
      "description": "Deck building card game tutorial"
    }
  ]
}
```

Add as many video-repo pairs as you want. Each pair defines:
- Which YouTube video
- Which GitHub repository
- Clear association between them

## Complete Workflow

### Step 1: Clone Repositories

```bash
uv run python pipeline/scripts/02_clone_repos.py --sources pipeline/sources.json
```

**What this does:**
- Reads `sources.json`
- Extracts unique repositories
- Clones them to `data/repos/`

**Note:** It automatically extracts repos from sources - no separate repos file!

### Step 2: Download Transcripts

```bash
uv run python pipeline/scripts/01_download_transcripts.py --sources pipeline/sources.json
```

**What this does:**
- Reads video IDs from `sources.json`
- Downloads YouTube transcripts using `youtube-transcript-api`
- Saves to `data/videos/{video_id}/transcript.txt`
- Updates metadata with download status
- Parallel downloads (5 workers by default)

**Download specific videos only:**
```bash
uv run python pipeline/scripts/01_download_transcripts.py --videos "Pa0P1lUoC-M" "another_id"
```

### Step 3: Analyze Commits

```bash
uv run python pipeline/scripts/03_analyze_commits.py
```

Analyzes all cloned repositories for Godot-relevant commits.

### Step 4: Discover Tasks

```bash
uv run python pipeline/scripts/04_discover_tasks.py --sources pipeline/sources.json
```

**What this does:**
- Finds all videos in `data/videos/`
- For each video, reads `sources.json` to find the associated repo
- Matches transcript to commits
- No `--repo` flag needed - it reads from sources.json!

### Step 5: Extract Tasks

```bash
uv run python pipeline/scripts/05_extract_task_from_commit.py
```

Extracts ground truth and starting point from git commits.

### Step 6: Generate Tests

```bash
uv run python pipeline/scripts/06_generate_tests.py
```

Generates validation tests for extracted tasks.

### Step 7: Validate

```bash
uv run python pipeline/scripts/07_validate_tasks.py
```

Validates that ground truth passes and starting point fails.

## Benefits

✅ **Single source of truth:** One `sources.json` file
✅ **Clear mapping:** Each video explicitly linked to repo
✅ **Automatic extraction:** Clone script extracts repos from sources
✅ **No intermediate files:** No separate `repos.json` needed
✅ **Metadata-driven:** Video-repo association stored once, used everywhere
✅ **Easy to scale:** Add 100+ sources by editing one file

## For Your Test

Your `sources.json` is already configured with the deck builder tutorial!

```bash
cd /Users/brianla/Documents/GitHub/gamedevbench

# Step 0: Set up associations
uv run python pipeline/scripts/00_process_sources.py --sources pipeline/sources.json

# Step 1: Clone repo (extracts from sources.json)
uv run python pipeline/scripts/02_clone_repos.py --sources pipeline/sources.json

# Step 2: Analyze commits
uv run python pipeline/scripts/03_analyze_commits.py --repos "deck_builder_tutorial"

# Step 3: Download transcript
uv run python pipeline/scripts/01_download_transcripts.py --sources pipeline/sources.json

# Step 4: Discover tasks (knows repo from metadata!)
uv run python pipeline/scripts/04_discover_tasks.py --videos "Pa0P1lUoC-M"

# Continue with remaining steps...
```

## Adding More Sources

Just edit `sources.json`:

```json
{
  "sources": [
    {
      "video_id": "Pa0P1lUoC-M",
      "repo_name": "deck_builder_tutorial",
      "repo_url": "https://github.com/guladam/deck_builder_tutorial",
      ...
    },
    {
      "video_id": "another_video",
      "repo_name": "another_repo",
      "repo_url": "https://github.com/user/another-repo",
      ...
    }
  ]
}
```

Then re-run:
```bash
uv run python pipeline/scripts/00_process_sources.py --sources pipeline/sources.json
uv run python pipeline/scripts/02_clone_repos.py --sources pipeline/sources.json
```

That's it! One file, clear organization.
