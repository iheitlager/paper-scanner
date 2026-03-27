#!/usr/bin/env python
"""
INTEGRATION_EXAMPLE.py

Practical example of how to integrate StepExecutor into CLI tasks
and REPL implementations.

This shows the refactored approach replacing separate run.py and repl.py
with a unified StepExecutor.
"""

from pathlib import Path
from typing import Optional

from paper_scanner.cli.executor import StepExecutor

# ==============================================================================
# INTEGRATION PATTERN 1: Batch Task (CLI-based, for run.py)
# ==============================================================================

class BatchTaskExecutor:
    """
    Refactored batch task using StepExecutor.
    This replaces the original run.py implementation.
    """

    def __init__(
        self,
        definition_file: Path,
        project_name: str,
        cache_dir: Optional[Path] = None,
        verbose: bool = False,
        debug: bool = False,
    ):
        """Initialize batch task executor"""
        self.definition_file = definition_file
        self.project_name = project_name
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.verbose = verbose
        self.debug = debug

    def run(
        self,
        skip_checkpoint: bool = False,
        clear_checkpoint: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """
        Execute complete pipeline batch.

        Returns:
            Execution results dictionary
        """
        # Setup general config
        general_config = {
            "project_name": self.project_name,
        }

        # Create executor (self-contained with lazy step loading)
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=self.cache_dir,
            verbose=self.verbose,
            debug=self.debug,
        )

        # Load and execute
        if self.verbose:
            print(f"Loading definition: {self.definition_file}")
        executor.load_definition(self.definition_file)

        if self.verbose:
            print("Checking for checkpoints...")
        executor.load_checkpoint(
            skip_checkpoint=skip_checkpoint,
            clear_checkpoint=clear_checkpoint
        )

        if self.verbose:
            print("Executing pipeline...")
        results = executor.run_all(dry_run=dry_run)

        # Report
        if self.verbose:
            stats = executor.get_stats()
            print("\n✓ Pipeline complete:")
            print(f"  Status: {results['status']}")
            print(f"  Steps: {results.get('steps_executed', 0)}/{stats['total_steps']}")
            print(f"  Papers: {stats['papers_unique']} unique")
            print(f"  Duration: {stats['total_duration_seconds']:.2f}s")

        return results


# ==============================================================================
# INTEGRATION PATTERN 2: REPL Session (Interactive, for repl.py)
# ==============================================================================

class REPLSession:
    """
    Refactored REPL session using StepExecutor.
    This replaces the original repl.py implementation.
    """

    def __init__(
        self,
        definition_file: Path,
        project_name: str,
        cache_dir: Optional[Path] = None,
        verbose: bool = False,
    ):
        """Initialize REPL session"""
        self.definition_file = definition_file
        self.project_name = project_name
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.verbose = verbose

        # Create executor (self-contained with lazy step loading)
        general_config = {"project_name": project_name}
        self.executor = StepExecutor(
            general_config=general_config,
            cache_dir=self.cache_dir,
            verbose=verbose,
            debug=False,
        )

        # Load definition and checkpoint
        self.executor.load_definition(definition_file)
        self.executor.load_checkpoint()

    def cmd_step(self, args: list) -> bool:
        """Execute next step (or specific step if index given)"""
        step_index = self.executor.current_step_index
        if args:
            try:
                step_index = int(args[0])
            except ValueError:
                print("Usage: step [index]")
                return False

        if step_index >= len(self.executor.steps):
            print(f"Step {step_index} out of range")
            return False

        print(f"Executing step {step_index}...")
        result = self.executor.execute_step(step_index)
        print(f"  Status: {result['status']}")
        if result.get('error'):
            print(f"  Error: {result['error']}")

        return result['status'] != 'error'

    def cmd_checkpoint(self, args: list) -> bool:
        """Save checkpoint"""
        result = self.executor.checkpoint()
        if result['status'] == 'ok':
            print(f"✓ Checkpoint saved: {result['checkpoint_file']}")
            return True
        else:
            print(f"✗ Checkpoint failed: {result.get('error')}")
            return False

    def cmd_stats(self, args: list) -> bool:
        """Show statistics"""
        stats = self.executor.get_stats()
        print("\nStatistics:")
        print(f"  Papers: {stats['papers_unique']} unique, {stats['papers_duplicates']} duplicates")
        print(f"  Progress: {stats['current_step_index']}/{stats['total_steps']} steps")
        print(f"  Duration: {stats['total_duration_seconds']:.2f}s")
        return True

    def cmd_history(self, args: list) -> bool:
        """Show execution history"""
        stats = self.executor.get_stats()
        print(f"\nExecution History ({len(stats['step_history'])} entries):")
        for entry in stats['step_history']:
            print(f"  [{entry['index']}] {entry['step']}: {entry['status']} ({entry['duration_seconds']:.2f}s)")
        return True

    def run(self):
        """Start interactive REPL loop"""
        print(f"REPL Session: {self.project_name}")
        print("Type 'help' for commands or 'quit' to exit\n")

        commands = {
            'step': self.cmd_step,
            'checkpoint': self.cmd_checkpoint,
            'stats': self.cmd_stats,
            'history': self.cmd_history,
        }

        while True:
            try:
                cmd_line = input(f"({self.executor.current_step_index}/{len(self.executor.steps)}) > ").strip()

                if not cmd_line:
                    continue

                parts = cmd_line.split()
                cmd = parts[0]
                args = parts[1:]

                if cmd == 'quit' or cmd == 'exit':
                    print("Exiting...")
                    break

                if cmd == 'help':
                    print("Available commands:")
                    for name in commands:
                        print(f"  {name}")
                    continue

                if cmd not in commands:
                    print(f"Unknown command: {cmd}")
                    continue

                commands[cmd](args)

            except KeyboardInterrupt:
                print("\nInterrupted. Exiting...")
                break


