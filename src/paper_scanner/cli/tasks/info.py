"""
Info steps task - Display available steps and their documentation

Shows which steps are available and what they do based on their docstrings.
"""

import importlib
import sys
from typing import Dict, Optional, Type

from rich.console import Console
from rich.table import Table

from paper_scanner.steps.base import BaseStep


def _get_step_description(step_class: Type[BaseStep], step_name: str) -> str:
    """
    Get a meaningful description for a step.

    Tries to extract from:
    1. Class docstring if it's not a generic wrapper description
    2. Module-level docstring otherwise
    3. Fallback to generic message

    Args:
        step_class: The step class
        step_name: Name of the step

    Returns:
        First line of description
    """
    # Get class docstring
    class_doc = step_class.__doc__

    # Check if it's a generic wrapper description
    is_generic_wrapper = (
        class_doc and
        ("Wrapper for" in class_doc or "wrapper for" in class_doc)
    )

    if class_doc and not is_generic_wrapper:
        # Use class docstring if it's not generic
        first_line = class_doc.strip().split('\n')[0].strip()
        return first_line

    # Try to get module docstring
    try:
        module = importlib.import_module(step_class.__module__)
        module_doc = module.__doc__

        if module_doc:
            # Get first meaningful line from module docstring
            first_line = module_doc.strip().split('\n')[0].strip()
            return first_line
    except (ImportError, AttributeError):
        pass

    # Fallback
    if class_doc:
        first_line = class_doc.strip().split('\n')[0].strip()
        return first_line

    return "(no description available)"


def execute_info_steps(builtin_steps: Dict[str, Type[BaseStep]], console: Optional[Console] = None) -> int:
    """
    Display information about available steps.

    Shows each available step with its name, description from docstring,
    and key information.

    Args:
        builtin_steps: Dictionary mapping step names to step classes
        console: Optional Rich console instance (uses stderr by default)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if console is None:
        console = Console(file=sys.stderr)

    try:
        if not builtin_steps:
            console.print("[red]No steps available[/red]")
            return 1

        # Create a table for the steps summary
        table = Table(title="Available Steps", show_header=True, header_style="bold cyan")
        table.add_column("Step Name", style="green")
        table.add_column("Description", style="white")

        # Sort steps alphabetically
        sorted_steps = sorted(builtin_steps.items())

        for step_name, step_class in sorted_steps:
            # Get the best available description for the step
            description = _get_step_description(step_class, step_name)
            table.add_row(step_name, description)

        console.print(table)
        console.print()

        return 0

    except Exception as e:
        console.print(f"[red]Error displaying step information: {e}[/red]")
        return 1
