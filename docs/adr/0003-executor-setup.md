# ADR-0003: Unified StepExecutor Architecture for Pipeline Execution

**Status**: Accepted

**Date**: 2025-12-22

## Context

The paper-scanner project had separate, duplicated execution implementations:
- `run.py` - Batch pipeline execution from YAML definitions
- `repl.py` - Interactive single-step execution

Both implementations needed:
- YAML definition parsing and template support
- Session state management (database, results, history)
- Step sequencing and execution orchestration
- Checkpoint management for resuming pipelines
- Statistics and timing collection

This duplication created:
- **Code duplication**: Parsing, checkpoint logic, statistics collection repeated
- **Inconsistent behavior**: Different handling of templates, errors, resume logic
- **Maintenance burden**: Fixes needed in two places
- **Testing complexity**: Both modes needed separate test suites

We needed a **unified execution engine** that could support both batch and interactive modes without duplication.

## Decision

Create a **unified `StepExecutor` class** that:

1. **Handles definition loading** (YAML parsing, template validation, configuration extraction)
2. **Manages session state** (papers database, results, execution history, timing)
3. **Supports multiple execution modes** (batch via `run_all()`, single-step via `execute_step()`)
4. **Implements template expansion** (static templates with recursive nesting)
5. **Manages checkpoints** (local file-based resumption points)
6. **Provides statistics & navigation** (progress tracking, step details, inventory)

### Architecture

#### Three-Level Configuration Model

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

#### Data Flow

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
    ├── Batch Mode: StepExecutor.run_all()
    └── Single Mode: StepExecutor.execute_step(index)
    ↓
For each step:
    ├── Parse Ansible-style config (builtin.step_name)
    ├── Check if run-template → expand recursively
    ├── Track timing & results
    └── Update session state
    ↓
Optional: StepExecutor.checkpoint() → save papers_db to JSON
    ↓
StepExecutor.get_stats() → aggregate statistics
```

### Core Methods

**Constructor**:
```python
StepExecutor(
    general_config: Dict[str, Any],
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
    debug: bool = False,
    get_step_func=None,
)
```

**Definition & Checkpoints**:
- `load_definition(definition_file)` - Parse and validate YAML
- `load_checkpoint(skip, clear)` - Manage resume points

**Execution**:
- `execute_step(index, config, dry_run)` - Run single step
- `run_all(dry_run, callbacks)` - Run all remaining steps
- `checkpoint()` - Explicitly save state

**State & Statistics**:
- `get_stats()` - Comprehensive statistics and inventory
- `get_session_state()` - Current session for REPL
- Navigation: `has_next_step`, `step_progress`, `describe_next_step()`, `execute_next_step()`

### Templates (v1: Static)

Templates are predefined sequences of steps:

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
            - "medical"
```

Referenced via `run-template`:

```yaml
steps:
  - step: "Apply basic screening"
    builtin.run-template:
      template: "screen_basics"
```

Features:
- Static step sequences (no parameter injection in v1)
- Recursive nesting (templates can call templates)
- Validation at definition load time (fail early)

### Checkpoint System

Checkpoints save pipeline state for resumption:

- **Location**: `~/.paper-scanner/checkpoints/` (configurable)
- **Naming**: `checkpoint_{project_hash}_step_{index:03d}.json`
- **Content**: Project name, step index, timestamp, papers list
- **Scope**: Local files only (v1)

Resumption:
```python
executor.load_checkpoint()  # Auto-detect and load latest
executor.run_all()          # Resume from checkpoint point
```

### Session State

Maintained in executor instance:

```python
papers_db: PapersDatabase       # Current papers
definition: Dict                # Loaded YAML
templates: Dict                 # Parsed templates
steps: List                     # Main steps
step_history: List              # Execution log
current_step_index: int         # Resume position
step_timings: List              # Per-step durations
```

### Error Handling

1. **Definition errors** - Raised immediately (FileNotFoundError, ValueError)
2. **Template validation** - All references checked at load time (fail early)
3. **Step execution errors** - Caught and returned in result dict
4. **HaltException** - Returns `status: halted` (distinct from error)
5. **Checkpoint errors** - Non-fatal, logged

## Consequences

### Positive
- ✅ **No duplication**: Single executor serves both batch and interactive modes
- ✅ **Consistent behavior**: Same parsing, checkpoint, statistics logic
- ✅ **Easier testing**: One implementation to test
- ✅ **Better maintainability**: Bug fixes apply to both modes
- ✅ **Flexible usage**: Can execute single steps or full pipelines
- ✅ **State introspection**: Full access to session state for UIs/REPL
- ✅ **Statistics tracking**: Comprehensive timing and inventory collection
- ✅ **Template support**: Reusable step sequences with nesting
- ✅ **Explicit checkpoints**: User controls save points (no accidental loss)

