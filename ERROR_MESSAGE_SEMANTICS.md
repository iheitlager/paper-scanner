# Error Message & Status Semantics - Enhancement Summary

Added comprehensive guidance to [ARCHITECTURE_RECOMMENDATIONS.md](ARCHITECTURE_RECOMMENDATIONS.md) for handling different result statuses and exceptions. Here's what was added:

## Status Hierarchy (Three Levels)

### 1. **SUCCESS** ✅
- **Meaning**: Completed as intended, all objectives met
- **Example**: "Imported 42 papers successfully"
- **Executor**: Continue to next step
- **Return**:
  ```python
  StepResult(
      status="success",
      message="Imported 42 papers",
      stats={"processed": 42, "created": 42}
  )
  ```

### 2. **WARNING** ⚠️
- **Meaning**: Completed with partial success; some items failed but step continued
- **Key distinction**: The step completed its objective, but not all inputs were fully processed
- **Examples**:
  - Retrieved metadata for 85/100 papers (15 citations unresolved)
  - Categorized 90/100 papers (10 LLM timeouts)
  - Processed 95 citations (5 DOI lookups failed)
- **Executor**: Continue to next step, but highlight in output
- **Return**:
  ```python
  StepResult(
      status="warning",
      message="Retrieved metadata for 85/100 papers",
      stats={"processed": 100, "created": 85, "errors": 15},
      details="Failed citations:\n- Paper A: ref not found\n- Paper B: DOI invalid"
  )
  ```

### 3. **ERROR** ❌
- **Meaning**: Step failed to complete its core function (not a data issue)
- **Examples**:
  - Cannot write output file (permission denied)
  - Database query failed
  - Network service unavailable (system-level, not temporary)
- **Key**: This is used for **interface/system failures**, NOT for individual data processing failures
- **Executor**: Try to continue (but likely cascades to failures in dependent steps)
- **Return**:
  ```python
  StepResult(
      status="error",
      message="Failed to write export file",
      error="Permission denied: /path/to/output.jsonl",
      error_detail="FileNotFoundError: [Errno 13] Permission denied\n  at export.py line 156"
  )
  ```

## Exception Handling (Outside Result Schema)

### **DO NOT use exceptions for data issues** ❌
```python
# WRONG:
try:
    metadata = resolve_citation(paper)
except CitationError as e:
    raise  # This halts the whole pipeline!

# CORRECT:
try:
    metadata = resolve_citation(paper)
except CitationError as e:
    stats["errors"] += 1
    callback.on_event(StepEvent(EventType.WARNING, f"Could not resolve: {e}"))
    # Return status="warning" at the end
```

### **DO use exceptions for system failures** ✅
```python
# System failures: Let them propagate
class StepHaltException(Exception):
    """Intentional halt - not an error"""
    pass

class StepFatalException(Exception):
    """Unrecoverable system failure - database unavailable, permission denied, etc."""
    pass

# In step:
if not db.is_connected():
    raise StepFatalException("Database connection lost")

if not os.access(output_dir, os.W_OK):
    raise StepFatalException("Output directory not writable")
```

### **Executor catches exceptions** 🛑
```python
try:
    result = step.execute(...)
    # Handle result.status in here
    
except (StepHaltException, StepFatalException) as e:
    # These exceptions HALT the pipeline immediately
    console.print(f"[red bold]FATAL[/red bold]: {str(e)}")
    break  # Exit pipeline
```

## Decision Tree for Step Authors

```
Is the step proceeding normally?
├─ YES, all objectives met
│   └─ return SUCCESS
│
├─ YES, but some items failed (data issues, timeouts, validation)
│   └─ return WARNING (with stats showing errors)
│
├─ NO, step can't proceed (system failure)
│   └─ Is it recoverable?
│       ├─ YES, try next time → return ERROR
│       └─ NO, fatal system issue → raise StepFatalException
│
└─ User requested halt
    └─ raise StepHaltException
```

## Practical Examples Included

Four real-world examples in the recommendations:

1. **`retrieve_metadata`** → Returns WARNING when some DOIs unresolvable
2. **`export`** → Returns ERROR when output file has permission issues
3. **`deduplication`** → Raises StepFatalException when database unavailable
4. **`categorization`** → Returns WARNING when LLM times out on some papers

Each shows:
- When to return what status
- When to raise exceptions
- How to use `callback` for live feedback
- How to populate `stats` dict
- When to include `error_detail` with traceback

## Reference Tables

### Status Behavior Reference
| Status | Meaning | Executor Action | Pipeline Continues |
|--------|---------|-----------------|-------------------|
| SUCCESS | All work done | Continue | Yes |
| WARNING | Partial success | Continue, highlight | Yes |
| ERROR | Step failed | Continue (cascades) | Yes |
| Exception | System fatal | Stop immediately | **No** |

### Exception Hierarchy
| Exception | When | Example | Result |
|-----------|------|---------|--------|
| StepHaltException | User halt | `halt` step | Stop gracefully |
| StepFatalException | System fatal | DB unavailable | Stop, report error |
| Other | Bugs | Not caught | Executor halts |

---

## Key Principles

1. **Data issues → Status field** (WARNING or ERROR status, depending on severity)
2. **System failures → Exceptions** (only StepHaltException or StepFatalException)
3. **Exceptions ALWAYS halt** the pipeline immediately
4. **Status field never halts** (executor continues to next step)
5. **No CRITICAL status** - use exceptions for critical/fatal issues instead
6. **Callbacks for live feedback** - use `on_event()` and `on_progress()` during execution
7. **Rich error details** - include `error_detail` field with full traceback for debugging

---

See [ARCHITECTURE_RECOMMENDATIONS.md](ARCHITECTURE_RECOMMENDATIONS.md) for the full details, code examples, and migration plan.
