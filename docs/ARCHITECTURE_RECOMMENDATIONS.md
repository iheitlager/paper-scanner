# Architecture Improvements: Step Result Handling & Logging

## Current State Analysis

### 1. **Result/Return Messages Issues**
- **Inconsistent structure**: Steps return `Dict[str, Any]` with no standardized schema
  - Some steps use `"count"`, others use `"papers_count"`, others use `"changed"`
  - Missing fields vary by step (no required vs optional contract)
  - Example inconsistencies:
    ```python
    # export.py
    {"status": "success", "message": "...", "count": 42}
    
    # halt.py  
    {"status": StepStatus.HALTED, "message": "...", "papers_count": 123}
    ```

- **No rich metadata**: Results lack operational details
  - No timestamps per step
  - No execution duration
  - No detail-level breakdown (e.g., processed vs skipped vs error count)
  - No warnings or non-fatal issues separate from success

- **Executor coupling**: Executor manually adds fields post-execution
  ```python
  result["step"] = step_name  # Added by executor, not step
  result["description"] = description  # Added by executor
  ```

### 2. **Logging Issues**
- **Logging mixed with results**: Steps use `console.print()` directly
  - Makes it hard to test (stdout/stderr pollution)
  - No structured logging (no log levels, no timestamp metadata)
  - Rich formatting is in code, not configuration
  - No way to disable logging during execution

- **No live feedback**: Long-running operations have no progress indication
  - User has no visibility until step completes
  - Especially problematic for network operations (DOI lookup, LLM calls)

- **Hardcoded console output**: Can't easily redirect or mock

### 3. **Error Handling Issues**
- **No distinction between types of failures**:
  - Fatal errors (should halt pipeline) vs warnings (should continue)
  - Some exceptions handled in executor, some in steps
  - `HaltException` is special-cased but inconsistent with normal error flow

- **Exception swallowing**: Executor catches all exceptions and converts to `"error"` status
  ```python
  except Exception as e:
      error_msg = f"Step {i} ({step_name}) failed: {str(e)}"
      # No way to distinguish between different error types
  ```

---

## Recommended Architecture

### 1. **Standardized Result Schema (Lightweight Dataclass)**

Create a new file: `src/paper_scanner/core/step_result.py`

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from paper_scanner.core.enum import StepStatus

@dataclass
class StepResult:
    """Standardized result from step execution"""
    
    # Required fields
    status: StepStatus  # Use StepStatus.SUCCESS, WARNING, ERROR, or HALTED
    step: str  # Step name (set by executor)
    
    # Result details
    message: str = ""  # Summary message for CLI display
    description: Optional[str] = None  # From YAML workflow definition
    
    # Statistics - flexible dict for any step-specific counts
    # Common keys: processed, created, updated, deleted, skipped, errors
    stats: Dict[str, int] = field(default_factory=dict)
    
    # Rich messages for operators
    details: Optional[str] = None  # Detailed result (markdown format, multi-line)
    
    # Error details (only if status is "error")
    error: Optional[str] = None  # Error summary
    error_detail: Optional[str] = None  # Full error with traceback
    
    # Metadata - flexible dict for timestamps, duration, etc.
    # Common keys: duration_seconds, duration_ms, started_at, ended_at
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __getitem__(self, key: str) -> Any:
        """
        Dict-like access for backward compatibility.
        
        Allows: result['message'] → result.message
        Preferred: Use attribute access directly (result.message)
        
        Args:
            key: Field name
            
        Returns:
            Field value
            
        Raises:
            KeyError: If field doesn't exist
        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for serialization.
        
        Recommended when you need JSON output or logging:
            result_dict = result.to_dict()
            json.dumps(result_dict)
        
        Returns:
            Dictionary representation
        """
        return {
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "step": self.step,
            "message": self.message,
            "description": self.description,
            "stats": self.stats,
            "details": self.details,
            "error": self.error,
            "error_detail": self.error_detail,
            "metadata": self.metadata,
        }
```

**Why lightweight**:
- No external dependencies (dataclass is stdlib)
- No validation (executor doesn't need it)
- Flexible dicts for `stats` and `metadata` (any step can add custom keys)
- Type-safe with IDE autocomplete
- Minimal overhead, easy to understand

**Simple Usage Example**:

```python
# In a step's execute() method
from paper_scanner.core.step_result import StepResult

def execute(self, config, verbose=False, dry_run=False, debug=False, callback=None):
    """Simple example: import papers from file"""
    
    file_path = config.get("file")
    papers = load_papers_from_file(file_path)
    
    return StepResult(
        status=StepStatus.SUCCESS,
        step="bibtex_import",
        message=f"Imported {len(papers)} papers",
        stats={"processed": len(papers), "created": len(papers)},
        metadata={"duration_seconds": 2.3}
    )

# In executor, just access fields:
result = step.execute(config)
if result.status == StepStatus.SUCCESS:
    print(f"✓ {result.message}")
    print(f"  Processed: {result.stats.get('processed', 0)}")
elif result.status == StepStatus.ERROR:
    print(f"✗ Error: {result.error}")
