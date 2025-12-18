"""
REPL task - Interactive shell for paper-scanner pipelines

Provides an interactive Python REPL with macro commands (@command syntax) for
running paper-scanner steps via the Definition API, combined with micro mode
(direct Python code) for full programmatic access.

Two modes of interaction:
- Macro mode: @command prefix for predefined operations (e.g., @run, @export)
- Micro mode: Plain Python code with full access to paper_scanner modules
"""

import sys
import os
import json
import code
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    # Try readline for basic history support on Unix systems
    try:
        import readline
    except ImportError:
        pass

from paper_scanner.core.database import PapersDatabase
from paper_scanner.cli.tasks.run import StepExecutor

console = Console(file=sys.stderr)


class REPLSession:
    """Interactive REPL session for paper-scanner pipelines"""

    def __init__(
        self,
        project_id: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        initial_definition: Optional[Path] = None,
        verbose: bool = False,
        debug: bool = False,
        builtin_steps: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize REPL session

        Args:
            project_id: Optional project ID for naming
            cache_dir: Cache directory for checkpoints
            initial_definition: Optional YAML file to load at startup (post-checkpoint)
            verbose: Enable verbose output
            debug: Enable debug output
            builtin_steps: Available builtin steps registry
        """
        self.project_id = project_id or "interactive_session"
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.verbose = verbose
        self.debug = debug
        self.builtin_steps = builtin_steps or {}

        # Session state
        self.papers_db: Optional[PapersDatabase] = None
        self.definition: Optional[Definition] = None
        self.general_config: Dict[str, Any] = {
            "project_id": self.project_id,
            "cache_dir": str(self.cache_dir),
        }
        self.results: Dict[str, Any] = {}
        self.step_history: List[str] = []
        self.current_step_index: int = 0
        self.loaded_definition_steps: List[Dict[str, Any]] = []
        self._current_definition_file: Optional[Path] = None

        # Load initial definition if provided
        if initial_definition:
            self._load_initial_definition(initial_definition)

    def _load_initial_definition(self, definition_path: Path) -> None:
        """Load and execute YAML definition up to last checkpoint"""
        if not definition_path.exists():
            console.print(f"[red]Definition file not found: {definition_path}[/red]")
            return

        try:
            with open(definition_path) as f:
                definition_data = yaml.safe_load(f)

            project_name = definition_data.get("project_name", "Loaded Project")
            console.print(f"[green]Loaded project:[/green] {project_name}")

            # Create database and load from checkpoint if exists
            self.papers_db = PapersDatabase()
            checkpoint_path = (
                self.cache_dir / self.project_id / "checkpoint_last.json"
            )

            if checkpoint_path.exists():
                console.print(f"[green]Loading checkpoint:[/green] {checkpoint_path}")
                self.papers_db.load_checkpoint(checkpoint_path)
                self.step_history.append(
                    f"Loaded checkpoint: {checkpoint_path} ({self.papers_db.count()} papers)"
                )
            else:
                console.print(
                    "[yellow]No checkpoint found, starting with empty database[/yellow]"
                )

            self.results = {
                "project": project_name,
                "papers_loaded": self.papers_db.count(),
                "checkpoint_path": str(checkpoint_path),
            }

        except Exception as e:
            console.print(f"[red]Error loading definition:[/red] {e}")

    def _execute_definition_file(
        self, definition_path: Path, execute: bool = True, verbose: bool = False
    ) -> None:
        """Load YAML definition and optionally execute it"""
        if not definition_path.exists():
            console.print(f"[red]Definition file not found: {definition_path}[/red]")
            return

        # Store the definition file path for status display
        self._current_definition_file = definition_path

        try:
            with open(definition_path) as f:
                definition_data = yaml.safe_load(f)

            project_name = definition_data.get("project_name", "Loaded Project")
            console.print(f"[green]Loaded project:[/green] {project_name}")

            # Initialize database if needed
            if self.papers_db is None:
                self.papers_db = PapersDatabase()

            # Get steps from definition
            steps = definition_data.get("steps", [])
            if not steps:
                console.print("[yellow]No steps found in definition[/yellow]")
                return

            console.print(f"[cyan]Steps in pipeline:[/cyan]")
            for step in steps:
                step_name = next(
                    (k.replace("builtin.", "") for k in step.keys()
                    if k.startswith("builtin.")), None)
                console.print(f"  - {step_name or 'unknown'}")

            if not execute:
                # Store steps for @step command
                self.loaded_definition_steps = steps
                self.current_step_index = 0
                console.print(f"[green]Definition loaded[/green] - {len(steps)} steps ready")
                console.print("[dim]Use[/dim] @step to execute steps one at a time, or @run to execute all")
                return

            # Execute each step
            console.print(f"\n[cyan bold]Executing pipeline...[/cyan bold]\n")

            for i, step_config in enumerate(steps, 1):
                step_config["step_index"] = i - 1
                step_config["project_name"] = project_name

                try:
                    # Create wrapper for step instantiation
                    from paper_scanner.cli.paper_processor import StepExecutor as ProcessorStepExecutor
                    get_step_func = lambda name: ProcessorStepExecutor.get_step(name, self.general_config, self.papers_db, self.cache_dir)

                    result = StepExecutor.execute_step(
                        step_config=step_config,
                        papers_db=self.papers_db,
                        step_executor_func=get_step_func,
                        verbose=verbose or self.verbose,
                        dry_run=False,
                        cache_dir=self.cache_dir,
                        step_index=i - 1,
                        project_name=project_name,
                        project_config=self.general_config,
                        debug=self.debug,
                        builtin_steps=self.builtin_steps,
                    )

                    # Track execution
                    step_name = next(
                        (k.replace("builtin.", "") for k in step_config.keys()
                        if k.startswith("builtin.")), "unknown")
                    
                    status = result.get("status", "unknown")
                    count = result.get("count", 0)
                    
                    if status == "ok":
                        if count > 0:
                            console.print(
                                f"[green]✓[/green] Step {i}: {step_name} - {count} items processed"
                            )
                            self.step_history.append(f"{step_name}: {count} items")
                        else:
                            console.print(
                                f"[green]✓[/green] Step {i}: {step_name}"
                            )
                            self.step_history.append(f"{step_name}: ok")
                    elif status == "error":
                        error_msg = result.get("error", "Unknown error")
                        console.print(
                            f"[red]✗[/red] Step {i}: {step_name} - {error_msg}"
                        )
                        self.step_history.append(f"{step_name}: ERROR - {error_msg}")
                        break
                    else:
                        console.print(
                            f"[yellow]?[/yellow] Step {i}: {step_name} - {status}"
                        )

                    self.results = result

                except Exception as e:
                    console.print(f"[red]Error executing step {i}:[/red] {e}")
                    if self.debug:
                        import traceback
                        traceback.print_exc()
                    break

            console.print(
                f"\n[green]Pipeline complete[/green] - "
                f"{self.papers_db.count()} papers in database"
            )

        except Exception as e:
            console.print(f"[red]Error processing definition:[/red] {e}")
            if self.debug:
                import traceback
                traceback.print_exc()

    def _get_status_line(self) -> str:
        """Build the status line showing DB records, step progress, and definition file"""
        parts = []
        
        # Database record count
        record_count = self.papers_db.count() if self.papers_db else 0
        parts.append(f"[cyan]PaperDB:[/cyan] {record_count} records")
        
        # Step progress (if loaded)
        if self.loaded_definition_steps:
            total = len(self.loaded_definition_steps)
            current = self.current_step_index
            if current == total:
                parts.append(f"[red]All steps completed ({total}/{total})[/red]")
            else:
                parts.append(f"[yellow]Step {current}/{total}[/yellow]")
        
        # Definition file (if loaded)
        if hasattr(self, '_current_definition_file') and self._current_definition_file:
            filename = self._current_definition_file.name
            parts.append(f"[magenta]{filename}[/magenta]")
        
        return " | ".join(parts)

    def _create_namespace(self) -> Dict[str, Any]:
        """Create namespace for Python REPL with helper objects/functions"""
        # Import here to avoid circular imports
        from paper_scanner.definition import Definition

        # Ensure we have a database for this session
        if self.papers_db is None:
            self.papers_db = PapersDatabase()

        def run_step(step_name: str, **config) -> Dict[str, Any]:
            """Helper function to run a single step"""
            return self._execute_step_directly(step_name, config)

        def show_papers(limit: int = 10) -> None:
            """Display current papers in database"""
            if self.papers_db is None:
                console.print("[yellow]No database loaded[/yellow]")
                return

            papers = self.papers_db.papers[: min(limit, len(self.papers_db.papers))]
            console.print(
                f"[cyan]Showing {len(papers)} of {self.papers_db.count()} papers:[/cyan]"
            )
            for i, paper in enumerate(papers, 1):
                console.print(
                    f"  {i}. {paper.title or 'Untitled'} "
                    f"[dim]({paper.doi or 'no DOI'})[/dim]"
                )

        def help_commands() -> None:
            """Display available macro commands"""
            commands = [
                ("@run <file.yml>", "Load and execute a YAML definition file"),
                ("@load <file.yml>", "Load YAML definition (view steps, don't execute)"),
                ("@step", "Execute the next step in a loaded definition"),
                ("@go", "Execute all remaining steps in a loaded definition"),
                ("@checkpoint <label>", "Save checkpoint with label"),
                ("@history", "Show step execution history"),
                ("@show", "Display current papers"),
                ("@export <format> <path>", "Export papers (jsonl, bib, json)"),
                ("@status", "Show session status"),
                ("@help", "Show this message"),
                ("@exit", "Exit REPL"),
            ]

            console.print("[cyan bold]Available Macro Commands (@prefix):[/cyan bold]")
            for cmd, desc in commands:
                console.print(f"  {cmd:<40} - {desc}")

            console.print(
                "\n[cyan bold]Namespace Objects:[/cyan bold]"
            )
            console.print(
                f"  papers_db (PapersDatabase)     - Current papers database"
            )
            console.print(f"  definition (Definition)           - Pipeline builder")
            console.print(f"  results (Dict)                    - Last step results")
            console.print(f"  general_config (Dict)             - Session configuration")

        # Create namespace with full paper_scanner access
        namespace = {
            # Core objects
            "papers_db": self.papers_db,
            "definition": self.definition or Definition(self.project_id),
            "results": self.results,
            "general_config": self.general_config,
            # Helper functions
            "run_step": run_step,
            "show_papers": show_papers,
            "help_commands": help_commands,
            # Imports for convenience
            "Definition": Definition,
            "PapersDatabase": PapersDatabase,
            "json": json,
            "Path": Path,
            "datetime": datetime,
        }

        return namespace

    def _execute_step_directly(
        self, step_name: str, step_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a step directly using StepExecutor"""
        if self.papers_db is None:
            return {"status": "error", "error": "No database initialized"}

        try:
            # Get step class
            step_class = self.builtin_steps.get(step_name)
            if not step_class:
                return {
                    "status": "error",
                    "error": f"Unknown step: {step_name}. Available steps: {list(self.builtin_steps.keys())}",
                }

            # Instantiate step
            step = step_class(
                general_config=self.general_config,
                db=self.papers_db,
                cache_dir=self.cache_dir,
            )

            # Validate config
            is_valid, errors = step.validate(step_config)
            if not is_valid:
                return {"status": "error", "error": f"Validation errors: {errors}"}

            # Execute step
            result = step.execute(
                step_config=step_config,
                verbose=self.verbose,
                dry_run=False,
                debug=self.debug,
            )

            # Track history
            self.step_history.append(
                f"{step_name}: {result.get('count', 0)} items processed"
            )
            self.results = result

            return result

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _parse_macro_command(self, line: str) -> Tuple[str, List[str], Dict[str, str]]:
        """
        Parse @command syntax into command name, positional args, and kwargs

        Format:
            @command arg1 arg2 key1=value1 key2=value2

        Returns:
            (command_name, args, kwargs)
        """
        # Remove @ prefix and split
        tokens = line[1:].split()
        if not tokens:
            return "", [], {}

        command = tokens[0]
        rest = tokens[1:]

        # Separate positional args and kwargs
        args = []
        kwargs = {}

        for token in rest:
            if "=" in token:
                key, value = token.split("=", 1)
                kwargs[key] = value
            else:
                args.append(token)

        return command, args, kwargs

    def _handle_macro_command(self, line: str) -> bool:
        """
        Handle @command macro execution

        Returns:
            True if command was handled, False if should go to Python REPL
        """
        if not line.startswith("@"):
            return False

        command, args, kwargs = self._parse_macro_command(line)

        if command == "run" and args:
            # @run <file.yml> - Load and execute YAML definition
            definition_file = Path(args[0])
            self._execute_definition_file(definition_file, execute=True, verbose=self.verbose)
            return True

        elif command == "load" and args:
            # @load <file.yml> - Load YAML definition without executing
            definition_file = Path(args[0])
            self._execute_definition_file(definition_file, execute=False)
            return True

        elif command == "step":
            # @step - Execute the next step in a loaded definition
            if not self.loaded_definition_steps:
                console.print("[yellow]No definition loaded. Use @load <file.yml> first[/yellow]")
                return True

            if self.current_step_index >= len(self.loaded_definition_steps):
                console.print(
                    f"[yellow]All {len(self.loaded_definition_steps)} steps completed[/yellow]"
                )
                return True

            try:
                step_config = self.loaded_definition_steps[self.current_step_index]
                step_num = self.current_step_index + 1
                total_steps = len(self.loaded_definition_steps)

                # Extract step name from config
                step_name = next(
                    (k.replace("builtin.", "") for k in step_config.keys()
                    if k.startswith("builtin.")), "unknown")

                console.print(
                    f"[cyan]Executing step {step_num}/{total_steps}:[/cyan] "
                    f"{step_name}"
                )

                # Execute the step - create a wrapper function
                from paper_scanner.cli.paper_processor import StepExecutor as ProcessorStepExecutor
                get_step_func = lambda name: ProcessorStepExecutor.get_step(name, self.general_config, self.papers_db, self.cache_dir)

                result = StepExecutor.execute_step(
                    step_config=step_config,
                    papers_db=self.papers_db,
                    step_executor_func=get_step_func,
                    verbose=self.verbose,
                    dry_run=False,
                    cache_dir=self.cache_dir,
                    step_index=self.current_step_index,
                    project_name=self.general_config.get("project_name", "Interactive"),
                    project_config=self.general_config,
                    debug=self.debug,
                    builtin_steps=self.builtin_steps,
                )

                self.current_step_index += 1
                self.step_history.append(
                    f"Step {step_num}: {step_name} - "
                    f"{result.get('status', 'unknown')}"
                )

                if result.get("status") == "error":
                    console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
                else:
                    count = result.get('count', 0)
                    if count > 0:
                        console.print(
                            f"[green]✓ Step completed:[/green] "
                            f"{count} items processed"
                        )
                    else:
                        console.print(f"[green]✓ Step completed[/green]")

            except Exception as e:
                console.print(f"[red]Error executing step:[/red] {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()

            return True

        elif command == "go":
            # @go - Execute all remaining steps in a loaded definition
            if not self.loaded_definition_steps:
                console.print("[yellow]No definition loaded. Use @load <file.yml> first[/yellow]")
                return True

            if self.current_step_index >= len(self.loaded_definition_steps):
                console.print(
                    f"[yellow]All {len(self.loaded_definition_steps)} steps completed[/yellow]"
                )
                return True

            try:
                total_steps = len(self.loaded_definition_steps)
                remaining = total_steps - self.current_step_index
                console.print(
                    f"[cyan bold]Executing {remaining} remaining step(s)...[/cyan bold]\n"
                )

                while self.current_step_index < total_steps:
                    step_config = self.loaded_definition_steps[self.current_step_index]
                    step_num = self.current_step_index + 1

                    # Extract step name from config
                    step_name = next(
                        (k.replace("builtin.", "") for k in step_config.keys()
                        if k.startswith("builtin.")), "unknown")

                    console.print(
                        f"[cyan]Step {step_num}/{total_steps}: {step_name}[/cyan]"
                    )

                    # Execute the step
                    from paper_scanner.cli.paper_processor import StepExecutor as ProcessorStepExecutor
                    get_step_func = lambda name: ProcessorStepExecutor.get_step(name, self.general_config, self.papers_db, self.cache_dir)

                    result = StepExecutor.execute_step(
                        step_config=step_config,
                        papers_db=self.papers_db,
                        step_executor_func=get_step_func,
                        verbose=self.verbose,
                        dry_run=False,
                        cache_dir=self.cache_dir,
                        step_index=self.current_step_index,
                        project_name=self.general_config.get("project_name", "Interactive"),
                        project_config=self.general_config,
                        debug=self.debug,
                        builtin_steps=self.builtin_steps,
                    )

                    self.current_step_index += 1
                    self.step_history.append(
                        f"Step {step_num}: {step_name} - "
                        f"{result.get('status', 'unknown')}"
                    )

                    if result.get("status") == "error":
                        console.print(f"[red]✗ Error:[/red] {result.get('error', 'Unknown error')}")
                        break
                    else:
                        count = result.get('count', 0)
                        if count > 0:
                            console.print(
                                f"[green]✓[/green] {count} items processed"
                            )
                        else:
                            console.print(f"[green]✓ Completed[/green]")

                if self.current_step_index >= total_steps:
                    console.print(
                        f"\n[green bold]All {total_steps} steps completed[/green bold]"
                    )

            except Exception as e:
                console.print(f"[red]Error executing steps:[/red] {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()

            return True

        elif command == "checkpoint" and args:
            # @checkpoint <label>
            label = args[0]
            if self.papers_db is None:
                console.print("[red]No database initialized[/red]")
                return True

            try:
                import json as json_module
                from paper_scanner.io.json import paper_to_dict

                checkpoint_dir = self.cache_dir / self.project_id
                checkpoint_dir.mkdir(parents=True, exist_ok=True)

                checkpoint_path = checkpoint_dir / f"checkpoint_{label}.json"

                # Serialize papers using paper_to_dict to match checkpoint step format
                checkpoint_data = {
                    "project_name": self.project_id,
                    "label": label,
                    "timestamp": datetime.now().isoformat(),
                    "papers_count": self.papers_db.count(primary_only=False),
                    "papers": [
                        paper_to_dict(p, exclude_none=True)
                        for p in self.papers_db.to_list(primary_only=False)
                    ],
                }

                with open(checkpoint_path, "w") as f:
                    json_module.dump(checkpoint_data, f, indent=2)

                console.print(
                    f"[green]Checkpoint saved:[/green] {checkpoint_path} "
                    f"({self.papers_db.count()} papers)"
                )
                self.step_history.append(f"Checkpoint saved: {label}")

            except Exception as e:
                console.print(f"[red]Error saving checkpoint:[/red] {e}")

            return True

        elif command == "show":
            # @show
            show_papers = self._create_namespace()["show_papers"]
            limit = int(args[0]) if args else 10
            show_papers(limit=limit)
            return True

        elif command == "history":
            # @history
            if not self.step_history:
                console.print("[yellow]No steps executed yet[/yellow]")
            else:
                console.print("[cyan bold]Step History:[/cyan bold]")
                for i, entry in enumerate(self.step_history, 1):
                    console.print(f"  {i}. {entry}")
            return True

        elif command == "status":
            # @status
            status_info = {
                "Project ID": self.project_id,
                "Papers in DB": self.papers_db.count() if self.papers_db else 0,
                "Steps Executed": len(self.step_history),
                "Cache Dir": str(self.cache_dir),
            }

            console.print("[cyan bold]Session Status:[/cyan bold]")
            for key, value in status_info.items():
                console.print(f"  {key}: {value}")

            return True

        elif command == "help":
            # @help
            help_func = self._create_namespace()["help_commands"]
            help_func()
            return True

        elif command == "export" and len(args) >= 2:
            # @export <format> <path>
            fmt = args[0]
            output_path = Path(args[1])

            if self.papers_db is None:
                console.print("[red]No database initialized[/red]")
                return True

            try:
                if fmt == "jsonl":
                    # Export as JSONLines
                    with open(output_path, "w") as f:
                        for paper in self.papers_db.papers:
                            f.write(json.dumps(paper.__dict__) + "\n")

                elif fmt == "json":
                    # Export as JSON
                    with open(output_path, "w") as f:
                        json.dump([p.__dict__ for p in self.papers_db.papers], f, indent=2)

                else:
                    console.print(f"[red]Unknown export format: {fmt}[/red]")
                    return True

                console.print(
                    f"[green]Exported {self.papers_db.count()} papers to[/green] {output_path}"
                )
                self.step_history.append(f"Exported to {output_path} ({fmt})")

            except Exception as e:
                console.print(f"[red]Error exporting:[/red] {e}")

            return True

        elif command == "exit":
            # @exit
            console.print("[yellow]Exiting REPL[/yellow]")
            return True  # Return True to indicate command was handled, don't call sys.exit in tests

        else:
            # Unknown command
            console.print(f"[red]Unknown command:[/red] @{command}")
            console.print("[dim]Type @help for available commands[/dim]")
            return True

    def run(self) -> None:
        """Start the interactive REPL session"""
        # Display banner
        console.print("[bold cyan]paper-scanner REPL[/bold cyan]")
        console.print(f"Project: [green]{self.project_id}[/green]")
        console.print(f"Papers DB: {self.papers_db.count() if self.papers_db else 0} papers")
        console.print("[dim]Type @help for macro commands or Ctrl+D to exit[/dim]\n")

        # Create namespace
        namespace = self._create_namespace()

        # Use prompt_toolkit if available for better history/arrow key support
        if HAS_PROMPT_TOOLKIT:
            self._run_with_prompt_toolkit(namespace)
        else:
            self._run_with_basic_input(namespace)

    def _run_with_prompt_toolkit(self, namespace: Dict[str, Any]) -> None:
        """Run REPL with prompt_toolkit for full history and arrow key support"""
        # Create history file in cache directory
        try:
            history_dir = self.cache_dir / self.project_id
            history_dir.mkdir(parents=True, exist_ok=True)
            history_file = history_dir / ".repl_history"
            session = PromptSession(history=FileHistory(str(history_file)))
        except Exception as e:
            if self.debug:
                console.print(f"[yellow]Warning: Could not set up history:[/yellow] {e}")
            session = PromptSession()

        while True:
            try:
                # Show status line
                status_line = self._get_status_line()
                console.print(status_line)
                
                # Get input with history support and arrow keys
                line = session.prompt(">>> ").strip()

                if not line:
                    continue

                # Check if it's a macro command
                if line.startswith("@"):
                    if line.startswith("@exit"):
                        break
                    try:
                        self._handle_macro_command(line)
                    except Exception as e:
                        console.print(f"[red]Error in macro command:[/red] {e}")
                        if self.debug:
                            import traceback
                            traceback.print_exc()
                else:
                    # Execute as Python code
                    try:
                        result = eval(line, namespace)
                        if result is not None:
                            print(repr(result))
                    except SyntaxError:
                        # Try to execute as statement
                        try:
                            exec(line, namespace)
                        except Exception as e:
                            console.print(f"[red]Error executing statement:[/red] {e}")
                            if self.debug:
                                import traceback
                                traceback.print_exc()
                    except Exception as e:
                        console.print(f"[red]Error evaluating expression:[/red] {e}")
                        if self.debug:
                            import traceback
                            traceback.print_exc()

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
            except EOFError:
                break
            except Exception as e:
                console.print(f"[red]Unexpected error in REPL loop:[/red] {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()

    def _run_with_basic_input(self, namespace: Dict[str, Any]) -> None:
        """Fallback REPL using basic input() (readline available on Unix)"""
        try:
            while True:
                try:
                    # Get input from user (readline module enables history on Unix if imported)
                    line = input(">>> ").strip()

                    if not line:
                        continue

                    # Check if it's a macro command
                    if line.startswith("@"):
                        if line.startswith("@exit"):
                            break
                        self._handle_macro_command(line)
                    else:
                        # Execute as Python code
                        try:
                            result = eval(line, namespace)
                            if result is not None:
                                print(repr(result))
                        except SyntaxError:
                            # Try to execute as statement
                            exec(line, namespace)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted[/yellow]")
                except EOFError:
                    break

        except Exception as e:
            console.print(f"[red]REPL Error:[/red] {e}")


def execute_repl(
    project_id: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    definition_file: Optional[Path] = None,
    verbose: bool = False,
    debug: bool = False,
    builtin_steps: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Execute REPL session

    Args:
        project_id: Optional project ID
        cache_dir: Cache directory
        definition_file: Optional YAML definition to load at startup
        verbose: Enable verbose output
        debug: Enable debug output
        builtin_steps: Available builtin steps

    Returns:
        Exit code (0 for success)
    """
    try:
        session = REPLSession(
            project_id=project_id,
            cache_dir=cache_dir,
            initial_definition=definition_file,
            verbose=verbose,
            debug=debug,
            builtin_steps=builtin_steps,
        )

        session.run()
        return 0

    except Exception as e:
        console.print(f"[red bold]REPL Error:[/red bold] {e}")
        return 1
