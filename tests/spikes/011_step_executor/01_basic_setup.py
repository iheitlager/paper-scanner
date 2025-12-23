#!/usr/bin/env python
"""
01_basic_setup.py

Demonstrates basic StepExecutor initialization and definition loading.

This is the foundation for all executor patterns.
"""

from pathlib import Path

from paper_scanner.core.executor import StepExecutor


def main():
    """Basic executor setup and definition loading"""
    
    print("=" * 60)
    print("01_basic_setup.py - StepExecutor Basics")
    print("=" * 60)
    
    # 1. Setup general configuration
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    # 2. Define cache directory for checkpoints
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    
    # 3. Create executor (self-contained with lazy step loading)
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
        debug=False,
    )
    
    print(f"\n✓ Executor created")
    print(f"  - Project: {executor.general_config['project_name']}")
    print(f"  - Cache dir: {executor.cache_dir}")
    print(f"  - Verbose: {executor.verbose}")
    
    # 4. Load definition file
    # This validates YAML, templates, and template references (fail-early)
    definition_file = Path(__file__).parent / "test_definition.yml"
    
    if not definition_file.exists():
        print(f"\n⚠ Definition file not found: {definition_file}")
        print(f"  Please run this spike with test_definition.yml in the same directory")
        return
    
    print(f"\nLoading definition from: {definition_file}")
    executor.load_definition(definition_file)
    
    # 5. Inspect loaded definition
    print(f"\n✓ Definition loaded successfully")
    print(f"  - Project name: {executor.definition.get('project', {}).get('name', 'N/A')}")
    print(f"  - Steps defined: {len(executor.steps)}")
    print(f"  - Templates defined: {len(executor.templates)}")
    
    if executor.templates:
        print(f"    - Template names: {list(executor.templates.keys())}")
    
    # 6. Show step structure
    print(f"\nSteps in pipeline:")
    for i, step in enumerate(executor.steps):
        step_name = step.get("step", "Unnamed")
        print(f"  [{i}] {step_name}")
        # Show step config keys (not values for brevity)
        for key in step.keys():
            if key.startswith("builtin."):
                print(f"      → {key}")
    
    # 7. Access session state
    print(f"\n✓ Session state initialized")
    print(f"  - Current step index: {executor.current_step_index}")
    print(f"  - Total steps: {len(executor.steps)}")
    print(f"  - Papers in DB: {executor.papers_db.count()}")
    
    # 8. Access public attributes
    print(f"\n✓ Public attributes available:")
    print(f"  - executor.general_config: {type(executor.general_config)}")
    print(f"  - executor.definition: {type(executor.definition)}")
    print(f"  - executor.templates: {type(executor.templates)}")
    print(f"  - executor.steps: {type(executor.steps)}")
    print(f"  - executor.papers_db: {type(executor.papers_db)}")
    print(f"  - executor.step_history: {type(executor.step_history)}")
    print(f"  - executor.current_step_index: {executor.current_step_index}")
    
    print(f"\n" + "=" * 60)
    print("✓ Basic setup complete - ready for execution patterns")
    print("=" * 60)


if __name__ == "__main__":
    main()
