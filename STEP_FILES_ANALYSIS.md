# Step Files Database Usage Analysis

Analysis of all step files in `src/paper_scanner/steps/` to identify migration needs from `List[Paper]` to `PapersDatabase`.

---

## Summary

| Priority | Count | Files |
|----------|-------|-------|
| **CRITICAL** | 1 | deduplication.py |
| **HIGH** | 5 | bibtex_import.py, categorization.py, keyword_screening.py, semantic_screening.py, checkpoint.py |
| **LOW** | 4 | export.py, echo.py, halt.py, summarize.py |

---

## CRITICAL PRIORITY

### deduplication.py

**Status:** Already partially updated - MIXED USAGE

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,  # ← Already using PapersDatabase
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- ✓ Uses `papers_db.count(primary_only=False)` - method exists
- ✓ Uses `papers_db.to_list(primary_only=False)` - method exists
- ✓ Uses `papers_db.update(paper)` - method exists for updating individual papers
- ✓ Iterates over papers with filters

**Details:**
- Already expects `PapersDatabase` type
- Uses database methods correctly
- Updates papers with `papers_db.update(paper)` call
- Properly handles duplicates through screening model

**Recommendation:**
- **VERIFY COMPATIBILITY**: Ensure `PapersDatabase.update()` works as expected
- **NO CHANGES NEEDED** - This file is already aligned with new database interface
- May serve as reference implementation for other files

**Imports:**
```python
from ..core.database import PapersDatabase
```

---

## HIGH PRIORITY

### bibtex_import.py

**Status:** Needs immediate updating - MODIFIES DATA

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 156: `papers_db.extend(papers)` - **CRITICAL**: Extends list with new papers
- Line 142: `len(papers)` - Gets count of imported papers
- Usage is **WRITE OPERATION** - adds papers to database

**Details:**
- Imports BibTeX files and adds multiple papers at once
- Uses `list.extend()` which won't work with `PapersDatabase`
- Currently expects mutable list interface

**Recommendation:**
**CRITICAL UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `papers_db.extend(papers)` with batch add method:
   - Check if `PapersDatabase` has `.add_many(papers)` or `.extend(papers)`
   - If not, implement `papers_db.add(paper)` in a loop OR add batch method to database
3. Keep `len(papers)` tracking for parsed papers
4. Import: Add `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper
from ..core.enum import DiscoveryMethod
```

---

### categorization.py

**Status:** Needs updating - MODIFIES PAPER FIELDS

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 387: `len(papers_db)` - Gets total paper count
- Line 394+: `for i, paper in enumerate(papers_db):` - Iterates all papers
- Line 409: `paper.screening.categorization = categorization` - **MODIFIES** paper fields
- Line 412: `paper.screening.current_stage = "categorization_complete"` - **MODIFIES** state
- Line 416-419: `paper.screening.final_decision = ScreeningDecision.EXCLUDED` - **MODIFIES** decision

**Details:**
- Reads all papers from list
- Modifies each paper in-place (updates screening model)
- Does NOT use list methods like append/extend
- Currently relies on iteration over list

**Recommendation:**
**HIGH UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `len(papers_db)` with `papers_db.count()`
3. Replace loop with: `for i, paper in enumerate(papers_db.to_list()):`
4. After modifying paper, add: `papers_db.update(paper)` if needed
   - OR verify that modifications are persisted automatically
5. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper, Categorization, ProcessingMetadata
from ..core.enum import PaperType, StudyType, QualityTier, ScreeningDecision
```

---

### keyword_screening.py

**Status:** Needs updating - MODIFIES PAPER FIELDS

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 415: `len(papers_db)` - Gets total paper count
- Line 432: `for i, paper in enumerate(papers_db):` - Iterates all papers
- Line 451: `paper.screening.keyword_screening = screening` - **MODIFIES** paper
- Line 454-458: `paper.screening.final_decision = ScreeningDecision.EXCLUDED` - **MODIFIES** decision

**Details:**
- Reads and processes all papers sequentially
- Performs keyword-based filtering
- Modifies screening results for each paper
- Does NOT create/remove papers from database

**Recommendation:**
**HIGH UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `len(papers_db)` with `papers_db.count()`
3. Replace loop with: `for i, paper in enumerate(papers_db.to_list()):`
4. After modifying paper, add: `papers_db.update(paper)` if needed
5. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper, KeywordScreening, ProcessingMetadata
from ..core.enum import ScreeningDecision
```

