# StepExecutor API Reference

## Constructor

```python
StepExecutor(
    general_config: Dict[str, Any],
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
    debug: bool = False,
    get_step_func=None,
)
```

**Parameters**:
- `general_config`: Project-level configuration dict (must include 'project_name')
- `cache_dir`: Directory for checkpoints (default: `~/.paper-scanner`)
- `verbose`: Enable verbose console output
- `debug`: Enable debug output with stack traces
- `get_step_func`: Function to instantiate steps: `Callable[[str], BaseStep]`

**Example**:
```python
from pathlib import Path
from paper_scanner.cli.executor import StepExecutor
from paper_scanner.cli.paper_processor import StepExecutor as ProcessorExecutor

general_config = {
    "project_name": "My Review",
    "researcher": "John Doe",
}

executor = StepExecutor(
    general_config,
    cache_dir=Path("/tmp/paper-scanner"),
    verbose=True,
    get_step_func=lambda name: ProcessorExecutor.get_step(name, general_config, executor.papers_db, executor.cache_dir)
)
```

---

## Core Methods

### load_definition(definition_file: Path) -> bool

Load and validate a YAML definition file.

**Arguments**:
- `definition_file`: Path to YAML definition file

**Returns**: `True` on success, raises exception on error

**Behavior**:
- Parses project metadata, templates, and steps
- Validates all template references (early fail)
- Initializes checkpoint directory
- Updates `general_config` from definition's `project` section

**Raises**:
- `FileNotFoundError`: Definition file not found
- `ValueError`: Empty definition, invalid YAML, or undefined template references

**Example**:
```python
executor.load_definition(Path("definition.yml"))
# Now executor.templates and executor.steps are populated
```

---

### load_checkpoint(skip_checkpoint: bool = False, clear_checkpoint: bool = False) -> None

Manage checkpoint state (load, skip, or clear).

**Arguments**:
- `skip_checkpoint`: If True, don't load from checkpoints
- `clear_checkpoint`: If True, delete all existing checkpoints

**Behavior**:
- Finds latest checkpoint file based on step index
- Restores papers database from checkpoint
- Sets `current_step_index` to resume point
- Does nothing if no checkpoint exists

**Example**:
```python
executor.load_checkpoint()  # Load latest if exists
executor.load_checkpoint(skip_checkpoint=True)  # Ignore checkpoints
executor.load_checkpoint(clear_checkpoint=True)  # Delete all, start fresh
```

---

### execute_step(step_index: int, step_config: Optional[Dict] = None, dry_run: bool = False) -> Dict[str, Any]

Execute a single step from the definition.

**Arguments**:
- `step_index`: Index in `self.steps` to execute (0-based)
- `step_config`: Override step config (default: use from definition)
- `dry_run`: If True, don't actually execute steps

**Returns**: Result dictionary with:
- `status`: "ok" | "error" | "halted" | "warning"
- `count`: Number of items processed
- `step`: Step name
- `description`: Optional step description
- Other step-specific fields

**Behavior**:
- Parses Ansible-style step config (`builtin.step_name`)
- Detects `run-template` and recursively expands template
- Tracks execution timing
- Updates `step_history` and `current_step_index`

**Example**:
```python
result = executor.execute_step(0)
if result['status'] == 'ok':
    print(f"Processed {result['count']} items")
    executor.checkpoint()  # Explicit save
```

---

### run_all(dry_run: bool = False) -> Dict[str, Any]

Execute all remaining steps sequentially.

**Arguments**:
- `dry_run`: If True, don't actually execute steps

**Returns**: Aggregated results dictionary with:
- `status`: Overall status ("ok" | "error" | "halted")
- `steps_executed`: Count of successfully executed steps
- `steps_failed`: Count of failed steps
- `total_duration_seconds`: Total execution time
- `step_results`: List of individual step results

**Behavior**:
- Loops from `current_step_index` to end of steps
- Stops on first error (returns with status "error")
- Respects checkpoint resume point
- Collects per-step timings

**Example**:
```python
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()  # Resume from checkpoint
results = executor.run_all()

if results['status'] == 'ok':
    print(f"Completed {results['steps_executed']} steps")
    print(f"Total time: {results['total_duration_seconds']}s")
```

---

### checkpoint() -> Dict[str, Any]

Save current database state as a checkpoint.

**Arguments**: None

**Returns**: Checkpoint result dictionary with:
- `status`: "ok" | "error"
- `checkpoint_file`: Path to saved checkpoint
- `papers_count`: Number of papers saved

**Behavior**:
- Creates checkpoints directory if needed
- Serializes all papers to JSON
- Saves with deterministic filename based on step index
- Only call this explicitly in single-step mode

**Example**:
```python
# Single-step mode (REPL)
executor.execute_step(0)
executor.checkpoint()  # Explicit save

executor.execute_step(1)
executor.checkpoint()
```

---

### get_stats() -> Dict[str, Any]

Get comprehensive execution statistics and inventory.

**Arguments**: None

