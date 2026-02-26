# GameDevBench Task Generation Pipeline

Automated pipeline for generating GameDevBench tasks from YouTube tutorials and GitHub repositories.

## Overview

This pipeline transforms YouTube tutorials and their companion repositories into complete benchmark tasks by:

1. **Downloading transcripts** from YouTube videos
2. **Cloning and analyzing** GitHub repositories
3. **Matching tutorial segments to commits** using LLM
4. **Extracting tasks from git history** (before/after states)
5. **Generating validation tests** using LLM
6. **Validating tasks** with Godot

## Directory Structure

```
pipeline/
├── data/
│   ├── videos/{video_id}/
│   │   ├── metadata.json
│   │   ├── transcript.txt
│   │   └── candidates.json
│   ├── repos/{repo_name}/
│   │   ├── metadata.json
│   │   ├── code/                    # Cloned repository
│   │   └── commits.json             # Analyzed commits
│   └── tasks/{task_id}/
│       ├── task_spec.json
│       ├── ground_truth/            # Complete implementation
│       ├── starting_point/          # Stubbed version
│       └── scripts/test.gd          # Validation test
├── scripts/
│   ├── 01_download_transcripts.py
│   ├── 02_clone_repos.py
│   ├── 03_analyze_commits.py
│   ├── 04_discover_tasks.py
│   ├── 05_extract_task_from_commit.py
│   ├── 06_generate_tests.py
│   ├── 07_validate_tasks.py
│   └── utils.py
├── config.yaml
├── run_pipeline.py
└── README.md
```

## Setup

### Prerequisites

- Python 3.8+
- Godot 4.x (in PATH)
- Git
- Anthropic API key

### Installation

#### Option A: Using `uv` (Recommended)

```bash
# From repository root, no installation needed! Just set API key:
export ANTHROPIC_API_KEY="your-key-here"

# Run with: uv run python pipeline/<script>
# Dependencies are automatically installed from root pyproject.toml
```

#### Option B: Traditional pip

```bash
# Install dependencies
pip install -r requirements.txt
# or
pip install anthropic pyyaml

# Set API key
export ANTHROPIC_API_KEY="your-key-here"
```

#### Verify Godot

```bash
# Verify Godot is in PATH
godot --version
```

See [UV_USAGE.md](UV_USAGE.md) for complete `uv` guide.

### Configuration

Edit `config.yaml`:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4.5
  api_key_env: ANTHROPIC_API_KEY

godot:
  executable: godot  # or full path
```

## Usage

### Quick Start

#### With uv (recommended):

```bash
# Test with small subset
uv run python run_pipeline.py --all --videos "video1,video2,video3"

# Run full pipeline
uv run python run_pipeline.py --all
```

#### Without uv:

```bash
# Test with small subset
python run_pipeline.py --all --videos "video1,video2,video3"

# Run full pipeline
python run_pipeline.py --all
```

### Stage-by-Stage Execution

```bash
# 1. Download transcripts
python run_pipeline.py --stage download

# 2. Clone repositories (requires repo list)
python pipeline/scripts/02_clone_repos.py --repos repo_list.json

# 3. Analyze commit history
python run_pipeline.py --stage analyze_commits

# 4. Discover task candidates (LLM matching)
python run_pipeline.py --stage discovery

# 5. Extract tasks from commits
python run_pipeline.py --stage extraction

# 6. Generate validation tests (LLM)
python run_pipeline.py --stage test_generation

