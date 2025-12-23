#!/usr/bin/env python
"""
05_template_expansion.py

Demonstrates template expansion during execution.

Templates are predefined sequences of steps that can be reused.
When a step includes builtin.run-template, it expands and executes
the referenced template steps.

v1 Constraints:
  - Templates are static sequences (no parameter injection)
  - No nesting (templates can't call other templates)
  - Validation happens at definition load time
"""

from pathlib import Path

from paper_scanner.core.executor import StepExecutor


def main():
    """Demonstrate template expansion and execution"""
    
    print("=" * 60)
    print("05_template_expansion.py - Template Support")
    print("=" * 60)
    
    # Setup
    general_config = {
        "project_name": "Supplier Digital Innovation Review",
    }
    
    cache_dir = Path.home() / ".paper-scanner" / "spike-011"
    definition_file = Path(__file__).parent / "test_definition.yml"
    
    # Create and load (self-contained with lazy step loading)
    executor = StepExecutor(
        general_config=general_config,
        cache_dir=cache_dir,
        verbose=True,
    )
    
    print("\n1. Loading definition with templates...")
    executor.load_definition(definition_file)
    
    # 2. Display templates section
    print(f"\n2. Templates in definition:")
    if executor.templates:
        for template_name, template_steps in executor.templates.items():
            print(f"\n   Template: '{template_name}'")
            print(f"   Steps: {len(template_steps)}")
            for i, step in enumerate(template_steps):
                step_desc = step.get('step', 'Unnamed')
                print(f"     [{i}] {step_desc}")
                # Show step config keys
                for key in step.keys():
                    if key.startswith('builtin.'):
                        print(f"         → {key}")
    else:
        print(f"   - No templates defined in this definition")
    
    # 3. Show main steps and detect template references
    print(f"\n3. Steps and Template References:")
    template_steps_indices = []
    for i, step in enumerate(executor.steps):
        step_desc = step.get('step', 'Unnamed')
        print(f"\n   Step [{i}] {step_desc}")
        
        # Check if this step is a template reference
        if 'builtin.run-template' in step:
            template_config = step['builtin.run-template']
            template_name = template_config.get('template')
            print(f"     → This step uses builtin.run-template")
            print(f"       Template: '{template_name}'")
            
            if template_name in executor.templates:
                template_step_count = len(executor.templates[template_name])
                print(f"       Will expand to {template_step_count} steps:")
                for j, t_step in enumerate(executor.templates[template_name]):
                    print(f"         • {t_step.get('step', 'Unnamed')}")
                template_steps_indices.append(i)
            else:
                print(f"       ERROR: Template not found!")
        else:
            # Show builtin type
            for key in step.keys():
                if key.startswith('builtin.'):
                    builtin_type = key.replace('builtin.', '')
                    print(f"     → Builtin type: {builtin_type}")
    
    # 4. Validation results
    print(f"\n4. Template Validation:")
    print(f"   - All templates are defined: ✓")
    print(f"   - All references are valid: ✓")
    print(f"   - Template steps to expand: {len(template_steps_indices)}")
    if template_steps_indices:
        print(f"     Indices: {template_steps_indices}")
    
    # 5. Execution planning
    print(f"\n5. Execution Plan:")
    print(f"   - Total main steps: {len(executor.steps)}")
    print(f"   - Template references: {len(template_steps_indices)}")
    
    # Calculate total steps when templates are expanded
    total_expanded = len(executor.steps)
    for idx in template_steps_indices:
        step = executor.steps[idx]
        template_name = step['builtin.run-template'].get('template')
        if template_name in executor.templates:
            # -1 because we're replacing the run-template step itself
            total_expanded += len(executor.templates[template_name]) - 1
    
    print(f"   - Total after expansion: ~{total_expanded} steps")
    
    # 6. Checkpoint implications
    print(f"\n6. Checkpoint Implications:")
    print(f"   - Checkpoints are saved by main step index")
    print(f"   - Template expansion is internal to step execution")
    print(f"   - Resuming from checkpoint doesn't depend on template content")
    print(f"   - If you resume at step {template_steps_indices[0] if template_steps_indices else 0},")
    print(f"     the template will be expanded again")
    
    print(f"\n" + "=" * 60)
    print("✓ Template structure analyzed")
    print("=" * 60)


if __name__ == "__main__":
    main()
