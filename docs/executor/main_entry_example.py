#!/usr/bin/env python
"""
Example main entry point using StepExecutor

Demonstrates typical usage:
1. Load definition file
2. Handle checkpoints
3. Execute pipeline
4. Report statistics
"""

from pathlib import Path

from paper_scanner.cli.executor import StepExecutor
from paper_scanner.cli.paper_processor import StepExecutor as ProcessorExecutor


def main():
    """Example: Load definition, execute, and report"""
    
    # 1. Setup configuration
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
        "researcher": "Ilja Heitlager",
        "institution": "TU Eindhoven",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "example"
    definition_file = Path("definition.yml")
    
    # 2. Create executor with step instantiation function
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
        debug=False,
        get_step_func=lambda name: ProcessorExecutor.get_step(
            name, general_config, executor.papers_db, executor.cache_dir
        ),
    )
    
    # 3. Load definition (validates templates early)
    print("Loading definition...")
    executor.load_definition(definition_file)
    print(f"  - Found {len(executor.steps)} steps")
    print(f"  - Found {len(executor.templates)} templates: {list(executor.templates.keys())}")
    
    # 4. Handle checkpoint (resume from last checkpoint if exists)
    print("\nChecking for checkpoints...")
    executor.load_checkpoint()
    print(f"  - Resuming from step {executor.current_step_index}")
    
    # 5. Execute all remaining steps
    print("\nExecuting pipeline...")
    results = executor.run_all(dry_run=False)
    
    # 6. Check status
    if results['status'] == 'ok':
        print(f"\n✓ Pipeline completed successfully")
    elif results['status'] == 'halted':
        print(f"\n⏸ Pipeline halted")
    else:
        print(f"\n✗ Pipeline failed: {results.get('error')}")
    
    # 7. Report statistics
    print("\n=== Statistics ===")
    stats = executor.get_stats()
    print(f"Papers: {stats['papers_unique']} unique, {stats['papers_duplicates']} duplicates")
    print(f"Duration: {stats['total_duration_seconds']}s")
    print(f"Steps executed: {stats['steps_executed']}/{stats['total_steps']}")
    
    # 8. Show timings
    if stats['step_timings']:
        print("\n=== Timings ===")
        for timing in stats['step_timings']:
            print(f"  {timing['step']}: {timing['duration_seconds']}s")
    
    # 9. Show inventory
    print("\n=== Inventory ===")
    print(f"Available steps: {len(stats['inventory']['builtin_steps'])}")
    print(f"Available templates: {len(stats['inventory']['templates'])}")
    if stats['inventory']['templates']:
        print(f"  - {', '.join(stats['inventory']['templates'])}")


def example_single_step_mode():
    """Example: Single-step mode for interactive exploration"""
    
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "example"
    definition_file = Path("definition.yml")
    
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
        get_step_func=lambda name: ProcessorExecutor.get_step(
            name, general_config, executor.papers_db, executor.cache_dir
        ),
    )
    
    executor.load_definition(definition_file)
    executor.load_checkpoint()
    
    # Execute step by step with manual checkpointing
    while executor.current_step_index < len(executor.steps):
        step_index = executor.current_step_index
        
        print(f"\nExecuting step {step_index}...")
        result = executor.execute_step(step_index)
        
        if result['status'] == 'ok':
            print(f"✓ Step succeeded ({result.get('count', 0)} items)")
            
            # Explicit checkpoint after each step
            checkpoint_result = executor.checkpoint()
            if checkpoint_result['status'] == 'ok':
                print(f"  Saved checkpoint: {checkpoint_result['checkpoint_file']}")
        elif result['status'] == 'error':
            print(f"✗ Step failed: {result['error']}")
            break
        else:
            print(f"? Step {result['status']}: {result.get('message', '')}")


def example_with_template_call():
    """Example: Definition with template reference and mid-pipeline template application"""
    
    # This would be your definition.yml with templates section:
    yaml_example = """
project:
  name: "Example Review"

templates:
  - template: "screen_basics"
    steps:
      - step: "Deduplicate"
        builtin.deduplication:
          methods:
            - method: "doi_exact"
              priority: 1
      
      - step: "Screen keywords"
        builtin.keyword_screening:
          exclusion_keywords:
            domains:
              - "medical"

steps:
  - step: "Import papers"
    builtin.bibtex_import:
      imports:
        - file_path: "data/papers.bib"

  - step: "Apply basic screening"
    builtin.run-template:
      template: "screen_basics"

  - step: "Export results"
    builtin.export:
      format: bibtex
      output_path: "./output/screened.bib"
"""
    
    print("Example definition.yml with templates:")
    print(yaml_example)


if __name__ == "__main__":
    # Run main example
    main()
    
    # Uncomment for other examples:
    # example_single_step_mode()
    # example_with_template_call()
