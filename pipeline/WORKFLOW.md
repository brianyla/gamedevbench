# Pipeline Workflow

Visual guide to the GameDevBench task generation pipeline.

## Overview Diagram

```
┌──────────────┐     ┌──────────────┐
│   YouTube    │     │   GitHub     │
│   Videos     │     │  Repositories│
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  Download    │     │    Clone     │
│ Transcripts  │     │     Repos    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       │                    ▼
       │             ┌──────────────┐
       │             │   Analyze    │
       │             │   Commits    │
       │             └──────┬───────┘
       │                    │
       └────────┬───────────┘
                ▼
         ┌──────────────┐
         │   Discover   │  ◄── LLM (Claude)
         │    Tasks     │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │   Extract    │  ◄── Git Operations
         │    Tasks     │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  Generate    │  ◄── LLM (Claude)
         │    Tests     │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │   Validate   │  ◄── Godot Engine
         │    Tasks     │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  GameDevBench│
         │    Tasks     │
         └──────────────┘
```

## Detailed Stage Flow

### Stage 1-2: Data Collection

```
INPUT:
  - video_ids: ["9tu-Q-T--mY", "n8D3vEx7NAE", ...]
  - repos.json: [{"name": "QuestManager", "url": "https://..."}]

DOWNLOAD TRANSCRIPTS (Parallel)
  └─→ data/videos/9tu-Q-T--mY/transcript.txt
  └─→ data/videos/n8D3vEx7NAE/transcript.txt

CLONE REPOS (Parallel)
  └─→ data/repos/QuestManager/code/.git
  └─→ data/repos/MovementSystem/code/.git
```

### Stage 3: Commit Analysis

```
FOR EACH REPO:
  Git log --all --name-status
  │
  ├─→ Filter Godot files (.gd, .tscn, .tres, ...)
  │
  └─→ commits.json:
      [
        {
          "hash": "a1b2c3d4...",
          "message": "Add quest UI with signals",
          "files_changed": [
            {"status": "M", "path": "scenes/quest_hud.tscn"},
            {"status": "A", "path": "scripts/quest_ui.gd"}
          ]
        }
      ]
```

### Stage 4: Task Discovery (LLM)

```
FOR EACH VIDEO:

  INPUT TO LLM:
    - Full transcript
    - Commit summaries (last 50 commits)

  LLM MATCHES:
    Transcript segment → Specific commit

  OUTPUT candidates.json:
    [
      {
        "name": "Quest HUD System",
        "instruction": "Create a CanvasLayer quest HUD...",
        "transcript_segment": "[2:30] - [8:45]",
        "commit_hash": "a1b2c3d4...",
        "difficulty": "intermediate"
      }
    ]

  COST: ~$0.30 per video
```

### Stage 5: Task Extraction (Git)

```
FOR EACH CANDIDATE:

  Step 1: CHECKOUT COMMIT (ground truth)
    git checkout a1b2c3d4
    │
    └─→ Copy all files to:
        data/tasks/task_05001/ground_truth/
          ├── scenes/quest_hud.tscn
          ├── scripts/quest_ui.gd
          └── project.godot

  Step 2: CHECKOUT PARENT (starting point)
    git checkout a1b2c3d4^
    │
    └─→ Copy all files to:
        data/tasks/task_05001/starting_point/
          ├── scenes/quest_hud.tscn (partial)
          ├── scripts/quest_ui.gd (stubbed)
          └── project.godot

  Step 3: RESTORE
    git checkout -

  RESULT: Real code diff from actual development!
```

### Stage 6: Test Generation (LLM)

```
FOR EACH TASK:

  ANALYZE GROUND TRUTH:
    - Main scene: main.tscn
    - Key nodes: QuestHUD, QuestManager
    - Scripts: quest_ui.gd, quest_manager.gd

  INPUT TO LLM:
    - Task instruction
    - Ground truth structure
    - Reference test examples

  LLM GENERATES:
    test.gd script with:
      ✓ Node structure validation
      ✓ Property checks
      ✓ Signal connection tests
      ✓ Runtime behavior tests

  OUTPUT:
    data/tasks/task_05001/ground_truth/scripts/test.gd

  COST: ~$0.10 per task
```