```

#### Status Semantics: SUCCESS vs WARNING vs ERROR

The three statuses have **clear, distinct meanings**. Crucially: **no CRITICAL status** — exceptions are reserved for fatal system failures that the executor catches and handles.

##### StepStatus Enum Reference

The `StepStatus` enum in `src/paper_scanner/core/enum.py` defines the allowed status values:

```python
class StepStatus(str, Enum):
    """Status of a processing step — returned in StepResult.status"""
    SUCCESS = "ok"      # Step completed successfully, no issues
    WARNING = "warning" # Step completed with partial success or recoverable issues
    ERROR = "error"     # Step failed to achieve its objective
    HALTED = "halted"   # Pipeline intentionally halted (via halt step)
    READY = "ready"     # (Reserved for future use)
    SKIPPED = "skipped" # (Reserved for future use)
```

**Important**: Only `SUCCESS`, `WARNING`, `ERROR`, and `HALTED` are in active use. See decision table below for when to use each.

##### Status Definitions

| Status | Meaning | Example | Executor Action | When to Use |
|--------|---------|---------|-----------------|-------------|
| **SUCCESS** | Completed as intended | `bibtex_import`: Processed 42 papers, 0 errors | ✅ Continue | All work succeeded, no issues |
| **WARNING** | Completed with partial success | `retrieve_metadata`: 85/100 papers, 15 citations unresolved | ✅ Continue | Most work succeeded, some items failed but step recovered |
| **ERROR** | Step failed to achieve objective | `export`: File permission denied on output | ❌ Log + Continue if possible (likely cascades) | Core functionality broken (DB, I/O, network service) |
| **HALTED** | Pipeline stopped intentionally | `halt` step executed | ⛔ Stop cleanly | User-requested halt (not an error) |

**Key Principles**:
1. Use **SUCCESS**, **WARNING**, **ERROR** for step completion status
2. **No CRITICAL** — fatal failures are **exceptions** (see below)
3. **Never** throw exceptions for data issues — return status=**ERROR** instead
4. **Only** throw exceptions for system-level failures (DB down, no file permissions)

---

##### Detailed Status Examples

**`SUCCESS`** — Completed as intended

```python
# All inputs processed without issues
return StepResult(
    status=StepStatus.SUCCESS,
    message="Imported 42 papers from 2 BibTeX files",
    stats={"processed": 42, "created": 42, "skipped": 0, "errors": 0},
    metadata={"duration_seconds": 2.3}
)
```

Characteristics:
- All inputs processed successfully
- No skipped items (or skipped due to valid reasons, but still "success")
- stats["errors"] = 0
- Executor continues to next step

---

**`WARNING`** — Completed with partial success

```python
# Most work succeeded, but some items failed without halting the step
return StepResult(
    status=StepStatus.WARNING,
    message="Retrieved metadata: 85/100 papers successful, 15 citations unresolved",
    stats={"processed": 100, "created": 85, "errors": 15},
    details="Failed to resolve 15 citations:\n"
            "- Smith et al. (2020): DOI lookup failed\n"
            "- Johnson et al. (2019): Crossref timeout\n"
            "... and 13 more",
    metadata={"duration_seconds": 45.2}
)
```

Characteristics:
- Step continued past errors and completed
- Some inputs had issues but step recovered
- stats["errors"] > 0 but step didn't abort
- Executor continues to next step
- Operator should review warnings before proceeding

**When to use WARNING** (not ERROR):
- ✅ Processing 100 papers, 15 fail → return status="warning"
- ✅ Deduplicating, some papers couldn't be analyzed → return status="warning"
- ✅ Exporting to BibTeX, 3 papers have encoding issues → return status="warning"
- ❌ NOT when database is unavailable → raise exception instead

---

**`ERROR`** — Step failed to achieve its objective

```python
# Core functionality broken; step could not complete
return StepResult(
    status=StepStatus.ERROR,
    message="Failed to write export file",
    error="Permission denied: /home/user/exports/output.jsonl",
    error_detail="Traceback:\n"
                "  File 'export.py', line 156, in execute\n"
                "    with open(output_file, 'w') as f:\n"
                "FileNotFoundError: [Errno 13] Permission denied",
    stats={"processed": 0, "errors": 1},
    metadata={"duration_seconds": 0.1}
)
```

Characteristics:
- Step attempted work but failed to achieve objective
- Unable to proceed (not "recovered and continued")
- Error is in **step logic**, not **data being processed**
- Executor logs error and continues (but subsequent steps may fail)

**When to use ERROR** (not an exception):
- ✅ Output file exists and is read-only → return status="error"
- ✅ Invalid configuration (missing required field) → return status="error"
- ✅ Database query failed (connection still up) → return status="error"
- ❌ NOT when system unavailable → raise exception instead

---

**`HALTED`** — Pipeline stopped intentionally (not an error)

```python
# User explicitly halted pipeline via halt step
raise HaltException("Reached checkpoint: manual review required")
# (Not returned as StepResult — the exception is the signal)
```

Characteristics:
- Only for intentional pipeline stops (halt step)
- NOT due to failure — this is a feature
- Executor exits cleanly, no error reported
- Exit code: 0 (success)

---

##### Error/Warning vs Exception: Critical Distinction

**Use ERROR or WARNING status when**:
- Step completed (didn't throw, didn't abort)
- Issues occurred but can be reported
- Work was done, but not perfectly
- Examples: Input validation failed, some papers couldn't be processed, file encoding issue

```python
def execute(self, config, ...):
    papers = load_papers(config['file'])
    results = []
    errors = 0
    
    for paper in papers:
        try:
            analysis = analyze_paper(paper)
            results.append(analysis)
        except AnalysisError as e:
            errors += 1
            callback.on_event(StepEvent(EventType.ERROR, f"Could not analyze {paper.title}"))
    
    # Step completed, even though some items failed
    return StepResult(
        status=StepStatus.WARNING if errors > 0 else StepStatus.SUCCESS,
        stats={"processed": len(papers), "errors": errors}
    )
