# Pipeline Documentation Index

Quick reference guide to all pipeline documentation.

## 🚀 Getting Started

**New to the pipeline? Start here:**

1. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
   - Setup environment
   - Test on small subset
   - Run full pipeline

2. **[verify_structure.py](verify_structure.py)** - Verify installation
   ```bash
   python3 pipeline/verify_structure.py
   ```

## 📖 Documentation

### Core Documentation

- **[README.md](README.md)** - Complete reference documentation
  - Overview and architecture
  - All pipeline stages explained
  - Usage examples
  - Troubleshooting guide
  - Cost estimation

- **[WORKFLOW.md](WORKFLOW.md)** - Visual workflow guide
  - Pipeline stage diagrams
  - Data flow examples
  - Control flow patterns
  - State machine diagrams

- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical details
  - Architecture decisions
  - Files created (19 files, ~2,300 lines)
  - Cost & performance analysis
  - Success metrics

### Quick Reference

| Document | Purpose | Read Time |
|----------|---------|-----------|
| QUICKSTART.md | Get started fast | 5 min |
| README.md | Full reference | 15 min |
| WORKFLOW.md | Visual guide | 10 min |
| IMPLEMENTATION_SUMMARY.md | Technical deep-dive | 20 min |

## 🛠️ Scripts Reference

### Pipeline Stages

| Script | Stage | Purpose | LLM Cost |
|--------|-------|---------|----------|
| `01_download_transcripts.py` | Download | Get YouTube transcripts | $0 |
| `02_clone_repos.py` | Clone | Clone GitHub repositories | $0 |
| `03_analyze_commits.py` | Analyze | Extract commit history | $0 |
| `04_discover_tasks.py` | Discovery | Match transcripts to commits | $0.30/video |
| `05_extract_task_from_commit.py` | Extraction | Extract Git before/after states | $0 |
| `06_generate_tests.py` | Test Gen | Generate validation tests | $0.10/task |
| `07_validate_tasks.py` | Validation | Run Godot tests | $0 |

### Utilities

- **`utils.py`** - Core utilities (LLM, Git, Godot, Metadata)
- **`run_pipeline.py`** - Pipeline orchestrator
- **`verify_structure.py`** - Installation verification

### Example Files

- **`example_repo_list.json`** - Template for repository list
- **`example_video_list.json`** - Template for video list

## 📊 Configuration

- **`config.yaml`** - Main configuration file
  - LLM settings (model, API key)
  - Pipeline settings (workers, retries)
  - Godot settings (executable path)
  - Reference tasks for test generation

- **`requirements.txt`** - Python dependencies
  ```bash
  pip install -r requirements.txt
  ```

## 🎯 Common Tasks

### First-Time Setup
```bash
# 1. Install dependencies
pip install -r pipeline/requirements.txt

# 2. Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Verify setup
python3 pipeline/verify_structure.py

# 4. See quick start guide
cat pipeline/QUICKSTART.md
```

### Running the Pipeline

**Full pipeline:**
```bash
python run_pipeline.py --all
```

**Specific stage:**
```bash
python run_pipeline.py --stage discovery
```

**Specific items:**
```bash
python run_pipeline.py --stage extraction --videos "vid1,vid2"
```

**Resume after interruption:**
```bash
python run_pipeline.py --all --resume
```

**Retry failures:**
```bash
python run_pipeline.py --stage discovery --retry-failed
```

### Monitoring & Debugging

**View statistics:**
```bash
python scripts/utils.py --stats
```

**Check validation results:**
```bash
cat validation_report.json | jq '.stats'
```

**Check metadata for specific item:**
```bash
cat data/videos/VIDEO_ID/metadata.json | jq '.stages'
cat data/tasks/TASK_ID/metadata.json
```

**Dry run (preview):**
```bash
python run_pipeline.py --stage validation --dry-run
```

## 📁 Directory Structure

