# StepExecutor Architecture

## Overview

`StepExecutor` is a unified execution engine for paper-scanner pipelines that harmonizes and replaces separate `run.py` and `repl.py` task implementations. It provides:

- **Definition loading** with YAML parsing and template validation
- **Template support** (v1: static step sequences)
- **Session state management** (database, results, execution history)
- **Step execution** in single-step or batch modes
- **Checkpoint management** (local file-based only)
- **Statistics & timing** collection
- **Interactive & batch modes** support

## Architecture

### Three-Level Configuration Model

Paper-scanner uses a three-level configuration hierarchy:

1. **general_config** (Project Level)
   - Project-wide settings (project_name, cache_dir, researcher, institution, etc.)
   - Passed to ALL steps at instantiation
   - Source: Definition file `project` section or CLI arguments

2. **step_config** (Step Level)
   - Step-specific parameters from YAML definition
   - Each step has its own config block under `builtin.<step_name>`
   - Example: `threshold: 0.90` for deduplication

3. **Runtime Flags** (Execution Level)
   - Flags controlling execution behavior (verbose, dry_run, debug)
   - Passed to step's `execute()` method
   - Same for all steps in a run

### Data Flow

```
Definition File (YAML)
    ↓
StepExecutor.load_definition()
    ├── Parse project metadata → general_config
    ├── Parse templates section
    ├── Parse steps section
    └── Validate template references (early fail)
    ↓
StepExecutor.load_checkpoint()
    ├── Find latest checkpoint
    └── Restore papers_db if found
    ↓
Execution Mode
    ├── Batch Mode: StepExecutor.run_all() → execute all remaining steps
    └── Single Mode: StepExecutor.execute_step(index) → execute one step
    ↓
For each step:
    ├── Parse Ansible-style config (builtin.step_name)
    ├── Check if run-template: YES → expand and execute template recursively
    │                             NO → execute builtin step
    ├── Track timing & results
    └── Update session state
    ↓
Optionally: StepExecutor.checkpoint() → save papers_db to JSON
    ↓
StepExecutor.get_stats() → aggregate statistics & inventory
```

## Key Concepts

### Templates (v1: Static Only)

Templates are predefined sequences of steps that can be reused. Defined in the `templates` section of a definition file:

```yaml
templates:
  - template: "screen_basics"
    steps:
      - step: "Deduplication"
        builtin.deduplication:
          methods:
            - method: "doi_exact"
              priority: 1
      
      - step: "Keyword screening"
        builtin.keyword_screening:
          exclusion_keywords:
            domains:
              - "medical"
```

Templates are referenced via the `run-template` builtin step:

```yaml
steps:
  - step: "Apply basic screening"
    builtin.run-template:
      template: "screen_basics"
```

**v1 Constraints**:
- Templates are static sequences of steps
- No parameter injection at call site
- Validation occurs at definition load time via `_validate_template_references()`
- Template nesting is supported (templates can call other templates)

### Checkpoint System

Checkpoints save the papers database at specific points in the pipeline for resumption.

- **Location**: `~/.paper-scanner/checkpoints/` (or configured cache_dir)
- **Naming**: `checkpoint_{project_hash}_step_{index:03d}.json`
- **Content**: Project name, step index, timestamp, papers list (JSON)
- **Scope**: Local files only (v1)
- **Control**: Explicit `executor.checkpoint()` call in single-step mode; automatic in batch mode after each step (optional)

Checkpoint resumption:
```python
executor.load_checkpoint(skip_checkpoint=False, clear_checkpoint=False)
# Finds latest checkpoint and sets current_step_index to resume point
executor.run_all()  # Skips steps before checkpoint
```

### Session State

Maintained in `StepExecutor` instance:

```python
papers_db: PapersDatabase       # Current papers
definition: Dict                # Loaded YAML definition
templates: Dict                 # Parsed templates
steps: List                     # Main steps sequence
results: Dict                   # Last step results
step_history: List              # Execution log
current_step_index: int         # Where to resume
step_timings: List              # Per-step durations
```

### Step Navigation API

For REPL/CLI convenience, the executor provides properties and methods for step navigation:

```python
# Properties
executor.has_steps         # bool: True if definition has steps
executor.has_next_step     # bool: True if there's a next step to execute
executor.step_progress     # Tuple[int, int]: (current_index, total_steps)

# Methods
executor.describe_next_step()   # Dict with step details or None
executor.execute_next_step()    # Execute current step, advance index
```

Example usage:
```python
while executor.has_next_step:
    info = executor.describe_next_step()
    print(f"Executing step {info['index']}: {info['description']}")
    if info['is_template']:
        print(f"  (template: {info['template_name']})")
    result = executor.execute_next_step()
    print(f"  Status: {result['status']}")
```

## Execution Modes

### Batch Mode (Workflow Execution)

Run complete pipelines from CLI:

