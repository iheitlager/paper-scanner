"""
Definition file processor for Paper Scanner

Processes YAML definition files and executes sequential steps
"""

import argparse
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Type

from dotenv import load_dotenv
from rich.console import Console

from paper_scanner import __version__
from paper_scanner.cli import STEP_REGISTRY_PATHS
from paper_scanner.cli.tasks import (
    execute_cache_clear,
    execute_cache_info,
    execute_cache_load,
    execute_db_stats,
    execute_db_clear,
    execute_info_steps,
    execute_repl,
    execute_run,
    execute_validate,
)
from paper_scanner.steps.base import BaseStep

# Load environment variables from .env file
load_dotenv()
# Handle broken pipe gracefully (when piping to head, wc, etc.)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Initialize rich console for colored output
console = Console(file=sys.stderr)


def _lazy_load_step(module_path: str, class_name: str) -> Type[BaseStep]:
    """
    Lazy load a step class from a module path.

    Args:
        module_path: Full module path (e.g., "paper_scanner.steps.echo")
        class_name: Class name to import

    Returns:
        The step class
    """
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LazyStepRegistry(dict):
    """Dictionary that lazy-loads step classes on access"""

    def __init__(self, paths: Dict[str, str]):
        """
        Initialize registry with module paths.

        Args:
            paths: Dict mapping step_name -> "module_path:ClassName"
        """
        self._paths = paths
        self._loaded = {}
        # Initialize dict with keys from paths (but don't load values yet)
        super().__init__({key: None for key in paths.keys()})

    def __getitem__(self, key: str) -> Type[BaseStep]:
        """Get a step class, lazy-loading if necessary"""
        if key not in self._paths:
            raise KeyError(f"Unknown step: {key}")

        # Return cached version if already loaded
        if key in self._loaded:
            return self._loaded[key]

        # Load and cache the step class
        path_str = self._paths[key]
        module_path, class_name = path_str.split(":")
        step_class = _lazy_load_step(module_path, class_name)
        self._loaded[key] = step_class
        # Update the dict value too
        super().__setitem__(key, step_class)
        return step_class

    def get(self, key: str, default=None):
        """Get with default value, lazy-loading if necessary"""
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        """Return items, lazy-loading all values first"""
        for key in self._paths.keys():
            yield key, self[key]

    def values(self):
        """Return values, lazy-loading all values first"""
        for key in self._paths.keys():
            yield self[key]


def _discover_steps() -> LazyStepRegistry:
    """
    Return a lazy-loading step registry.

    Steps are only imported when actually accessed, not at startup.
    This significantly speeds up CLI commands that don't use all steps.

    Returns:
        LazyStepRegistry that loads steps on demand
    """
    return LazyStepRegistry(STEP_REGISTRY_PATHS)


class _StepExecutorMeta(type):
    """Metaclass for lazy loading BUILTIN_STEPS on first access"""

    _cache: Optional[Dict[str, Type[BaseStep]]] = None

    @property
    def BUILTIN_STEPS(cls) -> Dict[str, Type[BaseStep]]:
        """Lazy load steps on first access"""
        if cls._cache is None:
            cls._cache = _discover_steps()
        return cls._cache


class StepExecutor(metaclass=_StepExecutorMeta):
    """Executor for definition file steps"""

    @staticmethod
    def get_step(step_name: str, general_config: Dict[str, Any], db, cache_dir: Path) -> BaseStep:
        """
        Get a step instance by name.

        Args:
            step_name: Name of the step (e.g., "bibtex_import")
            general_config: Project-level configuration
            db: PapersDatabase instance
            cache_dir: Cache directory path

        Returns:
            Instantiated step object (BaseStep subclass instance)
        """
        builtin_steps = StepExecutor.BUILTIN_STEPS

        if step_name not in builtin_steps:
            raise ValueError(f"Unknown step: {step_name}. Available: {list(builtin_steps.keys())}")

        step_class = builtin_steps[step_name]
        try:
            # Instantiate the step with required dependencies
            return step_class(general_config=general_config, db=db, cache_dir=cache_dir)
        except Exception as e:
            raise ValueError(f"Failed to instantiate step {step_name}: {e}")

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
        builtin_steps = StepExecutor.BUILTIN_STEPS
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