```
pipeline/
├── scripts/              # Pipeline stage scripts
│   ├── utils.py         # Shared utilities
│   ├── 01_download_transcripts.py
│   ├── 02_clone_repos.py
│   ├── 03_analyze_commits.py
│   ├── 04_discover_tasks.py
│   ├── 05_extract_task_from_commit.py
│   ├── 06_generate_tests.py
│   └── 07_validate_tasks.py
├── data/                # Pipeline data (created at runtime)
│   ├── videos/          # YouTube transcripts
│   ├── repos/           # Cloned repositories
│   └── tasks/           # Generated tasks
├── config.yaml          # Configuration
├── requirements.txt     # Dependencies
├── run_pipeline.py      # Orchestrator
├── verify_structure.py  # Setup verification
├── README.md            # Full documentation
├── QUICKSTART.md        # Quick start guide
├── WORKFLOW.md          # Visual workflow guide
├── IMPLEMENTATION_SUMMARY.md  # Technical details
├── INDEX.md             # This file
├── example_repo_list.json
├── example_video_list.json
└── .gitignore
```

## 🔍 Troubleshooting

### Common Issues

**"No module named 'anthropic'"**
```bash
pip install -r requirements.txt
```

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

**"godot: command not found"**
Edit `config.yaml`:
```yaml
godot:
  executable: /full/path/to/godot
```

**Pipeline interrupted**
```bash
python run_pipeline.py --all --resume
```

**Specific stage failed**
```bash
# Check errors
cat data/videos/*/metadata.json | jq 'select(.stages.discovery == "failed")'

# Retry failed items
python run_pipeline.py --stage discovery --retry-failed
```

### Getting Help

1. Check [README.md](README.md) troubleshooting section
2. Review error messages in metadata.json files
3. Run with specific items to debug:
   ```bash
   python scripts/04_discover_tasks.py --videos "problematic_video_id"
   ```

## 📈 Cost & Performance

### Expected Costs (100 videos → 300 tasks)

| Stage | Time | Cost | Notes |
|-------|------|------|-------|
| Discovery | 30 min | $30 | LLM matching |
| Test Generation | 1 hour | $30 | LLM test creation |
| Other Stages | 30 min | $0 | Git/Godot operations |
| **Total** | **~2 hours** | **~$60** | Fully automated |

### Optimization Tips

1. **Use Haiku for discovery:** Edit config.yaml
   ```yaml
   llm:
     model: claude-haiku-4.5  # Cheaper, faster
   ```

2. **Batch processing:** Process 10-20 videos at a time

3. **Parallel workers:** Increase for faster processing
   ```yaml
   processing:
     max_workers: 30
   ```

## 🎓 Learning Path

### For First-Time Users
1. Read [QUICKSTART.md](QUICKSTART.md) (5 min)
2. Run verification: `python3 verify_structure.py`
3. Test on 3 videos
4. Read [README.md](README.md) sections as needed

### For Developers
1. Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
2. Review [WORKFLOW.md](WORKFLOW.md) for data flow
3. Study `scripts/utils.py` for core utilities
4. Examine individual stage scripts

### For System Integrators
1. Read [README.md](README.md) architecture section
2. Review `config.yaml` for customization
3. Study `run_pipeline.py` for orchestration
4. Check metadata structure in [WORKFLOW.md](WORKFLOW.md)

## 📝 File Checklist

Before running the pipeline, ensure these files exist:

**Required:**
- [ ] `config.yaml` - Configuration
- [ ] `requirements.txt` - Dependencies installed
- [ ] `scripts/utils.py` - Core utilities
- [ ] All 7 stage scripts (01-07)
- [ ] `run_pipeline.py` - Orchestrator

**Data (created at runtime):**
- [ ] `data/videos/` directory
- [ ] `data/repos/` directory
- [ ] `data/tasks/` directory

**Input data (you provide):**
- [ ] Repository list JSON
- [ ] Video IDs list

**Verify with:**
```bash
python3 pipeline/verify_structure.py
```

## 🔄 Version History

- **v1.0** - Initial implementation (Feb 2026)
  - Git-based task extraction
  - LLM-powered discovery & test generation
  - File-based state management
  - 7-stage pipeline with orchestration

## 📄 License

See main repository LICENSE file.

---

**Quick Links:**
- [QUICKSTART.md](QUICKSTART.md) - Get started now
- [README.md](README.md) - Full documentation
- [WORKFLOW.md](WORKFLOW.md) - Visual guide
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details
