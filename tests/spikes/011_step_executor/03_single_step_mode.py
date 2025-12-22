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


def print_menu():
    """Print REPL menu options"""
    print("""
Commands:
  step [N]     - Execute step N (default: next step)
  checkpoint   - Save current state
  stats        - Show statistics
  state        - Show session state
  history      - Show execution history
  quit         - Exit
  help         - Show this menu

Keyboard:
  CTRL-C       - Stop current operation
  CTRL-D       - Exit REPL
  ↑/↓          - Navigate command history
""")


def main():
    """Interactive single-step execution"""
    
    print("=" * 60)
    print("03_single_step_mode.py - Interactive Step-by-Step Execution")
    print("=" * 60)
    
    # Setup
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    definition_file = Path(__file__).parent / "test_definition.yml"
    
    # Create executor
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
    
    # Load definition
    print(f"\n1. Loading definition...")
    executor.load_definition(definition_file)
    print(f"   ✓ Loaded {len(executor.steps)} steps")
    
    # Load checkpoint (resume if exists)
    print(f"\n2. Loading checkpoint...")
    executor.load_checkpoint()
    print(f"   ✓ Starting from step {executor.current_step_index}")
    
    # Interactive loop
    print(f"\n3. Interactive mode - type 'help' for commands\n")
    print_menu()
    
    try:
        while True:
            try:
                cmd = input(f"({executor.current_step_index}/{len(executor.steps)}) > ").strip()
                
                if not cmd:
                    continue
                
                if cmd == "quit" or cmd == "exit":
                    print("\n✓ Exiting...")
                    break
                
                elif cmd == "help":
                    print_menu()
                
                elif cmd.startswith("step"):
                    # Parse optional step number
                    parts = cmd.split()
                    step_index = executor.current_step_index
                    
                    if len(parts) > 1:
                        try:
                            step_index = int(parts[1])
                        except ValueError:
                            print("Invalid step number")
                            continue
                    
                    if step_index >= len(executor.steps):
                        print(f"Step {step_index} out of range (0-{len(executor.steps)-1})")
                        continue
                    
                    # Execute step
                    print(f"\nExecuting step {step_index}...")
                    result = executor.execute_step(step_index)
                    
                    print(f"  Status: {result['status']}")
                    print(f"  Step: {result.get('step', 'N/A')}")
                    if result.get('count') is not None:
                        print(f"  Count: {result['count']}")
                    if result.get('error'):
                        print(f"  Error: {result['error']}")
                    
                    # Auto-advance if success
                    if result['status'] == 'ok':
                        print(f"✓ Step executed successfully")
                
                elif cmd == "checkpoint":
                    print("Saving checkpoint...")
                    result = executor.checkpoint()
                    if result['status'] == 'ok':
                        print(f"✓ Checkpoint saved: {result['checkpoint_file']}")
                        print(f"  Papers saved: {result['papers_count']}")
                    else:
                        print(f"✗ Checkpoint failed: {result.get('error')}")
                
                elif cmd == "stats":
                    stats = executor.get_stats()
                    print(f"\nStatistics:")
                    print(f"  Project: {stats['project_name']}")
                    print(f"  Papers total: {stats['papers_total']}")
                    print(f"  Papers unique: {stats['papers_unique']}")
                    print(f"  Papers duplicates: {stats['papers_duplicates']}")
                    print(f"  Current step: {stats['current_step_index']}/{stats['total_steps']}")
                    print(f"  Steps executed: {stats['steps_executed']}")
                    print(f"  Total duration: {stats['total_duration_seconds']:.2f}s")
                
                elif cmd == "state":
                    state = executor.get_session_state()
                    print(f"\nSession State:")
                    print(f"  Papers in DB: {state['papers_count']}")
                    print(f"  Current step: {state['current_step_index']}")
                    print(f"  Total steps: {state['total_steps']}")
                    print(f"  Last results: {state['results']}")
                
                elif cmd == "history":
                    history = executor.step_history
                    print(f"\nExecution History ({len(history)} entries):")
                    for entry in history:
                        print(f"  [{entry['index']}] {entry['step']}")
                        print(f"      Status: {entry['status']}, Duration: {entry['duration_seconds']:.2f}s")
                
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
            
            except EOFError:
                # CTRL-D pressed
                print("\n\n✓ EOF received - exiting...")
                break
            
            except KeyboardInterrupt:
                # CTRL-C pressed
                print("\n⚠️  Interrupted (CTRL-C) - type 'help' for commands or 'quit' to exit")
            
            except Exception as e:
                print(f"Error: {e}")
                if executor.debug:
                    import traceback
                    traceback.print_exc()
    
    except KeyboardInterrupt:
        # CTRL-C in outer try
        print("\n\n✓ Interrupted - cleaning up...")
    
    except EOFError:
        # CTRL-D in outer try
        print("\n\n✓ EOF received - cleaning up...")
    
    # Final summary
    print(f"\n" + "=" * 60)
    stats = executor.get_stats()
    print(f"Session summary:")
    print(f"  Steps executed: {stats.get('steps_executed', 0)}/{stats.get('total_steps', 0)}")
    print(f"  Total duration: {stats.get('total_duration_seconds', 0):.2f}s")
    print(f"  Papers in DB: {stats.get('papers_unique', 0)} unique")
    print("=" * 60)


if __name__ == "__main__":
    main()
