"""
RunTemplateStep - Execute a predefined template of steps

A template is a reusable sequence of steps defined in the templates section
of a definition file. This step references a template by name and executes
all steps in that template in sequence.

v1: Static templates only (no parameters or nesting)
"""

from typing import Any, Dict, List, Tuple

from paper_scanner.core.enum import StepStatus
from paper_scanner.steps.base import BaseStep
from paper_scanner.steps.result import StepResult


class RunTemplateStep(BaseStep):
    """
    Execute a predefined template of steps.

    Configuration:
        template: Name of the template to execute (required)

    Example YAML:
        - step: Apply basic screening template
          builtin.run-template:
            template: "screen_basics"
    """

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate run-template configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if "template" not in config:
            errors.append("Missing required 'template' parameter")
        else:
            template = config.get("template")
            if not template or (isinstance(template, str) and not template.strip()):
                errors.append("Template name cannot be empty")

        return len(errors) == 0, errors

    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """
        Execute template (handled by StepExecutor).

        Note: This step is primarily for validation. The actual template
        expansion and execution is handled by StepExecutor._execute_template()
        to allow recursive handling and proper integration with the execution flow.

        Args:
            step_config: Step configuration with 'template' key
            verbose: Enable verbose output
            dry_run: Don't actually execute
            debug: Enable debug output

        Returns:
            Result dictionary
        """
        is_valid, errors = self.validate(step_config)
        if not is_valid:
            return StepResult(
                status=StepStatus.ERROR,
                error=f"Invalid template config: {', '.join(errors)}",
            )

        template_name = step_config.get("template")

        if dry_run:
            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Would execute template: {template_name}",
                stats = {"paper_count": 0},
            )

        # Template execution is handled by StepExecutor._execute_template
        # This step just validates the configuration
        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Template '{template_name}' expanded (see template_results)",
            stats={"paper_count": 0},
        )
