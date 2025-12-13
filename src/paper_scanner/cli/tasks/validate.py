"""
Validate task - Validate a definition file

This task loads and validates a YAML definition file, checking the
structure and running step-specific validation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import importlib

import yaml
from rich.console import Console

console = Console(file=sys.stderr)


def validate_definition_file(
    definition_file: Path,
    verbose: bool = False,
    builtin_steps: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Validate definition file structure and step configurations.

    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        builtin_steps: Available builtin steps

    Returns:
        Tuple of (is_valid, error_messages)
    """
    if builtin_steps is None:
        builtin_steps = {}

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
            step_value = step_config.get("step")
            description = step_config.get("description", "")

            # Find the builtin key
            builtin_key = None
            for key in step_config.keys():
                if key.startswith("builtin."):
                    builtin_key = key
                    break

            if not builtin_key:
                errors.append(f"Step {i}: Missing 'builtin.<step>' key")
                continue

            # Extract step name from builtin key
            step_name = builtin_key.replace("builtin.", "")

            # If step_value contains spaces or is not a valid step name, use it as description
            if " " in step_value or step_value not in builtin_steps:
                if not description:
                    description = step_value
            else:
                step_name = step_value

            # Check if step exists
            if step_name not in builtin_steps:
                errors.append(
                    f"Step {i}: Unknown step '{step_name}'. Available: {list(builtin_steps.keys())}"
                )
                continue

            # Get the step params
            step_params = step_config.get(builtin_key, {})

            if not step_params:
                step_params = {
                    k: v
                    for k, v in step_config.items()
                    if k not in ["step", "description"] and not k.startswith("builtin.")
                }

            # Get the step module and run validation
            step_module_name = builtin_steps[step_name]
            step_func_module = __import__(
                f"paper_scanner.steps.{step_module_name}", fromlist=["validate"]
            )

            if hasattr(step_func_module, "validate"):
                is_valid, validation_errors = step_func_module.validate(step_params)
                if not is_valid:
                    for error in validation_errors:
                        errors.append(f"Step {i} ({step_name}): {error}")

        except Exception as e:
            errors.append(f"Step {i}: {str(e)}")

    return len(errors) == 0, errors


def execute_validate(
    definition_file: Path,
    verbose: bool = False,
    builtin_steps: Optional[Dict[str, str]] = None,
) -> int:
    """
    Validate a definition file and exit with appropriate code.

    Args:
        definition_file: Path to YAML definition file
        verbose: Enable verbose output
        builtin_steps: Available builtin steps

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    is_valid, errors = validate_definition_file(definition_file, verbose=verbose, builtin_steps=builtin_steps)

    if not is_valid:
        console.print(f"\n[red bold]Validation failed:[/red bold]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        return 1
    else:
        console.print(f"[green]✓ Definition file is valid[/green]")
        if verbose:
            console.print(f"File: [cyan]{definition_file}[/cyan]")
        return 0
