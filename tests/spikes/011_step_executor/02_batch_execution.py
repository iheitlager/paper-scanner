#!/usr/bin/env python
"""
02_batch_execution.py

Demonstrates batch execution mode (run_all) with checkpoint support.

Batch mode executes a complete pipeline sequentially, optionally
resuming from a checkpoint if one exists.
"""

from pathlib import Path

from paper_scanner.cli.executor import StepExecutor
from paper_scanner.cli.paper_processor import StepExecutor as ProcessorExecutor


def main(skip_checkpoint: bool = False, clear_checkpoint: bool = False, dry_run: bool = False):
    """Execute pipeline in batch mode"""
    
    print("=" * 60)
    print("02_batch_execution.py - Batch Mode Pipeline Execution")
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
    
    # Handle checkpoint
    print(f"\n2. Checking for checkpoints...")
    executor.load_checkpoint(
        skip_checkpoint=skip_checkpoint, 
        clear_checkpoint=clear_checkpoint
    )
    print(f"   ✓ Starting from step {executor.current_step_index}")
    
    if skip_checkpoint:
        print(f"   - Skipped checkpoint loading (--skip-checkpoint)")
    if clear_checkpoint:
        print(f"   - Cleared all checkpoints (--clear-checkpoint)")
    
    # Execute all remaining steps
    print(f"\n3. Executing pipeline...")
    print(f"   - dry_run={dry_run}")
    print()
    
    results = executor.run_all(dry_run=dry_run)
    
    # Report results
    print(f"\n4. Pipeline completed")
    print(f"   - Status: {results['status']}")
    print(f"   - Steps executed: {results.get('steps_executed', 0)}")
    print(f"   - Steps failed: {results.get('steps_failed', 0)}")
    print(f"   - Duration: {results.get('total_duration_seconds', 0):.2f}s")
    
    # Show per-step results
    if results.get('step_results'):
        print(f"\n5. Step Results:")
        for i, step_result in enumerate(results['step_results']):
            status = step_result.get('status', 'unknown')
            step_name = step_result.get('step', 'Unknown')
            duration = step_result.get('duration_seconds', 0)
            print(f"   [{i}] {step_name}")
            print(f"       Status: {status}, Duration: {duration:.2f}s")
            if step_result.get('error'):
                print(f"       Error: {step_result['error']}")
    
    # Show statistics
    print(f"\n6. Statistics")
    stats = executor.get_stats()
    print(f"   - Papers total: {stats['papers_total']}")
    print(f"   - Papers unique: {stats['papers_unique']}")
    print(f"   - Papers duplicates: {stats['papers_duplicates']}")
    print(f"   - Current step: {stats['current_step_index']}/{stats['total_steps']}")
    print(f"   - Total duration: {stats['total_duration_seconds']:.2f}s")
    
    # Show timings
    if stats.get('step_timings'):
        print(f"\n7. Step Timings:")
        for timing in stats['step_timings']:
            print(f"   {timing['step']}: {timing['duration_ms']}ms")
    
    # Show inventory
    if stats.get('inventory'):
        inventory = stats['inventory']
        print(f"\n8. Inventory:")
        if inventory.get('builtin_steps'):
            print(f"   - Builtin steps ({len(inventory['builtin_steps'])}): {inventory['builtin_steps'][:3]}...")
        if inventory.get('templates'):
            print(f"   - Templates: {inventory['templates']}")
    
    # Final status
    print(f"\n" + "=" * 60)
    if results['status'] == 'ok':
        print(f"✓ Pipeline executed successfully")
    elif results['status'] == 'halted':
        print(f"⏸ Pipeline halted (explicit halt step)")
    else:
        print(f"✗ Pipeline failed: {results.get('error', 'Unknown error')}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch execution demo")
    parser.add_argument("--skip-checkpoint", action="store_true", help="Skip checkpoint loading")
    parser.add_argument("--clear-checkpoint", action="store_true", help="Clear all checkpoints")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (don't modify data)")
    
    args = parser.parse_args()
    
    main(
        skip_checkpoint=args.skip_checkpoint,
        clear_checkpoint=args.clear_checkpoint,
        dry_run=args.dry_run
    )
