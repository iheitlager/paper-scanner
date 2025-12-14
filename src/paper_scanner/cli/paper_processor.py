"""
Definition file processor for Paper Scanner

Processes YAML definition files and executes sequential steps
"""

import argparse
import sys
import importlib
import signal
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from rich.console import Console

from paper_scanner import __version__
from paper_scanner.cli.tasks import execute_run, execute_validate, execute_cache_clear, execute_cache_info

# Handle broken pipe gracefully (when piping to head, wc, etc.)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Initialize rich console for colored output
console = Console(file=sys.stderr)


def _discover_steps() -> Dict[str, str]:
    """
    Dynamically discover available step modules from the steps folder

    Returns:
        Dictionary of step_name -> module_name
    
    Note: This only checks for .py files without importing them.
    Import errors will be caught when get_step() actually tries to load a module.
    """
    steps_dir = Path(__file__).parent.parent / "steps"
    available_steps = {}

    # Look for all .py files except __init__.py and those starting with _
    # Don't import modules here - just enumerate files for fast discovery
    for module_file in steps_dir.glob("*.py"):
        if module_file.name.startswith("_") or module_file.name == "__init__.py":
            continue

        module_name = module_file.stem
        # Add without verifying - verification happens at load time in get_step()
        available_steps[module_name] = module_name

    return available_steps


class _StepExecutorMeta(type):
    """Metaclass for lazy loading BUILTIN_STEPS on first access"""
    
    _cache: Optional[Dict[str, str]] = None
    
    @property
    def BUILTIN_STEPS(cls) -> Dict[str, str]:
        """Lazy load steps on first access"""
        if cls._cache is None:
            cls._cache = _discover_steps()
        return cls._cache


class StepExecutor(metaclass=_StepExecutorMeta):
    """Executor for definition file steps"""

    @staticmethod
    def get_step(step_name: str) -> Callable:
        """
        Load a step module by name

        Args:
            step_name: Name of the step (e.g., "bibtex_import")

        Returns:
            Step execute function
        """
        builtin_steps = StepExecutor.BUILTIN_STEPS

        if step_name not in builtin_steps:
            raise ValueError(f"Unknown step: {step_name}. Available: {list(builtin_steps.keys())}")

        module_name = builtin_steps[step_name]
        try:
            module = importlib.import_module(f".{module_name}", package="paper_scanner.steps")
            return module.execute
        except ImportError as e:
            raise ValueError(f"Failed to load step {step_name}: {e}")

    @staticmethod
    def parse_step_config(step_config: Dict[str, Any]) -> tuple[str, Dict[str, Any], Optional[str]]:
        """
        Parse Ansible-style step configuration

        Args:
            step_config: Raw step configuration from YAML

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
            raise ValueError(f"Step configuration missing 'builtin.<step>' key")

        # Extract step name from builtin key
        step_name = builtin_key.replace("builtin.", "")

        # If step_value contains spaces or is not a valid step name, use it as description
        if " " in step_value or step_value not in StepExecutor.BUILTIN_STEPS:
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
                if k not in ["step", "description"] and not k.startswith("builtin.")
            }

        return step_name, step_params, description


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Process definition files and execute paper scanner steps"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
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
    
    run_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output for detailed step information"
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
    
    info_parser = cache_subparsers.add_parser(
        "info",
        help="Show cache information"
    )
    
    info_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )
    
    info_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
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
            builtin_steps = StepExecutor.BUILTIN_STEPS
            
            results = execute_run(
                args.definition_file,
                verbose=args.verbose,
                dry_run=args.dry_run,
                cache_dir=args.cache_dir,
                skip_checkpoint=args.no_checkpoint,
                clear_checkpoint=args.clear_checkpoint,
                show_timings=args.timings,
                debug=args.debug,
                output_file=args.output,
                get_step_func=StepExecutor.get_step,
                builtin_steps=builtin_steps,
            )
            
            # Exit with appropriate code
            if results["errors"]:
                sys.exit(1)
            else:
                sys.exit(0)
        
        elif args.command == "validate":
            builtin_steps = StepExecutor.BUILTIN_STEPS
            
            exit_code = execute_validate(
                args.definition_file,
                verbose=args.verbose,
                builtin_steps=builtin_steps,
            )
            sys.exit(exit_code)
        
        elif args.command == "cache":
            if not args.cache_command:
                cache_parser.print_help()
                sys.exit(1)
            
            if args.cache_command == "info":
                exit_code = execute_cache_info(
                    cache_dir=args.cache_dir,
                    verbose=args.verbose,
                )
                sys.exit(exit_code)
            
            elif args.cache_command == "clear":
                exit_code = execute_cache_clear(
                    args.target,
                    cache_dir=args.cache_dir,
                    verbose=args.verbose,
                )
                sys.exit(exit_code)
    
    except Exception as e:
        console.print(f"[red bold]Error:[/red bold] {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
