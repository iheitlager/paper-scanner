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
import readline
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from paper_scanner.cli.executor import StepExecutor

# Enable readline history and tab completion
readline.parse_and_bind('tab: complete')

# Rich console
console = Console()


def beautiful_header():
    """Print a beautiful header for the REPL."""
    console.print(Panel.fit(
        "📊 StepExecutor Interactive Mode (Single-Step)",
        border_style="bold cyan"
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
    beautiful_header()
    
    if debug:
        console.print("[yellow]⚠ Debug mode enabled - verbose output will be shown[/yellow]\n")
    
    if verbose:
        console.print("[blue]ℹ Verbose mode enabled - showing step details before execution[/blue]\n")
    
    # Load definition
    definition_path = Path(__file__).parent / "test_definition.yml"
    
    console.print(f"📂 Loading definition: {definition_path}")
    
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
        verbose=True,
        debug=debug,
    )
    
    executor.load_definition(definition_path)
    
    if not executor.has_steps:
        console.print("[red]✗ No steps loaded from definition[/red]")
        sys.exit(1)
    
    current, total = executor.step_progress
    console.print(f"[green]✓ Loaded {total} steps from definition[/green]\n")
    beautiful_menu()
    
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
                        console.print(f"\n[cyan]\\[{step_info['index']}] Executing:[/cyan] {step_info['description']} [dim](template: {step_info['template_name']})[/dim]")
                    else:
                        console.print(f"\n[cyan]\\[{step_info['index']}] Executing:[/cyan] {step_info['description']} [dim](builtin.{step_info['name']})[/dim]")
                else:
                    console.print("[blue]ℹ Executing next step...[/blue]")
                
                prev_index = step_info["index"]
                result = executor.execute_next_step(dry_run=False)
                
                # Track how many steps were actually executed
                new_index = executor.current_step_index
                steps_executed = new_index - prev_index
                
                if debug and result:
                    console.print(f"\n[dim]Debug: Executed from step {prev_index} to {new_index} ({steps_executed} step(s))[/dim]")
                    console.print(f"[dim]Debug: Full result: {result}[/dim]\n")
                
                # Show what was executed
                if steps_executed > 1:
                    console.print(f"  [blue]ℹ Auto-advanced {steps_executed} step(s)[/blue]")
                
                # Display result information
                if result:
                    has_error = result.get('error') is not None
                    has_details = 'details' in result
                    explicit_status = result.get('status')
                    # Use the description from step_info for consistent naming
                    step_name = step_info["description"] or result.get('step', 'Unknown')
                    
                    if explicit_status == 'ok' or (not has_error and has_details):
                        count = result.get('papers_imported') or result.get('count', 0)
                        console.print(f"[blue]✓ {step_name} completed[/blue]")
                        if count > 0:
                            console.print(f"  [cyan]Processed:[/cyan] {count} items")
                        if timings and 'duration_seconds' in result:
                            duration = result['duration_seconds']
                            console.print(f"  [cyan]Duration:[/cyan] {duration:.2f}s")
                    else:
                        status = explicit_status or 'completed'
                        error_msg = result.get('error', 'No error details')
                        console.print(f"[blue]✓ {step_name} {status}[/blue]")
                        count = result.get('papers_imported') or result.get('count', 0)
                        if count > 0:
                            console.print(f"  [cyan]Processed:[/cyan] {count} items")
                else:
                    console.print("  [red]✗ No result returned from execution[/red]")
                
                # Check if all steps are now completed
                if not executor.has_next_step:
                    console.print(f"\n[green bold]🎉 All steps completed![/green bold]\n")
                console.print()
            
            elif cmd == "run" or cmd == "go":
                if not executor.has_next_step:
                    console.print("[yellow]⚠ All steps already completed![/yellow]\n")
                    continue
                
                current, total = executor.step_progress
                remaining = total - current
                console.print(f"\n[blue]ℹ Running {remaining} remaining step(s)...[/blue]\n")
                
                # Track step count for display
                step_count = [0]
                
                def on_step_start(idx, step_config, total):
                    step_count[0] += 1
                    step_desc = step_config.get('step', 'Unknown')
                    if verbose:
                        step_info = executor.describe_next_step()
                        if step_info and step_info["is_template"]:
                            console.print(f"  [{step_count[0]}/{remaining}] {step_info['description']} [dim](template: {step_info['template_name']})[/dim]...", end=" ")
                        elif step_info:
                            console.print(f"  [{step_count[0]}/{remaining}] {step_info['description']} [dim](builtin.{step_info['name']})[/dim]...", end=" ")
                    else:
                        console.print(f"  [{step_count[0]}/{remaining}] {step_desc}...", end=" ")
                
                def on_step_end(idx, step_config, result):
                    if result and result.get('status') == 'ok':
                        count = result.get('papers_imported') or result.get('count', 0)
                        if count > 0:
                            console.print(f"[green]✓ ({count} items)", end="")
                            if timings and 'duration_seconds' in result:
                                console.print(f" [dim]({result['duration_seconds']:.2f}s)[/dim]")
                            else:
                                console.print("[/green]")
                        else:
                            console.print("[green]✓[/green]", end="")
                            if timings and 'duration_seconds' in result:
                                console.print(f" [dim]({result['duration_seconds']:.2f}s)[/dim]")
                            else:
                                console.print()
                    elif result and result.get('status') == 'halted':
                        console.print(f"[yellow]⏸ halted[/yellow]")
                    elif result and result.get('status') == 'error':
                        console.print(f"[red]✗ error[/red]")
                    else:
                        status = result.get('status', 'completed') if result else 'no_result'
                        console.print(f"[green]✓ ({status})[/green]")
                
                results = executor.run_all(
                    dry_run=False,
                    on_step_start=on_step_start,
                    on_step_end=on_step_end
                )
                
                if results["status"] == "ok":
                    console.print(f"\n[green]✓ All steps completed![/green]")
                    if timings and results.get('total_duration_seconds'):
                        console.print(f"[cyan]Total duration:[/cyan] {results['total_duration_seconds']:.2f}s")
                    console.print()
                elif results["status"] == "halted":
                    console.print(f"\n[yellow]⏸ Pipeline halted[/yellow]\n")
                else:
                    console.print(f"\n[red]✗ Pipeline failed: {results.get('error', 'unknown error')}[/red]\n")
            
            elif cmd == "steps":
                console.print("\n[bold]📋 Pipeline Steps:[/bold]")
                
                # Show templates
                if executor.templates:
                    console.print(f"\n[cyan]Templates ({len(executor.templates)}):[/cyan]")
                    for template_name, template_steps in executor.templates.items():
                        console.print(f"  [green]•[/green] {template_name} ({len(template_steps)} steps)")
                
                # Show main steps
                if executor.steps:
                    console.print(f"\n[cyan]Main Steps ({len(executor.steps)}):[/cyan]")
                    for i, step_config in enumerate(executor.steps):
                        step_name = list(step_config.keys())[0] if step_config else "unknown"
                        step_desc = step_config.get('step', 'No description')
                        status = "✓" if i < executor.current_step_index else " "
                        console.print(f"  [{status}] Step {i}: {step_desc}")
                console.print()
            
            elif cmd == "checkpoint":
                console.print("\n[blue]ℹ Saving checkpoint...[/blue]")
                result = executor.checkpoint()
                if result['status'] == 'ok':
                    console.print("  [green]✓ Checkpoint saved[/green]")
                    ckpt_file = result.get('checkpoint_file', 'N/A')
                    papers_count = result.get('papers_count', 0)
                    console.print(f"  [cyan]📁 File:[/cyan] {ckpt_file}")
                    console.print(f"  [cyan]📰 Papers:[/cyan] {papers_count} saved")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    console.print(f"  [red]✗ Checkpoint failed: {error_msg}[/red]")
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
                
                console.print(f"  [cyan]Project:[/cyan] {project_name}")
                console.print(f"  [cyan]Papers:[/cyan] {papers_total} total ([green]{papers_unique} unique[/green], [yellow]{papers_duplicates} duplicates[/yellow])")
                console.print(f"  [cyan]Progress:[/cyan] {current_step}/{total_steps} steps")
                console.print(f"  [cyan]Executed:[/cyan] {steps_executed} steps")
                console.print(f"  [cyan]Total Duration:[/cyan] {total_duration:.2f}s")
                
                if step_timings:
                    console.print("\n  [bold cyan]Step Timings:[/bold cyan]")
                    for timing in step_timings:
                        step_name = timing.get('step', 'Unknown')
                        duration_ms = timing.get('duration_ms', 0)
                        # Calculate percentage of total time
                        percentage = (timing.get('duration_seconds', 0) / total_duration * 100) if total_duration > 0 else 0
                        console.print(f"    • [green]{step_name:<25}[/green] {duration_ms:>7.0f}ms ({percentage:>5.1f}%)")
                console.print()
            
            elif cmd == "state":
                state = executor.get_session_state()
                console.print("\n[bold]🎯 Session State:[/bold]")
                
                papers_count = state.get('papers_count', 0)
                current_step_idx = state.get('current_step_index', 0)
                total_steps_val = state.get('total_steps', 0)
                
                console.print(f"  [cyan]Papers in DB:[/cyan] {papers_count}")
                console.print(f"  [cyan]Current step:[/cyan] {current_step_idx}")
                console.print(f"  [cyan]Total steps:[/cyan] {total_steps_val}")
                
                if state.get('results'):
                    status_val = state['results'].get('status', 'N/A')
                    console.print(f"  [cyan]Last result status:[/cyan] {status_val}")
                console.print()
            
            elif cmd == "history":
                console.print("\n[bold]📜 Command History:[/bold]")
                for i, h in enumerate(command_history[-10:], 1):
                    console.print(f"  {i:2}. {h}")
                console.print()
            
            elif cmd == "help":
                beautiful_menu()
            
            elif cmd == "quit":
                # Calculate final stats
                stats = executor.get_stats()
                total_steps_val = len(executor.steps)
                steps_executed = stats.get('steps_executed', 0)
                percentage = (steps_executed / total_steps_val * 100) if total_steps_val > 0 else 0
                
                console.print(Panel.fit(
                    f"Steps Completed: {steps_executed}/{total_steps_val} ({percentage:.1f}%)\n"
                    f"Total Duration:  {stats.get('total_duration_seconds', 0):.2f}s\n"
                    f"Papers Processed: {stats.get('papers_total', 0)}",
                    title="📈 Final Summary",
                    border_style="bold cyan"
                ))
                console.print()
                break
            
            else:
                console.print(f"[yellow]⚠ Unknown command: {cmd}[/yellow]")
                console.print("Type '[green]help[/green]' for available commands.\n")
        
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
