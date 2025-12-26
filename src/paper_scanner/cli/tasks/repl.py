r"""REPL task - Interactive shell for paper-scanner pipelines

Provides an interactive Python REPL with macro commands (\command syntax) for
running paper-scanner steps via the Definition API, combined with micro mode
(direct Python code) for full programmatic access.

Two modes of interaction:
- Macro mode: \command prefix for predefined operations (e.g., \run, \export)
- Micro mode: Plain Python code with full access to paper_scanner modules
"""

import time
from typing import Dict, Callable

from paper_scanner.core.controller import AbstractController
from paper_scanner.core.step_result import StepResult, StepStatus
# from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.reporter import AbstractStepReporter, AbstractControllerReporter, ConsoleLoggingMixin


def macro_step(*names: str) -> Callable:
    """Decorator to register a function as a macro step command.
    
    Marks a method as a macro command with one or more aliases.
    The decorated method will be registered during controller initialization.
    
    Args:
        *names: Command name(s) and aliases (e.g., "step", "s" for step command and shortcut)
        
    Example:
        @macro_step("step", "s")
        def step_cmd(self):
            return StepResult(...)
    """
    def decorator(func: Callable) -> Callable:
        func._macro_names = names  # type: ignore
        return func
    return decorator

class ConsoleReporter(AbstractControllerReporter, AbstractStepReporter, ConsoleLoggingMixin):
    """Single console reporter implementing both interfaces"""

    def __init__(self) -> None:
        ConsoleLoggingMixin.__init__(self)
        AbstractControllerReporter.__init__(self)
        AbstractStepReporter.__init__(self)

    # AbstractControllerReporter
    def on_start(self) -> None:
        self.log("[green]Starting REPL...[/green]")
        self.log("[dim]Type 'help' or '?' for commands[/dim]")
        self.log("")

    def on_close(self) -> None:
        self.log()
        self.log("[green]Goodbye![/green]")

    def on_error(self, error: str) -> None:
        self.log_error(f"REPL error: {error}")

    def on_macro_start(self, command: str) -> None:
        pass  # Usually silent

    def on_macro_end(self, command: str, result: StepResult, duration_ms: float) -> None:
        """Called when macro command completes"""
        if command in ("step", "run", "checkpoint"):
            if result.status == StepStatus.SUCCESS:
                self.log_success(f"ok: ({result.stats.get('processed', 0)}")
            elif result.status == StepStatus.WARNING:
                self.log_warning(result.message)

    def on_macro_error(self, command: str, error: Exception, duration_ms: float) -> None:
        self.log_error(f"✗ {error}")

    # AbstractStepReporter
    def on_step_start(self, idx: int, step_config: Dict, total: int) -> None:
        description = step_config.get("description", "Unknown")
        self.log_info(f"[{idx}/{total}] {description}...")

    def on_step_end(self, idx: int, step_config: Dict, result: StepResult) -> None:
        if result.status == StepStatus.SUCCESS:
            count = result.stats.get("processed", 0)
            self.log_success(f" ✓ ({count} items)")
        elif result.status == StepStatus.ERROR:
            self.log_error(f" ✗ {result.error}")

    def on_execution_start(self, total_steps: int) -> None:
        self.log_info(f"[blue]Starting pipeline: {total_steps} steps[/blue]\n")

    def on_execution_complete(self, results: StepResult) -> None:
        self.log_success("\nPipeline complete")

    def on_execution_error(self, error: str) -> None:
        self.log_error(f"Pipeline error: {error}")

    def on_configuration_error(self, error: str) -> None:
        self.log_error(f"Configuration error: {error}")




