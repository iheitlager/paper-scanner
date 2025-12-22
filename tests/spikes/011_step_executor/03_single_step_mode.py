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

import readline
import sys
from pathlib import Path

from paper_scanner.cli.executor import StepExecutor
from paper_scanner.cli.paper_processor import StepExecutor as ProcessorExecutor

# Enable readline history and tab completion
readline.parse_and_bind('tab: complete')

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    GRAY = '\033[90m'
    
    @staticmethod
    def success(text):
        return f"{Colors.GREEN}✓ {text}{Colors.END}"
    
    @staticmethod
    def error(text):
        return f"{Colors.RED}✗ {text}{Colors.END}"
    
    @staticmethod
    def info(text):
        return f"{Colors.BLUE}ℹ {text}{Colors.END}"
    
    @staticmethod
    def warning(text):
        return f"{Colors.YELLOW}⚠ {text}{Colors.END}"


def beautiful_header():
    """Print a beautiful header for the REPL."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║      📊 StepExecutor Interactive Mode (Single-Step)      ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════╝{Colors.END}\n")


def beautiful_menu():
    """Print a beautifully formatted menu."""
    print(f"{Colors.BOLD}Available Commands:{Colors.END}")
    print(f"  {Colors.GREEN}step{Colors.END:<12} - Execute next step")
    print(f"  {Colors.GREEN}checkpoint{Colors.END:<12} - Save checkpoint")
    print(f"  {Colors.GREEN}stats{Colors.END:<12} - Show execution statistics")
    print(f"  {Colors.GREEN}state{Colors.END:<12} - Show current session state")
    print(f"  {Colors.GREEN}history{Colors.END:<12} - Show command history")
    print(f"  {Colors.GREEN}help{Colors.END:<12} - Show this menu")
    print(f"  {Colors.GREEN}quit{Colors.END:<12} - Exit REPL\n")


def main():
    """Interactive REPL for single-step execution."""
    beautiful_header()
    
    # Load definition
    definition_path = Path(__file__).parent / "test_definition.yml"
    
    print(f"📂 Loading definition: {definition_path}")
    
    if not definition_path.exists():
        print(f"{Colors.error(f'Definition file not found: {definition_path}')}")
        sys.exit(1)
    
    # Setup config
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    
    # Initialize executor
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
        debug=False,
        get_step_func=lambda name: ProcessorExecutor.get_step(
            name, 
            general_config, 
            executor.papers_db,
            executor.cache_dir
        ),
    )
    
    executor.load_definition(definition_path)
    
    if len(executor.steps) == 0:
        print(f"{Colors.error('No steps loaded from definition')}")
        sys.exit(1)
    
    print(f"{Colors.success(f'Loaded {len(executor.steps)} steps from definition')}\n")
    beautiful_menu()
    
    command_history = []
    
    try:
        while True:
            try:
                # Calculate progress
                progress = f"[{executor.current_step_index}/{len(executor.steps)}]"
                prompt = f"{Colors.BOLD}{Colors.BLUE}{progress} > {Colors.END}"
                
                cmd = input(prompt).strip().lower()
                
                if not cmd:
                    continue
                
                command_history.append(cmd)
                
                # Execute commands
                if cmd == "step":
                    print(f"\n{Colors.info('Executing next step...')}")
                    result = executor.execute_step(executor.current_step_index, dry_run=False)
                    executor.current_step_index += 1
                    
                    if result and result.get('status') == 'ok':
                        step_name = result.get('step_name', 'Unknown')
                        count = result.get('count', 0)
                        print(f"  {Colors.success(f'{step_name} completed')}")
                        print(f"  {Colors.CYAN}Processed:{Colors.END} {count} items")
                        if 'duration_seconds' in result:
                            duration = result['duration_seconds']
                            print(f"  {Colors.CYAN}Duration:{Colors.END} {duration:.2f}s")
                    else:
                        error_msg = result.get('error', 'Unknown error') if result else 'No result'
                        print(f"  {Colors.error(f'Execution failed: {error_msg}')}")
                    print()
                
                elif cmd == "checkpoint":
                    print(f"\n{Colors.info('Saving checkpoint...')}")
                    result = executor.checkpoint()
                    if result['status'] == 'ok':
                        print(f"  {Colors.success('Checkpoint saved')}")
                        ckpt_file = result.get('checkpoint_file', 'N/A')
                        papers_count = result.get('papers_count', 0)
                        print(f"  {Colors.CYAN}📁 File:{Colors.END} {ckpt_file}")
                        print(f"  {Colors.CYAN}📰 Papers:{Colors.END} {papers_count} saved")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        print(f"  {Colors.error(f'Checkpoint failed: {error_msg}')}")
                    print()
                
                elif cmd == "stats":
                    stats = executor.get_stats()
                    print(f"\n{Colors.BOLD}📊 Statistics:{Colors.END}")
                    
                    project_name = stats.get('project_name', 'N/A')
                    papers_total = stats.get('papers_total', 0)
                    papers_unique = stats.get('papers_unique', 0)
                    papers_duplicates = stats.get('papers_duplicates', 0)
                    current_step = stats.get('current_step_index', 0)
                    total_steps = stats.get('total_steps', 0)
                    steps_executed = stats.get('steps_executed', 0)
                    duration = stats.get('total_duration_seconds', 0)
                    
                    print(f"  {Colors.CYAN}Project:{Colors.END} {project_name}")
                    print(f"  {Colors.CYAN}Papers:{Colors.END} {papers_total} total " +
                          f"({Colors.GREEN}{papers_unique} unique{Colors.END}, " +
                          f"{Colors.YELLOW}{papers_duplicates} duplicates{Colors.END})")
                    print(f"  {Colors.CYAN}Progress:{Colors.END} {current_step}/{total_steps} steps")
                    print(f"  {Colors.CYAN}Executed:{Colors.END} {steps_executed} steps")
                    print(f"  {Colors.CYAN}Duration:{Colors.END} {duration:.2f}s")
                    print()
                
                elif cmd == "state":
                    state = executor.get_session_state()
                    print(f"\n{Colors.BOLD}🎯 Session State:{Colors.END}")
                    
                    papers_count = state.get('papers_count', 0)
                    current_step_idx = state.get('current_step_index', 0)
                    total_steps_val = state.get('total_steps', 0)
                    
                    print(f"  {Colors.CYAN}Papers in DB:{Colors.END} {papers_count}")
                    print(f"  {Colors.CYAN}Current step:{Colors.END} {current_step_idx}")
                    print(f"  {Colors.CYAN}Total steps:{Colors.END} {total_steps_val}")
                    
                    if state.get('results'):
                        status_val = state['results'].get('status', 'N/A')
                        print(f"  {Colors.CYAN}Last result status:{Colors.END} {status_val}")
                    print()
                
                elif cmd == "history":
                    print(f"\n{Colors.BOLD}📜 Command History:{Colors.END}")
                    for i, h in enumerate(command_history[-10:], 1):
                        print(f"  {i:2}. {h}")
                    print()
                
                elif cmd == "help":
                    beautiful_menu()
                
                elif cmd == "quit":
                    # Calculate final stats
                    stats = executor.get_stats()
                    total_steps_val = len(executor.steps)
                    steps_executed = stats.get('steps_executed', 0)
                    percentage = (steps_executed / total_steps_val * 100) if total_steps_val > 0 else 0
                    
                    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════╗{Colors.END}")
                    print(f"{Colors.BOLD}{Colors.CYAN}║                   📈 Final Summary                        ║{Colors.END}")
                    print(f"{Colors.BOLD}{Colors.CYAN}╠══════════════════════════════════════════════════════════╣{Colors.END}")
                    print(f"{Colors.CYAN}║  Steps Completed:     {steps_executed}/{total_steps_val} ({percentage:5.1f}%)                        {Colors.END}║")
                    print(f"{Colors.CYAN}║  Total Duration:      {stats.get('total_duration_seconds', 0):.2f}s                                  {Colors.END}║")
                    print(f"{Colors.CYAN}║  Papers Processed:    {stats.get('papers_total', 0)}                                      {Colors.END}║")
                    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════╝{Colors.END}\n")
                    break
                
                else:
                    print(f"{Colors.warning(f'Unknown command: {cmd}')}")
                    print(f"Type '{Colors.GREEN}help{Colors.END}' for available commands.\n")
            
            except KeyboardInterrupt:
                print(f"\n{Colors.warning('Operation cancelled by user')}")
            
            except EOFError:
                print(f"\n{Colors.info('EOF received')}")
                break
    
    except KeyboardInterrupt:
        print(f"\n{Colors.warning('Exiting...')}")
        sys.exit(0)
    
    except EOFError:
        print(f"\n{Colors.info('Goodbye!')}")
        sys.exit(0)


if __name__ == "__main__":
    main()
