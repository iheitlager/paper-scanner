# 011 StepExecutor Trial

**Spike**: Evaluate and trial unified `StepExecutor` architecture  
**Branch**: spike/011-step-executor  
**Status**: Complete  
**Date**: 2025-12-22  

## Goals

Explore and demonstrate the new unified `StepExecutor` architecture that:
- Replaces separate `run.py` and `repl.py` implementations
- Provides unified pipeline execution with both batch and interactive modes
- Handles definition loading, templates, checkpoints, and statistics centrally
- Offers clear integration patterns for CLI and REPL usage

## Research Questions

1. Does StepExecutor effectively unify batch and interactive execution?
2. Can it handle all current execution scenarios (batch, REPL, debugging)?
3. Are the integration patterns clear enough to implement in production?
4. What's the learning curve for new developers?
5. Are there gaps or limitations compared to current approach?

## Approach

- Review existing `executor.py` implementation
- Create working examples for all major features
- Demonstrate both execution modes (batch + REPL)
- Document integration patterns
- Provide comprehensive reference materials

## Findings

### ✅ Architecture Works Well
- Single unified core handles all execution modes
- Clear separation between executor logic and integration
- Integration patterns (BatchTaskExecutor, REPLSession) are straightforward
- Easy to add new features that benefit all modes

### ✅ All Features Implemented
- Definition loading with YAML parsing and template validation
- Template support (v1: static step sequences)
- Checkpoint management (save/load/resume)
- Session state management (database, results, history)
- Statistics collection and queries
- Error handling (fail-early + caught errors + non-fatal recovery)

### ✅ Documentation & Examples
- 6 progressive examples (basic → advanced)
- Comprehensive API reference
- Integration patterns clearly documented
- Quick reference cheat sheet
- Production-ready code samples

## Structure

```
011_step_executor/
├── Documentation
│   ├── README.md (this file)
│   ├── QUICK_REFERENCE.md - API cheat sheet
│   └── test_definition.yml - Sample YAML definition (uses Scopus data)
├── Examples (Progressive Complexity)
│   ├── 01_basic_setup.py - Executor init & definition loading
│   ├── 02_batch_execution.py - Batch mode with CLI args
│   ├── 03_single_step_mode.py - Interactive REPL mode
│   ├── 04_statistics.py - Stats & session state queries
│   ├── 05_template_expansion.py - Template analysis
│   └── 06_error_handling.py - Error scenarios
└── Integration
    └── INTEGRATION_EXAMPLE.py - Integration patterns for run.py/repl.py
```

**Test Data**: All examples use `tests/data/scopus_sample_20.bib` (Scopus export format with 20 papers)

## Quick Start

### 1. Understand Architecture (5 min)
```bash
# Read the quick reference
cat QUICK_REFERENCE.md
```

### 2. See It In Action (2 min)
```bash
# Run basic setup example
uv run 01_basic_setup.py

# Run batch execution (dry-run is safe)
uv run 02_batch_execution.py --dry-run
```

### 3. Try Interactive Mode (5 min)
```bash
# Run REPL example
uv run 03_single_step_mode.py
# Try: step, checkpoint, stats, history commands
```

### 4. Explore Specifics
```bash
uv run 04_statistics.py        # Query stats
uv run 05_template_expansion.py # Understand templates
uv run 06_error_handling.py    # See error handling
```

### 5. Study Integration
```bash
# View integration patterns
python INTEGRATION_EXAMPLE.py
```

## Key Concepts

### Three-Level Configuration
```
Level 1: general_config (project-wide)
├─ project_name, researcher, institution
Level 2: step_config (step-specific)
├─ methods, thresholds, parameters
Level 3: runtime_flags (execution-wide)
├─ verbose, dry_run, debug
```

### Execution Modes

**Batch Mode** (run_all)
- Execute all steps sequentially
- Auto-checkpoint after each step
- Comprehensive statistics collection
- Ideal for complete pipeline runs

**Single-Step Mode** (execute_step)
- Manual step-by-step control
- Explicit checkpointing
- Full access to session state
- Ideal for REPL/interactive exploration

### Templates (v1)
- Static sequences of steps
- No parameter injection (constraint)
- No nesting (constraint)
- Defined in YAML, referenced via `builtin.run-template`
- Validated at definition load time

### Checkpoints
- Save papers database at step boundaries
- Automatic resume in batch mode
- Explicit control in single-step mode
- File-based: `~/.paper-scanner/checkpoints/checkpoint_{hash}_step_{index:03d}.json`

## Public API Summary