```

**Throw exceptions when**:
- System-level failure (database, filesystem, network service)
- No recovery possible
- Pipeline should halt immediately
- Examples: DB connection lost, no write permissions, API auth failed

```python
def execute(self, config, ...):
    try:
        self.db.connect()  # Required
    except ConnectionError:
        raise StepFatalException("Database unavailable: cannot proceed")
    
    # This exception is caught by executor, pipeline halts with error
```

---

##### Exception Hierarchy

Create `src/paper_scanner/core/step_exceptions.py`:

```python
class StepException(Exception):
    """
    Base exception for step execution failures.
    
    These WILL halt the pipeline when raised.
    Only use for unrecoverable system-level failures.
    """
    pass

class StepHaltException(StepException):
    """
    Intentional pipeline halt — not an error, just a stop signal.
    
    Used by halt step when user wants to pause/end the workflow.
    Executor catches this and exits cleanly (exit code 0).
    """
    pass

class StepFatalError(PaperScannerError):
    """
    Raised when a step encounters a non-recoverable and fatal resource error during execution.

    Examples:
    - Not able to write to filesystems
    - No database available (to read or to write)
    """

    pass

class CheckpointError(PaperScannerError):
    """
    Raised when checkpoint operations fail.

    Examples:
    - Checkpoint file I/O errors
    - Corrupt checkpoint data
    - Checkpoint restoration fails
    """
    pass


class PipelineExecutionError(PaperScannerError):
    """
    Raised when a step execution fails during pipeline run.

    Examples:
    - Step processing fails
    - Data transformation errors
    - External service failures
    """
    pass
```

**When to raise which exception**:

```python
# ❌ DON'T: Raise for expected data issues
for paper in papers:
    try:
        metadata = resolve_metadata(paper)
    except ResolveError as e:
        raise e  # ❌ WRONG! This halts the pipeline
    
# ✅ DO: Return warning status instead
for paper in papers:
    try:
        metadata = resolve_metadata(paper)
    except ResolveError as e:
        errors += 1
        callback.on_event(StepEvent(EventType.ERROR, str(e)))
        continue  # Keep processing
        
return StepResult(status="warning" if errors else "success", stats={...})
```

```python
# ✅ DO: Raise for system failures
if not self.db.is_connected():
    raise StepFatalException("Database connection lost")

if not os.access(output_dir, os.W_OK):
    raise StepFatalException(f"No write permission: {output_dir}")

if api_response.status == 401:
    raise StepFatalException("API authentication failed")
```

---

##### Executor Behavior for Each Status

```python
try:
    result = step.execute(..., callback=callback)
    
    if result.status == StepStatus.SUCCESS:
        # ✅ Step completed successfully
        console.print(f"[green]ok[/green]: [{step_name}]")
        results["steps_executed"].append(result)
        # Continue to next step
        
    elif result.status == StepStatus.WARNING:
        # ⚠️  Step completed but with issues
        console.print(f"[yellow]warning[/yellow]: [{step_name}] {result.message}")
        if result.details:
            console.print(f"[dim]{result.details}[/dim]")
        results["steps_executed"].append(result)
        results["warnings"].append(result)
        # Continue to next step (but operator should review)
        
    elif result.status == StepStatus.ERROR:
        # ❌ Step failed to achieve its objective
        console.print(f"[red]error[/red]: [{step_name}] {result.message}")
        if result.error_detail and debug:
            console.print(f"[dim]{result.error_detail}[/dim]")
        results["steps_executed"].append(result)
        results["errors"].append(result)
        # Continue to next step (but likely to fail due to missing data)
        
except StepHaltException as e:
    # ⛔ User explicitly halted pipeline
    console.print(f"[yellow]halt[/yellow]: [{step_name}] {str(e)}")
    results["halted"] = True
    break  # Exit pipeline cleanly
    
    
except Exception as e:
    # 🔴 Unexpected exception (bug in step code)
    console.print(f"[red bold]BUG[/red bold]: [{step_name}] Unexpected {type(e).__name__}: {str(e)}")
    if debug:
        console.print(traceback.format_exc())
    results["errors"].append(f"Unexpected error: {str(e)}")
    break  # Exit pipeline with error
