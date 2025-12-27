"""
Reporter module for pipeline execution and macro command lifecycle events.

This module defines abstract reporter interfaces for monitoring and reporting on:
- Step-level execution events (start, end, errors)
- Macro command execution lifecycle
- Configuration and execution errors

Reporters implement the observer pattern to provide custom handling of pipeline events.
"""

from abc import ABC, abstractmethod
import sys
from typing import Any, Dict

from rich.console import Console

from paper_scanner.core.step_result import StepResult


class NoOpCallback:
    '''Default no-operation callback class. Does nothing when called.'''
    def __call__(self, *args, **kwargs) -> None:
        pass

NOOP = NoOpCallback()


class AbstractStepReporter(ABC):
    """Abstract base class for step execution reporters.

    Provides callback hooks for monitoring individual step execution within a pipeline.
    Implementations handle logging, progress reporting, and error notification.
    """

    def __init__(self) -> None:
        """Initialize the step reporter.

        """
        self.executor = None # type: StepExecutor

    @abstractmethod
    def on_step_start(self, idx: int, step_config: Dict[str, Any], total: int) -> None:
        """Called when a step starts execution.

        Args:
            idx: Zero-based index of the step in the pipeline.
            step_config: Configuration dictionary for the step.
            total: Total number of steps in the pipeline.
        """
        pass

    @abstractmethod
    def on_step_end(self, idx: int, step_config: Dict[str, Any], result: Any) -> None:
        """Called when a step completes execution.

        Args:
            idx: Zero-based index of the step in the pipeline.
            step_config: Configuration dictionary for the step.
            result: Result object returned by the step.
        """
        pass

    @abstractmethod
    def on_step_event(self, msg: str, debug: bool = False) -> None:
        """Called when a step completes execution.

        Args:
            msg: Event message from the step.
            debug: Whether the message is for debugging purposes.
        """
        pass

    @abstractmethod
    def on_execution_start(self, total_steps: int) -> None:
        """Called when pipeline execution starts.

        Args:
            total_steps: Total number of steps in the pipeline.
        """
        pass

    @abstractmethod
    def on_execution_complete(self, results: StepResult) -> None:
        """Called when all pipeline steps have completed successfully.

        Args:
            results: Aggregated results from all executed steps.
        """
        pass

    @abstractmethod
    def on_execution_error(self, error: str) -> None:
        """Called when an error occurs during step execution.

        Args:
            error: Error message describing the execution failure.
        """
        pass

    @abstractmethod
    def on_configuration_error(self, error: str) -> None:
        """Called when an error occurs during pipeline configuration validation.

        Args:
            error: Error message describing the configuration issue.
        """
        pass


class AbstractControllerReporter(ABC):
    """Abstract base class for controller and macro command execution reporters.

    Provides callback hooks for monitoring macro command execution lifecycle.
    Macros are high-level commands that may orchestrate multiple steps or external operations.
    """

    def __init__(self) -> None:
        """Initialize the macro reporter."""
        self.controller = None

    @abstractmethod
    def on_start(self) -> None:
        """Called when the application starts"""
        pass

    @abstractmethod
    def on_close(self) -> None:
        """Called when the application closes"""
        pass

    @abstractmethod
    def on_macro_start(self, command: str) -> None:
        """Called when a macro command starts execution.

        Args:
            command: Name or identifier of the macro command.
        """
        pass

    @abstractmethod
    def on_macro_end(self, command: str, result: StepResult, duration_ms: float) -> None:
        """Called when a macro command completes execution.

        Args:
            command: Name or identifier of the macro command.
            result: Result object from the macro execution.
            duration_ms: Execution duration in milliseconds.
        """
        pass

    @abstractmethod
    def on_macro_error(self, command: str, error: Exception, duration_ms: float) -> None:
        """Called when a macro command fails with an error.

        Args:
            command: Name or identifier of the macro command.
            error: Exception raised during macro execution.
            duration_ms: Execution duration before failure in milliseconds.
        """
        pass

    # ============================================================
    # Non mandatory hooks
    # ============================================================
    def on_definition_loaded(self, definition_file: str, definition: dict) -> None:
        """Called when a pipeline definition is loaded.

        Args:
            definition_file: Path to the definition file.
            definition: The loaded pipeline definition.
        """
        pass

    def on_initialized(self) -> None:
        """Called when the controller has been initialized"""
        pass

class ConsoleLoggingMixin:
    """Mixin providing console logging capabilities for reporters."""

    def __init__(self) -> None:
        self.console = Console(file=sys.stderr)
        self.debug = False
        self.verbose = False
        self.quiet = False

    def log(self, message: str = "") -> None:
        """Log a message to the console, guaranteed.

        Args:
            message: The message string to log.
        """
        self.console.print(message)

    def log_msg(self, message: str = "") -> None:
        """Log a message if not in quiet mode.

        Args:
            message: The message string to log.
        """
        if not self.quiet:
            self.console.print(message)

    def log_info(self, message: str = "") -> None:
        """Log an info message if not in quiet mode.

        Args:
            message: The info message string to log.
        """
        if self.verbose and not self.quiet:
            self.console.print(message)

    def log_success(self, message: str) -> None:
        """Log a success message.

        Args:
            message: The success message string to log.
        """
        if not self.quiet:
            self.console.print(f"[green]Success: {message}[/green]")

    def log_warning(self, message: str) -> None:
        """Log a warning message.

        Args:
            message: The warning message string to log.
        """
        self.console.print(f"[yellow]⚠ Warning: {message}[/yellow]")

    def log_error(self, message: str) -> None:
        """Log an error message.

        Args:
            message: The error message string to log.
        """
        self.console.print(f"[red]REPL ERROR: {message}[/red]")
        if self.debug:
            import traceback
            self.console.print(traceback.format_exc())

    def log_debug(self, message: str) -> None:
        """Log a debug message if debug mode is enabled.

        Args:
            message: The debug message string to log.
        """
        if self.debug and not self.quiet:
            self.console.print(f"[dim]{message}[/dim]")