# 7. Validate tasks
python run_pipeline.py --stage validation
```

### Common Scenarios

**Resume after interruption:**
```bash
python run_pipeline.py --all --resume
```

**Retry failed items:**
```bash
python run_pipeline.py --stage discovery --retry-failed
```

**Process specific items:**
```bash
python run_pipeline.py --stage extraction --videos "vid1,vid2"
python run_pipeline.py --stage test_generation --tasks "task_5001,task_5002"
```

**Dry run (preview):**
```bash
python run_pipeline.py --stage validation --dry-run
```

### Statistics

```bash
# View pipeline statistics
python pipeline/scripts/utils.py --stats
```

## Pipeline Stages

### 1. Download Transcripts

Downloads YouTube video transcripts.

**Input:** List of video IDs
**Output:** `data/videos/{video_id}/transcript.txt`

### 2. Clone Repositories

Clones GitHub repositories in parallel.

**Input:** `repo_list.json` with format:
```json
[
  {"name": "QuestManager", "url": "https://github.com/user/repo"},
  ...
]
```
**Output:** `data/repos/{repo_name}/code/`

### 3. Analyze Commits

Extracts commit history with Godot-relevant changes.

**Input:** Cloned repositories
**Output:** `data/repos/{repo_name}/commits.json`

### 4. Discover Tasks

Uses LLM to match transcript segments to specific commits.

**Input:** Transcripts + Commit history
**Output:** `data/videos/{video_id}/candidates.json`

**Cost:** ~$0.30 per video

### 5. Extract Tasks

Extracts before/after states from git commits.

**Input:** Task candidates
**Output:**
- `data/tasks/{task_id}/ground_truth/` (commit state)
- `data/tasks/{task_id}/starting_point/` (commit^ state)

### 6. Generate Tests

Uses LLM to generate validation tests.

**Input:** Task spec + Ground truth structure
**Output:** `data/tasks/{task_id}/ground_truth/scripts/test.gd`

**Cost:** ~$0.10 per task

### 7. Validate Tasks

Runs tests to verify task quality.

**Input:** Tasks with tests
**Output:** `pipeline/validation_report.json`

**Validation criteria:**
- ✅ Ground truth test passes
- ✅ Starting point test fails
- ✅ No syntax errors

## Cost Estimation

For 100 videos → ~300 tasks:

| Stage | LLM Calls | Cost |
|-------|-----------|------|
| Discovery | 100 | $30 |
| Test Generation | 300 | $30 |
| **Total** | **400** | **~$60** |

**Time:** ~2 hours (fully automated)

## Output Format

### Task Specification

```json
{
  "task_id": "task_05001",
  "name": "Quest HUD System",
  "instruction": "Create a CanvasLayer-based quest HUD...",
  "difficulty": "intermediate",
  "estimated_time_minutes": 30,
  "tags": ["ui", "signals", "canvas_layer"],
  "video_id": "9tu-Q-T--mY",
  "repo_name": "QuestManager",
  "commit_hash": "a1b2c3d4...",
  "commit_message": "Add quest UI with signal connections"
}
```

### Validation Report

```json
{
  "stats": {
    "total": 300,
    "valid": 270,
    "warnings": 20,
    "invalid": 10
  },
  "results": [...]
}
```

## Troubleshooting

### Common Issues

**API rate limits:**
- Pipeline includes exponential backoff
- Reduce `llm_batch_size` in config

**Godot not found:**
```bash
# Set full path in config.yaml
godot:
  executable: /Applications/Godot.app/Contents/MacOS/Godot
```

**Git checkout errors:**
- Ensure repos are properly cloned
- Check for uncommitted changes in repo directories

**Test generation fails:**
- Check reference tasks exist in `tasks/`
- Verify ground truth structure is valid

### Debug Mode

```bash
# Run individual scripts with verbose output
python pipeline/scripts/04_discover_tasks.py --videos "video1" --config config.yaml
```

## Development

### Adding New Stages

1. Create script in `pipeline/scripts/`
2. Add stage name to `PipelineOrchestrator.STAGES`
3. Implement stage logic in `run_pipeline.py`

### Customizing Prompts

Edit prompt templates in:
- `scripts/04_discover_tasks.py` - Task discovery
- `scripts/06_generate_tests.py` - Test generation

### Testing

```bash
# Test on small subset first
python run_pipeline.py --all --videos "vid1,vid2,vid3" --dry-run
python run_pipeline.py --all --videos "vid1,vid2,vid3"

# Validate results
python pipeline/scripts/utils.py --stats
cat pipeline/validation_report.json | jq '.stats'
```

## Architecture Notes

### Git-Based Extraction

**Key Insight:** Instead of generating ground truth with LLMs, we extract it directly from Git commits where the tutorial author implemented the feature.

**Benefits:**
- Real, tested code (no syntax errors)
- Natural progression (commit^ → commit)
- 75% cost reduction vs LLM generation
- 3x faster execution

### File-Based State Tracking

Uses directory structure as database:
- No external database required
- Metadata in JSON files
- Resume support via stage tracking
- Easy to debug and inspect

### Parallel Processing

- Downloads: 20 parallel workers
- LLM calls: Sequential with retry logic
- Git operations: Parallel analysis

## License

See main repository LICENSE.