```

---

##### Output Examples

**Scenario 1: All SUCCESS**
```
$ paper-processor definition.yml
[green]ok[/green]: [bibtex_import] Imported 42 papers
[green]ok[/green]: [deduplication] Marked 5 duplicates
[green]ok[/green]: [export] Exported 37 unique papers

PLAY RECAP
ok=3 changed=0 failed=0
```

**Scenario 2: SUCCESS + WARNING**
```
$ paper-processor definition.yml
[green]ok[/green]: [bibtex_import] Imported 42 papers
[yellow]warning[/yellow]: [retrieve_metadata] Retrieved 38/42 papers (4 DOI lookups failed)
  Failed papers: Smith2020, Johnson2019, ...
[green]ok[/green]: [export] Exported 42 papers

PLAY RECAP
ok=2 changed=0 failed=0 warnings=1
```

**Scenario 3: ERROR (Step Failed)**
```
$ paper-processor definition.yml
[green]ok[/green]: [bibtex_import] Imported 42 papers
[red]error[/red]: [export] Failed to write output file
  Permission denied: /home/user/output.jsonl
[green]ok[/green]: [echo] Step executed (but has no input due to export failure)

PLAY RECAP
ok=2 changed=0 failed=1
```

**Scenario 4: FATAL EXCEPTION**
```
$ paper-processor definition.yml
[green]ok[/green]: [bibtex_import] Imported 42 papers
[red bold]FATAL[/red bold]: [retrieve_metadata] Database connection lost
(Pipeline halted - no further steps executed)

Exit Code: 1
```

### 2. **Callback-Based Event System**

Create `src/paper_scanner/core/step_callback.py`:

```python
from typing import Protocol, Callable
from enum import Enum

class EventType(str, Enum):
    """Types of events that can be reported during step execution"""
    INFO = "info"           # Informational message
    PROGRESS = "progress"   # Progress update (e.g., "Processing 5/100")
    WARNING = "warning"     # Non-fatal issue
    ERROR = "error"         # Error that doesn't halt but is recorded

class StepEvent:
    """Event emitted by step during execution"""
    def __init__(self, type: EventType, message: str, context: dict = None):
        self.type = type
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.now()

class StepCallback(Protocol):
    """Callback interface for steps to report progress/messages"""
    
    def on_event(self, event: StepEvent) -> None:
        """Called when step emits an event (warning, error, info)"""
        ...
    
    def on_progress(self, current: int, total: int, message: str = "") -> None:
        """Called to report progress during iteration
        
        Args:
            current: Current item count
            total: Total items to process
            message: Optional status message (e.g., "Processing paper 1")
        """
        ...
```

**Usage in steps**:

Callback should be initialized in `__init__` and stored as instance variable:

```python
from paper_scanner.core.step_callback import StepCallback, NullCallback
from paper_scanner.core.step_result import StepResult

class BibtexImportStep(BaseStep):
    def __init__(
        self,
        general_config: Dict[str, Any],
        db: PapersDatabase,
        cache_dir: Path,
        callback: Optional[StepCallback] = None,
    ):
        super().__init__(general_config, db, cache_dir)
        # Store callback as instance variable (allow injection for testing)
        self.callback = callback or NullCallback()  # Default no-op
    
    def execute(self, step_config, verbose=False, dry_run=False, debug=False, callback=None):
        # Use instance callback if no override provided
        cb = callback or self.callback
        
        # ... iteration ...
        for i, paper in enumerate(papers):
            cb.on_progress(i+1, len(papers), f"Importing {paper.title}")
            # ... process ...
            if warning:
                cb.on_event(StepEvent(EventType.WARNING, msg))
        
        return StepResult(status="success", stats={"processed": len(papers)})
```

**Usage in executor**:
```python
class ExecutorCallback:
    def __init__(self, verbose: bool, console: Console):
        self.verbose = verbose
        self.console = console
    
    def on_event(self, event: StepEvent):
        if event.type == EventType.WARNING:
            self.console.print(f"[yellow]⚠ {event.message}[/yellow]")
        elif event.type == EventType.ERROR:
            self.console.print(f"[red]✗ {event.message}[/red]")
        elif self.verbose and event.type == EventType.INFO:
            self.console.print(f"[cyan]ℹ {event.message}[/cyan]")
    
    def on_progress(self, current: int, total: int, message: str = ""):
        if self.verbose:
            pct = (current / total) * 100 if total > 0 else 0
            self.console.print(f"[dim]{message} ({current}/{total}, {pct:.0f}%)[/dim]")

# In executor:
callback = ExecutorCallback(verbose=verbose, console=console)
result = step.execute(step_config, verbose=verbose, callback=callback)
```

### 3. **Separate Error/Exception Handling**

Update `BaseStep.execute()` signature:

```python
@abstractmethod
def execute(
    self,
    step_config: Dict[str, Any],
    verbose: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    callback: Optional[StepCallback] = None,
) -> StepResult:
    """
    Execute the step.
    
    Args:
        step_config: Step-specific configuration
        verbose: Enable verbose output
        dry_run: Don't persist changes
        debug: Enable debug logging
        callback: Optional callback for progress/event reporting
    
    Returns:
        StepResult with standardized schema
    
    Raises:
        StepHaltException: Only when intentionally halting pipeline
        
    Notes:
        - Do NOT raise general exceptions; catch and return error status
        - Use callback.on_event() for live feedback
        - Use StepResult.error for fatal issues (status="error")
    """