**Returns**: Statistics dictionary with:
- `project_name`: Project name
- `papers_total`: Total papers (including duplicates)
- `papers_unique`: Unique papers (primary only)
- `papers_duplicates`: Duplicate count
- `current_step_index`: Current execution position
- `total_steps`: Total steps in definition
- `steps_executed`: Steps completed so far
- `step_timings`: List of per-step timing dicts
- `step_history`: List of execution log entries
- `templates`: Template count and names
- `inventory`: Available steps and templates
- `total_duration_seconds`: Overall duration

**Example**:
```python
stats = executor.get_stats()
print(f"Papers: {stats['papers_unique']} unique, {stats['papers_duplicates']} duplicates")
print(f"Progress: step {stats['current_step_index']}/{stats['total_steps']}")
print(f"Available templates: {stats['inventory']['templates']}")
```

---

### get_session_state() -> Dict[str, Any]

Get current session state for REPL integration.

**Arguments**: None

**Returns**: State dictionary with:
- `papers_db`: PapersDatabase instance
- `papers_count`: Count of papers
- `current_step_index`: Current position
- `total_steps`: Total steps
- `step_history`: Execution log
- `results`: Last step results
- `general_config`: Project configuration

**Example**:
```python
state = executor.get_session_state()
db = state['papers_db']
print(f"Papers in DB: {state['papers_count']}")
```

---

## Public Attributes

### papers_db: PapersDatabase

The indexed in-memory papers database. Can be queried and modified directly:

```python
papers = executor.papers_db.papers  # List of Paper objects
count = executor.papers_db.count(primary_only=True)  # Unique papers only
```

### definition: Dict[str, Any]

The loaded YAML definition as a dictionary:

```python
project_name = executor.definition['project']['name']
search_query = executor.definition['search']['query_definition']
```

### templates: Dict[str, List[Dict]]

Parsed templates, keyed by template name:

```python
template_steps = executor.templates['screen_basics']
for step in template_steps:
    print(step['step'])  # Step description
```

### steps: List[Dict[str, Any]]

Main steps sequence from definition:

```python
for i, step in enumerate(executor.steps):
    print(f"Step {i}: {step.get('step')}")
```

### step_history: List[Dict[str, Any]]

Execution log with timing information:

```python
for entry in executor.step_history:
    print(f"{entry['step']}: {entry['duration_seconds']}s")
```

### step_timings: List[Dict[str, Any]]

Per-step timing information:

```python
for timing in executor.step_timings:
    print(f"{timing['step']}: {timing['duration_ms']}ms")
```

### current_step_index: int

Current execution position (0-based):

```python
remaining = len(executor.steps) - executor.current_step_index
print(f"Steps remaining: {remaining}")
```

---

## Internal Methods (Reference)

### _validate_template_references() -> None

Validates all template references at definition load time. Raises `ValueError` if undefined templates are referenced.

### _parse_step_config(step_config: Dict) -> Tuple[str, Dict, Optional[str]]

Parses Ansible-style step config to extract step name, parameters, and description.

Returns: `(step_name, step_params, description)`

### _execute_builtin_step(...) -> Dict[str, Any]

Executes a single builtin step via `get_step_func`.

### _execute_template(...) -> Dict[str, Any]

Recursively expands and executes template steps.

### _get_project_hash() -> str

Generates deterministic MD5 hash for checkpoint naming.

### _find_latest_checkpoint() -> Tuple[Optional[int], Optional[Path]]

Finds latest checkpoint file and resume position.

### _load_checkpoint_file(checkpoint_file: Path) -> None

Loads papers from checkpoint JSON file.

---

## Error Handling Pattern

All public methods follow consistent error handling:

```python
# Configuration errors: Raised immediately
executor.load_definition(bad_file)  # Raises FileNotFoundError

# Execution errors: Returned in result dict
result = executor.execute_step(0)
if result['status'] == 'error':
    print(f"Step failed: {result['error']}")

# Template validation: Fails at definition load
executor.load_definition(definition_with_undefined_template)  # Raises ValueError
```

---

## Typical Workflows

### Complete Batch Pipeline
```python
executor = StepExecutor(general_config, get_step_func=get_step)
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()  # Resume if checkpoint exists
results = executor.run_all()
stats = executor.get_stats()
```

### Interactive Single-Step Exploration
```python
executor = StepExecutor(general_config, get_step_func=get_step, verbose=True)
executor.load_definition(Path("definition.yml"))

for i in range(len(executor.steps)):
    result = executor.execute_step(i)
    print(f"Step {i}: {result['status']}")
    
    if result['status'] == 'ok':
        executor.checkpoint()
    else:
        break
```

### Mid-Pipeline Template Application
```python
executor = StepExecutor(general_config, get_step_func=get_step)
executor.load_definition(Path("definition.yml"))

# Execute first few steps
for i in range(3):
    executor.execute_step(i)

# Apply template at step 3
result = executor.execute_step(3)  # run-template step

# Continue
executor.execute_step(4)
```

### Dry-Run Validation
```python
executor = StepExecutor(general_config, get_step_func=get_step)
executor.load_definition(Path("definition.yml"))
results = executor.run_all(dry_run=True)
print("Validation passed" if results['status'] == 'ok' else "Validation failed")
```
