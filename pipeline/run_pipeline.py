"""Pipeline orchestrator for GameDevBench task generation."""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from scripts.utils import Config, MetadataManager


class PipelineOrchestrator:
    """Orchestrate the pipeline execution."""

    STAGES = [
        "download",
        "clone",
        "analyze_commits",
        "discovery",
        "extraction",
        "test_generation",
        "validation"
    ]

    def __init__(self, config_path: str = "pipeline/config.yaml"):
        self.config = Config(config_path)
        self.data_dir = Path(self.config.get('sources.videos')).parent

    def get_items_for_stage(self, stage: str, filter_status: str = None,
                           item_ids: list = None) -> list:
        """Get items ready for a specific stage."""

        # Determine base directory based on stage
        if stage in ["download", "discovery"]:
            base_dir = self.data_dir / "videos"
        elif stage in ["clone", "analyze_commits"]:
            base_dir = self.data_dir / "repos"
        elif stage in ["extraction", "test_generation", "validation"]:
            base_dir = self.data_dir / "tasks"
        else:
            raise ValueError(f"Unknown stage: {stage}")

        if not base_dir.exists():
            base_dir.mkdir(parents=True, exist_ok=True)
            return []

        items = []
        for item_dir in base_dir.iterdir():
            if not item_dir.is_dir():
                continue

            # Filter by ID if specified
            if item_ids and item_dir.name not in item_ids:
                continue

            # Check metadata status
            stage_status = MetadataManager.get_stage_status(item_dir, stage)

            # Filter by status
            if filter_status is None:
                items.append(item_dir)
            elif stage_status == filter_status:
                items.append(item_dir)

        return items

    def run_stage(self, stage: str, items: list, dry_run: bool = False, **kwargs):
        """Run a pipeline stage on specified items."""

        print(f"\n{'='*60}")
        print(f"Stage: {stage.upper()}")
        print(f"Items: {len(items)}")
        print(f"{'='*60}\n")

        if dry_run:
            print("DRY RUN - Would process:")
            for item in items:
                print(f"  - {item.name}")
            return

        if not items:
            print("No items to process.")
            return

        # Import and run the appropriate script
        try:
            if stage == "download":
                from scripts import download_transcripts
                # Assume this script exists and has a main function
                print("⚠️  download_transcripts script needs to be adapted")
                print("   Please ensure it accepts video IDs as arguments")

            elif stage == "clone":
                from scripts import clone_repos
                # This would need a repo list
                print("⚠️  Please provide --repo-list argument for cloning")

            elif stage == "analyze_commits":
                import subprocess
                result = subprocess.run([
                    sys.executable,
                    "pipeline/scripts/03_analyze_commits.py",
                    "--repos"] + [item.name for item in items],
                    check=True
                )

            elif stage == "discovery":
                import subprocess
                result = subprocess.run([
                    sys.executable,
                    "pipeline/scripts/04_discover_tasks.py",
                    "--videos"] + [item.name for item in items],
                    check=True
                )

            elif stage == "extraction":
                import subprocess
                video_ids = set()
                for item in items:
                    spec_file = item / "task_spec.json"
                    if spec_file.exists():
                        spec = json.loads(spec_file.read_text())
                        video_ids.add(spec["video_id"])

                if video_ids:
                    result = subprocess.run([
                        sys.executable,
                        "pipeline/scripts/05_extract_task_from_commit.py",
                        "--videos"] + list(video_ids),
                        check=True
                    )

            elif stage == "test_generation":
                import subprocess
                result = subprocess.run([
                    sys.executable,
                    "pipeline/scripts/06_generate_tests.py",
                    "--tasks"] + [item.name for item in items],
                    check=True
                )

            elif stage == "validation":
                import subprocess
                result = subprocess.run([
                    sys.executable,
                    "pipeline/scripts/07_validate_tasks.py",
                    "--tasks"] + [item.name for item in items],
                    check=True
                )

        except Exception as e:
            print(f"\n❌ Error running stage {stage}: {e}")
            sys.exit(1)

    def run_all_stages(self, dry_run: bool = False, resume: bool = False):
        """Run all pipeline stages in sequence."""

        print("\n" + "="*60)
        print("RUNNING FULL PIPELINE")
        print("="*60 + "\n")

        for stage in self.STAGES:
            # Determine filter status
            filter_status = "pending" if resume else None

            # Get items for this stage
            items = self.get_items_for_stage(stage, filter_status)

            if not items and stage not in ["download", "clone"]:
                print(f"⏭️  Skipping {stage}: no items to process\n")
                continue

            # Run stage
            self.run_stage(stage, items, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="GameDevBench Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run specific stage on all items
  python run_pipeline.py --stage download

  # Run specific stage on specific items
  python run_pipeline.py --stage extraction --videos "vid1,vid2"

  # Retry failed items
  python run_pipeline.py --stage discovery --retry-failed

  # Resume pipeline (skip completed stages)
  python run_pipeline.py --all --resume

  # Dry run to preview
  python run_pipeline.py --stage validation --dry-run
        """
    )

    # Stage selection
    parser.add_argument("--stage",
                       choices=["download", "clone", "analyze_commits",
                               "discovery", "extraction", "test_generation",
                               "validation", "all"],
                       help="Pipeline stage to run")

    # Item filtering
    parser.add_argument("--videos",
                       help="Comma-separated video IDs")
    parser.add_argument("--repos",
                       help="Comma-separated repo names")
    parser.add_argument("--tasks",
                       help="Comma-separated task IDs")

    # Execution options
    parser.add_argument("--retry-failed", action="store_true",
                       help="Retry only failed items")
    parser.add_argument("--resume", action="store_true",
                       help="Skip completed stages")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be processed")

    # Configuration
    parser.add_argument("--config", default="pipeline/config.yaml",
                       help="Config file path")
    parser.add_argument("--repo-list",
                       help="JSON file with repository list (for clone stage)")

    # Utility
    parser.add_argument("--all", action="store_true",
                       help="Run all stages")

    args = parser.parse_args()

    # Validate arguments
    if not args.stage and not args.all:
        parser.error("Must specify --stage or --all")

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(args.config)

    # Run full pipeline
    if args.all or args.stage == "all":
        orchestrator.run_all_stages(dry_run=args.dry_run, resume=args.resume)
        return

    # Determine filter status
    if args.retry_failed:
        filter_status = "failed"
    elif args.resume:
        filter_status = "pending"
    else:
        filter_status = None

    # Parse item IDs
    item_ids = None
    if args.videos:
        item_ids = args.videos.split(",")
    elif args.repos:
        item_ids = args.repos.split(",")
    elif args.tasks:
        item_ids = args.tasks.split(",")

    # Get items to process
    items = orchestrator.get_items_for_stage(args.stage, filter_status, item_ids)

    # Run stage
    orchestrator.run_stage(args.stage, items, dry_run=args.dry_run,
                          repo_list=args.repo_list)


if __name__ == "__main__":
    main()