```python
executor = StepExecutor(general_config, cache_dir=cache_dir, verbose=verbose, debug=debug)
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()
stats = executor.run_all(dry_run=False)
print(executor.get_stats())
```

- Automatic checkpoint detection and resume
- Fails on first step error
- Collects comprehensive statistics

#### Progress Callbacks

For UIs that need progress feedback, `run_all()` supports optional callbacks:

```python
def on_step_start(step_index: int, step_config: Dict, total_steps: int) -> None:
    """Called before each step executes"""
    print(f"Starting step {step_index + 1}/{total_steps}...")

def on_step_end(step_index: int, step_config: Dict, result: Dict) -> None:
    """Called after each step completes"""
    status = result.get('status', 'unknown')
    print(f"Step {step_index} completed with status: {status}")

executor.run_all(
    dry_run=False,
    on_step_start=on_step_start,
    on_step_end=on_step_end
)
```

This keeps UI concerns separate from the executor while avoiding reimplementation of the execution loop.

### Single-Step Mode (REPL/Interactive)

Run steps one at a time with explicit checkpoint control:

```python
executor = StepExecutor(general_config, cache_dir=cache_dir, verbose=verbose, debug=debug)
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()

# Execute step by step
result = executor.execute_step(0)
if result['status'] == 'ok':
    executor.checkpoint()  # Explicit save

result = executor.execute_step(1)
if result['status'] == 'ok':
    executor.checkpoint()

# Check status anytime
stats = executor.get_stats()
```

- Manual step control
- Explicit checkpointing (no auto-save)
- Full access to session state

## Statistics & Inventory

The executor collects timing and execution statistics throughout pipeline runs via `step_timings` (per-step duration tracking) and `step_history` (execution log with status).

`executor.get_stats()` returns:

```python
{
    "project_name": str,
    "papers_total": int,
    "papers_unique": int,
    "papers_duplicates": int,
    "current_step_index": int,
    "total_steps": int,
    "steps_executed": int,
    "step_timings": [
        {"step": str, "duration_seconds": float, "duration_ms": int}
    ],
    "step_history": [
        {"index": int, "step": str, "status": str, "duration_seconds": float}
    ],
    "templates": {"count": int, "names": [str]},
    "inventory": {
        "builtin_steps": [str],      # Available builtin steps
        "templates": [str]            # Defined templates in definition
    },
    "total_duration_seconds": float
}
```

## Error Handling

1. **Definition Load Errors**: Raised immediately if file not found or invalid YAML
2. **Template Validation**: All references validated at load time via `_validate_template_references()` (fail early)
3. **Undefined Templates**: Caught during validation, not at execution
4. **Step Execution Errors**: Caught during `execute_step()`, returned in result dict with `status: error`
5. **HaltException Handling**: When a step raises `HaltException`, the executor catches it and returns `status: halted` (distinct from `status: error`). This allows graceful pipeline stops without being treated as failures. Custom halt messages are preserved in the result.
6. **Checkpoint Errors**: Non-fatal; logged but don't halt pipeline

## Integration with REPL & Batch Tasks

### Batch Task (run.py)

```python
from paper_scanner.cli.executor import StepExecutor

executor = StepExecutor(general_config, cache_dir=cache_dir, verbose=verbose, debug=debug)
executor.load_definition(definition_file)
executor.load_checkpoint(skip_checkpoint, clear_checkpoint)
results = executor.run_all(dry_run)
```

### REPL Task (repl.py)

```python
executor = StepExecutor(general_config, cache_dir=cache_dir, verbose=verbose, debug=debug)
executor.load_definition(definition_file)
executor.load_checkpoint()

# Interactive loop
for user_command in repl_loop():
    if user_command == "step":
        result = executor.execute_step(executor.current_step_index)
    elif user_command == "checkpoint":
        executor.checkpoint()
    elif user_command == "stats":
        print(executor.get_stats())
```

## Design Decisions

1. **Static Templates (v1)**: No parameter injection to keep scope manageable. Template nesting is supported. Parameter injection can be added in v2.
2. **Local Checkpoints Only (v1)**: No remote S3/HTTP downloads. Can add in v2.
3. **Explicit Checkpointing in Single-Step**: User must call `executor.checkpoint()` to save. Prevents accidental data loss.
4. **Early Template Validation**: Fail at definition load time to catch configuration errors before execution.
5. **Recursive Template Expansion**: Templates can be nested via `_execute_template()` recursively calling itself, enabling sophisticated reuse patterns.
6. **Class-Level Lazy Step Registry**: The `LazyStepRegistry` is stored at class level (`_step_registry`) rather than instance level. This is intentional:
   - **Lazy loading at validation time**: Step classes are imported when first accessed during `parse_step_config()` or `get_step()`, which occurs during validation. This ensures imports happen only when needed.
   - **Shared across instances**: Multiple executor instances (e.g., in tests or REPL sessions) share the same loaded classes, avoiding redundant imports.
   - **Fast startup**: CLI commands that don't use all steps benefit from not importing unused step modules.