---

### semantic_screening.py

**Status:** Needs updating - MODIFIES PAPER FIELDS

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False,
    project_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 268: `len(papers_db)` - Gets total paper count
- Line 297+: `for i, paper in enumerate(papers_db):` - Iterates all papers
- Modifies `paper.screening.semantic_screening` field
- Modifies `paper.screening.final_decision` field
- Uses embedding-based similarity scoring

**Details:**
- Reads all papers from list
- Performs semantic similarity screening using ML model
- Updates screening results for each paper
- Does NOT add/remove papers
- Computationally intensive (embedding generation)

**Recommendation:**
**HIGH UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `len(papers_db)` with `papers_db.count()`
3. Replace loop with: `for i, paper in enumerate(papers_db.to_list()):`
4. After modifying paper, add: `papers_db.update(paper)` if needed
5. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper, ProcessingMetadata, SemanticScreening
from ..core.enum import ScreeningDecision
```

---

### checkpoint.py

**Status:** Needs updating - READS AND SERIALIZES

**Current Signature:**
```python
def execute(config: Dict[str, Any], papers: List[Paper], verbose: bool = False, dry_run: bool = False) -> Dict[str, Any]:
```

**Note:** Parameter named `papers` instead of `papers_db` - inconsistent naming.

**Key Usage Patterns:**
- Line 50: `_serialize_papers(papers)` - Serializes all papers to JSON
- Line 52: Uses `papers` as list for serialization
- Does NOT iterate or modify papers
- Purely serialization operation

**Details:**
- Saves checkpoint of database state
- Converts all papers to JSON-serializable format
- No modifications to papers
- Read-only operation

**Recommendation:**
**HIGH UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase` (rename for consistency)
2. Rename `papers` to `papers_db` internally
3. Replace `papers` with `papers_db.to_list()` in serialization call:
   ```python
   serialized = _serialize_papers(papers_db.to_list())
   ```
4. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from paper_scanner.core.models import Paper
```

---

## LOW PRIORITY

### export.py

**Status:** Needs updating - READS AND FILTERS

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 83+: `if duplicates_option == "only":` filters with `p for p in papers_db if...`
- Line 87: `papers_to_export = papers_db` - Reference to full list
- Line 89: `papers_to_export = [p for p in papers_db if...]` - Filters with list comprehension
- Exports to JSONL or BibTeX format
- Does NOT modify papers

**Details:**
- Read-only filtering and export operation
- Uses list comprehensions for filtering
- Exports to external format
- No persistence to database

**Recommendation:**
**LOW UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. For full list: `papers_to_export = papers_db.to_list()`
3. For filtered lists: `papers_to_export = [p for p in papers_db.to_list() if...]`
   - OR implement filter method in `PapersDatabase`
4. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper
from ..io.json import papers_to_jsonl
from ..io.bibtex import papers_to_bibtex
```

---

### echo.py

**Status:** Needs updating - READS ONLY FOR LOGGING

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 54: `len(papers_db)` - Gets count for output
- Solely for displaying information
- No iteration, no modification

**Details:**
- Simple debug/logging step
- Only accesses paper count
- No meaningful database interaction beyond count

**Recommendation:**
**LOW UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `len(papers_db)` with `papers_db.count()`
3. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper
```

---

### halt.py

**Status:** Needs updating - READS ONLY FOR LOGGING

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 62: `len(papers_db)` - Gets count for output
- Line 68: `len(papers_db)` - Logs paper count
- Raises `HaltException` to stop pipeline
- No actual database interaction

**Details:**
- Control flow step (halt/stop)
- Only accesses paper count for logging
- Minimal database interaction

**Recommendation:**
**LOW UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace both `len(papers_db)` with `papers_db.count()`
3. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper
```

