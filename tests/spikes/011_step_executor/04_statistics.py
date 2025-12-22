#!/usr/bin/env python
"""
04_statistics.py

Demonstrates querying execution statistics and session state.

The executor provides two main methods for introspection:
  - get_stats(): Comprehensive statistics and inventory
  - get_session_state(): Current session state for REPL integration
"""

from pathlib import Path

from paper_scanner.cli.executor import StepExecutor


def main():
    """Query and display executor statistics and state"""
    
    print("=" * 60)
    print("04_statistics.py - Statistics & Session State Queries")
    print("=" * 60)
    
    # Setup
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    definition_file = Path(__file__).parent / "test_definition.yml"
    
    # Create and load (self-contained with lazy step loading)
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=False,
    )
    
    executor.load_definition(definition_file)
    executor.load_checkpoint()
    
    # 1. Query get_stats()
    print("\n1. Statistics via get_stats():")
    stats = executor.get_stats()
    
    print(f"\n   Project Information:")
    print(f"     - project_name: {stats.get('project_name')}")
    
    print(f"\n   Paper Counts:")
    print(f"     - total: {stats.get('papers_total')}")
    print(f"     - unique: {stats.get('papers_unique')}")
    print(f"     - duplicates: {stats.get('papers_duplicates')}")
    
    print(f"\n   Execution Progress:")
    print(f"     - current_step_index: {stats.get('current_step_index')}")
    print(f"     - total_steps: {stats.get('total_steps')}")
    print(f"     - steps_executed: {stats.get('steps_executed')}")
    
    print(f"\n   Timing Information:")
    print(f"     - total_duration_seconds: {stats.get('total_duration_seconds')}")
    
    # 2. Step timings
    print(f"\n2. Step Timings:")
    timings = stats.get('step_timings', [])
    if timings:
        for timing in timings:
            print(f"     - {timing['step']}: {timing['duration_ms']}ms ({timing['duration_seconds']:.2f}s)")
    else:
        print(f"     - No timings yet (no steps executed)")
    
    # 3. Step history
    print(f"\n3. Step History:")
    history = stats.get('step_history', [])
    if history:
        for entry in history:
            print(f"     [{entry['index']}] {entry['step']}")
            print(f"         Status: {entry['status']}, Duration: {entry['duration_seconds']:.2f}s")
    else:
        print(f"     - No history yet (no steps executed)")
    
    # 4. Template information
    print(f"\n4. Template Information:")
    templates_info = stats.get('templates', {})
    print(f"     - Count: {templates_info.get('count', 0)}")
    if templates_info.get('names'):
        for name in templates_info['names']:
            print(f"     - {name}")
    
    # 5. Inventory
    print(f"\n5. Inventory:")
    inventory = stats.get('inventory', {})
    
    builtin_steps = inventory.get('builtin_steps', [])
    print(f"     - Builtin Steps ({len(builtin_steps)}):")
    for step in builtin_steps[:5]:  # Show first 5
        print(f"       • {step}")
    if len(builtin_steps) > 5:
        print(f"       ... and {len(builtin_steps) - 5} more")
    
    templates = inventory.get('templates', [])
    print(f"     - Defined Templates ({len(templates)}):")
    for template in templates:
        print(f"       • {template}")
    if not templates:
        print(f"       (none defined)")
    
    # 6. Get session state
    print(f"\n6. Session State via get_session_state():")
    state = executor.get_session_state()
    
    print(f"     - papers_count: {state.get('papers_count')}")
    print(f"     - current_step_index: {state.get('current_step_index')}")
    print(f"     - total_steps: {state.get('total_steps')}")
    print(f"     - papers_db type: {type(state.get('papers_db'))}")
    print(f"     - general_config keys: {list(state.get('general_config', {}).keys())}")
    
    # 7. Direct attribute access
    print(f"\n7. Direct Attribute Access:")
    print(f"     - executor.papers_db.count(): {executor.papers_db.count()}")
    print(f"     - executor.papers_db.count(primary_only=True): {executor.papers_db.count(primary_only=True)}")
    print(f"     - len(executor.steps): {len(executor.steps)}")
    print(f"     - len(executor.templates): {len(executor.templates)}")
    print(f"     - len(executor.step_history): {len(executor.step_history)}")
    print(f"     - executor.current_step_index: {executor.current_step_index}")
    
    # 8. Access definition content
    print(f"\n8. Definition Content:")
    if executor.definition:
        project_config = executor.definition.get('project', {})
        print(f"     - project.name: {project_config.get('name', 'N/A')}")
        print(f"     - Number of steps: {len(executor.steps)}")
        print(f"     - Number of templates: {len(executor.templates)}")
        if executor.templates:
            for template_name in executor.templates:
                template_steps = executor.templates[template_name]
                print(f"       - Template '{template_name}' has {len(template_steps)} steps")
    
    print(f"\n" + "=" * 60)
    print("✓ Statistics and state queries complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
