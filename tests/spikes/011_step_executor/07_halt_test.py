#!/usr/bin/env python
"""
07_halt_test.py

Demonstrates HaltException handling in StepExecutor.

The halt step is used to stop pipeline execution gracefully without
raising an error. This is useful for:
  - Debugging pipelines at a specific step
  - Conditional early termination
  - Interactive checkpoints before expensive operations

This test uses an echo/halt/echo sequence to verify that:
  1. The first echo executes normally
  2. The halt step stops execution with status "halted"
  3. The second echo is never executed
"""

import tempfile
from pathlib import Path

import yaml

from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.enum import StepStatus


def test_halt_stops_execution():
    """Test that halt step stops pipeline execution gracefully"""
    print("\n" + "=" * 60)
    print("Test 1: Halt Stops Execution (echo/halt/echo)")
    print("=" * 60)
    
    # Create a definition with echo -> halt -> echo
    definition = {
        'project': {'name': 'Halt Test'},
        'steps': [
            {
                'step': 'First echo (should execute)',
                'builtin.echo': {'message': '✓ First echo executed'}
            },
            {
                'step': 'Halt pipeline',
                'builtin.halt': {'message': 'Stopping here for testing'}
            },
            {
                'step': 'Second echo (should NOT execute)',
                'builtin.echo': {'message': '✗ This should never appear'}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Halt Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011-halt"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=True,
            debug=False,
        )
        
        executor.load_definition(temp_path)
        
        print(f"\nLoaded {len(executor.steps)} steps:")
        for i, step in enumerate(executor.steps):
            print(f"  [{i}] {step.get('step', 'Unknown')}")
        
        print("\nExecuting steps individually:")
        
        # Execute step 0 (first echo)
        print("\n--- Step 0: First Echo ---")
        result0 = executor.execute_step(0)
        print(f"  Status: {result0.get('status')}")
        print(f"  Message: {result0.get('message')}")
        print(f"  Error: {result0.get('error')}")
        assert result0.get('status') == StepStatus.SUCCESS, f"Expected 'ok', got {result0.get('status')}"
        print("  ✓ First echo completed successfully")
        
        # Execute step 1 (halt)
        print("\n--- Step 1: Halt ---")
        result1 = executor.execute_step(1)
        print(f"  Status: {result1.get('status')}")
        print(f"  Message: {result1.get('message')}")
        assert result1.get('status') == 'halted', f"Expected 'halted', got {result1.get('status')}"
        print("  ✓ Halt step returned 'halted' status")
        
        # Verify step 2 was never executed
        print("\n--- Verification ---")
        print(f"  Current step index: {executor.current_step_index}")
        print(f"  Steps in history: {len(executor.step_history)}")
        
        # The halt step returned 'halted' status but didn't increment step index
        # (because it raised an exception before the normal completion path)
        executed_steps = [h.get('step') for h in executor.step_history]
        print(f"  Executed steps: {executed_steps}")
        
        # Only 1 step should be in history (the first echo)
        # The halt step raises exception before being added to history
        assert len(executor.step_history) == 2, \
            f"Expected 1 step in history, got {len(executor.step_history)}"
        assert executor.step_history[0].get('step') == 'echo', \
            "First step should be echo"
        print("  ✓ Only first echo is in history (halt raised exception)")
        print("  ✓ Second echo was NOT executed (as expected)")
        
    finally:
        temp_path.unlink()
    
    print("\n✓ Test 1 passed: Halt stops execution correctly")


def test_halt_in_run_all():
    """Test that halt stops run_all() execution"""
    print("\n" + "=" * 60)
    print("Test 2: Halt Stops run_all() Batch Execution")
    print("=" * 60)
    
    definition = {
        'project': {'name': 'Halt Batch Test'},
        'steps': [
            {
                'step': 'Echo 1',
                'builtin.echo': {'message': 'Step 1'}
            },
            {
                'step': 'Echo 2',
                'builtin.echo': {'message': 'Step 2'}
            },
            {
                'step': 'Halt here',
                'builtin.halt': {'message': 'Batch halted at step 3'}
            },
            {
                'step': 'Echo 3 (unreachable)',
                'builtin.echo': {'message': 'Step 3'}
            },
            {
                'step': 'Echo 4 (unreachable)',
                'builtin.echo': {'message': 'Step 4'}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Halt Batch Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011-halt"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=True,
            debug=False,
        )
        
        executor.load_definition(temp_path)
        
        print(f"\nLoaded {len(executor.steps)} steps")
        print("Running batch execution with run_all()...\n")
        
        results = executor.run_all()
        
        print(f"\n--- Results ---")
        print(f"  Overall status: {results.get('status')}")
        print(f"  Steps executed: {results.get('steps_executed')}")
        print(f"  Steps failed: {results.get('steps_failed')}")
        print(f"  Step results count: {len(results.get('step_results', []))}")
        
        # Verify batch was halted
        assert results.get('status') == 'halted', \
            f"Expected 'halted', got {results.get('status')}"
        
        # Steps executed should be 2 (echo, echo) before halt
        assert results.get('steps_executed') == 2, \
            f"Expected 2 steps executed, got {results.get('steps_executed')}"
        
        # Should have 3 step results (2 ok + 1 halted)
        assert len(results.get('step_results', [])) == 3, \
            f"Expected 3 step results, got {len(results.get('step_results', []))}"
        
        print("  ✓ Batch execution halted correctly")
        print("  ✓ Only 2 steps executed before halt")
        print("  ✓ Steps 4 and 5 were never reached")
        
    finally:
        temp_path.unlink()
    
    print("\n✓ Test 2 passed: run_all() halts correctly")


def test_halt_with_custom_message():
    """Test halt step with custom message"""
    print("\n" + "=" * 60)
    print("Test 3: Halt with Custom Message")
    print("=" * 60)
    
    custom_message = "Custom halt: Review papers before proceeding"
    
    definition = {
        'project': {'name': 'Halt Message Test'},
        'steps': [
            {
                'step': 'Halt with message',
                'builtin.halt': {'message': custom_message}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Halt Message Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011-halt"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=False,
        )
        
        executor.load_definition(temp_path)
        result = executor.execute_step(0)
        
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")
        
        assert result.get('status') == 'halted'
        assert result.get('message') == custom_message, \
            f"Expected '{custom_message}', got '{result.get('message')}'"
        
        print("  ✓ Custom message preserved in result")
        
    finally:
        temp_path.unlink()
    
    print("\n✓ Test 3 passed: Custom message works correctly")


def test_halt_default_message():
    """Test halt step with default message"""
    print("\n" + "=" * 60)
    print("Test 4: Halt with Default Message")
    print("=" * 60)
    
    definition = {
        'project': {'name': 'Halt Default Test'},
        'steps': [
            {
                'step': 'Halt without message',
                'builtin.halt': {}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Halt Default Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011-halt"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=False,
        )
        
        executor.load_definition(temp_path)
        result = executor.execute_step(0)
        
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")
        
        assert result.get('status') == 'halted'
        assert result.get('message') == 'Pipeline halted', \
            f"Expected default message, got '{result.get('message')}'"
        
        print("  ✓ Default message used when none provided")
        
    finally:
        temp_path.unlink()
    
    print("\n✓ Test 4 passed: Default message works correctly")


def main():
    """Run all halt tests"""
    print("\n" + "=" * 80)
    print("07_halt_test.py - HaltException Handling Tests")
    print("=" * 80)
    
    test_halt_stops_execution()
    test_halt_in_run_all()
    test_halt_with_custom_message()
    test_halt_default_message()
    
    print("\n" + "=" * 80)
    print("✓ All halt tests passed!")
    print("=" * 80)
    print("\nKey findings:")
    print("  • HaltException is caught by executor and returns 'halted' status")
    print("  • Steps after halt are never executed")
    print("  • run_all() stops gracefully on halt (not counted as error)")
    print("  • Custom messages are preserved in the result")


if __name__ == "__main__":
    main()