```

**Exception rules**:
- Only `StepHaltException` escapes (intentional halt)
- All other exceptions are caught by step → return `StepResult(status="error", error=str(e))`
- This makes executor simpler and more predictable

```python
# In executor (simplified):
try:
    result = step.execute(..., callback=callback)
    if result.status == "error":
        results["errors"].append(result)
    elif result.status == "halted":
        break
except StepHaltException as e:
    # Only this escapes - predictable
    break
```

### 4. **Structured Logging Instead of Console.print**

Replace direct `console.print()` with structured logging:

```python
# Old (in steps):
console.print(f"[cyan]Processing {paper.title}[/cyan]")

# New:
self.callback.on_event(StepEvent(
    EventType.INFO, 
    f"Processing {paper.title}",
    context={"paper_id": paper.id}
))
```

**Benefits**:
- Testable (no stdout pollution)
- Filterable (executor controls verbosity)
- Structured (can log to files, metrics)
- Decoupled (steps don't know about Rich)

---

## Practical Examples: When to Use SUCCESS vs WARNING vs ERROR

### Example 1: `retrieve_metadata` Step

**Scenario**: Fetch DOI metadata for 100 papers. 85 succeed, 15 fail to resolve citations.

```python
def execute(self, config, verbose=False, dry_run=False, debug=False, callback=None):
    callback = callback or NullCallback()
    stats = {"processed": 0, "created": 0, "errors": 0}
    failed_details = []
    
    for i, paper in enumerate(self.db.get_all_papers()):
        callback.on_progress(i, len(papers), f"Fetching metadata: {paper.title}")
        stats["processed"] += 1
        
        try:
            metadata = self.fetch_from_crossref(paper.doi)
            paper.authors = metadata.authors
            self.db.update(paper)
            stats["created"] += 1
            
        except DOINotFoundError as e:
            # Data issue, not system failure - record and continue
            stats["errors"] += 1
            callback.on_event(StepEvent(
                EventType.WARNING,
                f"Could not resolve DOI {paper.doi}: {str(e)}"
            ))
            failed_details.append(f"- {paper.title}: {str(e)}")
        
        except Exception as e:
            # Unexpected error - still try to continue but record
            stats["errors"] += 1
            if debug:
                raise  # Re-raise in debug mode
    
    # Return WARNING status because some papers were not fully processed
    return StepResult(
        status=StepStatus.WARNING if stats["errors"] > 0 else StepStatus.SUCCESS,
        message=f"Fetched metadata for {stats['created']}/{stats['processed']} papers",
        stats=stats,
        details="Failed to fetch:\n" + "\n".join(failed_details) if failed_details else None
    )
```

**Executor output**:
```
[yellow]warning[/yellow]: [retrieve_metadata] Fetched metadata for 85/100 papers
```

---

### Example 2: `export` Step - File Permission Error

**Scenario**: Trying to export to read-only directory.

```python
def execute(self, config, verbose=False, dry_run=False, debug=False, callback=None):
    output_file = config["output"]
    
    # System check before processing
    try:
        with open(output_file, 'w') as f:
            pass  # Just test write permission
    except PermissionError as e:
        # This is a SYSTEM failure, not a data issue → return ERROR status
        return StepResult(
            status=StepStatus.ERROR,
            message=f"Cannot write to output file",
            error=f"Permission denied: {output_file}",
            error_detail=f"{type(e).__name__}: {str(e)}\n  Check directory permissions",
            stats={"processed": 0, "errors": 1}
        )
    
    # Now process papers
    papers = self.db.get_all_papers()
    
    try:
        with open(output_file, 'w') as f:
            for paper in papers:
                f.write(json.dumps(paper.to_dict()) + '\n')
        
        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Exported {len(papers)} papers",
            stats={"processed": len(papers), "created": len(papers)}
        )
        
    except Exception as e:
        # Unexpected failure during export
        return StepResult(
            status=StepStatus.ERROR,
            message="Export failed unexpectedly",
            error=str(e),
            error_detail=traceback.format_exc(),
            stats={"processed": 0, "errors": 1}
        )
```

**Executor output**:
```
[red]error[/red]: [export] Cannot write to output file
Details: Permission denied: /read-only/output.jsonl
```

---

### Example 3: `deduplication` Step - Database Failure

**Scenario**: Database connection lost mid-step.

```python
def execute(self, config, verbose=False, dry_run=False, debug=False, callback=None):
    callback = callback or NullCallback()
    
    try:
        papers = self.db.get_all_papers()  # ← Could raise if DB unavailable
        
        duplicates = self._find_duplicates(papers)
        
        for dup_group in duplicates:
            self.db.mark_duplicates(dup_group)  # ← Could raise if connection lost
            
        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Marked {len(duplicates)} duplicate groups",
            stats={"processed": len(papers), "created": len(duplicates)}
        )
        
    except DatabaseError as e:
        # SYSTEM failure - let it propagate to executor as exception
        # Executor will catch and halt
        raise StepFatalException(f"Database error: {str(e)}")
        
    except Exception as e:
        if debug:
            raise
        # Unexpected issue - return error status
        return StepResult(
            status="error",
            message="Deduplication failed",
            error=str(e),
            error_detail=traceback.format_exc()
        )
