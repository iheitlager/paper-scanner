r"""REPL task - Interactive shell for paper-scanner pipelines

Provides an interactive Python REPL with macro commands (\command syntax) for
running paper-scanner steps via the Definition API, combined with micro mode
(direct Python code) for full programmatic access.

Two modes of interaction:
- Macro mode: \command prefix for predefined operations (e.g., \run, \export)
- Micro mode: Plain Python code with full access to paper_scanner modules
"""

import time
from typing import Dict

import textwrap

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator
from pygments.lexers.python import PythonLexer

from paper_scanner.core.controller import AbstractController, macro_step
from paper_scanner.core.step_result import StepResult, StepStatus
from paper_scanner.core.reporter import AbstractStepReporter, AbstractControllerReporter, ConsoleLoggingMixin

TABSTOP = 2

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
        self.log()
        if self.controller.debug:
            self.log("[yellow]⚠ Debug mode enabled - verbose output will be shown[/yellow]")
        if self.controller.verbose:
            self.log("[yellow]ℹ Verbose mode enabled - showing step details before execution[/yellow]")
        if self.controller.timings:
            self.log("[yellow]↻ Timings mode enabled - showing timing info after each step[/yellow]")

    def on_close(self) -> None:
        self.log_info()
        self.log_info("[green]Goodbye![/green]")

    def on_error(self, error: str) -> None:
        self.log_error(f"REPL error: {error}")

    def on_macro_start(self, command: str) -> None:
        pass  # Usually silent

    def on_macro_end(self, command: str, result: StepResult, duration_ms: float) -> None:
        """Called when macro command completes"""
        timings = f"[[dim]⏱ {duration_ms:.2f} ms[/dim]]" if self.controller.timings else ""

        if command in ("step", "run", "checkpoint"):
            if result.status == StepStatus.SUCCESS:
                self.log_info(f"[green]ok: {result.stats.get('processed', 0)}[/green] {timings} ")
            elif result.status == StepStatus.WARNING:
                self.log_warning(result.message)
        else:
            self.log_info(f"[green]ok: [/green] {timings} ")
        if command in ("step", "run"):
            if not self.executor.has_next_step:
                self.log_info("[green bold]🎉 All steps completed![/green bold]")

    def on_macro_error(self, command: str, error: Exception, duration_ms: float) -> None:
        self.log_error(f"✗ {error}")

    def on_definition_loaded(self, definition_file: str, definition: Dict) -> None:
        num_steps = len(definition.get("steps", []))
        self.log_info(f"[blue]Definition [white]{definition_file}[/white] with {num_steps} steps loaded[/blue]\n")

    def on_initialized(self) -> None:
        if self.controller.autorun and self.definition:
            self.log_debug("Auto-running all steps...")
        self.log_debug(f"History file: {str(self.controller.history_file)}")
        if self.controller.history_file.exists():
            self.log_debug(f"History file size: {self.controller.history_file.stat().st_size} bytes")

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
    """Main Controller for REPL task."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize REPL controller with macro steps dict."""
        super().__init__(*args, **kwargs)
        self._macro_steps: Dict = {}
        self._help_text = ["Available commands:", ""]
        self._commands = {}

    def _do_initialize(self) -> bool:
        # Initialization logic here
        self.should_quit = self.args.quit or False
        self.autorun = self.args.auto_run or False

        self._prep_macro_steps()
        self._prep_repl_session()
        return True

    def _prep_repl_session(self) -> None:
        # Setup history file with manual persistence
        history_obj = None
        history_dir = self.cache_dir
        history_dir.mkdir(parents=True, exist_ok=True)
        # Use single shared history file for all sessions (not per-project)
        self.history_file = history_dir / ".repl_history"

        # Create FileHistory object
        history_obj = FileHistory(str(self.history_file))

        # Setup key bindings for tab expansion
        kb = KeyBindings()
        
        @kb.add('tab')
        def _(event):
            """Convert tab to spaces"""
            event.current_buffer.insert_text(' ' * TABSTOP)

        self.session = PromptSession(
            completer=WordCompleter([], ignore_case=True),
            style=Style.from_dict(
                {
                    "completion-menu.completion": "bg:#008888 #ffffff",
                    "completion-menu.completion.current": "bg:#00aaaa #000000",
                    "prompt": "#00aa00 bold",
                }
            ),
            history=history_obj,
            lexer=PygmentsLexer(PythonLexer),
            enable_history_search=True,
            validate_while_typing=True,
            key_bindings=kb,
        )

    def _prep_macro_steps(self) -> None:
        # Register all macro commands by scanning for @macro_step decorated methods
        # This is sophisticated Python reflection stuff for decorators
        for attr_name in dir(self):
            # Skip private attributes
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)

            # Check if method is decorated with @macro_step
            if hasattr(attr, "_macro_names"):
                names = attr._macro_names
                # Register under all provided names
                for name in names:
                    if type(name) is str:
                        self._macro_steps[name] = attr
                    elif type(name) is list:
                        for n in name:
                            self._macro_steps[n] = attr

                self._help_text.append((names[0], names[1:], attr.__doc__))
                for name in names[1:]:
                    self._commands[name] = names[0]
        self._help_text.append(("quit", ("q", "x"), "Exit REPL"))

    def _get_macro_step(self, name: str):
        """Get a registered macro step"""
        return self._macro_steps.get(name)

    def _get_status_line(self) -> (str, str):
        """Get status line and prompt string for REPL"""
        prompt = ">>> "  # Default prompt

        parts = []
        # Database record count
        record_count = self.executor.papers_db.count() if self.executor.papers_db else 0
        parts.append(f"[cyan]db:[/cyan] {record_count}")

        if self.definition_file:
            current, total = self.executor.step_progress
            prompt = f"[{current}/{total}] > "

            if current == total:
                parts.append(f"[red]All steps completed ({total}/{total})[/red]")

            parts.append(f"[magenta]{self.definition_file}[/magenta]")

        return " | ".join(parts) if not self.quiet else "", prompt

    def _do_exec(self) -> int:
        """REPL loop - macro commands and Python code"""

        # Python REPL namespace
        namespace = {
            "executor": self.executor,
            "db": self.executor.papers_db,
            "steps": self.executor.steps,
            "reporter": self.step_reporter,
        }

        if self.autorun:
            if not self.executor.has_next_step:
                return StepResult(status=StepStatus.WARNING, message="All steps done")
            result = self.executor.run_all(
                dry_run=self.dry_run,
                on_step_start=self.step_reporter.on_step_start,
                on_step_end=self.step_reporter.on_step_end,
            )
            if self.should_quit:
                return result

        while True:
            try:
                # Display prompt
                status_line, prompt = self._get_status_line()
                self.controller_reporter.log(status_line)
                user_input = self.session.prompt(prompt, multiline=False, enable_history_search=True).strip()

                if not user_input:
                    continue

                # Check for quit before we parse anything else
                if user_input in ("quit", "q", "bye", "exit", "x"):
                    break
                elif user_input.startswith("\\") and user_input[1:] in ("quit", "q", "exit", "x"):
                    break

                # Check if it's a macro command (starts with \)
                if user_input.startswith("\\"):
                    self._execute_macro_command(user_input)
                else:
                    self._execute_python_code(user_input, namespace, len(prompt))

            except KeyboardInterrupt:
                self.controller_reporter.on_error("\nInterrupted")
            except EOFError:
                break

        return 0

    def _execute_macro_command(self, user_input: str) -> int:
        """Execute a macro command (task layer)"""
        # Strip the backslash and execute as macro
        command_line = user_input[1:].split(" ")  # Remove \ and split on space
        command, args = command_line[0], command_line[1:]
        # expand aliases
        if command in self._commands:
            command = self._commands[command]
        start = time.time()
        self.controller_reporter.on_macro_start(command)

        try:
            macro_func = self._get_macro_step(command)
            if not macro_func:
                self.controller_reporter.on_error(f"Unknown command: [dim]{command}[/dim]")
                return 1

            result = macro_func(args)
            duration_ms = (time.time() - start) * 1000
            self.controller_reporter.on_macro_end(command, result, duration_ms)
            return 0

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.controller_reporter.on_macro_error(command, e, duration_ms)
            return 1

    def _execute_python_code(self, user_input: str, namespace: dict, prompt_length: int) -> None:
        """Execute Python code in REPL (arbitrary computation)"""
        code = user_input
        indent_level = 0
        prompt = f"...{' ' * (prompt_length - 3)}"
        # Handle multi-line code input
        while True:
            try:
                compile(textwrap.dedent(code), "<input>", "exec")
                break  # Valid code
            except IndentationError as e:
                # Incomplete code, prompt for more input
                # check comments
                code = code.split('#')[0].rstrip()
                # check blocks
                if code[-1] == ":":
                    indent_level += 1
                else:
                    indent_level = max(0, indent_level - 1)
                indent_str = " " * (TABSTOP * indent_level)
                try:
                    more_input = self.session.prompt(f"{prompt}{indent_str}", multiline=False, enable_history_search=True)
                except KeyboardInterrupt:
                    self.controller_reporter.log_warning("KeyboardInterrupt during code input")
                    return
                if more_input.strip() == "":  # Empty line ends input
                    more_input = ""
                    break
                code += "\n" + indent_str + more_input
            except SyntaxError as e:
                self.controller_reporter.log_error(f"SyntaxError: {e}")
                return
            except EOFError:
                break

        # Now execute the complete code
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
                self.controller_reporter.log_error(e)
        except Exception as e:
            self.controller_reporter.log_error(e)

    def _do_shutdown(self) -> None:
        # Shutdown logic here
        pass

    # ================================================================
    # Macro REPL step implementations
    # ================================================================

    @macro_step("step", "s", "n")
    def step_cmd(self, args: list[str]) -> StepResult:
        """Execute next step"""
        if not self.executor.has_next_step:
            return StepResult(status=StepStatus.WARNING, message="Step: All steps done")
        return self.executor.execute_next_step(self.dry_run)

    @macro_step("run", "r")
    def run_cmd(self, args: list[str]) -> StepResult:
        """Execute all remaining steps"""
        if not self.executor.has_next_step:
            return StepResult(status=StepStatus.WARNING, message="Run: All steps done")
        return self.executor.run_all(
            dry_run=self.dry_run,
            on_step_start=self.step_reporter.on_step_start,
            on_step_end=self.step_reporter.on_step_end,
        )

    @macro_step("steps", "ls")
    def list_steps_cmd(self, args: list[str]) -> StepResult:
        """List all steps"""
        # console.print("\n[bold]📋 Pipeline Steps:[/bold]")

        # # Show templates
        # if executor.templates:
        #     console.print(f"\n[cyan]Templates ({len(executor.templates)}):[/cyan]")
        #     for template_name, template_steps in executor.templates.items():
        #         console.print(f"  • [white]{template_name}[/white] [dim]({len(template_steps)} steps)[/dim]")

        # # Show main steps
        # if executor.steps:
        #     console.print(f"\n[cyan]Main Steps ({len(executor.steps)}):[/cyan]")
        steps = self.executor.steps
        for idx, step in enumerate(steps):
            status = "✓" if idx < self.executor.current_step_index else " "
            description = step.get("step", "No description")
            self.controller_reporter.log(f"[{status}] Step {idx + 1}: [blue]{description}[/blue]")
        self.controller_reporter.log("")
        return StepResult(status=StepStatus.SUCCESS)

    @macro_step("checkpoint", "c")
    def checkpoint_cmd(self, args: list[str]) -> StepResult:
        """Save checkpoint"""
        # console.print("\n[blue]ℹ Saving checkpoint...[/blue]")
        # result = executor.checkpoint()
        # if result['status'] == 'ok':
        #     console.print("[green]✓[/green] [white]Checkpoint saved[/white]")
        #     console.print(f"  [cyan]File:[/cyan] [white]{result.get('checkpoint_file', 'unknown')}[/white]")
        #     console.print(f"  [cyan]Papers:[/cyan] [white]{result.get('papers_count', 0)}[/white]")
        # else:
        #     error_msg = result.get('error', 'Unknown error')
        #     console.print("[red]✗[/red] [white]Checkpoint failed[/white]")
        #     console.print(f"  [red]Error:[/red] [white]{error_msg}[/white]")
        return self.executor.checkpoint()

    @macro_step("help", "?")
    def help_cmd(self, args: list[str]) -> StepResult:
        """Show help"""
        for line in self._help_text:
            if type(line) is str:
                self.controller_reporter.log(f"[yellow]{line}[/yellow]")
            else:
                name, aliases, description = line
                alias_str = ", ".join(aliases)
                cmd_str = f"{name} ({alias_str})"
                self.controller_reporter.log(f"  [cyan]{cmd_str:<15}[/cyan] - {description}")
        self.controller_reporter.log("")
        return StepResult(status=StepStatus.SUCCESS)


def execute_repl(args: dict[str, any]) -> int:
    """Run the REPL task. This is the main entry point for the CLI command."""

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