# ==============================================================================
# COMPARISON: Old vs New Approach
# ==============================================================================

def show_comparison():
    """
    Show side-by-side comparison of old vs new approach.

    OLD: Separate run.py and repl.py with different initialization
    NEW: Unified StepExecutor with integration patterns
    """

    comparison = """
╔════════════════════════════════════════════════════════════════════════════╗
║ OLD APPROACH: Separate run.py and repl.py                                 ║
╚════════════════════════════════════════════════════════════════════════════╝

run.py:
  - Parse definition manually
  - Load steps from YAML
  - Create PapersDatabase
  - Execute each step individually
  - Handle checkpoints manually
  - Collect stats from scratch

repl.py:
  - Similar setup as run.py
  - REPL loop with command parsing
  - Separate checkpoint handling
  - Overlapping code with run.py

Problems:
  - Duplicated initialization logic
  - Different checkpoint handling
  - Inconsistent statistics collection
  - Difficult to add new features (affects both files)

╔════════════════════════════════════════════════════════════════════════════╗
║ NEW APPROACH: Unified StepExecutor                                        ║
╚════════════════════════════════════════════════════════════════════════════╝

StepExecutor (core/executor.py):
  - Definition loading with validation
  - Checkpoint management
  - Step execution (single or batch)
  - Statistics collection
  - Session state management

BatchTaskExecutor (integrates StepExecutor):
  - Wraps StepExecutor for CLI batch mode
  - Minimal code: initialization + run_all()
  - Inherits all features automatically

REPLSession (integrates StepExecutor):
  - Wraps StepExecutor for interactive mode
  - Per-command methods using executor methods
  - Automatic checkpoint/stats support

Benefits:
  - Single source of truth for execution logic
  - Easy to add features (update StepExecutor once)
  - Consistent behavior across modes
  - Clear separation of concerns
  - Better testability
  - Better maintainability

╔════════════════════════════════════════════════════════════════════════════╗
║ KEY INSIGHT: StepExecutor is the core, integration patterns wrap it       ║
╚════════════════════════════════════════════════════════════════════════════╝
    """

    print(comparison)


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

def example_batch():
    """Example: Using BatchTaskExecutor"""
    print("\n" + "=" * 60)
    print("Example 1: Batch Task Integration")
    print("=" * 60 + "\n")

    BatchTaskExecutor(
        definition_file=Path("definition.yml"),
        project_name="Example Project",
        verbose=True,
    )

    # In real CLI, would use argparse:
    # results = batch.run(
    #     skip_checkpoint=args.skip_checkpoint,
    #     clear_checkpoint=args.clear_checkpoint,
    #     dry_run=args.dry_run,
    # )

    print("✓ BatchTaskExecutor ready to use in run.py")


def example_repl():
    """Example: Using REPLSession"""
    print("\n" + "=" * 60)
    print("Example 2: REPL Session Integration")
    print("=" * 60 + "\n")

    # repl = REPLSession(
    #     definition_file=Path("definition.yml"),
    #     project_name="Example Project",
    #     verbose=True,
    # )
    # repl.run()  # Starts interactive loop

    print("✓ REPLSession ready to use in repl.py")


if __name__ == "__main__":
    show_comparison()
    example_batch()
    example_repl()
