#!/usr/bin/env python
"""
03_single_step_mode.py

Demonstrates single-step execution mode for interactive/REPL usage.

In single-step mode:
- You execute one step at a time
- You control checkpointing explicitly
- You have full access to session state between steps
- Steps before checkpoint are skipped

This is ideal for interactive exploration and debugging.

Controls:
- CTRL-C: Stop current operation gracefully
- CTRL-D: Exit REPL (or type 'quit')
- ↑/↓: Command history (readline)
"""

import argparse
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from paper_scanner.cli.executor import StepExecutor
from paper_scanner.core.enum import StepStatus

# Enable readline history and tab completion (optional, not available on all platforms)
try:
    import readline
    readline.parse_and_bind('tab: complete')
except ImportError:
    pass

# Rich console
console = Console(file=sys.stderr)


def beautiful_header():
    """Print a header for the REPL."""
    console.print(Panel(
        "[bold cyan]📊 StepExecutor Interactive Mode (Single-Step)[/bold cyan]",
        box=box.SQUARE,
        padding=(0, 2)
    ))
    console.print()


def beautiful_menu():
    """Print a beautifully formatted menu."""
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Command", style="green")
    table.add_column("Description")
    
    commands = [
        ("step", "Execute next step"),
        ("run", "Execute all remaining steps"),
        ("checkpoint", "Save checkpoint"),
        ("steps", "List loaded steps and templates"),
        ("stats", "Show execution statistics"),
        ("state", "Show current session state"),
        ("history", "Show command history"),
        ("help", "Show this menu"),
        ("quit", "Exit REPL"),
    ]
    
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    
    console.print("[bold]Available Commands:[/bold]")
    console.print(table)
    console.print()


