# Quick Start Guide

Get started with the GameDevBench task generation pipeline in 5 minutes.

## 1. Setup Environment

### Option A: Using `uv` (Recommended - No manual install needed!)

```bash
# From repository root:
export ANTHROPIC_API_KEY="sk-ant-..."

# That's it! uv automatically handles dependencies from root pyproject.toml
# Just run with: uv run python pipeline/<script>
```

### Option B: Traditional pip install

```bash
cd pipeline

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Verify Godot

```bash
# Verify Godot is installed
godot --version
# If not in PATH, update config.yaml with full path
```

## 2. Prepare Input Data

### Create Repository List

Create `my_repos.json`:

```json
[
  {
    "name": "MyGodotProject",
    "url": "https://github.com/username/my-godot-project"
  }
]
```

### Create Video List

Create `my_videos.json` with video IDs from YouTube URLs:

```json
["9tu-Q-T--mY", "n8D3vEx7NAE", "abc123def45"]
```

## 3. Test on Small Subset

### With uv (recommended):

```bash
# Test with 2-3 videos first
uv run python scripts/02_clone_repos.py --repos my_repos.json --workers 2

# Analyze commits
uv run python scripts/03_analyze_commits.py --repos "MyGodotProject"

# Check results
uv run python scripts/utils.py --stats
cat data/repos/MyGodotProject/commits.json | head -50
```

### Without uv:

```bash
python scripts/02_clone_repos.py --repos my_repos.json --workers 2
python scripts/03_analyze_commits.py --repos "MyGodotProject"
python scripts/utils.py --stats
```

## 4. Run Discovery

```bash
# Match transcripts to commits (uses LLM)
uv run python scripts/04_discover_tasks.py --videos "9tu-Q-T--mY"

# Check candidates
cat data/videos/9tu-Q-T--mY/candidates.json
```

## 5. Extract Tasks

```bash
# Extract before/after states from git
uv run python scripts/05_extract_task_from_commit.py --videos "9tu-Q-T--mY"

# Check extracted tasks
ls data/tasks/
```

## 6. Generate Tests

```bash
# Generate validation tests (uses LLM)
uv run python scripts/06_generate_tests.py --tasks "task_xxxxx"

# Check test
cat data/tasks/task_xxxxx/ground_truth/scripts/test.gd
```

## 7. Validate

```bash
# Run validation
uv run python scripts/07_validate_tasks.py --tasks "task_xxxxx"

# Check report
cat validation_report.json | jq '.stats'
```

## Full Pipeline

Once you've tested individual stages:

```bash
# Run everything on all videos/repos
uv run python run_pipeline.py --all

# Or resume from where you left off
uv run python run_pipeline.py --all --resume
```

## Monitoring Progress

```bash
# View statistics
uv run python scripts/utils.py --stats

# Output:
# ============================================================
# PIPELINE STATISTICS
# ============================================================
#
# Videos: 10
#   - Downloaded: 10
#   - Pending: 0
#
# Repositories: 5
#   - Cloned: 5
#   - Pending: 0
#
# Tasks: 25
#   - Extracted: 20
#   - Pending: 5
```

## Troubleshooting

### "No module named 'anthropic'"

With uv:
```bash
# Just use: uv run python <script>
# Dependencies are auto-installed
```

Without uv:
```bash
pip install -r requirements.txt
```

### "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### "godot: command not found"

Edit `config.yaml`:
```yaml
godot:
  executable: /full/path/to/godot
```

### "Git checkout failed"

Ensure repos are cloned correctly:
```bash
cd data/repos/MyProject/code
git status
```

## Next Steps

- Review generated tasks in `data/tasks/`
- Adjust prompts in scripts for better quality
- Scale up to 100+ videos
- Export tasks to main `tasks/` directory

## Cost Tracking

For 100 videos:
- Discovery: ~$30 (1 call per video)
- Test generation: ~$30 (1 call per task)
- **Total: ~$60**

Track actual costs at: https://console.anthropic.com/

## Need Help?

See full documentation in `README.md`