def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(description="Process definition files and execute paper scanner steps")

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ===== RUN COMMAND =====
    run_parser = subparsers.add_parser("run", help="Run a definition file")

    run_parser.add_argument("definition_file", type=Path, help="Path to YAML definition file")

    run_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    run_parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually execute steps, just show what would happen"
    )

    run_parser.add_argument("-o", "--output", type=Path, default=None, help="Output results to JSON file")

    run_parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )

    run_parser.add_argument(
        "--no-checkpoint", action="store_true", help="Skip loading from checkpoints (start fresh from beginning)"
    )

    run_parser.add_argument(
        "--clear-checkpoint", action="store_true", help="Clear all checkpoints before processing (creates new ones)"
    )

    run_parser.add_argument("-t", "--timings", action="store_true", help="Show timing information for each step")

    run_parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug output for detailed step information"
    )

    # ===== VALIDATE COMMAND =====
    validate_parser = subparsers.add_parser("validate", help="Validate a definition file")

    validate_parser.add_argument("definition_file", type=Path, help="Path to YAML definition file")

    validate_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    # ===== INFO COMMAND =====
    info_parser = subparsers.add_parser("info", help="Show information about steps and configuration")

    info_subparsers = info_parser.add_subparsers(dest="info_command", help="Info commands")

    steps_parser = info_subparsers.add_parser("steps", help="Show available steps and their documentation")

    # ===== REPL COMMAND =====
    repl_parser = subparsers.add_parser("repl", help="Start interactive REPL for building pipelines")

    repl_parser.add_argument(
        "-f",
        "--definition",
        type=Path,
        default=None,
        help="Optional YAML definition file to load at startup (post-checkpoint)",
    )

    repl_parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )

    repl_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    repl_parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output")

    repl_parser.add_argument(
        "-q",
        "--quit",
        action="store_true",
        help="Quit immediately after executing definition file (no interactive mode)",
    )

    repl_parser.add_argument(
        "-n", "--no-autorun", action="store_true", help="Only load definition file (direct into interactive mode)"
    )

    # ===== CACHE COMMAND =====
    cache_parser = subparsers.add_parser("cache", help="Manage cache operations")

    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache operations")

    info_parser = cache_subparsers.add_parser("info", help="Show cache information")

    info_parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )

    info_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    clear_parser = cache_subparsers.add_parser("clear", help="Clear cache contents")

    clear_parser.add_argument("target", choices=["checkpoints", "pdfs"], help="What to clear")

    clear_parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )

    clear_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    load_parser = cache_subparsers.add_parser("load", help="Load PDFs into cache from folder (indexed by DOI)")

    load_parser.add_argument("folder", type=str, help="Path to folder containing PDF files")

    load_parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Cache directory (default: ~/.paper-scanner, or CACHE_DIR env var)"
    )

    load_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    load_parser.add_argument("--dry-run", action="store_true", help="Don't actually cache files")

    # ===== DB COMMAND =====
    db_parser = subparsers.add_parser("db", help="Database management commands")

    db_subparsers = db_parser.add_subparsers(dest="db_command", help="Database commands")

    stats_parser = db_subparsers.add_parser("stats", help="Show database statistics")

    stats_parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL (optional, will use env var if not provided)",
    )

    stats_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    # ===== CLEAR SUBCOMMAND =====
    clear_parser = db_subparsers.add_parser("clear", help="Clear records from database tables")

    clear_parser.add_argument(
        "target", nargs="?", default="all", help="Table to clear: 'all' or specific table name (default: all)"
    )

    clear_parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL (optional, will use env var if not provided)",
    )

    clear_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    clear_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be cleared without actually doing it"
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

        elif args.command == "repl":
            builtin_steps = StepExecutor.BUILTIN_STEPS

            exit_code = execute_repl(
                cache_dir=args.cache_dir,
                definition_file=args.definition,
                auto_run=not args.no_autorun,
                verbose=args.verbose,
                debug=args.debug,
                quit_after_definition=args.quit,
                builtin_steps=builtin_steps,
            )
            sys.exit(exit_code)

        elif args.command == "info":
            if not args.info_command:
                info_parser.print_help()
                sys.exit(1)

            if args.info_command == "steps":
                builtin_steps = StepExecutor.BUILTIN_STEPS
                exit_code = execute_info_steps(builtin_steps=builtin_steps)
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

            elif args.cache_command == "load":
                exit_code = execute_cache_load(
                    args.folder,
                    cache_dir=args.cache_dir,
                    verbose=args.verbose,
                    dry_run=args.dry_run,
                )
                sys.exit(exit_code)

        elif args.command == "db":
            if not args.db_command:
                db_parser.print_help()
                sys.exit(1)

            if args.db_command == "stats":
                exit_code = execute_db_stats(
                    database_url=args.database_url,
                    cache_dir=None,
                    console=console,
                    verbose=args.verbose,
                )
                sys.exit(exit_code)

            elif args.db_command == "clear":
                exit_code = execute_db_clear(
                    target=args.target,
                    database_url=args.database_url,
                    cache_dir=None,
                    console=console,
                    verbose=args.verbose,
                    dry_run=args.dry_run,
                )
                sys.exit(exit_code)

    except Exception as e:
        console.print(f"[red bold]Error:[/red bold] {e}", style="red")
        if args.debug:
            import traceback

            console.print(traceback.print_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