def main(debug: bool = False, verbose: bool = False, timings: bool = False):
    """Interactive REPL for single-step execution."""
    
    def display_step_result(index, step_config, result):
        """
        Display step execution result in consistent format.
        
        Args:
            result: Step execution result dict
            step_info: Optional step info dict (for single-step mode)
            mode: 'step' (single-step) or 'batch' (batch mode)
        """
        if not result:
            raise ValueError("No result provided to display_step_result")

        if debug:
            console.print(f"[dim]Debug: Full result: {result}[/dim]")
            console.print(f"[dim]Step config: {step_config}[/dim]")

        status = result.get('status') if result else None
        if not status:
            raise ValueError("Result missing 'status' key in display_step_result")

        step_name = step_config["description"] if step_config else result.get('step', 'Unknown')
       # Always show halt and error status
        if status == StepStatus.HALTED:
            console.print(f"[yellow]⏸ halted[/yellow]")
            return
        elif status == StepStatus.ERROR:
            console.print(f"[red]✗ ERROR: {result.get('error', 'Unknown error')}[/red]")
            return
        elif status == StepStatus.SUCCESS:
            if verbose:
                step_name = step_config["description"] if step_config else result.get('step', 'Unknown')

                count = result.get('papers_imported') or result.get('count', 0)
                console.print(f"[green]✓[/green] [white]{step_name}[/white] completed")
                if count > 0:
                    console.print(f"  [cyan]Items:[/cyan] [white]{count}[/white]")
        else:
            console.print(f"[yellow]⚠️: {status.value} {step_name} - {result.get('message', '')}[/yellow] ")
            count = result.get('papers_imported') or result.get('count', 0)
            if count > 0:
                console.print(f"  [cyan]Processed:[/cyan] {count} items")
        if timings and 'duration_seconds' in result:
            duration = result['duration_seconds']
            console.print(f"  [cyan]Duration:[/cyan] [white]{duration:.2f}s[/white]")


    beautiful_header()
    
    if debug:
        console.print("[yellow]⚠ Debug mode enabled - verbose output will be shown[/yellow]")
    
    if verbose:
        console.print("[blue]ℹ Verbose mode enabled - showing step details before execution[/blue]")
    
    # Load definition
    definition_path = Path(__file__).parent / "test_definition.yml"
    
    console.print(f"[blue]ℹ Loading definition:[/blue] [white]{definition_path}[/white]")
    
    if not definition_path.exists():
        console.print(f"[red]✗ Definition file not found: {definition_path}[/red]")
        sys.exit(1)
    
    # Setup config
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    
    # Initialize executor (self-contained with lazy step loading)
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=verbose,
        debug=debug,
    )
    
    executor.load_definition(definition_path)
    
    if not executor.has_steps:
        console.print("[red]✗ No steps loaded from definition[/red]")
        sys.exit(1)
    
    current, total = executor.step_progress
    console.print(f"[green]✓[/green] Loaded [white]{total}[/white] steps from definition\n")
    
    command_history = []
    
    while True:
        try:
            # Calculate progress
            current, total = executor.step_progress
            prompt = f"[bold blue][{current}/{total}] > [/bold blue]"
            
            console.print(prompt, end="")
            cmd = input().strip().lower()
            
            if not cmd:
                continue
            
            command_history.append(cmd)
            
            # Execute commands
            if cmd == "step":
                if not executor.has_next_step:
                    console.print("[yellow]⚠ All steps already completed![/yellow]\n")
                    continue
                
                # Show step info before execution if verbose
                step_info = executor.describe_next_step()
                if verbose:
                    if step_info["is_template"]:
                        console.print(f"\n[cyan]Executing:[/cyan] [white]{step_info['description']}[/white] [dim](template: {step_info['template_name']})[/dim]")
                    else:
                        console.print(f"\n[cyan]Executing:[/cyan] [white]{step_info['description']}[/white] [dim](builtin.{step_info['name']})[/dim]")
                else:
                    # Show step description and type even in normal mode
                    step_type = f"template: {step_info['template_name']}" if step_info["is_template"] else f"builtin: {step_info['name']}"
                    console.print(f"[blue]ℹ {step_info['description']}[/blue] [dim]({step_type})[/dim]")
                
                prev_index = step_info["index"]
                result = executor.execute_next_step(dry_run=False)
                
                # Track how many steps were actually executed
                new_index = executor.current_step_index
                steps_executed = new_index - prev_index
                
                if debug and result:
                    console.print(f"[dim]Debug: Executed from step {prev_index} to {new_index} ({steps_executed} step(s))[/dim]")
                    console.print(f"[dim]Debug: Full result: {result}[/dim]\n")
                
                # Show what was executed
                if steps_executed > 1:
                    console.print(f"  [blue]ℹ Auto-advanced {steps_executed} step(s)[/blue]")
                
                # Display result information using unified function
                display_step_result(new_index, step_info, result)
                
                # Check if all steps are now completed
                if not executor.has_next_step:
                    console.print(f"[green bold]🎉 All steps completed![/green bold]\n")
            
            elif cmd == "run" or cmd == "go":
                if not executor.has_next_step:
                    console.print("[yellow]⚠ All steps already completed![/yellow]\n")
                    continue
                
                current, total = executor.step_progress
                remaining = total - current
                if verbose:
                    console.print(f"\n[blue]ℹ Running {remaining} remaining step(s)...[/blue]\n")
                
                # Track step count for display
                step_count = [0]
                
                def on_step_start(idx, step_config, total):
                    step_count[0] += 1
                    step_desc = step_config.get('step', 'Unknown')
                    step_info = executor.describe_next_step()
                    msg = f"[{step_count[0]}/{remaining}]"
                    if step_info:
                        # Show step info in all modes (normal/verbose/debug)
                        step_type = f"template: {step_info['template_name']}" if step_info["is_template"] else f"builtin: {step_info['name']}"
                        msg +=  f" {step_info['description']}"
                        if verbose or debug:
                            msg += f" [dim]({step_type})[/dim]"
                    else:
                        msg += f"{step_desc}..."
                    console.print(msg)

                _ = executor.run_all(
                    dry_run=False,
                    on_step_start=on_step_start,
                    on_step_end=display_step_result
                )
            
            elif cmd == "steps":
                console.print("\n[bold]📋 Pipeline Steps:[/bold]")
                
                # Show templates
                if executor.templates:
                    console.print(f"\n[cyan]Templates ({len(executor.templates)}):[/cyan]")
                    for template_name, template_steps in executor.templates.items():
                        console.print(f"  • [white]{template_name}[/white] [dim]({len(template_steps)} steps)[/dim]")
                
                # Show main steps
                if executor.steps:
                    console.print(f"\n[cyan]Main Steps ({len(executor.steps)}):[/cyan]")
                    for i, step_config in enumerate(executor.steps):
                        step_name = list(step_config.keys())[0] if step_config else "unknown"
                        step_desc = step_config.get('step', 'No description')
                        status = "✓" if i < executor.current_step_index else " "
                        status_color = "dim" if status == " " else "green"
                        console.print(f"  [white]{i}: \\[[/white][{status_color}]{status}[/{status_color}][white]] {step_desc}[/white]")
                console.print()
            
            elif cmd == "checkpoint":
                console.print("\n[blue]ℹ Saving checkpoint...[/blue]")
                result = executor.checkpoint()
                if result['status'] == 'ok':
                    console.print(f"[green]✓[/green] [white]Checkpoint saved[/white]")
                    console.print(f"  [cyan]File:[/cyan] [white]{result.get('checkpoint_file', 'unknown')}[/white]")
                    console.print(f"  [cyan]Papers:[/cyan] [white]{result.get('papers_count', 0)}[/white]")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    console.print(f"[red]✗[/red] [white]Checkpoint failed[/white]")
                    console.print(f"  [red]Error:[/red] [white]{error_msg}[/white]")
                console.print()
            
            elif cmd == "stats":
                stats = executor.get_stats()
                console.print("\n[bold]📊 Statistics:[/bold]")
                
                project_name = stats.get('project_name', 'N/A')
                papers_total = stats.get('papers_total', 0)
                papers_unique = stats.get('papers_unique', 0)
                papers_duplicates = stats.get('papers_duplicates', 0)
                current_step = stats.get('current_step_index', 0)
                total_steps = stats.get('total_steps', 0)
                steps_executed = stats.get('steps_executed', 0)
                total_duration = stats.get('total_duration_seconds', 0)
                step_timings = stats.get('step_timings', [])
                
                console.print(f"  [cyan]Project:[/cyan] [white]{project_name}[/white]")
                console.print(f"  [cyan]Papers:[/cyan] [white]{papers_total}[/white] total [dim]([green]{papers_unique}[/green] unique, [yellow]{papers_duplicates}[/yellow] duplicates)[/dim]")
                console.print(f"  [cyan]Progress:[/cyan] [white]{current_step}/{total_steps}[/white] steps")
                console.print(f"  [cyan]Executed:[/cyan] [white]{steps_executed}[/white] steps")
                console.print(f"  [cyan]Total duration:[/cyan] [white]{total_duration:.2f}s[/white]")
                
                if step_timings:
                    console.print("\n  [bold cyan]Step Timings:[/bold cyan]")
                    for i, timing in enumerate(step_timings):
                        step_name = timing.get('step', 'Unknown')
                        duration_ms = timing.get('duration_ms', 0)
                        percentage = (timing.get('duration_seconds', 0) / total_duration * 100) if total_duration > 0 else 0
                        color = "white" if i % 2 == 0 else "magenta"
                        console.print(f"    • [{color}]{step_name:<25}[/{color}] [dim]{duration_ms:>7.0f}ms ({percentage:>5.1f}%)[/dim]")
                console.print()
            
            elif cmd == "state":
                state = executor.get_session_state()
                console.print("\n[bold]🎯 Session State:[/bold]")
                
                papers_count = state.get('papers_count', 0)
                current_step_idx = state.get('current_step_index', 0)
                total_steps_val = state.get('total_steps', 0)
                
                console.print(f"  [cyan]Papers in DB:[/cyan] [white]{papers_count}[/white]")
                console.print(f"  [cyan]Current step:[/cyan] [white]{current_step_idx}[/white]")
                console.print(f"  [cyan]Total steps:[/cyan] [white]{total_steps_val}[/white]")
                
                if state.get('results'):
                    last_step_info = state.get("last_step")
                    if last_step_info:
                        console.print(f"  [cyan]Last Step:[/cyan] [blue]{last_step_info['description']}[/blue] - [dim]{last_step_info['name']}[/dim]")
                    status_val = state['results'].get('status', 'N/A')
                    status_msg = state['results'].get('message')
                    console.print(f"  [cyan]Last result status:[/cyan] [white]{status_val}[/white]")
                    if status_msg:
                        console.print(f"  [cyan]Last Message:[/cyan] [white]{status_msg}[/white]")

                if "current_step" in state:
                    cs = state["current_step"]
                    console.print(f"  [cyan]Coming Step:[/cyan]: [blue]{cs['description']}[/blue] - [dim]{cs['name']}[/dim]")
                console.print()
            
            elif cmd == "history":
                console.print("\n[bold cyan]Command History:[/bold cyan]")
                if not command_history:
                    console.print("  [dim]No commands executed yet[/dim]")
                else:
                    for i, h in enumerate(command_history[-10:], 1):
                        console.print(f"  {i:2}. [white]{h}[/white]")
                console.print()
            
            elif cmd == "help":
                beautiful_menu()
            
            elif cmd == "quit":
                # Calculate final stats
                stats = executor.get_stats()
                total_steps_val = len(executor.steps)
                steps_executed = stats.get('steps_executed', 0)
                percentage = (steps_executed / total_steps_val * 100) if total_steps_val > 0 else 0
                
                console.print(Panel(
                    f"[cyan]Steps Completed:[/cyan] [white]{steps_executed}/{total_steps_val}[/white] [dim]({percentage:.1f}%)[/dim]\n"
                    f"[cyan]Total Duration:[/cyan] [white]{stats.get('total_duration_seconds', 0):.2f}s[/white]\n"
                    f"[cyan]Papers Processed:[/cyan] [white]{stats.get('papers_total', 0)}[/white]",
                    box=box.SQUARE,
                    title="[bold cyan]📈 Final Summary[/bold cyan]",
                    padding=(1, 2)
                ))
                console.print()
                break
            
            else:
                console.print(f"[yellow]⚠ Unknown command:[/yellow] [white]{cmd}[/white]")
                console.print("Type [cyan]help[/cyan] for available commands.\n")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
        
        except EOFError:
            console.print("\n[blue]ℹ Goodbye![/blue]")
            sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Interactive REPL for StepExecutor single-step mode"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug mode with verbose output"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show step name and type before execution"
    )
    parser.add_argument(
        "-t", "--timings",
        action="store_true",
        help="Display timing information after each step"
    )
    args = parser.parse_args()
    
    main(debug=args.debug, verbose=args.verbose, timings=args.timings)