### Negative
- ⚠️ **Single class complexity**: Large class with many methods (but well-organized)
- ⚠️ **No async support**: Synchronous only (acceptable for v1)
- ⚠️ **Static templates only**: No parameter injection yet (planned for v2)
- ⚠️ **Local checkpoints only**: No remote/S3 support (planned for v2)
- ⚠️ **Tight coupling to BaseStep**: Depends on step interface design (ADR-0002)

### Design Trade-offs Explained

1. **Static Templates (v1)**: No parameter injection to keep scope manageable. Can add in v2.
2. **Local Checkpoints Only (v1)**: No remote S3/HTTP. Can add in v2.
3. **Explicit Checkpointing**: Prevents accidental data loss by requiring manual save.
4. **Early Template Validation**: Catch configuration errors before execution starts.
5. **Recursive Template Expansion**: Enables sophisticated reuse via nesting.
6. **Class-Level Lazy Step Registry**: Shared across instances, imports only when needed.

## Implementation

### File Organization

```
src/paper_scanner/cli/
├── executor.py              # StepExecutor class
├── tasks/
│   ├── run.py              # Batch mode task (uses executor)
│   └── repl.py             # Interactive mode (uses executor)
└── paper_processor.py      # CLI entry point

docs/executor/
├── explanation.md          # Architecture overview (this section)
└── class.md                # API Reference (detailed method docs)
```

### Execution Modes

#### Batch Mode
```python
executor = StepExecutor(config, cache_dir=cache_dir)
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()
results = executor.run_all(dry_run=False)
```

- Automatic checkpoint detection
- Fails on first error
- Comprehensive statistics

#### Single-Step Mode (REPL)
```python
executor = StepExecutor(config, cache_dir=cache_dir)
executor.load_definition(Path("definition.yml"))
executor.load_checkpoint()

result = executor.execute_step(0)
if result['status'] == 'ok':
    executor.checkpoint()  # Explicit save
```

- Manual step control
- Explicit checkpointing
- Full state access

#### Progress Callbacks
```python
executor.run_all(
    on_step_start=lambda idx, cfg, total: print(f"Step {idx+1}/{total}..."),
    on_step_end=lambda idx, cfg, result: print(f"Status: {result['status']}")
)
```

### Testing Strategy

- Unit tests for each method
- Integration tests with sample definitions
- Batch mode execution tests
- Single-step/checkpoint tests
- Template expansion tests
- Error handling tests

### Phase 1: Core Implementation (Complete)
- [x] Create `StepExecutor` class
- [x] Implement `load_definition()` and YAML parsing
- [x] Implement checkpoint management
- [x] Implement `run_all()` and `execute_step()`
- [x] Template expansion with recursion
- [x] Statistics and inventory collection
- [x] Migrate `run.py` to use executor
- [x] Migrate `repl.py` to use executor

### Phase 2: Enhancements (Future)
- [ ] Parameter injection for templates (v2)
- [ ] Remote checkpoint storage (S3, HTTP)
- [ ] Async/parallel step execution
- [ ] Progress callback standardization
- [ ] Metrics export (Prometheus format)

## Alternatives Considered

### 1. Keep Separate Implementations
- ❌ Rejected: Maintenance burden, duplication, inconsistency

### 2. Create Lightweight Wrapper
- ❌ Rejected: Doesn't address root causes (duplication remains)

### 3. Shared Base Class
- ❌ Rejected: Inheritance hierarchy becomes complex, less flexible

### 4. Completely Async Design
- ❌ Rejected: Complexity not justified for current use cases
- ✅ Deferred to v2 when needed

## API Reference

See [executor/class.md](../executor/class.md) for detailed API documentation including:
- Constructor parameters
- Core methods (load_definition, execute_step, run_all, checkpoint, get_stats)
- Public attributes
- Error handling patterns
- Typical workflows

## Migration Path

1. **Phase 1**: Create unified executor, migrate both run.py and repl.py
2. **Phase 2**: Remove old separate implementations
3. **Phase 3**: Add enhancements (templates v2, async, remote checkpoints)

## Validation Checklist

- [x] Both batch and single-step modes work
- [x] Checkpoint resume works correctly
- [x] Statistics collection is accurate
- [x] Template validation catches errors early
- [x] Error handling is consistent
- [x] REPL integration is smooth
- [x] No regression from original implementations

## Relevant Links

- [ADR-0001: Pipeline Architecture](./0001-pipeline-architecture.md)
- [ADR-0002: Step Architecture](./0002-step-architecture.md)
- [StepExecutor API Reference](../executor/class.md)
- [StepExecutor Explanation](../executor/explanation.md)

## Questions & Future Decisions

1. **Async execution**: Should steps run in parallel? (Deferred to v2)
2. **Parameter injection for templates**: How to pass variables to templates? (v2 feature)
3. **Remote checkpoints**: Support S3/HTTP/database storage? (v2 feature)
4. **Plugin architecture**: Allow custom step loading? (Long-term)
5. **Metrics export**: Prometheus/OpenTelemetry integration? (v2 feature)