```

**Executor behavior**:
```python
try:
    result = step.execute(...)
except StepFatalException as e:
    # Halts pipeline immediately
    console.print(f"[red bold]FATAL[/red bold]: [{step_name}] {str(e)}")
    break  # Don't continue to next step
```

---

### Example 4: `categorization` Step - Partial LLM Failure

**Scenario**: LLM service timeout on 10% of papers, but step continues.

```python
def execute(self, config, verbose=False, dry_run=False, debug=False, callback=None):
    callback = callback or NullCallback()
    stats = {"processed": 0, "created": 0, "errors": 0}
    
    papers = self.db.get_all_papers()
    
    for paper in papers:
        callback.on_progress(
            stats["processed"], 
            len(papers),
            f"Categorizing: {paper.title}"
        )
        stats["processed"] += 1
        
        try:
            category = self.llm_categorize(paper)  # → Might timeout
            paper.category = category
            self.db.update(paper)
            stats["created"] += 1
            
        except LLMTimeoutError as e:
            # Service temporarily unavailable - record and continue
            stats["errors"] += 1
            callback.on_event(StepEvent(
                EventType.WARNING,
                f"LLM timeout for {paper.title}, skipping categorization"
            ))
            # Note: paper.category stays None/unchanged
            
        except Exception as e:
            stats["errors"] += 1
            if debug:
                raise
    
    # Mixed result - some succeeded, some failed
    status = StepStatus.SUCCESS if stats["errors"] == 0 else StepStatus.WARNING
    
    return StepResult(
        status=status,
        message=f"Categorized {stats['created']}/{stats['processed']} papers",
        stats=stats,
        details=f"{stats['errors']} papers skipped due to LLM timeouts" if stats["errors"] > 0 else None
    )
```

**Executor output**:
```
[yellow]warning[/yellow]: [categorization] Categorized 90/100 papers
Details: 10 papers skipped due to LLM timeouts
```

Details: 10 papers skipped due to LLM timeouts

---

## Status Decision Tree & Reference Table

### Decision Tree

```
Did the step complete its main objective?
├─ YES, no issues → return SUCCESS
├─ YES, but some items failed/skipped → return WARNING
├─ NO, step couldn't proceed → return ERROR
└─ User/config requested halt → raise HaltException

Is the failure due to a system/infrastructure issue?
├─ YES (DB unavailable, file permission, network auth) → raise StepFatalException
└─ NO (data issue, validation, LLM timeout) → return ERROR or WARNING status
```

### Status Behavior Reference

| Status | Meaning | Examples | Executor Action | Exit? |
|--------|---------|----------|-----------------|-------|
| **SUCCESS** | Completed as intended | All papers processed, no issues | ✅ Continue | No |
| **WARNING** | Completed with partial success | 85/100 papers processed, 15 citations failed | ✅ Continue, highlight issue | No |
| **ERROR** | Step failed to complete | Cannot write output file, DB query failed | ⚠️ Continue (but likely cascades) | No* |
| **HALTED** | Intentional stop (halt step) | User called halt | ⛔ Stop | Yes |
| **Exception** | System failure, unrecoverable | DB down, auth failed, corrupted data | ⛔ Stop immediately | Yes |

*Error status continues to next step, but pipeline likely fails later if dependent

### Exception Hierarchy

| Exception | Meaning | Examples | Executor Action |
|-----------|---------|----------|-----------------|
| **StepHaltException** | Intentional halt | `halt` step called | ⛔ Stop gracefully |
| **StepFatalException** | Unrecoverable system failure | DB unavailable, file permission denied, API auth error | ⛔ Stop, report fatal error |
| **Other exceptions** | Unexpected bugs | Should not escape steps | ⛔ Caught as fatal |

---

## Migration Plan

### Phase 1: Core Infrastructure (Minimal Breaking Change)
1. Create `StepResult` dataclass
2. Create `StepCallback` protocol
3. Update `BaseStep.execute()` signature to accept optional `callback`
4. Update `StepStatus` enum (already exists, keep it for backward compatibility)

### Phase 2: Executor Changes
1. Update `StepExecutor.execute_step()` to create and pass callback
2. Update result handling to work with `StepResult` objects
3. Update error display logic

### Phase 3: Step Migration (Can be incremental)
1. One step at a time, convert to return `StepResult`
2. Replace `console.print()` calls with `callback.on_event()`
3. Add progress reporting where applicable

### Phase 4: Legacy Cleanup
- Remove old result format support
- Deprecate direct `console.print()` in steps

---

## Example: Updated BibtexImportStep

```python
from paper_scanner.core.step_result import StepResult, StepResultStats
from paper_scanner.core.step_callback import StepCallback, StepEvent, EventType

