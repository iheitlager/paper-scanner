#!/usr/bin/env python
"""
08_python_interpreter.py

Pure Python REPL with proper prompt_toolkit integration.

Demonstrates the "micro mode" - direct Python code execution with:
- Multiline input handling (continuation prompt "... ")
- Proper eval/exec distinction
- Session namespace with paper_scanner objects
- Clean prompt_toolkit setup (no readline fallback)

This tests the best practice for handling Python interpreter in prompt_toolkit,
as a foundation for the REPL's micro mode (vs macro mode for \\commands).

Key Features:
- Multiline code completion detection (unclosed brackets, colons, etc)
- Namespace with common objects (Path, json, datetime, etc)
- Exception handling and error display
- History support via FileHistory
- Code validation before execution
"""

import json
import sys
import textwrap
import traceback
from datetime import datetime
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.python import PythonLexer
from rich.console import Console

# Rich console for error/output display
console = Console(file=sys.stderr)


def _is_code_complete(code: str) -> bool:
    """
    Check if Python code is syntactically complete.

    Returns True if code can be executed, False if more input needed.

    Detects:
    - Lines ending with colon (if, for, def, etc)
    - Unclosed brackets, parentheses, braces
    - Unclosed strings
    """
    code = code.strip()
    if not code:
        return True

    # Remove comments
    code_no_comment = code.split('#')[0].rstrip()

    # Lines ending with colon need indentation (for, while, if, def, class, etc)
    if code_no_comment.endswith(':'):
        return False

    # Check for unclosed brackets/parens/braces
    # Count only those not in strings or comments
    open_parens = 0
    open_brackets = 0
    open_braces = 0
    in_string = False
    string_char = None
    i = 0

    while i < len(code_no_comment):
        char = code_no_comment[i]

        # Handle strings
        if char in ('"', "'") and (i == 0 or code_no_comment[i - 1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None

        # Count brackets only outside strings
        if not in_string:
            if char == '(':
                open_parens += 1
            elif char == ')':
                open_parens -= 1
            elif char == '[':
                open_brackets += 1
            elif char == ']':
                open_brackets -= 1
            elif char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1

        i += 1

    # If any brackets are unclosed, need more input
    if open_parens > 0 or open_brackets > 0 or open_braces > 0:
        return False

    try:
        # Try to compile the code
        compile(textwrap.dedent(code), '<input>', 'exec')
        return True
    except SyntaxError as e:
        # "unexpected EOF" means incomplete
        return "unexpected EOF" not in str(e)


class PythonInterpreter:
    """Pure Python REPL with prompt_toolkit"""

    def __init__(
        self,
        cache_dir: Path | None = None,
        debug: bool = False,
        verbose: bool = False,
    ):
        """Initialize interpreter with optional history"""
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.debug = debug
        self.verbose = verbose

        # Session state
        self.namespace = self._create_namespace()
        self.command_history = []

    def _create_namespace(self) -> dict:
        """Create namespace for Python code execution"""
        return {
            # Standard library
            "json": json,
            "Path": Path,
            "datetime": datetime,
            # Session helpers
            "print": print,
            "help": help,
            "dir": dir,
            "type": type,
            "len": len,
            "str": str,
            "int": int,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "range": range,
        }

    def _validate_code(self, code: str) -> tuple[bool, str | None]:
        """
        Validate code before execution.

        Returns:
            (is_valid, error_message)
        """
        try:
            compile(textwrap.dedent(code), '<input>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"Syntax Error: {e.msg} at line {e.lineno}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def _execute_code(self, code: str) -> None:
        """Execute code and handle result appropriately"""
        code_to_exec = textwrap.dedent(code)

        try:
            # Try eval first for single expressions
            try:
                result = eval(code_to_exec, self.namespace)
                if result is not None:
                    console.print(repr(result))
                return
            except SyntaxError:
                # If eval fails (statements, blocks, etc), use exec
                pass

            # Execute as statements/blocks
            exec(code_to_exec, self.namespace)

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {type(e).__name__}: {str(e)}")
            if self.debug:
                traceback.print_exc()

    def run(self) -> None:
        """Main REPL loop with prompt_toolkit"""
        # Setup history file
        history_dir = self.cache_dir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / ".python_repl_history"

        if self.debug:
            console.print(f"[dim]History file: {history_file}[/dim]")

        # Create main session (for >>> prompt with completion)
        main_session = PromptSession(
            completer=WordCompleter(
                list(self.namespace.keys()),
                ignore_case=True,
                sentence=True,
            ),
            history=FileHistory(str(history_file)),
            lexer=PygmentsLexer(PythonLexer),
            enable_history_search=True,
            multiline=False,
            style=Style.from_dict({
                'completion-menu.completion': 'bg:#008888 #ffffff',
                'completion-menu.completion.current': 'bg:#00aaaa #000000',
                'prompt': '#00aa00 bold',
            }),
        )

        # Create continuation session (for ... prompt with auto-indent, no completion)
        # This avoids tab being hijacked by completer during indentation
        continuation_session = PromptSession(
            completer=None,  # No completion during continuation
            history=FileHistory(str(history_file)),
            lexer=PygmentsLexer(PythonLexer),
            enable_history_search=False,
            multiline=False,
            style=Style.from_dict({
                'prompt': '#00aa00 bold',
            }),
        )

        # Display banner
        console.print("[cyan]Python REPL with prompt_toolkit[/cyan]")
        console.print("[dim]Type 'exit()' or Ctrl+D to exit, Ctrl+C to cancel[/dim]\n")

        try:
            while True:
                try:
                    # Get initial line with completion
                    line = main_session.prompt(">>> ")

                    if not line.strip():
                        continue

                    # Multiline input loop
                    accumulated = line
                    while not _is_code_complete(accumulated):
                        if self.debug:
                            console.print("[dim]Code incomplete, waiting for more input...[/dim]")
                        try:
                            # Use continuation session (no completion, tab = indent)
                            continuation = continuation_session.prompt("... ")
                            accumulated += "\n" + continuation
                        except KeyboardInterrupt:
                            console.print("\n[yellow]⚠ Cancelled input[/yellow]")
                            accumulated = ""
                            break

                    if not accumulated.strip():
                        continue

                    # Validate before executing
                    is_valid, error = self._validate_code(accumulated)
                    if not is_valid:
                        console.print(f"[red]{error}[/red]")
                        continue

                    if self.debug:
                        console.print(f"[dim]Executing code: {len(accumulated)} chars[/dim]")

                    # Execute the code
                    self._execute_code(accumulated)
                    self.command_history.append(accumulated)

                except KeyboardInterrupt:
                    console.print("\n[yellow]⚠ Interrupted[/yellow]")
                except EOFError:
                    break

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Keyboard interrupt[/yellow]")
        finally:
            console.print("\n[cyan]Goodbye![/cyan]")

    def run_file(self, file_path: Path) -> None:
        """Execute Python code from a file"""
        if not file_path.exists():
            console.print(f"[red]File not found:[/red] {file_path}")
            return

        try:
            with open(file_path) as f:
                code = f.read()

            if self.debug:
                console.print(f"[dim]Executing {file_path}[/dim]")

            self._execute_code(code)
        except Exception as e:
            console.print(f"[red]Error:[/red] {type(e).__name__}: {str(e)}")
            if self.debug:
                traceback.print_exc()


def demo_basic():
    """Demo: Basic Python expressions and statements"""
    console.print("[bold cyan]Demo: Basic Expressions and Statements[/bold cyan]\n")

    interpreter = PythonInterpreter(debug=True)

    # Simulate user input
    test_inputs = [
        ("2 + 2", "Simple expression"),
        ("x = [1, 2, 3]\nprint(f'List: {x}')", "Multiline with statement"),
        ('d = {"key": "value"}', "Dictionary"),
        ("if True:\n    print('Block statement works!')", "If block statement"),
        ("for i in range(3):\n    print(f'i={i}')", "For loop block"),
    ]

    for code, description in test_inputs:
        console.print(f"[blue]→ {description}[/blue]")
        console.print(f"[dim]{code}[/dim]")
        interpreter._execute_code(code)
        console.print()


def demo_multiline():
    """Demo: Multiline code completion detection"""
    console.print("[bold cyan]Demo: Multiline Code Detection[/bold cyan]\n")

    test_cases = [
        ("x = 1", True, "Simple assignment"),
        ("if x > 0:", False, "If statement (incomplete)"),
        ("if x > 0:\n    print('positive')", True, "If statement (complete)"),
        ("def greet(name):", False, "Function def (incomplete)"),
        ("def greet(name):\n    return f'Hello {name}'", True, "Function def (complete)"),
        ("[1, 2,", False, "Unclosed bracket"),
        ("[1, 2, 3]", True, "Closed bracket"),
        ("x = (1 +", False, "Unclosed paren"),
        ("x = (1 + 2)", True, "Closed paren"),
    ]

    for code, expected, description in test_cases:
        is_complete = _is_code_complete(code)
        status = "✓" if is_complete == expected else "✗"
        complete_str = "complete" if is_complete else "incomplete"
        console.print(f"[cyan]{status}[/cyan] {description}")
        console.print(f"  [dim]{code!r} → {complete_str}[/dim]")

    console.print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Pure Python REPL with prompt_toolkit"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        help="Execute file instead of starting REPL"
    )
    parser.add_argument(
        "--demo-basic",
        action="store_true",
        help="Run basic demo"
    )
    parser.add_argument(
        "--demo-multiline",
        action="store_true",
        help="Run multiline detection demo"
    )

    args = parser.parse_args()

    if args.demo_basic:
        demo_basic()
    elif args.demo_multiline:
        demo_multiline()
    elif args.file:
        interpreter = PythonInterpreter(debug=args.debug, verbose=args.verbose)
        interpreter.run_file(args.file)
    else:
        interpreter = PythonInterpreter(debug=args.debug, verbose=args.verbose)
        interpreter.run()
