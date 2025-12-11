"""
Definition file processor for Paper Scanner

Processes YAML definition files and executes sequential steps
"""

import argparse
import sys
import importlib
import inspect
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Tuple
import yaml
import json
from datetime import datetime
import time

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel

from paper_scanner.core.models import Paper
from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.halt import HaltException

# Initialize rich console for colored output
console = Console()


def _discover_steps() -> Dict[str, str]:
    """
    Dynamically discover available step modules from the steps folder

    Returns:
        Dictionary of step_name -> module_name
    """
    steps_dir = Path(__file__).parent.parent / "steps"
    available_steps = {}

    # Look for all .py files except __init__.py and those starting with _
    for module_file in steps_dir.glob("*.py"):
        if module_file.name.startswith("_") or module_file.name == "__init__.py":
            continue

        module_name = module_file.stem
        # Verify the module has an execute function
        try:
            module = importlib.import_module(f".{module_name}", package="paper_scanner.steps")
            if hasattr(module, "execute"):
                available_steps[module_name] = module_name
        except ImportError:
            pass

    return available_steps


class StepExecutor:
    """Executor for definition file steps"""

    # Discover steps on class load
    BUILTIN_STEPS = _discover_steps()

    @staticmethod
    def get_step(step_name: str) -> Callable:
        """
        Load a step module by name

        Args:
            step_name: Name of the step (e.g., "bibtex_import")

        Returns:
            Step execute function
        """

        if step_name not in StepExecutor.BUILTIN_STEPS:
            raise ValueError(f"Unknown step: {step_name}. Available: {list(StepExecutor.BUILTIN_STEPS.keys())}")

        module_name = StepExecutor.BUILTIN_STEPS[step_name]
        try:
            module = importlib.import_module(f".{module_name}", package="paper_scanner.steps")
            return module.execute
        except ImportError as e:
            raise ValueError(f"Failed to load step {step_name}: {e}")

    @staticmethod
    def parse_step_config(step_config: Dict[str, Any]) -> tuple[str, Dict[str, Any], Optional[str]]:
        """
        Parse Ansible-style step configuration

        Format 1:
            step: step_name
            description: "Optional step description"
            builtin.step_name:
              key: value

        Format 2 (task name as description):
            step: "Full task description here"
            builtin.step_name:
              key: value

        Args:
            step_config: Raw step configuration from YAML

        Returns:
            Tuple of (step_name, step_params, description)
        """

        step_value = step_config.get("step")
        if not step_value:
            raise ValueError("Step configuration missing 'step' key")

        # Check for explicit description
        description = step_config.get("description", "")

        # Find the builtin key to determine actual step name
        builtin_key = None
        for key in step_config.keys():
            if key.startswith("builtin."):
                builtin_key = key
                break

        if not builtin_key:
            raise ValueError(f"Step configuration missing 'builtin.<step>' key")

        # Extract step name from builtin key
        step_name = builtin_key.replace("builtin.", "")

        # If step_value contains spaces or is not a valid step name, use it as description
        if " " in step_value or step_value not in StepExecutor.BUILTIN_STEPS:
            # step_value is the task description
            if not description:
                description = step_value
        else:
            # step_value is the step name (old format)
            step_name = step_value

        # Get step params from builtin key
        step_params = step_config.get(builtin_key, {})

        # Also accept step-specific params at root level for convenience
        # (for backward compatibility)
        if not step_params:
            # Copy all keys except 'step', 'description' and builtin keys
            step_params = {
                k: v
                for k, v in step_config.items()
                if k not in ["step", "description"] and not k.startswith("builtin.")
            }

        return step_name, step_params, description

    @staticmethod
    def execute_step(
        step_config: Dict[str, Any],
        papers_db: PapersDatabase,
        verbose: bool = False,
        dry_run: bool = False,
        cache_dir: Optional[Path] = None,
        step_index: Optional[int] = None,
        project_name: str = "Unknown",
        project_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single step with Ansible-style output

        Args:
            step_config: Step configuration (must have 'step' key)
            papers_db: Current papers database (PapersDatabase instance)
            verbose: Enable verbose output
            dry_run: Don't actually execute
            cache_dir: Cache directory (for checkpoint steps)
            step_index: Step index in definition (for checkpoint steps)
            project_name: Project name (for checkpoint steps)
            project_config: Project configuration (for steps needing it)

        Returns:
            Step execution results
        """

        # Parse configuration
        step_name, step_params, description = StepExecutor.parse_step_config(step_config)

        # For checkpoint steps, add cache_dir and step_index to params
        if step_name == "checkpoint" and cache_dir is not None:
            step_params = dict(step_params)  # Make a copy
            step_params["cache_dir"] = str(cache_dir)
            step_params["step_index"] = step_index
            step_params["project_name"] = project_name

        # Get the step function
        step_func = StepExecutor.get_step(step_name)

        # Execute the step - check if it accepts project_config
        import inspect
        sig = inspect.signature(step_func)
        if "project_config" in sig.parameters:
            result = step_func(step_params, papers_db, verbose=verbose, dry_run=dry_run, project_config=project_config)
        else:
            result = step_func(step_params, papers_db, verbose=verbose, dry_run=dry_run)

        # Ensure step and description are in result
        result["step"] = step_name
        if description:
            result["description"] = description

        return result


def load_definition(filepath: Path) -> Dict[str, Any]:
    """Load and parse YAML definition file"""

    if not filepath.exists():
        raise FileNotFoundError(f"Definition file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        definition = yaml.safe_load(f)

    if not definition:
        raise ValueError("Definition file is empty")

    return definition


def validate_definition(definition: Dict[str, Any]) -> None:
    """Validate definition file structure"""

    if "steps" not in definition:
        raise ValueError("Definition file missing 'steps' key")

    steps = definition["steps"]
    if not isinstance(steps, list):
        raise ValueError("'steps' must be a list")

    if len(steps) == 0:
        raise ValueError("'steps' list is empty")

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Step {i} is not a dictionary")

        if "step" not in step:
            raise ValueError(f"Step {i} missing 'step' key")


def _find_latest_checkpoint(
    cache_dir: Path, project_name: str, steps: List[Dict[str, Any]]
) -> tuple[Optional[int], Optional[Path]]:
    """
    Find the latest checkpoint file in cache directory

    Scans checkpoints folder for existing checkpoint files and returns the index
    of the step to resume from (checkpoint_index + 1) and the checkpoint file path.

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

    # Generate expected checkpoint filenames and find the latest existing one
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
        # Resume from the step AFTER the checkpoint
        return latest_index + 1, latest_file

    return None, None


def _load_checkpoint(checkpoint_file: Path) -> List[Any]:
    """Load papers from checkpoint file"""
    from paper_scanner.steps.checkpoint import load_checkpoint

    papers, _ = load_checkpoint(checkpoint_file)
    return papers


def validate_definition_file(definition_file: Path, verbose: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate definition file structure and step configurations.
    
    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    definition_file = Path(definition_file)
    
    # Check file exists
    if not definition_file.exists():
        return False, [f"Definition file not found: {definition_file}"]
    
    try:
        # Load YAML
        with open(definition_file, "r", encoding="utf-8") as f:
            definition = yaml.safe_load(f)
        
        if not definition:
            return False, ["Definition file is empty"]
        
        # Check structure
        if "steps" not in definition:
            return False, ["Definition file missing 'steps' key"]
        
        steps = definition["steps"]
        if not isinstance(steps, list):
            return False, ["'steps' must be a list"]
        
        if len(steps) == 0:
            return False, ["'steps' list is empty"]
    
    except Exception as e:
        return False, [f"Error parsing YAML: {str(e)}"]
    
    # Validate each step
    for i, step_config in enumerate(steps):
        try:
            if not isinstance(step_config, dict):
                errors.append(f"Step {i}: Configuration is not a dictionary")
                continue
                
            if "step" not in step_config:
                errors.append(f"Step {i}: Missing 'step' key")
                continue
            
            # Parse step configuration
            step_name, step_params, description = StepExecutor.parse_step_config(step_config)
            
            # Check if step exists
            if step_name not in StepExecutor.BUILTIN_STEPS:
                errors.append(f"Step {i}: Unknown step '{step_name}'. Available: {list(StepExecutor.BUILTIN_STEPS.keys())}")
                continue
            
            # Get the step module and run validation
            step_module_name = StepExecutor.BUILTIN_STEPS[step_name]
            step_func_module = __import__(
                f"paper_scanner.steps.{step_module_name}",
                fromlist=["validate"]
            )
            
            if hasattr(step_func_module, "validate"):
                is_valid, validation_errors = step_func_module.validate(step_params)
                if not is_valid:
                    for error in validation_errors:
                        errors.append(f"Step {i} ({step_name}): {error}")
        
        except Exception as e:
            errors.append(f"Step {i}: {str(e)}")
    
    return len(errors) == 0, errors


def _validate_and_run_definition(
    definition_file: Path,
    verbose: bool = False,
    dry_run: bool = False,
    cache_dir: Optional[Path] = None,
    skip_checkpoint: bool = False,
    clear_checkpoint: bool = False,
    show_timings: bool = False,
) -> Dict[str, Any]:
    """
    Validate definition file, then process it.
    
    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        dry_run: Don't actually execute steps
        cache_dir: Optional cache directory
        skip_checkpoint: Skip loading from checkpoints
        clear_checkpoint: Clear all checkpoints before processing
        show_timings: Show timing information
        
    Returns:
        Execution results
    """
    if verbose:
        console.print(f"Validating definition file: [bold cyan]{definition_file}[/bold cyan]")
    
    # Validate the definition
    is_valid, errors = validate_definition_file(definition_file, verbose=verbose)
    
    if not is_valid:
        console.print(f"\n[red bold]Validation failed:[/red bold]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        sys.exit(1)
    
    if verbose:
        console.print(f"[green]✓ Definition file is valid[/green]\n")
    
    # If validation passed, proceed with execution
    return process_definition(
        definition_file,
        verbose=verbose,
        dry_run=dry_run,
        cache_dir=cache_dir,
        skip_checkpoint=skip_checkpoint,
        clear_checkpoint=clear_checkpoint,
        show_timings=show_timings,
    )


def process_definition(
    definition_file: Path,
    verbose: bool = False,
    dry_run: bool = False,
    cache_dir: Optional[Path] = None,
    skip_checkpoint: bool = False,
    clear_checkpoint: bool = False,
    show_timings: bool = False,
) -> Dict[str, Any]:
    """
    Process definition file and execute steps

    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        dry_run: Don't actually execute steps
        cache_dir: Optional cache directory (overrides env and definition file)
        skip_checkpoint: Skip loading from checkpoints (start fresh)
        clear_checkpoint: Clear all checkpoints before processing
        show_timings: Show timing information for each step

    Returns:
        Execution results
    """

    # Load and validate
    if verbose:
        console.print(f"Loading definition file: [bold cyan]{definition_file}[/bold cyan]\n")

    definition = load_definition(definition_file)
    validate_definition(definition)

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
        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]\n")

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

    # Get checkpoint options from definition file (can be overridden by CLI args)
    project_config = definition.get("project", {})
    checkpoint_config = project_config.get("checkpoints", {})

    # Determine checkpoint behavior
    # Priority: CLI args > definition file > default (use checkpoints)
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
                console.print(f"[yellow]Cleared checkpoints directory[/yellow]\n")

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
            # Skip this step - show as skipped in verbose mode
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
                verbose=verbose,
                dry_run=dry_run,
                cache_dir=cache_dir,
                step_index=i - 1,  # 0-based index for checkpoint naming
                project_name=project_name,
                project_config=definition.get("project"),
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
                # Step failed - add to errors and continue
                error_msg = step_result.get("error", "Unknown error")
                results["errors"].append(f"{step_name}: {error_msg}")
                if verbose:
                    console.print(f"[red]fatal[/red]: [{step_name}] {error_msg}")
                else:
                    console.print(f"[red]fatal[/red]: [{step_name}]")
            else:
                # Ansible-style result output
                if verbose:
                    console.print(f"[green]ok[/green]: [{step_name}]")
                else:
                    console.print(f"[green]ok[/green]: [{step_name}]")

        except HaltException as e:
            # Graceful halt - not an error
            halt_msg = f"Pipeline halted: {str(e)}"
            results["steps_executed"].append({"step": step_name, "status": "halted", "message": str(e)})

            # Track final papers statistics
            results["papers_total"] = papers_db.count(primary_only=False)
            results["papers_unique"] = papers_db.count(primary_only=True)
            results["papers_duplicates"] = papers_db.count(primary_only=False) - papers_db.count(primary_only=True)

            console.print(f"[yellow]halt[/yellow]: [{step_name}] => {str(e)}")

            # Stop processing remaining steps
            break

        except Exception as e:
            error_msg = f"Step {i} ({step_name}) failed: {str(e)}"
            results["errors"].append(error_msg)

            # Ansible-style error output
            console.print(f"[red bold]fatal[/red bold]: [{step_name}] => ERROR! {str(e)}")

            # Continue to next step on error
            continue

    # Calculate total duration
    total_duration = time.time() - overall_start_time
    results["total_duration_seconds"] = round(total_duration, 2)

    # Final summary (Ansible-style)
    if verbose:
        console.print(f"\n[bold cyan]{'=' * 70}[/bold cyan]")
        console.print(f"[bold yellow]PLAY RECAP[/bold yellow]")
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
            console.print(f"\n[red bold]Failed tasks:[/red bold]")
            for error in results["errors"]:
                console.print(f"  - [red]{error}[/red]")

        # Show timing epilog if enabled
        if show_timings and results["step_timings"]:
            console.print(f"\n[bold yellow]TIMINGS[/bold yellow]")
            for timing in results["step_timings"]:
                console.print(
                    f"  {timing['step']}: [cyan]{timing['duration_seconds']}s[/cyan] ({timing['duration_ms']:.0f}ms)"
                )
            console.print(f"  [bold yellow]Total[/bold yellow]: [cyan]{results['total_duration_seconds']}s[/cyan]")

    return results


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Process definition files and execute paper scanner steps"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ===== RUN COMMAND =====
    run_parser = subparsers.add_parser(
        "run",
        help="Run a definition file"
    )
    
    run_parser.add_argument(
        "definition_file",
        type=Path,
        help="Path to YAML definition file"
    )
    
    run_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually execute steps, just show what would happen"
    )
    
    run_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output results to JSON file"
    )
    
    run_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )
    
    run_parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Skip loading from checkpoints (start fresh from beginning)"
    )
    
    run_parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear all checkpoints before processing (creates new ones)"
    )
    
    run_parser.add_argument(
        "-t", "--timings",
        action="store_true",
        help="Show timing information for each step"
    )
    
    # ===== VALIDATE COMMAND =====
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a definition file"
    )
    
    validate_parser.add_argument(
        "definition_file",
        type=Path,
        help="Path to YAML definition file"
    )
    
    validate_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    # ===== CACHE COMMAND =====
    cache_parser = subparsers.add_parser(
        "cache",
        help="Manage cache operations"
    )
    
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache operations")
    
    clear_parser = cache_subparsers.add_parser(
        "clear",
        help="Clear cache contents"
    )
    
    clear_parser.add_argument(
        "target",
        choices=["checkpoints"],
        help="What to clear"
    )
    
    clear_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )
    
    clear_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Handle no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == "run":
            results = _validate_and_run_definition(
                args.definition_file,
                verbose=args.verbose,
                dry_run=args.dry_run,
                cache_dir=args.cache_dir,
                skip_checkpoint=args.no_checkpoint,
                clear_checkpoint=args.clear_checkpoint,
                show_timings=args.timings
            )
            
            # Output results
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, default=str)
                if args.verbose:
                    console.print(f"\n[green]Results saved to:[/green] [bold cyan]{args.output}[/bold cyan]")
            
            # Exit with appropriate code
            if results["errors"]:
                sys.exit(1)
            else:
                sys.exit(0)
        
        elif args.command == "validate":
            is_valid, errors = validate_definition_file(args.definition_file, verbose=args.verbose)
            
            if not is_valid:
                console.print(f"\n[red bold]Validation failed:[/red bold]")
                for error in errors:
                    console.print(f"  [red]✗[/red] {error}")
                sys.exit(1)
            else:
                console.print(f"[green]✓ Definition file is valid[/green]")
                if args.verbose:
                    console.print(f"File: [cyan]{args.definition_file}[/cyan]")
                sys.exit(0)
        
        elif args.command == "cache":
            if not args.cache_command:
                cache_parser.print_help()
                sys.exit(1)
            
            if args.cache_command == "clear":
                # Determine cache_dir
                cache_dir = args.cache_dir
                if cache_dir is None:
                    cache_dir = Path(os.getenv("CACHE_DIR", ""))
                    if not cache_dir or str(cache_dir) == ".":
                        cache_dir = None
                
                if cache_dir is None:
                    cache_dir = Path("~/.paper-scanner").expanduser()
                else:
                    cache_dir = cache_dir.expanduser()
                
                if args.target == "checkpoints":
                    checkpoints_dir = cache_dir / "checkpoints"
                    
                    if args.verbose:
                        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]")
                        console.print(f"Target: [yellow]checkpoints[/yellow]")
                    
                    if checkpoints_dir.exists():
                        shutil.rmtree(checkpoints_dir)
                        console.print(f"[green]✓ Cleared checkpoints[/green]: {checkpoints_dir}")
                    else:
                        console.print(f"[green]✓ No checkpoints to clear[/green] (directory is clean)")
                    
                    sys.exit(0)
    
    except Exception as e:
        console.print(f"[red bold]Error:[/red bold] {e}", style="red")
        sys.exit(1)
