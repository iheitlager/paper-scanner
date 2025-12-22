#!/usr/bin/env python
"""
06_error_handling.py

Demonstrates error handling in the StepExecutor.

Error scenarios covered:
  1. Definition loading errors (file not found, invalid YAML)
  2. Template validation errors (undefined template references)
  3. Step execution errors (caught during execute_step)
  4. Checkpoint errors (non-fatal)
"""

from pathlib import Path

from paper_scanner.cli.executor import StepExecutor


def test_missing_definition():
    """Test error: Definition file not found"""
    print("\n" + "=" * 60)
    print("Test 1: Missing Definition File")
    print("=" * 60)
    
    general_config = {"project_name": "Test"}
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
    )
    
    try:
        executor.load_definition(Path("/nonexistent/definition.yml"))
        print("✗ ERROR: Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        print(f"✓ Caught expected error: {e}")


def test_invalid_yaml():
    """Test error: Invalid YAML syntax"""
    print("\n" + "=" * 60)
    print("Test 2: Invalid YAML Syntax")
    print("=" * 60)
    
    # Create a temporary invalid YAML file
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write("project:\n  name: Test\n  invalid: [unclosed list")
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=True,
        )
        
        try:
            executor.load_definition(temp_path)
            print("✗ ERROR: Should have raised an exception")
        except Exception as e:
            print(f"✓ Caught expected error: {type(e).__name__}")
            print(f"  Details: {str(e)[:100]}...")
    finally:
        temp_path.unlink()


def test_undefined_template_reference():
    """Test error: Referenced template not defined"""
    print("\n" + "=" * 60)
    print("Test 3: Undefined Template Reference")
    print("=" * 60)
    
    import tempfile
    import yaml
    
    # Create a definition with undefined template reference
    definition = {
        'project': {'name': 'Test'},
        'templates': [
            {
                'template': 'existing_template',
                'steps': [
                    {
                        'step': 'Echo',
                        'builtin.echo': {'message': 'Hello'}
                    }
                ]
            }
        ],
        'steps': [
            {
                'step': 'Use template',
                'builtin.run-template': {'template': 'undefined_template'}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=True,
        )
        
        try:
            executor.load_definition(temp_path)
            print("✗ ERROR: Should have raised ValueError")
        except ValueError as e:
            print(f"✓ Caught expected error (template validation):")
            print(f"  {e}")
    finally:
        temp_path.unlink()


def test_step_execution_error():
    """Test error: Step execution failure"""
    print("\n" + "=" * 60)
    print("Test 4: Step Execution Error")
    print("=" * 60)
    
    import tempfile
    import yaml
    
    # Create a definition with an invalid step config
    definition = {
        'project': {'name': 'Test'},
        'steps': [
            {
                'step': 'Load files',
                'builtin.load-files': {
                    # Missing required configuration
                }
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(definition, f)
        temp_path = Path(f.name)
    
    try:
        general_config = {"project_name": "Test"}
        cache_dir = Path.home() / ".paper-scanner" / "spike-011"
        
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=cache_dir,
            verbose=True,
            debug=False,
        )
        
        executor.load_definition(temp_path)
        
        print("Attempting to execute step...")
        result = executor.execute_step(0)
        
        print(f"✓ Step execution completed (no exception)")
        print(f"  Status: {result.get('status')}")
        print(f"  Error: {result.get('error', 'None')}")
        
        if result['status'] == 'error':
            print(f"✓ Error was caught and returned in result")
        else:
            print(f"⚠ Unexpected status (may indicate missing fixture)")
    
    finally:
        temp_path.unlink()


def test_checkpoint_error_recovery():
    """Test error: Checkpoint loading doesn't halt pipeline"""
    print("\n" + "=" * 60)
    print("Test 5: Checkpoint Error Recovery (Non-Fatal)")
    print("=" * 60)
    
    general_config = {"project_name": "Test"}
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
    )
    
    # Create invalid checkpoint file
    checkpoints_dir = cache_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    invalid_checkpoint = checkpoints_dir / "checkpoint_test_step_000.json"
    with open(invalid_checkpoint, "w") as f:
        f.write("{invalid json")
    
    try:
        print("Attempting to load checkpoint with invalid JSON...")
        executor.load_checkpoint(skip_checkpoint=False)
        
        print(f"✓ load_checkpoint() completed without raising")
        print(f"  Current step index: {executor.current_step_index}")
        print(f"  (If checkpoint loading failed, should still be 0)")
    
    finally:
        if invalid_checkpoint.exists():
            invalid_checkpoint.unlink()


def main():
    """Run all error handling tests"""
    print("\n" + "=" * 80)
    print("06_error_handling.py - Error Handling & Recovery")
    print("=" * 80)
    
    test_missing_definition()
    test_invalid_yaml()
    test_undefined_template_reference()
    test_step_execution_error()
    test_checkpoint_error_recovery()
    
    print("\n" + "=" * 80)
    print("✓ Error handling tests complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