---

### summarize.py

**Status:** Needs updating - READS AND AGGREGATES

**Current Signature:**
```python
def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],  # ← NEEDS UPDATE
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
```

**Key Usage Patterns:**
- Line 99: `len(papers_db)` - Gets total count
- Line 101+: `for paper in papers_db:` - Iterates all papers for statistics
- Line 110: `[p for p in papers_db if...]` - List comprehension for filtering
- Generates summary statistics only
- Does NOT modify papers

**Details:**
- Read-only statistics aggregation step
- Iterates papers for counting, grouping, filtering
- Uses list comprehensions
- Generates output tables/reports

**Recommendation:**
**LOW UPDATE NEEDED:**
1. Change signature: `papers_db: PapersDatabase`
2. Replace `len(papers_db)` with `papers_db.count()`
3. Replace loops: `for paper in papers_db.to_list():`
4. Replace comprehensions: `[p for p in papers_db.to_list() if...]`
   - OR use `papers_db.filter()` if available
5. Add import: `from ..core.database import PapersDatabase`

**Current Imports:**
```python
from ..core.models import Paper
from ..core.enum import ScreeningDecision
```

---

## Migration Checklist

### Prerequisites
- [ ] Verify `PapersDatabase` API is complete:
  - [ ] `.count()` - Get paper count
  - [ ] `.to_list()` - Get all papers as list
  - [ ] `.update(paper)` - Update single paper
  - [ ] `.add(paper)` or `.add_many(papers)` - Add papers
  - [ ] `.filter()` - If filtering is common

### Immediate Updates (CRITICAL)
- [ ] **deduplication.py** - Verify existing usage works correctly
- [ ] **bibtex_import.py** - Add batch insertion method or loop

### Phase 1 (HIGH)
- [ ] **categorization.py** - Update signatures and method calls
- [ ] **keyword_screening.py** - Update signatures and method calls
- [ ] **semantic_screening.py** - Update signatures and method calls
- [ ] **checkpoint.py** - Update signatures and serialization call

### Phase 2 (LOW)
- [ ] **export.py** - Update signatures and filtering
- [ ] **summarize.py** - Update signatures and iterations
- [ ] **echo.py** - Update signatures and count
- [ ] **halt.py** - Update signatures and count

### Testing
- [ ] Unit tests for each step with `PapersDatabase`
- [ ] Integration test of full pipeline
- [ ] Checkpoint/resume functionality with new database

---

## Implementation Notes

### Pattern: Read All Papers
```python
# OLD
for paper in papers_db:

# NEW
for paper in papers_db.to_list():
```

### Pattern: Get Count
```python
# OLD
len(papers_db)

# NEW
papers_db.count()
```

### Pattern: Filter Papers
```python
# OLD
filtered = [p for p in papers_db if condition]

# NEW
filtered = [p for p in papers_db.to_list() if condition]
# OR if PapersDatabase.filter() exists:
filtered = papers_db.filter(condition)
```

### Pattern: Add Papers
```python
# OLD
papers_db.extend(papers)

# NEW
# Option 1: If batch add exists
papers_db.add_many(papers)
# Option 2: Add individually
for paper in papers:
    papers_db.add(paper)
```

### Pattern: Update Paper
```python
# OLD (in-place mutation)
paper.field = value

# NEW (verify if needed)
paper.field = value
papers_db.update(paper)  # Only if database doesn't track mutations
```

---

## Notes

1. **Inconsistent parameter naming**: `checkpoint.py` uses `papers` while others use `papers_db`. Should be standardized.

2. **Iteration patterns**: Most HIGH priority files need `.to_list()` wrapping when iterating.

3. **Deduplication is the reference**: Already uses `PapersDatabase` correctly - use as implementation guide.

4. **Performance consideration**: `.to_list()` creates a copy. If needed, consider adding iterator support to `PapersDatabase`.

5. **Update semantics**: Clarify whether `PapersDatabase` auto-persists mutations or requires explicit `.update()` calls.
