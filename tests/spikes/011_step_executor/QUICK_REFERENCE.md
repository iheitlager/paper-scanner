# StepExecutor Quick Reference Card

## Execution Modes

### Batch Mode (Execute All)
```python
executor = StepExecutor(general_config, cache_dir, verbose, debug, get_step_func)
executor.load_definition(definition_file)
executor.load_checkpoint()
results = executor.run_all(dry_run=False)
```

### Single-Step Mode (REPL)
```python
executor = StepExecutor(general_config, cache_dir, verbose, debug, get_step_func)
executor.load_definition(definition_file)
executor.load_checkpoint()

result = executor.execute_step(0)
executor.checkpoint()  # Explicit save
```

## Core Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `load_definition(path)` | Parse YAML, validate templates | bool |
| `load_checkpoint(skip, clear)` | Load/skip/clear saved state | None |
| `execute_step(index, config, dry_run)` | Execute one step | Dict |
| `run_all(dry_run)` | Execute all remaining steps | Dict |
| `checkpoint()` | Save current state | Dict |
| `get_stats()` | Get comprehensive statistics | Dict |
| `get_session_state()` | Get session info for REPL | Dict |

## Configuration Levels

```
Level 1: general_config        (Project-wide)
├─ project_name
├─ researcher
└─ institution

Level 2: step_config           (Step-specific)
├─ methods, thresholds, etc.
└─ Varies per step type

Level 3: Runtime flags         (Execution-wide)
├─ verbose=True/False
├─ dry_run=True/False
└─ debug=True/False
```

## Templates

### Definition (in YAML)
```yaml
templates:
  - template: "name"
    steps:
      - step: "Description"
        builtin.step-type: {...config...}
```

### Usage (in main steps)
```yaml
- step: "Apply template"
  builtin.run-template:
    template: "name"
```

## Checkpoints

**When to use**:
- Batch mode: Automatic after each step
- Single-step mode: Explicit via `executor.checkpoint()`

**Checkpoint file location**:
```
~/.paper-scanner/checkpoints/checkpoint_{hash}_step_{index:03d}.json
```

**Resume from checkpoint**:
```python
executor.load_checkpoint()  # Auto-loads latest
executor.run_all()          # Resumes from next step
```

## Statistics

### get_stats() Returns

```python
{
    'project_name': str,
    'papers_total': int,
    'papers_unique': int,
    'papers_duplicates': int,
    'current_step_index': int,
    'total_steps': int,
    'steps_executed': int,
    'step_timings': [
        {'step': str, 'duration_seconds': float, 'duration_ms': int}
    ],
    'step_history': [
        {'index': int, 'step': str, 'status': str, 'duration_seconds': float}
    ],
    'templates': {'count': int, 'names': [str]},
    'inventory': {
        'builtin_steps': [str],
        'templates': [str]
    },
    'total_duration_seconds': float
}
```

### get_session_state() Returns

```python
{
    'papers_db': PapersDatabase,
    'papers_count': int,
    'current_step_index': int,
    'total_steps': int,
    'step_history': [dict],
    'results': dict,
    'general_config': dict
}
```

## Error Handling

### Fail-Early (Definition Load)
```python
try:
    executor.load_definition(path)
except FileNotFoundError:      # File missing
    ...
except ValueError:            # Invalid YAML or undefined template
    ...
```

### Caught Errors (Step Execution)
```python
result = executor.execute_step(0)
if result['status'] == 'error':
    error_msg = result['error']  # Full details
```

### Non-Fatal (Checkpoint)
```python
# Checkpoint errors logged but don't halt
# Pipeline continues even if checkpoint fails
executor.checkpoint()  # Non-fatal if this fails
```

## Public Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `papers_db` | PapersDatabase | The papers database |
| `definition` | Dict | Loaded YAML definition |
| `templates` | Dict | Parsed templates |
| `steps` | List | Main steps sequence |
| `step_history` | List | Execution log |
| `current_step_index` | int | Resume point |
| `general_config` | Dict | Project config |

## Common Patterns

### Pattern: Start Fresh
```python
executor.load_checkpoint(clear_checkpoint=True, skip_checkpoint=True)
```

### Pattern: Resume from Checkpoint
```python
executor.load_checkpoint()  # Auto-finds latest
executor.run_all()
```

### Pattern: Dry Run
```python
executor.run_all(dry_run=True)
```

### Pattern: Interactive Loop
```python
while True:
    cmd = input("> ")
    if cmd == "step":
        result = executor.execute_step(executor.current_step_index)
    elif cmd == "checkpoint":
        executor.checkpoint()
    elif cmd == "stats":
        print(executor.get_stats())
```

### Pattern: Get Step Count
```python
total = len(executor.steps)
current = executor.current_step_index
remaining = total - current
```

### Pattern: Access Papers Database
```python
count = executor.papers_db.count()
count_unique = executor.papers_db.count(primary_only=True)
papers = executor.papers_db.papers  # Direct list access
```

## Result Dictionary Format

**From execute_step() or run_all()**:
```python
{
    'status': 'ok' | 'error' | 'halted' | 'warning',
    'step': str,                    # Step name
    'description': str,             # Optional
    'count': int,                   # Items processed
    'error': str,                   # If status='error'
    'duration_seconds': float,      # Execution time
    # ... plus step-specific fields
}
```

## Checkpoint Result Format

**From checkpoint()**:
```python
{
    'status': 'ok' | 'error',
    'checkpoint_file': Path,        # Where saved
    'papers_count': int,            # Papers saved
    'error': str                    # If status='error'
}
```

## Step Execution Steps

1. Get step config from definition
2. Check if `builtin.run-template` → expand template recursively
3. Instantiate step via `get_step_func()`
4. Validate step config
5. Execute step with (general_config + step_config + runtime_flags)
6. Return result dict
7. Track timing
8. Update step_history

## Files to Reference

| File | Purpose |
|------|---------|
| [class.md](../../../docs/executor/class.md) | Full API reference |
| [explanation.md](../../../docs/executor/explanation.md) | Architecture details |
| [executor.py](../../../src/paper_scanner/cli/executor.py) | Source code |
| [base.py](../../../src/paper_scanner/steps/base.py) | Step base class |

## Quick Test Files

| File | What it tests |
|------|---------------|
| 01_basic_setup.py | Definition loading |
| 02_batch_execution.py | Batch mode execution |
| 03_single_step_mode.py | Interactive mode |
| 04_statistics.py | Stats queries |
| 05_template_expansion.py | Templates |
| 06_error_handling.py | Error scenarios |

Run any with: `uv run filename.py`