class ReplController(AbstractController):
    """Controller for REPL task."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize REPL controller with macro steps dict."""
        super().__init__(*args, **kwargs)
        self._macro_steps: Dict = {}

    def _do_initialize(self) -> bool:
        # Initialization logic here
        self.should_quit = self.args.quit or False
        self.dry_run = False
        self.no_autorun = self.args.no_autorun or False

        # Register all macro commands by scanning for @macro_step decorated methods
        # This is sophisticated Python reflection stuff for decorators
        for attr_name in dir(self):
            # Skip private attributes
            if attr_name.startswith('_'):
                continue

            attr = getattr(self, attr_name)

            # Check if method is decorated with @macro_step
            if hasattr(attr, '_macro_names'):
                names = attr._macro_names
                # Register under all provided names
                for name in names:
                    self._macro_steps[name] = attr

        return True


    def _get_macro_step(self, name: str):
        """Get a registered macro step"""
        return self._macro_steps.get(name)

    def _do_exec(self) -> int:
        """REPL loop - macro commands and Python code"""

        # Python REPL namespace
        namespace = {
            "executor": self.executor,
            "db": self.executor.papers_db,
        }

        while True:
            try:
                # Display prompt
                current = self.executor.current_step_index
                total = len(self.executor.steps)

                # Get user input
                user_input = input(f"[{current}/{total}] > ").strip()

                if not user_input:
                    continue

                # Check for quit
                if user_input in ("quit", "q", "bye", "exit", "x"):
                    break
                elif user_input.startswith("\\") and user_input[1:] in ("quit", "q"):
                    break

                # Check if it's a macro command (starts with \)
                if user_input.startswith("\\"):
                    # Strip the backslash and execute as macro
                    command = user_input[1:]  # Remove \
                    self._execute_macro_command(command)

                else:
                    # Execute as Python code
                    self._execute_python_code(user_input, namespace)

            except KeyboardInterrupt:
                self.controller_reporter.on_error("\nInterrupted")
            except EOFError:
                break

        return 0

    def _execute_macro_command(self, command: str) -> int:
        """Execute a macro command (task layer)"""
        start = time.time()
        self.controller_reporter.on_macro_start(command)

        try:
            macro_func = self._get_macro_step(command)
            if not macro_func:
                self.controller_reporter.on_error(f"Unknown command: [dim]{command}[/dim]")
                return 1

            result = macro_func()
            duration_ms = (time.time() - start) * 1000
            self.controller_reporter.on_macro_end(command, result, duration_ms)
            return 0

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.controller_reporter.on_macro_error(command, e, duration_ms)
            return 1

    def _execute_python_code(self, code: str, namespace: dict) -> None:
        """Execute Python code in REPL (arbitrary computation)"""
        try:
            # Try eval first (for expressions)
            result = eval(code, namespace)
            if result is not None:
                print(repr(result))
        except SyntaxError:
            # Try exec for statements
            try:
                exec(code, namespace)
            except Exception as e:
                print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def _do_shutdown(self) -> None:
        # Shutdown logic here
        pass

    # ================================================================
    # Macro step implementations
    # ================================================================

    @macro_step("step", "s")
    def step_cmd(self) -> StepResult:
        """Execute next step"""
        if not self.executor.has_next_step:
            return StepResult(status=StepStatus.WARNING, message="All steps done")
        return self.executor.execute_next_step()

    @macro_step("run", "r")
    def run_cmd(self) -> StepResult:
        """Execute all remaining steps"""
        if not self.executor.has_next_step:
            return StepResult(status=StepStatus.WARNING, message="All steps done")
        return self.executor.run_all()

    @macro_step("checkpoint", "c")
    def checkpoint_cmd(self) -> StepResult:
        """Save checkpoint"""
        return self.executor.checkpoint()

    @macro_step("quit", "q")
    def quit_cmd(self) -> StepResult:
        """Quit REPL"""
        return StepResult(status=StepStatus.SUCCESS)

    @macro_step("help", "?")
    def help_cmd(self) -> StepResult:
        """Show help"""
        print("Available commands:")
        print("  step (s)       - Execute next step")
        print("  run (r)        - Execute all remaining steps")
        print("  checkpoint (c) - Save checkpoint")
        print("  help (?)       - Show this help")
        print("  quit (q)       - Exit REPL")
        return StepResult(status=StepStatus.SUCCESS)



def execute_repl(args: dict[str, any]) -> int:
    """Run the REPL task."""

    # Create reporters
    shared_reporter = ConsoleReporter()

    # Create controller
    controller = ReplController(
        controller_reporter=shared_reporter,
        step_reporter=shared_reporter,
        # executor_class=StepExecutor,
        args=args,
    )

    # Lifecycle: initialize → exec → shutdown
    try:
        if not controller.initialize():
            return 1

        return_code = controller.exec()
        return return_code

    finally:
        # ALWAYS shutdown, even if exec() failed
        # This is sophisticated Python semantics
        controller.shutdown()
