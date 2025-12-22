r"""REPL task - Interactive shell for paper-scanner pipelines

Provides an interactive Python REPL with macro commands (\command syntax) for
running paper-scanner steps via the Definition API, combined with micro mode
(direct Python code) for full programmatic access.

Two modes of interaction:
- Macro mode: \command prefix for predefined operations (e.g., \run, \export)
- Micro mode: Plain Python code with full access to paper_scanner modules
"""

import json
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from rich.console import Console

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.lexers import PygmentsLexer
    from prompt_toolkit.styles import Style
    from prompt_toolkit.validation import ValidationError, Validator
    from pygments.lexers.python import PythonLexer
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    # Try readline for basic history support on Unix systems
    try:
        import readline
    except ImportError:
        pass

from paper_scanner.cli.tasks.run import StepExecutor
from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.halt import HaltException

console = Console(file=sys.stderr)


def _is_code_complete(code: str) -> bool:
    """Check if Python code is syntactically complete."""
    code = code.strip()
    if not code:
        return True
    
    # Remove comments to check for colon properly
    code_no_comment = code.split('#')[0].rstrip()
    
    # Check for lines that require indentation (end with colon)
    # This catches: for, while, if, elif, else, def, class, with, try, except, finally
    if code_no_comment.endswith(':'):
        return False
    
    try:
        # Try to compile the dedented code
        compile(textwrap.dedent(code), '<input>', 'exec')
        return True
    except SyntaxError as e:
        # "unexpected EOF" indicates incomplete code (e.g., unclosed parenthesis, colon without body)
        return "unexpected EOF" not in str(e)