class BibtexImportStep(BaseStep):
    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
        callback: Optional[StepCallback] = None,
    ) -> StepResult:
        """Execute bibtex import with live progress feedback"""
        
        callback = callback or NullCallback()
        imports_config = step_config.get("imports", [])
        stats = StepResultStats(processed=0, created=0, skipped=0, errors=0)
        
        for i, import_item in enumerate(imports_config):
            callback.on_progress(i, len(imports_config), f"Loading BibTeX file")
            
            try:
                bibtex_file = import_item.get("file")
                papers = bibtex_file_to_papers(bibtex_file)
                
                for j, paper in enumerate(papers):
                    callback.on_progress(i * 100 + j, len(imports_config) * 100)
                    
                    if dry_run:
                        stats["skipped"] += 1
                        continue
                    
                    existing = self.db.get_by_doi(paper.doi)
                    if existing:
                        stats["skipped"] += 1
                        callback.on_event(StepEvent(
                            EventType.INFO,
                            f"Paper '{paper.title}' already exists",
                            context={"doi": paper.doi}
                        ))
                        continue
                    
                    self.db.add(paper)
                    stats["created"] += 1
                    stats["processed"] += 1
                    
            except Exception as e:
                stats["errors"] += 1
                callback.on_event(StepEvent(
                    EventType.ERROR,
                    f"Failed to import {import_item.get('file')}: {str(e)}",
                    context={"file": import_item.get("file")}
                ))
                if debug:
                    raise
        
        # Return structured result
        return StepResult(
            status=StepStatus.SUCCESS if stats["errors"] == 0 else StepStatus.WARNING,
            step="bibtex_import",
            message=f"Imported {stats['created']} papers, skipped {stats['skipped']}",
            stats=stats,
            metadata={
                "duration_seconds": elapsed,
                "duration_ms": int(elapsed * 1000),
            }
        )
```

---

## Key Improvements Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Result Structure** | Inconsistent dict | Standardized TypedDict |
| **Live Feedback** | None | Callback-based events |
| **Error Granularity** | All exceptions same | Distinct error types |
| **Logging** | Rich formatting in code | Structured events, formatting in executor |
| **Testability** | Difficult (stdout) | Easy (no side effects) |
| **Error Recovery Info** | Missing | `error_detail` with traceback |
| **Progress Tracking** | Manual | Built-in progress callbacks |
| **Backward Compat** | N/A | Optional `callback` param, gradual migration |

---

## Files to Create/Modify

### New Files
- `src/paper_scanner/core/step_result.py` - Result schema
- `src/paper_scanner/core/step_callback.py` - Event system
- `src/paper_scanner/core/step_exceptions.py` - Clean exception hierarchy

### Modified Files
- `src/paper_scanner/steps/base.py` - Update signature, add callback param
- `src/paper_scanner/cli/tasks/run.py` - Update executor logic
- All step files - Incremental migration (non-breaking)

---

## Benefits for Your Team

1. **Better Debugging**: Clear error messages with context
2. **User Experience**: Real-time feedback for long operations
3. **Testing**: Mockable callbacks, no stdout pollution
4. **Monitoring**: Structured data ready for metrics/logging
5. **Maintainability**: Consistent patterns across all steps
6. **Extensibility**: Easy to add new event types or callbacks

---

## Design Patterns Reference: Similar Approaches in Other Systems

This architecture follows proven patterns used in production systems. Here's how other projects apply the same principles:

### 1. **Ansible - Task Result Standardization**

[Ansible](https://www.ansible.com/) uses a similar standardized result schema for all modules:

```python
# Ansible module result format (YAML)
{
    "changed": bool,           # Similar to our stats tracking
    "failed": bool,            # Similar to status=ERROR
    "rc": int,                 # Exit code
    "stdout": str,             # Similar to message
    "stderr": str,             # Error details
    "msg": str,                # Human-readable message
    "warning": [str],          # Array of warnings (our callback system)
}
```

**Key learnings**:
- All tasks return same schema → predictable executor
- Separate `changed` flag from `failed` → clear intent
- Warnings collected separately → operator visibility
- Callbacks for progress → long-running tasks stay responsive

### 2. **Apache Airflow - Task Status & Callbacks**

[Airflow](https://airflow.apache.org/) defines explicit task states and callback handlers:

```python
# Airflow task states (similar to our StepStatus)
class State:
    SUCCESS = "success"
    FAILED = "failed"
    UPSTREAM_FAILED = "upstream_failed"
    SKIPPED = "skipped"
    QUEUED = "queued"
    RUNNING = "running"
    SENSING = "sensing"

# Callback pattern (similar to our StepCallback)
def on_success_callback(context):
    """Called when task succeeds"""
    task = context['task_instance']
    print(f"Task {task.task_id} succeeded")

def on_failure_callback(context):
    """Called when task fails"""
    task = context['task_instance']
    exception = context['exception']