### Stage 7: Validation

```
FOR EACH TASK:

  TEST GROUND TRUTH:
    godot --path ground_truth --headless -s scripts/test.gd
    │
    ├─→ VALIDATION_PASSED ✅
    └─→ Expected!

  TEST STARTING POINT:
    godot --path starting_point --headless -s scripts/test.gd
    │
    ├─→ VALIDATION_FAILED ✅
    └─→ Expected! (student needs to complete it)

  QUALITY CHECKS:
    ✓ Ground truth has no syntax errors
    ✓ Test validates task requirements
    ✓ Starting point has meaningful diff

  OUTPUT:
    validation_report.json
```

## Data Flow Example

### Example: Quest HUD Task

```
1. VIDEO TRANSCRIPT (input)
   "Now we'll create a quest HUD using a CanvasLayer.
    First, add a MarginContainer as a child..."

2. GIT COMMITS (input)
   a1b2c3d4: "Add quest UI with signal connections"
   - Modified: scenes/quest_hud.tscn
   - Added: scripts/quest_ui.gd

3. LLM DISCOVERY (Stage 4)
   → Matches transcript to commit a1b2c3d4
   → Generates task instruction

4. GIT EXTRACTION (Stage 5)
   Ground Truth (commit a1b2c3d4):
     quest_hud.tscn: Full UI hierarchy
     quest_ui.gd: Complete implementation

   Starting Point (commit a1b2c3d4^):
     quest_hud.tscn: Root node only
     quest_ui.gd: Function signatures, no logic

5. LLM TEST GENERATION (Stage 6)
   → Analyzes ground truth structure
   → Generates test.gd:
     - Check QuestHUD node exists
     - Verify signal connections
     - Test quest display updates

6. VALIDATION (Stage 7)
   Ground Truth Test: PASSED ✅
   Starting Point Test: FAILED ✅
   Status: VALID TASK
```

## Control Flow

### Sequential Execution

```bash
python run_pipeline.py --all

Stage: DOWNLOAD
  ├─→ Process video_1 → ✅
  ├─→ Process video_2 → ✅
  └─→ Process video_N → ✅

Stage: CLONE
  ├─→ Clone repo_1 → ✅
  └─→ Clone repo_M → ✅

Stage: ANALYZE_COMMITS
  ├─→ Analyze repo_1 → ✅
  └─→ Analyze repo_M → ✅

Stage: DISCOVERY
  ├─→ Match video_1 → 3 candidates ✅
  ├─→ Match video_2 → 2 candidates ✅
  └─→ Match video_N → 4 candidates ✅
  Total: 300 candidates

Stage: EXTRACTION
  ├─→ Extract task_05001 → ✅
  ├─→ Extract task_05002 → ✅
  └─→ Extract task_05300 → ✅

Stage: TEST_GENERATION
  ├─→ Generate test for task_05001 → ✅
  ├─→ Generate test for task_05002 → ✅
  └─→ Generate test for task_05300 → ✅

Stage: VALIDATION
  ├─→ Validate task_05001 → VALID ✅
  ├─→ Validate task_05002 → WARNING ⚠️
  └─→ Validate task_05300 → VALID ✅
  Valid: 270/300 (90%)

DONE! Generated 300 tasks in ~2 hours for ~$60
```

### Parallel Execution

```bash
# Stages can run items in parallel

DOWNLOAD (20 parallel workers):
  Thread 1: video_1  → ✅
  Thread 2: video_2  → ✅
  ...
  Thread 20: video_20 → ✅
  [Next batch of 20...]

CLONE (10 parallel workers):
  Thread 1: repo_1 → ✅
  Thread 2: repo_2 → ✅
  ...

ANALYZE (20 parallel workers):
  Fast git operations, highly parallel
```

### Resume/Retry Flow

