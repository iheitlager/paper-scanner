"""
Definition file processor for Paper Scanner

Processes YAML definition files and executes sequential steps
"""

import argparse
import sys
import importlib
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
import yaml
import json
from datetime import datetime

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel

from paper_scanner.core.models import Paper

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
            step_params = {k: v for k, v in step_config.items() 
                          if k not in ["step", "description"] and not k.startswith("builtin.")}
        
        return step_name, step_params, description
    
    @staticmethod
    def execute_step(
        step_config: Dict[str, Any],
        papers_db: List[Paper],
        verbose: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a single step with Ansible-style output
        
        Args:
            step_config: Step configuration (must have 'step' key)
            papers_db: Current papers database
            verbose: Enable verbose output
            dry_run: Don't actually execute
        
        Returns:
            Step execution results
        """
        
        # Parse configuration
        step_name, step_params, description = StepExecutor.parse_step_config(step_config)
        
        # Get the step function
        step_func = StepExecutor.get_step(step_name)
        
        # Execute the step
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
    
    with open(filepath, 'r', encoding='utf-8') as f:
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


def process_definition(
    definition_file: Path,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Process definition file and execute steps
    
    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        dry_run: Don't actually execute steps
    
    Returns:
        Execution results
    """
    
    # Load and validate
    if verbose:
        console.print(f"Loading definition file: [bold cyan]{definition_file}[/bold cyan]\n")
    
    definition = load_definition(definition_file)
    validate_definition(definition)
    
    # Print project info if available
    if "project" in definition and verbose:
        project = definition["project"]
        project_panel = Panel(
            f"[yellow]{project.get('description', 'N/A')}[/yellow]",
            title=f"[bold blue]{project.get('name', 'Unknown')}[/bold blue]",
            border_style="cyan"
        )
        console.print(project_panel)
    
    # Initialize papers database
    papers_db: List[Paper] = []
    
    # Execute steps
    results = {
        "definition_file": str(definition_file),
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "steps_executed": [],
        "total_papers": 0,
        "errors": []
    }
    
    steps = definition.get("steps", [])
    
    for i, step_config in enumerate(steps, 1):
        step_name = step_config.get("step", "unknown")
        description = step_config.get("description", "")
        
        # Ansible-style output
        task_header = f"{step_name}"
        if description:
            task_header += f" | {description}"
        
        if verbose:
            console.print(f"\n[bold magenta]TASK[/bold magenta] [cyan]{task_header}[/cyan]")
            if dry_run:
                console.print("[bold yellow](DRY RUN - no changes will be made)[/bold yellow]")
        else:
            console.print(f"\n[bold magenta]TASK[/bold magenta] [cyan]{task_header}[/cyan]")
        
        try:
            step_result = StepExecutor.execute_step(
                step_config,
                papers_db,
                verbose=verbose,
                dry_run=dry_run
            )
            
            results["steps_executed"].append(step_result)
            results["total_papers"] = len(papers_db)
            
            # Ansible-style result output
            if verbose:
                console.print(f"[green]ok[/green]: [{step_name}] => {step_result.get('status', 'ok')}")
            else:
                console.print(f"[green]ok[/green]: [{step_name}]")
            
        except Exception as e:
            error_msg = f"Step {i} ({step_name}) failed: {str(e)}"
            results["errors"].append(error_msg)
            
            # Ansible-style error output
            console.print(f"[red bold]fatal[/red bold]: [{step_name}] => ERROR! {str(e)}")
            
            # Continue to next step on error
            continue
    
    # Final summary (Ansible-style)
    if verbose:
        console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        console.print(f"[bold yellow]PLAY RECAP[/bold yellow]")
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        
        ok_count = len(results['steps_executed'])
        error_count = len(results['errors'])
        changed_count = len([s for s in results['steps_executed'] if s.get('status') == 'changed'])
        
        summary_line = f"ok={ok_count}"
        if changed_count > 0:
            summary_line += f" changed={changed_count}"
        if error_count > 0:
            summary_line += f" failed={error_count}"
        
        console.print(f"Definition file: [green]{summary_line}[/green]")
        console.print(f"Total papers in database: [cyan]{results['total_papers']}[/cyan]")
        
        if results["errors"]:
            console.print(f"\n[red bold]Failed tasks:[/red bold]")
            for error in results["errors"]:
                console.print(f"  - [red]{error}[/red]")
    
    return results


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Process definition files and execute paper scanner steps"
    )
    
    parser.add_argument(
        "definition_file",
        type=Path,
        help="Path to YAML definition file"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually execute steps, just show what would happen"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output results to JSON file"
    )
    
    args = parser.parse_args()
    
    try:
        results = process_definition(
            args.definition_file,
            verbose=args.verbose,
            dry_run=args.dry_run
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
    
    except Exception as e:
        console.print(f"[red bold]Error:[/red bold] {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
