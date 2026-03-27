"""
Run task - Execute a definition file and process papers

This task loads a YAML definition file, validates it, and executes
a sequence of processing steps on the papers database.
"""

import inspect
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel

from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.halt import HaltException

console = Console(file=sys.stderr)


class StepExecutor:
    """Executor for definition file steps"""

    @staticmethod
    def parse_step_config(step_config: Dict[str, Any], builtin_steps: Dict[str, str]) -> tuple[str, Dict[str, Any], Optional[str]]:
        """
        Parse Ansible-style step configuration

        Args:
            step_config: Raw step configuration from YAML
            builtin_steps: Available builtin steps

        Returns:
            Tuple of (step_name, step_params, description)
        """
        step_value = step_config.get("step")
        if not step_value:
            raise ValueError("Step configuration missing 'step' key")

        description = step_config.get("description", "")

        # Find the builtin key to determine actual step name
        builtin_key = None
        for key in step_config.keys():
            if key.startswith("builtin."):
                builtin_key = key
                break

        if not builtin_key:
            raise ValueError("Step configuration missing 'builtin.<step>' key")

        # Extract step name from builtin key
        step_name = builtin_key.replace("builtin.", "")

        # If step_value contains spaces or is not a valid step name, use it as description
        if " " in step_value or step_value not in builtin_steps:
            if not description:
                description = step_value
        else:
            step_name = step_value

        # Get step params from builtin key
        step_params = step_config.get(builtin_key, {})

        # Also accept step-specific params at root level for convenience
        if not step_params:
            step_params = {
                k: v
                for k, v in step_config.items()
                if k not in ("step", "description") and not k.startswith("builtin.")
            }

        return step_name, step_params, description

    @staticmethod
    def execute_step(
        step_config: Dict[str, Any],
        papers_db: PapersDatabase,
        step_executor_func,
        verbose: bool = False,
        dry_run: bool = False,
        cache_dir: Optional[Path] = None,
        step_index: Optional[int] = None,
        project_name: str = "Unknown",
        project_config: Optional[Dict[str, Any]] = None,
        debug: bool = False,
        builtin_steps: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single step

        Args:
            step_config: Step configuration
            papers_db: Current papers database
            step_executor_func: Function to execute the step (can be callable with just step_name, or step_executor class)
            verbose: Enable verbose output
            dry_run: Don't actually execute
            cache_dir: Cache directory
            step_index: Step index in definition
            project_name: Project name
            project_config: Project configuration
            debug: Enable debug output
            builtin_steps: Available builtin steps

        Returns:
            Step execution results
        """
        if builtin_steps is None:
            builtin_steps = {}

        step_name, step_params, description = StepExecutor.parse_step_config(step_config, builtin_steps)

        # For checkpoint steps, add cache_dir and step_index to params
        if step_name == "checkpoint" and cache_dir is not None:
            step_params = dict(step_params)
            step_params["cache_dir"] = str(cache_dir)
            step_params["step_index"] = step_index
            step_params["project_name"] = project_name

        # Get the step instance
        # step_executor_func can be either:
        # 1. A callable that takes (step_name, general_config, db, cache_dir) -> step_instance
        # 2. A callable that takes just (step_name) -> step_instance
        sig = inspect.signature(step_executor_func)
        if len(sig.parameters) > 1:
            # Old-style: requires general_config, db, cache_dir
            step_instance = step_executor_func(step_name, project_config or {}, papers_db, cache_dir)
        else:
            # New-style: just takes step_name
            step_instance = step_executor_func(step_name)

        # Execute the step
        result = step_instance.execute(step_params, verbose=verbose, dry_run=dry_run, debug=debug)

        # Ensure step and description are in result
        result["step"] = step_name
        if description:
            result["description"] = description

        return result


def _find_latest_checkpoint(
    cache_dir: Path, project_name: str, steps: List[Dict[str, Any]]
) -> tuple[Optional[int], Optional[Path]]:
    """
    Find the latest checkpoint file in cache directory

    Args:
        cache_dir: Cache directory path
        project_name: Project name for generating checkpoint hash
        steps: List of step configurations

    Returns:
        Tuple of (resume_step_index, checkpoint_file) or (None, None) if no checkpoint
    """
    import hashlib

    checkpoints_dir = cache_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return None, None

    project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
    latest_index = None
    latest_file = None

    for i in range(len(steps)):
        checkpoint_name = f"checkpoint_{project_hash}_step_{i:03d}.json"
        checkpoint_file = checkpoints_dir / checkpoint_name

        if checkpoint_file.exists():
            latest_index = i
            latest_file = checkpoint_file

    if latest_index is not None:
        return latest_index + 1, latest_file

    return None, None


def _load_checkpoint(checkpoint_file: Path) -> List[Any]:
    """Load papers from checkpoint file"""
    from paper_scanner.steps.checkpoint import load_checkpoint

    papers, _ = load_checkpoint(checkpoint_file)
    return papers


def execute_run(
    definition_file: Path,
    verbose: bool = False,
    dry_run: bool = False,
    cache_dir: Optional[Path] = None,
    skip_checkpoint: bool = False,
    clear_checkpoint: bool = False,
    show_timings: bool = False,
    debug: bool = False,
    output_file: Optional[Path] = None,
    get_step_func=None,
    builtin_steps: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute a definition file

    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        dry_run: Don't actually execute steps
        cache_dir: Optional cache directory
        skip_checkpoint: Skip loading from checkpoints
        clear_checkpoint: Clear all checkpoints before processing
        show_timings: Show timing information
        debug: Enable debug output for detailed step information
        output_file: Optional output file for results
        get_step_func: Function to get step by name
        builtin_steps: Available builtin steps

    Returns:
        Execution results
    """

    # Load and validate
    if verbose:
        console.print(f"Loading definition file: [bold cyan]{definition_file}[/bold cyan]\n")

    if not definition_file.exists():
        raise FileNotFoundError(f"Definition file not found: {definition_file}")

    with open(definition_file, "r", encoding="utf-8") as f:
        definition = yaml.safe_load(f)

    if not definition:
        raise ValueError("Definition file is empty")

    # Determine cache_dir with priority:
    # 1. CLI argument (cache_dir parameter)
    # 2. Environment variable CACHE_DIR
    # 3. Definition file project.cache_dir
    # 4. Default: ~/.paper-scanner
    if cache_dir is None:
        cache_dir = Path(os.getenv("CACHE_DIR", ""))
        if not cache_dir or str(cache_dir) == ".":
            cache_dir = None

    if cache_dir is None and "project" in definition:
        project = definition["project"]
        if "cache_dir" in project:
            cache_dir = Path(project["cache_dir"])

    if cache_dir is None:
        cache_dir = Path("~/.paper-scanner").expanduser()
    else:
        cache_dir = cache_dir.expanduser()

    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]")

    # Print project info if available
    if "project" in definition and verbose:
        project = definition["project"]
        description = project.get("description", "N/A")
        project_info = f"[yellow]{description}[/yellow]\n[dim]Cache: {cache_dir}[/dim]"
        project_panel = Panel(
            project_info, title=f"[bold blue]{project.get('name', 'Unknown')}[/bold blue]", border_style="cyan"
        )
        console.print(project_panel)

    # PRERUN: Check for existing checkpoints
    steps = definition.get("steps", [])
    project_name = definition.get("project", {}).get("name", "Unknown")
    resume_from_step = None
    checkpoint_file = None

    # Get checkpoint options from definition file
    project_config = definition.get("project", {})
    checkpoint_config = project_config.get("checkpoints", {})

    # Determine checkpoint behavior
    use_checkpoints = True
    if skip_checkpoint:
        use_checkpoints = False
    elif isinstance(checkpoint_config, str):
        if checkpoint_config.lower() == "skip":
            use_checkpoints = False
    elif isinstance(checkpoint_config, dict):
        if checkpoint_config.get("mode") == "skip":
            use_checkpoints = False

    # Handle clear checkpoints
    should_clear_checkpoints = (
        clear_checkpoint
        or (isinstance(checkpoint_config, str) and checkpoint_config.lower() == "clear")
        or (isinstance(checkpoint_config, dict) and checkpoint_config.get("mode") == "clear")
    )

    if should_clear_checkpoints and not skip_checkpoint:
        checkpoints_dir = cache_dir / "checkpoints"
        if checkpoints_dir.exists():
            shutil.rmtree(checkpoints_dir)
            if verbose:
                console.print("[yellow]Cleared checkpoints directory[/yellow]\n")

    if verbose:
        if use_checkpoints:
            console.print("\n[bold yellow]PRERUN[/bold yellow]: Scanning for checkpoints...\n")
        else:
            console.print("\n[bold yellow]PRERUN[/bold yellow]: Checkpoint loading disabled\n")

    # Only search for checkpoints if enabled
    if use_checkpoints:
        resume_from_step, checkpoint_file = _find_latest_checkpoint(cache_dir, project_name, steps)

        if checkpoint_file:
            if verbose:
                console.print(f"[green]Found checkpoint[/green]: {checkpoint_file.name}")
                console.print(f"[dim]Resuming from step {resume_from_step}[/dim]\n")

    # Initialize papers database
    papers_db = PapersDatabase()

    # Load checkpoint if found
    if checkpoint_file and use_checkpoints:
        checkpoint_papers = _load_checkpoint(checkpoint_file)
        papers_db.from_list(checkpoint_papers)
        if verbose:
            console.print(f"[green]Loaded {len(checkpoint_papers)} papers from checkpoint[/green]\n")

    # Start overall timing
    overall_start_time = time.time()

    # Execute steps
    results = {
        "definition_file": str(definition_file),
        "cache_dir": str(cache_dir),
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "steps_executed": [],
        "papers_total": 0,
        "papers_unique": 0,
        "papers_duplicates": 0,
        "errors": [],
        "checkpoint": str(checkpoint_file) if checkpoint_file else None,
        "resumed_from_step": resume_from_step,
        "step_timings": [] if show_timings else None,
        "total_duration_seconds": 0,
    }

    for i, step_config in enumerate(steps, 1):
        step_name = step_config.get("step", "unknown")
        description = step_config.get("description", "")

        # Check if we should skip this step (it's before the checkpoint resume point)
        should_skip = resume_from_step is not None and i < resume_from_step

        # Ansible-style output
        task_header = f"{step_name}"
        if description:
            task_header += f" | {description}"

        if should_skip:
            if verbose:
                console.print(f"\n[bold magenta]TASK[/bold magenta] [cyan]{task_header}[/cyan]")
                console.print(f"[dim]skipped[/dim]: [{step_name}] (checkpoint resume)")
            continue

        if verbose:
            console.print(f"\n[bold magenta]TASK[/bold magenta] [cyan]{task_header}[/cyan]")
            if dry_run:
                console.print("[bold yellow](DRY RUN - no changes will be made)[/bold yellow]")
        else:
            console.print(f"\n[bold magenta]TASK[/bold magenta] [cyan]{task_header}[/cyan]")

        # Start step timing
        step_start_time = time.time() if show_timings else None

        try:
            step_result = StepExecutor.execute_step(
                step_config,
                papers_db,
                get_step_func,
                verbose=verbose,
                dry_run=dry_run,
                cache_dir=cache_dir,
                step_index=i - 1,
                project_name=project_name,
                project_config=definition.get("project"),
                debug=debug,
                builtin_steps=builtin_steps,
            )

            # Record step timing
            if show_timings:
                step_duration = time.time() - step_start_time
                results["step_timings"].append(
                    {
                        "step": step_name,
                        "duration_seconds": round(step_duration, 2),
                        "duration_ms": round(step_duration * 1000, 0),
                    }
                )

            results["steps_executed"].append(step_result)

            # Track papers statistics
            results["papers_total"] = papers_db.count(primary_only=False)
            results["papers_unique"] = papers_db.count(primary_only=True)
            results["papers_duplicates"] = papers_db.count(primary_only=False) - papers_db.count(primary_only=True)

            # Check if step failed
            if step_result.get("status") == "error":
                error_msg = step_result.get("error", "Unknown error")
                results["errors"].append(f"{step_name}: {error_msg}")
                if verbose:
                    console.print(f"[red]fatal[/red]: [{step_name}] {error_msg}")
                else:
                    console.print(f"[red]fatal[/red]: [{step_name}]")
            else:
                console.print(f"[green]ok[/green]: [{step_name}]")

        except HaltException as e:
            f"Pipeline halted: {str(e)}"
            results["steps_executed"].append({"step": step_name, "status": "halted", "message": str(e)})

            # Track final papers statistics
            results["papers_total"] = papers_db.count(primary_only=False)
            results["papers_unique"] = papers_db.count(primary_only=True)
            results["papers_duplicates"] = papers_db.count(primary_only=False) - papers_db.count(primary_only=True)

            console.print(f"[yellow]halt[/yellow]: [{step_name}] => {str(e)}")
            break

        except Exception as e:
            error_msg = f"Step {i} ({step_name}) failed: {str(e)}"
            results["errors"].append(error_msg)
            console.print(f"[red bold]fatal[/red bold]: [{step_name}] => ERROR! {str(e)}")
            continue

    # Calculate total duration
    total_duration = time.time() - overall_start_time
    results["total_duration_seconds"] = round(total_duration, 2)

    # Final summary (Ansible-style)
    if verbose:
        console.print(f"\n[bold cyan]{'=' * 70}[/bold cyan]")
        console.print("[bold yellow]PLAY RECAP[/bold yellow]")
        console.print(f"[bold cyan]{'=' * 70}[/bold cyan]")

        ok_count = len(results["steps_executed"])
        error_count = len(results["errors"])
        changed_count = len([s for s in results["steps_executed"] if s.get("status") == "changed"])

        summary_line = f"ok={ok_count}"
        if changed_count > 0:
            summary_line += f" changed={changed_count}"
        if error_count > 0:
            summary_line += f" failed={error_count}"

        console.print(f"Definition file: [green]{summary_line}[/green]")
        console.print(f"Total papers in database: [cyan]{results['papers_total']}[/cyan]")
        console.print(f"Unique papers: [cyan]{results['papers_unique']}[/cyan]")
        console.print(f"Duplicate papers: [cyan]{results['papers_duplicates']}[/cyan]")

        if results["errors"]:
            console.print("\n[red bold]Failed tasks:[/red bold]")
            for error in results["errors"]:
                console.print(f"  - [red]{error}[/red]")

        # Show timing epilog if enabled
        if show_timings and results["step_timings"]:
            console.print("\n[bold yellow]TIMINGS[/bold yellow]")
            for timing in results["step_timings"]:
                console.print(
                    f"  {timing['step']}: [cyan]{timing['duration_seconds']}s[/cyan] ({timing['duration_ms']:.0f}ms)"
                )
            console.print(f"  [bold yellow]Total[/bold yellow]: [cyan]{results['total_duration_seconds']}s[/cyan]")

    # Output results if requested
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        if verbose:
            console.print(f"\n[green]Results saved to:[/green] [bold cyan]{output_file}[/bold cyan]")

    return results