### Methods
| Method | Purpose |
|--------|---------|
| `load_definition(path)` | Load and validate YAML |
| `load_checkpoint(skip, clear)` | Load/skip/clear checkpoints |
| `execute_step(index, config, dry_run)` | Execute single step |
| `run_all(dry_run)` | Execute all remaining steps |
| `checkpoint()` | Save current state |
| `get_stats()` | Get comprehensive statistics |
| `get_session_state()` | Get session information |

### Attributes
| Attribute | Type | Purpose |
|-----------|------|---------|
| `papers_db` | PapersDatabase | The papers database |
| `definition` | Dict | Loaded YAML definition |
| `templates` | Dict | Parsed templates |
| `steps` | List | Main steps sequence |
| `step_history` | List | Execution log |
| `current_step_index` | int | Resume point |
| `general_config` | Dict | Project config |

## Error Handling

### Fail-Early (Definition Load)
- Missing file → `FileNotFoundError`
- Invalid YAML → Exception from yaml.safe_load()
- Undefined template → `ValueError` during validation

### Caught (Step Execution)
- Returned in result dict with `status='error'`
- Full error details in `result['error']`
- Pipeline continues (user controls retry)

### Non-Fatal (Checkpoint)
- Logged but don't halt execution
- Allows recovery from read-only filesystems

## Integration Patterns

### Pattern 1: Batch Task (for run.py)
```python
class BatchTaskExecutor:
    def run(self, skip_checkpoint=False, dry_run=False):
        executor = StepExecutor(general_config, cache_dir, ...)
        executor.load_definition(definition_file)
        executor.load_checkpoint(skip_checkpoint=skip_checkpoint)
        return executor.run_all(dry_run=dry_run)
```

### Pattern 2: REPL Session (for repl.py)
```python
class REPLSession:
    def run(self):
        executor = StepExecutor(general_config, cache_dir, ...)
        executor.load_definition(definition_file)
        executor.load_checkpoint()
        
        while True:
            cmd = input("> ")
            if cmd == "step":
                executor.execute_step(executor.current_step_index)
            elif cmd == "checkpoint":
                executor.checkpoint()
            elif cmd == "stats":
                print(executor.get_stats())
```

See `INTEGRATION_EXAMPLE.py` for full implementations.

## Example Files

### 01_basic_setup.py
Demonstrates:
- Executor initialization
- Definition loading
- Structure inspection
- Session state access

### 02_batch_execution.py
Demonstrates:
- Definition loading
- Checkpoint management
- Batch execution (run_all)
- Statistics collection
- CLI argument support (--dry-run, --skip-checkpoint, --clear-checkpoint)

### 03_single_step_mode.py
Demonstrates:
- Definition loading
- Interactive REPL loop
- Single-step execution
- Explicit checkpointing
- Per-command statistics

Commands: step, checkpoint, stats, state, history, quit

### 04_statistics.py
Demonstrates:
- get_stats() comprehensive statistics
- get_session_state() for REPL integration
- Direct attribute access
- Definition content queries

### 05_template_expansion.py
Demonstrates:
- Template definition and structure
- Template validation
- Template reference detection
- Expansion planning

### 06_error_handling.py
Demonstrates:
- Missing definition file
- Invalid YAML syntax
- Undefined template references
- Step execution errors
- Checkpoint error recovery

## References

### Core Implementation
- `src/paper_scanner/cli/executor.py` - StepExecutor implementation
- `docs/executor/class.md` - Full API reference
- `docs/executor/explanation.md` - Architecture details
- `src/paper_scanner/steps/base.py` - Step base class

### Related Spikes
- `tests/spikes/007_new_approach/` - Fluent definition API

## Next Steps (v2 Planning)

### Planned Features
- **Parameterized Templates**: Inject variables at call site
- **Template Nesting**: Templates calling other templates
- **Remote Checkpoints**: S3, HTTP support
- **Streaming Statistics**: Real-time UI updates
- **Step Rollback**: Replay from checkpoint
- **Checkpoint Branching**: Fork execution paths

## Verification Checklist

✅ All core features demonstrated  
✅ Both execution modes working  
✅ Error handling covered  
✅ Integration patterns documented  
✅ Examples are self-contained  
✅ Documentation is comprehensive  
✅ API is clear and usable  
✅ Production-ready code patterns  

## Conclusion

The StepExecutor architecture is **production-ready**. It effectively:
- Unifies batch and interactive execution
- Handles all current scenarios
- Provides clear integration patterns
- Simplifies maintenance and feature additions

Ready to integrate into `run.py` and `repl.py` using provided patterns.