```

**Key learnings**:
- Discrete task states → clear semantics
- On-success/on-failure callbacks → decoupled from task logic
- Context passed to callbacks → full visibility
- Catch all exceptions → handle systematically

### 3. **Kubernetes Operators - Status Fields & Reconciliation**

[Kubernetes](https://kubernetes.io/) operator pattern uses status fields to track resource state:

```python
# Custom Resource status (similar to StepResult)
status:
    phase: "Running" | "Succeeded" | "Failed"
    conditions:
      - type: "Ready"
        status: "True"
        message: "All replicas ready"
    observedGeneration: 42
    replicas:
        desired: 3
        ready: 3
        updated: 3
```

**Key learnings**:
- Separate `spec` (intent) from `status` (state) → clear model
- Multiple conditions → granular error reporting
- observedGeneration tracking → eventual consistency
- Structured status object → machine-readable results

### 4. **GitHub Actions - Job & Step Status**

[GitHub Actions](https://github.com/features/actions) uses status enums for jobs and steps:

```yaml
# Job status outputs
status:
  - success       # Job succeeded
  - failure       # Job or step failed
  - cancelled     # Workflow cancelled

# Step result
steps:
  - name: "Build"
    run: "npm run build"
    id: build
    
# Access step result
${{ steps.build.outcome }}     # success | failure | cancelled
${{ steps.build.conclusion }}  # same, includes skipped
```

**Key learnings**:
- Step ID → referencing across workflow
- outcome vs conclusion → distinguish behavior
- Status always available → executor doesn't guess
- Conditional steps → continue or halt based on status

### 5. **Make & Task Runners - Exit Code Pattern**

Traditional build tools use simple exit code semantics:

```makefile
# Makefile - simple but effective
.PHONY: build
build:
	@npm run build || exit 1  # Fail immediately
	@npm run test || exit 1   # Exit code → status

# With warnings
@./script.sh              # Exit 0 = success
@if [ $$? -ne 0 ]; then \
  echo "Warning: Step had issues"; \
  exit 0;  # Continue despite issues (like our WARNING status) \
fi
```

**Key learnings**:
- Exit codes map to status → universal convention
- Small, composable steps → predictable behavior
- Error-first pattern → fail-safe defaults
- Pipe operators → natural error propagation

### 6. **Celery - Task Status & Event Streams**

[Celery](https://docs.celeryproject.io/) task status model:

```python
# Task states (similar to StepStatus)
class States:
    PENDING = "PENDING"      # Waiting to execute
    RECEIVED = "RECEIVED"    # Received but not yet executing
    STARTED = "STARTED"      # Task started
    SUCCESS = "SUCCESS"      # Task succeeded
    FAILURE = "FAILURE"      # Task failed
    RETRY = "RETRY"          # Task will retry
    REVOKED = "REVOKED"      # Task was cancelled

# Event callback pattern (similar to StepCallback)
def on_message(body):
    """Real-time event handler"""
    print(f"Task {body['id']}: {body['type']}")
    
app.control.inspect().active_queues()
```

**Key learnings**:
- Granular state machine → precise error handling
- Event stream callbacks → real-time visibility
- Separate PENDING from STARTED → understand bottlenecks
- Custom task results → structured error info

---

## Comparison: Our Architecture vs Others

| Aspect | Ansible | Airflow | Kubernetes | GitHub Actions | Ours |
|--------|---------|---------|-----------|-----------------|------|
| **Standardized Result** | ✅ Module schema | ✅ Task state | ✅ Status object | ✅ Step status | ✅ StepResult |
| **Multiple Status Types** | ✅ (changed, failed) | ✅ (8+ states) | ✅ (phases + conditions) | ✅ (success/failure/cancelled) | ✅ (SUCCESS/WARNING/ERROR/HALTED) |
| **Callback System** | ✅ Handler plugins | ✅ on_success/on_failure | ✅ Watch handlers | ❌ Limited | ✅ StepCallback protocol |
| **Live Progress** | ❌ No | ✅ Task logs | ✅ Events | ✅ Logs | ✅ on_progress() |
| **Error Granularity** | ✅ (rc, stderr, msg) | ✅ (exceptions logged) | ✅ (conditions array) | ❌ Binary | ✅ (error, error_detail) |
| **Testability** | ✅ (mocks) | ✅ (fixtures) | ✅ (test client) | ❌ Tied to GitHub | ✅ (NullCallback) |
| **Metadata Tracking** | ⚠️ (minimal) | ✅ (logs, duration) | ✅ (observedGeneration) | ✅ (timestamps) | ✅ (metadata dict) |

---

## Why This Design Is Proven

All these systems converge on the same patterns because:

1. **Standardized Results** → Executor can't guess what went wrong; step must communicate clearly
2. **Multiple Status Types** → Binary success/failure is too coarse; real work has nuance
3. **Callbacks for Live Feedback** → Users need visibility during long operations
4. **Structured Error Info** → Debugging requires context, not just exception messages
5. **Testability** → Mocking callbacks lets you test without side effects

This architecture will make `paper-scanner` align with industry best practices while remaining lightweight and easy to understand.
