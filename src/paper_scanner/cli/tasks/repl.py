r"""REPL task - Interactive shell for paper-scanner pipelines

Provides an interactive Python REPL with macro commands (\command syntax) for
running paper-scanner steps via the Definition API, combined with micro mode
(direct Python code) for full programmatic access.

Two modes of interaction:
- Macro mode: \command prefix for predefined operations (e.g., \run, \export)
- Micro mode: Plain Python code with full access to paper_scanner modules
"""
import sys
from rich.console import Console


from paper_scanner.core.controller import BaseController
from paper_scanner.cli.tasks.run import StepExecutor
from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.halt import HaltException

console = Console(file=sys.stderr)

class ReplController(BaseController):
    """Controller for REPL task."""

    def initialize(self) -> bool:
        console.print("[bold green]Initializing REPL Controller...[/bold green]")
        # Initialization logic here
        return True

    def exec(self) -> int:
        console.print("[bold green]Starting REPL... Type \\help for commands.[/bold green]")
        return 0

    def shutdown(self) -> None:
        console.print("[bold green]Shutting down REPL Controller...[/bold green]")


def execute_repl(args: dict[str, any]) -> int:
    """Run the REPL task."""

    cache_dir = args.get("cache_dir", None)
    verbose = args.get("verbose", False)
    debug = args.get("debug", False)

    exc = StepExecutor
    ctrl = ReplController(exc, args=args)
    ctrl.initialize()
    return_code = ctrl.exec()
    ctrl.shutdown()

    return return_code