```bash
# Initial run interrupted
python run_pipeline.py --all
  ├─→ Download: 100/100 ✅
  ├─→ Clone: 80/100 ✅
  ├─→ Analyze: 50/100 ✅
  └─→ Discovery: 0/100 ⏹️  [INTERRUPTED]

# Resume where it left off
python run_pipeline.py --all --resume
  ├─→ Download: 0/0 (skip completed)
  ├─→ Clone: 20/20 (resume pending)
  ├─→ Analyze: 50/50 (resume pending)
  └─→ Discovery: 100/100 (all pending)

# Retry only failures
python run_pipeline.py --stage discovery --retry-failed
  └─→ Discovery: 5/5 (only failed items)
```

## Metadata State Machine

```
Each item (video/repo/task) tracks stage status:

         ┌─────────┐
         │ pending │ ◄── Initial state
         └────┬────┘
              │
         [Process]
              │
         ┌────▼──────┐
    ┌───►│in_progress│
    │    └────┬──────┘
    │         │
    │    [Success/Failure]
    │         │
    │    ┌────▼────┐     ┌────────┐
    │    │completed│     │ failed │
    │    └─────────┘     └───┬────┘
    │                        │
    │                    [Retry]
    └────────────────────────┘

Status stored in metadata.json:
{
  "stages": {
    "download": "completed",
    "discovery": "failed",
    "extraction": "pending"
  }
}
```

## File Structure Evolution

```
Initial State (empty):
  pipeline/data/

After Download:
  pipeline/data/
  └── videos/
      └── 9tu-Q-T--mY/
          ├── metadata.json
          └── transcript.txt

After Clone + Analyze:
  pipeline/data/
  ├── videos/...
  └── repos/
      └── QuestManager/
          ├── metadata.json
          ├── code/
          │   └── [git repository]
          └── commits.json

After Discovery:
  pipeline/data/
  ├── videos/
  │   └── 9tu-Q-T--mY/
  │       ├── metadata.json
  │       ├── transcript.txt
  │       └── candidates.json ◄── NEW
  └── repos/...

After Extraction:
  pipeline/data/
  ├── videos/...
  ├── repos/...
  └── tasks/
      └── task_05001/
          ├── task_spec.json
          ├── ground_truth/
          │   ├── scenes/
          │   ├── scripts/
          │   └── project.godot
          └── starting_point/
              ├── scenes/
              ├── scripts/
              └── project.godot

After Test Generation:
  pipeline/data/
  └── tasks/
      └── task_05001/
          ├── task_spec.json
          ├── ground_truth/
          │   └── scripts/
          │       └── test.gd ◄── NEW
          └── starting_point/
              └── scripts/
                  └── test.gd ◄── COPIED

After Validation:
  pipeline/
  ├── data/...
  └── validation_report.json ◄── NEW
```

## Usage Patterns

### Pattern 1: Full Pipeline
```bash
# One command, start to finish
python run_pipeline.py --all
```

### Pattern 2: Staged Development
```bash
# Test each stage individually
python run_pipeline.py --stage download
[Review downloads]

python run_pipeline.py --stage clone
[Review clones]

python run_pipeline.py --stage discovery
[Review candidates]

# etc...
```

### Pattern 3: Subset Testing
```bash
# Test with 3 videos first
python run_pipeline.py --all --videos "vid1,vid2,vid3"

# Review quality
python scripts/utils.py --stats
cat validation_report.json

# If good, scale up
python run_pipeline.py --all
```

### Pattern 4: Iterative Refinement
```bash
# Generate initial tasks
python run_pipeline.py --all

# Review, find issues
cat validation_report.json

# Regenerate specific tasks
python run_pipeline.py --stage test_generation --tasks "task_05001,task_05002"

# Re-validate
python run_pipeline.py --stage validation --tasks "task_05001,task_05002"
```

## Next Steps

1. **Setup:** Follow `QUICKSTART.md`
2. **Test:** Run on 3-5 videos
3. **Review:** Check quality of generated tasks
4. **Scale:** Run on full dataset
5. **Deploy:** Export to main tasks directory