class REPLSession:
    """Interactive REPL session for paper-scanner pipelines"""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        verbose: bool = False,
        debug: bool = False,
        builtin_steps: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize REPL session

        Args:
            cache_dir: Cache directory for checkpoints
            initial_definition: Optional YAML file to load at startup (post-checkpoint)
            verbose: Enable verbose output
            debug: Enable debug output
            quit_after_definition: Quit immediately after executing definition (no interactive mode)
            builtin_steps: Available builtin steps registry
        """
        self.project_name = "interactive_session"
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.verbose = verbose
        self.debug = debug
        self.builtin_steps = builtin_steps or {}

        # Session state
        self.papers_db: Optional[PapersDatabase] = None
        self.general_config: Dict[str, Any] = {
            "project_name": self.project_name,
            "cache_dir": str(self.cache_dir),
        }
        self.results: Dict[str, Any] = {}
        self.step_history: List[str] = []
        self.current_step_index: int = 0
        self.loaded_definition: List[Dict[str, Any]] = []
        self._current_definition_file: Optional[Path] = None



    def load_initial_definition(self, definition_path: Path) -> bool:
        """Load and execute YAML definition up to last checkpoint"""
        if not definition_path.exists():
            raise FileNotFoundError(f"Definition file not found: {definition_path}")

        # Store the definition file path for status display
        self._current_definition_file = definition_path

        try:
            # Create database and load from checkpoint if exists
            self.papers_db = PapersDatabase()

            checkpoint_path = (self.cache_dir / "checkpoint_last.json")
            if checkpoint_path.exists():
                console.print(f"[green]Loading checkpoint:[/green] {checkpoint_path}")
                self.papers_db.load_checkpoint(checkpoint_path)
                self.step_history.append(
                    f"Loaded checkpoint: {checkpoint_path} ({self.papers_db.count()} papers)"
                )

            with open(definition_path) as f:
                self.loaded_definition = yaml.safe_load(f)

            self.current_step_index = 0
            self.project_name = self.loaded_definition.get("project", {}).get("name")
            self.general_config["project_name"] = self.project_name
            steps = self.loaded_definition.get("steps", [])
            if not steps:
                console.print("[yellow]No steps found in definition[/yellow]")
                return
            self.loaded_definition_steps = steps
            if self.debug:
                console.print(f"[dim]Loaded project: {definition_path} with {len(steps)} steps[/dim]")
            return True
        except Exception as e:
            console.print(f"[red]Error loading definition:[/red] {e}")
            return False

    def execute_definition_file(self) -> None:
        """Execute preloaded YAML definition"""
        # Initialize database if needed
        if self.papers_db is None:
            self.papers_db = PapersDatabase()

        # Get steps from definition
        steps = self.loaded_definition_steps
        if not steps:
            console.print("[yellow]No steps found in definition[/yellow]")
            return

        if self.verbose:
            console.print(f"[cyan]Steps in pipeline:[/cyan]")
            for step in steps:
                step_name = next(
                    (k.replace("builtin.", "") for k in step.keys()
                    if k.startswith("builtin.")), None)
                console.print(f"  - {step_name or 'unknown'}")
        try:
            # Execute each step
            if self.verbose:
                console.print(f"\n[cyan bold]Executing pipeline...[/cyan bold]\n")

            for i, step_config in enumerate(steps, 1):
                step_config["step_index"] = i - 1
                step_config["project_name"] = self.project_name

                # Create wrapper for step instantiation
                from paper_scanner.cli.paper_processor import \
                    StepExecutor as ProcessorStepExecutor
                get_step_func = lambda name: ProcessorStepExecutor.get_step(name, self.general_config, self.papers_db, self.cache_dir)

                result = StepExecutor.execute_step(
                    step_config=step_config,
                    papers_db=self.papers_db,
                    step_executor_func=get_step_func,
                    verbose=self.verbose,
                    dry_run=False,
                    cache_dir=self.cache_dir,
                    step_index=i - 1,
                    project_name=self.project_name,
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


            console.print(
                f"\n[green]Pipeline complete[/green] - "
                f"{self.papers_db.count()} papers in database"
            )

        except HaltException as e:
            # Pipeline halted gracefully
            console.print(f"[yellow]⏸ Pipeline halted:[/yellow] {e}")
            console.print(
                f"[cyan]Papers in database:[/cyan] {self.papers_db.count()} "
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
                ("\\run <file.yml>", "Load and execute a YAML definition file"),
                ("\\load <file.yml>", "Load YAML definition (view steps, don't execute)"),
                ("\\step, \\n", "Execute the next step in a loaded definition"),
                ("\\go, \\g", "Execute all remaining steps in a loaded definition"),
                ("\\do, \\d <step> {params}", "Execute ad-hoc step with parameters"),
                # ("  Examples:", ""),
                # ("    \\do summarize summary=true", "Simple parameter"),
                # ("    \\do summarize tabulate[field=paper_type]", "Nested config"),
                # ("    \\do summarize tabulate[field=paper_type,duplicates=false]", "Multiple nested params"),
                ("\\checkpoint <label>", "Save checkpoint with label"),
                ("\\history, \\h", "Show step execution history"),
                ("\\show, \\p", "Display current papers"),
                ("\\export <format> <path>", "Export papers (jsonl, bib, json)"),
                ("\\status, \\s", "Show session status"),
                ("\\help, \\?", "Show this message"),
                ("\\exit, \\q", "Exit REPL"),
            ]

            console.print(r"[cyan bold]Available Macro Commands (\prefix):[/cyan bold]")
            for cmd, desc in commands:
                if desc:
                    console.print(f"  {cmd:<40} - {desc}")
                else:
                    console.print(f"  {cmd:<40}")

            console.print(
                "\n[cyan bold]Namespace Objects:[/cyan bold]"
            )
            console.print(
                f"  papers_db (PapersDatabase)        - Current papers database"
            )
            console.print(f"  db (alias)                        - Shorthand for papers_db")
            console.print(f"  results (Dict)                    - Last step results")
            console.print(f"  general_config (Dict)             - Session configuration")

        # Create namespace with full paper_scanner access
        namespace = {
            # Core objects
            "papers_db": self.papers_db,
            "db": self.papers_db,  # Alias for papers_db
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

    def _parse_macro_command(self, line: str) -> Tuple[str, List[str], Dict[str, Any]]:
        r"""
        Parse \command syntax into command name, positional args, and kwargs

        Format:
            \command arg1 arg2 key1=value1 key2=value2
            \command arg1 nested[key1=val1,key2=val2]

        Shortcuts:
            d -> do, g -> go, h -> history, s -> status, ? -> help, p -> show, q -> exit

        Returns:
            (command_name, args, kwargs)
        """
        # Shortcut mappings
        shortcuts = {
            "d": "do",
            "g": "go",
            "h": "history",
            "n": "step",
            "s": "status",
            "?": "help",
            "p": "show",
            "q": "exit",
        }

        # Remove \ prefix and split
        tokens = line[1:].split()
        if not tokens:
            return "", [], {}

        command = tokens[0]
        
        # Expand shortcuts
        if command in shortcuts:
            command = shortcuts[command]
        
        rest = tokens[1:]

        # Separate positional args and kwargs
        args = []
        kwargs = {}

        for token in rest:
            # Check for nested config: key[nested_params]
            if "[" in token and "]" in token:
                match = re.match(r"(\w+)\[(.*)\]", token)
                if match:
                    key = match.group(1)
                    nested_str = match.group(2)
                    
                    # Parse nested parameters
                    nested_config = {}
                    for param in nested_str.split(","):
                        if "=" in param:
                            k, v = param.split("=", 1)
                            nested_config[k.strip()] = v.strip()
                    
                    kwargs[key] = nested_config if nested_config else True
                    continue
            
            if "=" in token:
                key, value = token.split("=", 1)
                kwargs[key] = value
            else:
                args.append(token)

        return command, args, kwargs

    def _handle_macro_command(self, line: str) -> bool:
        r"""
        Handle \command macro execution

        Returns:
            True if command was handled, False if should go to Python REPL
        """
        if not line.startswith("\\"):
            return False

        command, args, kwargs = self._parse_macro_command(line)

        if command == "run" and args:
            # \run <file.yml> - Load and execute YAML definition
            definition_file = Path(args[0])
            self._execute_definition_file(definition_file, execute=True, verbose=self.verbose)
            return True

        elif command == "load" and args:
            # \load <file.yml> - Load YAML definition without executing
            definition_file = Path(args[0])
            self._execute_definition_file(definition_file, execute=False)
            return True

        elif command == "do" and args:
            # \do <step_name> [params] - Execute ad-hoc step with parameters
            step_name = args[0]
            
            # Convert string values to appropriate types
            def parse_value(v: Any) -> Any:
                """Parse values to Python types"""
                if isinstance(v, dict):
                    # Recursively parse nested dictionaries
                    return {k: parse_value(val) for k, val in v.items()}
                if not isinstance(v, str):
                    return v
                if v.lower() == "true":
                    return True
                elif v.lower() == "false":
                    return False
                elif v.lower() == "none" or v == "":
                    return None
                elif v.isdigit():
                    return int(v)
                else:
                    try:
                        return float(v)
                    except ValueError:
                        return v
            
            # Build config from kwargs, parsing values appropriately
            step_config = {k: parse_value(v) for k, v in kwargs.items()}
            
            if self.papers_db is None:
                console.print("[yellow]No database. Initialize with papers first.[/yellow]")
                return True
            
            try:
                console.print(f"[cyan]Executing step:[/cyan] {step_name}")
                if step_config:
                    console.print(f"[dim]Parameters: {step_config}[/dim]")
                
                # Execute the step
                from paper_scanner.cli.paper_processor import \
                    StepExecutor as ProcessorStepExecutor

                # Build step config with required "step" key and builtin. prefix
                # Format: {"step": "<description>", "builtin.{step_name}": {params}}
                full_step_config = {
                    "step": f"Ad-hoc: {step_name}",
                    f"builtin.{step_name}": step_config
                }
                
                get_step_func = lambda name: ProcessorStepExecutor.get_step(name, self.general_config, self.papers_db, self.cache_dir)
                
                result = StepExecutor.execute_step(
                    step_config=full_step_config,
                    papers_db=self.papers_db,
                    step_executor_func=get_step_func,
                    verbose=self.verbose,
                    dry_run=False,
                    cache_dir=self.cache_dir,
                    step_index=len(self.step_history),
                    project_name=self.general_config.get("project_name", "Interactive"),
                    project_config=self.general_config,
                    debug=self.debug,
                    builtin_steps=self.builtin_steps,
                )
                
                self.step_history.append(f"Ad-hoc: {step_name} - {result.get('status', 'unknown')}")
                self.results = result
                
                if result.get("status") == "error":
                    console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
                else:
                    count = result.get('count', 0)
                    if count > 0:
                        console.print(f"[green]✓ Step completed:[/green] {count} items processed")
                    else:
                        console.print(f"[green]✓ Step completed[/green]")
            
            except Exception as e:
                console.print(f"[red]Error executing step:[/red] {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
            
            return True

        elif command == "step":
            # \step - Execute the next step in a loaded definition
            if not self.loaded_definition_steps:
                console.print(r"[yellow]No definition loaded. Use \load <file.yml> first[/yellow]")
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
                from paper_scanner.cli.paper_processor import \
                    StepExecutor as ProcessorStepExecutor
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
            # \go - Execute all remaining steps in a loaded definition
            if not self.loaded_definition_steps:
                console.print(r"[yellow]No definition loaded. Use \load <file.yml> first[/yellow]")
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
                    from paper_scanner.cli.paper_processor import \
                        StepExecutor as ProcessorStepExecutor
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
            # \checkpoint <label>
            label = args[0]
            if self.papers_db is None:
                console.print("[red]No database initialized[/red]")
                return True

            try:
                import json as json_module

                from paper_scanner.io.json import paper_to_dict

                checkpoint_dir = self.cache_dir / "checkpoints"
                checkpoint_dir.mkdir(parents=True, exist_ok=True)

                checkpoint_path = checkpoint_dir / f"checkpoint_{label}.json"

                # Serialize papers using paper_to_dict to match checkpoint step format
                checkpoint_data = {
                    "project_name": self.project_name,
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
            # \show
            show_papers = self._create_namespace()["show_papers"]
            limit = int(args[0]) if args else 10
            show_papers(limit=limit)
            return True

        elif command == "history":
            # \history
            if not self.step_history:
                console.print("[yellow]No steps executed yet[/yellow]")
            else:
                console.print("[cyan bold]Step History:[/cyan bold]")
                for i, entry in enumerate(self.step_history, 1):
                    console.print(f"  {i}. {entry}")
            return True

        elif command == "status":
            # \status
            status_info = {
                "Project Name": self.project_name,
                "Papers in DB": self.papers_db.count() if self.papers_db else 0,
                "Steps Executed": len(self.step_history),
                "Cache Dir": str(self.cache_dir),
            }

            console.print("[cyan bold]Session Status:[/cyan bold]")
            for key, value in status_info.items():
                console.print(f"  {key}: {value}")

            return True

        elif command == "help":
            # \help
            help_func = self._create_namespace()["help_commands"]
            help_func()
            return True

        elif command == "export" and len(args) >= 2:
            # \export <format> <path>
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
            # \exit
            console.print("[yellow]Exiting REPL[/yellow]")
            return True  # Return True to indicate command was handled, don't call sys.exit in tests

        else:
            # Unknown command
            console.print(rf"[red]Unknown command:[/red] \{command}")
            console.print(r"[dim]Type \help for available commands[/dim]")
            return True

    def run(self) -> None:
        """Start the interactive REPL session"""
        # Display banner
        console.print(f"Project: [green]{self.project_name}[/green]")
        console.print(r"[dim]Type \help for macro commands or Ctrl+D to exit[/dim]" + "\n")

        # Create namespace
        namespace = self._create_namespace()

        # Use prompt_toolkit if available for better history/arrow key support
        if HAS_PROMPT_TOOLKIT:
            self._run_with_prompt_toolkit(namespace)
        else:
            self._run_with_basic_input(namespace)

    def _run_with_prompt_toolkit(self, namespace: Dict[str, Any]) -> None:
        """Run REPL with prompt_toolkit for full history and arrow key support"""
        if self.debug:
            console.print("[dim]Using prompt_toolkit for REPL[/dim]")
        
        # Setup history file with manual persistence
        session = None
        history_file = None
        history_obj = None
        try:
            history_dir = self.cache_dir
            history_dir.mkdir(parents=True, exist_ok=True)
            # Use single shared history file for all sessions (not per-project)
            history_file = history_dir / ".repl_history"
            if self.debug:
                console.print(f"[dim]History file: {history_file}[/dim]")
                console.print(f"[dim]History file exists: {history_file.exists()}[/dim]")
                if history_file.exists():
                    console.print(f"[dim]History file size: {history_file.stat().st_size} bytes[/dim]")
            
            # Create FileHistory object
            history_obj = FileHistory(str(history_file))
            
            session = PromptSession(
                completer=WordCompleter([], ignore_case=True),
                style=Style.from_dict({
                    'completion-menu.completion': 'bg:#008888 #ffffff',
                    'completion-menu.completion.current': 'bg:#00aaaa #000000',
                    'prompt': '#00aa00 bold',
                }),
                history=history_obj,
                lexer=PygmentsLexer(PythonLexer),
                enable_history_search=True,
                validate_while_typing=True,
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not set up history:[/yellow] {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            try:
                session = PromptSession(lexer=PygmentsLexer(PythonLexer))
            except Exception:
                session = PromptSession()

        try:
            while True:
                try:
                    # Show status line
                    status_line = self._get_status_line()
                    console.print(status_line)
                    
                    # Get input - let prompt_toolkit handle history
                    line = session.prompt(">>> ")

                    if line.startswith("\\exit") or line.startswith("\\q") or line.strip() in ("exit()", "quit()", "quit", "exit", "x", "bye"):
                        if self.debug:
                            console.print("[dim]Exiting REPL loop[/dim]")
                        break
                    elif line.startswith("\\"):
                        self._handle_macro_command(line.strip())
                        continue

                    # Accumulate multiline input manually for incomplete code
                    accumulated = line
                    while not _is_code_complete(accumulated):
                        try:
                            # Calculate indentation for next line
                            last_line = accumulated.split('\n')[-1]
                            if last_line.rstrip().endswith(':'):
                                indent_level = len(last_line) - len(last_line.lstrip()) + 4
                            else:
                                indent_level = 0
                            
                            # Get continuation line with indentation prompt
                            indent_str = " " * indent_level
                            continuation = session.prompt(f"... {indent_str}")
                            accumulated += "\n" + indent_str + continuation
                        except EOFError:
                            break
                    
                    if not accumulated.strip():
                        continue

                    # Execute as Python code (supports multiline)
                    # Dedent the code to handle indented blocks properly
                    code_to_exec = textwrap.dedent(accumulated)
                    # Try eval first (for expressions)
                    result = eval(code_to_exec, namespace)
                    if result is not None:
                        print(repr(result))
                except SyntaxError as e:
                    # Fall back to exec for statements
                    try:
                        exec(code_to_exec, namespace)
                    except SyntaxError as syntax_err:
                        # Show syntax error with details
                        console.print(f"[red]SyntaxError:[/red] {syntax_err.msg}")
                        if syntax_err.text:
                            console.print(f"  {syntax_err.text.rstrip()}")
                        if syntax_err.offset:
                            console.print(f"  {' ' * (syntax_err.offset - 1)}^")
                        if self.debug:
                            import traceback
                            traceback.print_exc()
                    except Exception as e:
                        console.print(f"[red]Error:[/red] {e}")
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
        finally:
            # Ensure history is flushed
            if history_obj is not None:
                try:
                    # Force flush of the history object
                    if hasattr(history_obj, '_file_obj') and history_obj._file_obj:
                        history_obj._file_obj.flush()
                    if self.debug:
                        console.print(f"[dim]History flushed[/dim]")
                except Exception as e:
                    if self.debug:
                        console.print(f"[yellow]Warning: Could not flush history:[/yellow] {e}")

    def _run_with_basic_input(self, namespace: Dict[str, Any]) -> None:
        """Fallback REPL using basic input() (readline available on Unix)"""
        if self.debug:
            console.print("[dim]Using basic input() for REPL[/dim]")

        while True:
            try:
                # Get input
                line = input(">>> ").strip()

                if not line:
                    continue
                
                # Handle multiline input by accumulating lines until we have complete code
                accumulated = line
                indent_level = 0
                while not _is_code_complete(accumulated):
                    try:
                        # Calculate indentation for next line
                        last_line = accumulated.split('\n')[-1]
                        if last_line.rstrip().endswith(':'):
                            indent_level = len(last_line) - len(last_line.lstrip()) + 4

                        # Build prompt with indentation as visual cue
                        indent_str = " " * indent_level
                        continuation = input(f"... {indent_str}")
                        # Prepend indentation to the user's input
                        if not continuation.strip():
                            break
                        accumulated += "\n" + indent_str + continuation
                    except EOFError:
                        break

                # Check if it's a macro command
                first_line = accumulated.split('\n')[0] if '\n' in accumulated else accumulated
                if first_line.startswith("\\"):
                    if first_line.startswith("\\exit") or first_line.startswith("\\q"):
                        break
                    self._handle_macro_command(first_line.strip())
                else:
                    # Execute as Python code
                    code_to_exec = textwrap.dedent(accumulated)
                    try:
                        result = eval(code_to_exec, namespace)
                        if result is not None:
                            print(repr(result))
                    except SyntaxError as e:
                        # Try to execute as statement
                        try:
                            exec(code_to_exec, namespace)
                        except SyntaxError as syntax_err:
                            console.print(f"[red]SyntaxError:[/red] {syntax_err.msg}")
                            if syntax_err.text:
                                console.print(f"  {syntax_err.text.rstrip()}")
                                if syntax_err.offset:
                                    console.print(f"  {' ' * (syntax_err.offset - 1)}^")
                        except Exception as ex:
                            console.print(f"[red]Error:[/red] {ex}")
                    except Exception as ex:
                        console.print(f"[red]Error:[/red] {ex}")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
            except EOFError:
                break



def execute_repl(
    cache_dir: Optional[Path] = None,
    definition_file: Optional[Path] = None,
    auto_run: bool = False,
    verbose: bool = False,
    debug: bool = False,
    quit_after_definition: bool = False,
    builtin_steps: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Execute REPL session
        cache_dir: Cache directory
        definition_file: Optional YAML definition to load at startup
        verbose: Enable verbose output
        debug: Enable debug output
        quit_after_definition: Quit immediately after executing definition (no interactive mode)
        builtin_steps: Available builtin steps

    Returns:
        Exit code (0 for success)
    """
    session = REPLSession(
        cache_dir=cache_dir,
        verbose=verbose,
        debug=debug,
        builtin_steps=builtin_steps,
    )

    if session.load_initial_definition(definition_file) and auto_run:
        session.execute_definition_file()
        if quit_after_definition:
            console.print(
                "[green]Definition execution complete.[/green] "
                "Exiting REPL as --quit mode is enabled."
            )
            sys.exit(0)

    session.run()
