# Paper Scanner 2.3.0 - Expansion Feature Implementation

## Overview
Implemented backward snowballing expansion feature for Paper Scanner to automatically expand the paper database by following references cited in existing papers.

## Changes Made

### Version Update
- Updated version from 2.2.0 to 2.3.0 in `src/paper_scanner/__init__.py`

### Core Models & Enums
1. **Added to `core/enum.py`:**
   - `BACKWARD_SNOWBALLING` discovery method
   - `FORWARD_SNOWBALLING` discovery method (prepared for future)

2. **Citation Model (`core/models.py`):**
   - Already had `resolved_paper` field for linking citations to papers
   - Used for tracking resolved references

### New Database Class
**`CitationsDatabase`** in `src/paper_scanner/core/database.py`:
- Manages citations extracted from papers
- Features:
  - DOI-based indexing with normalization (lowercase, whitespace trimmed)
  - Fast O(1) lookups by citation ID and DOI
  - CRUD operations (Create, Read, Update, Delete)
  - Batch operations and statistics
  - Supports linking citations to resolved papers
  - Maintains consistency across indexes during updates

### New Expansion Step
**`src/paper_scanner/steps/expansion.py`**:

#### Core Components:
1. **`ExpansionStatistics`** class:
   - Tracks: papers expanded, citations found, new papers added, citations resolved
   - Duration tracking and statistics export

2. **Configuration Validation**:
   - Validates expansion configuration (extraction methods, iterations, saturation threshold)
   - Ensures 'crossref' is configured as extraction method

3. **Citation Extraction**:
   - `_extract_citations_from_paper()`: Extracts references from paper using Crossref API
   - Converts Crossref reference format to Citation objects

4. **Paper Fetching & Addition**:
   - `_fetch_and_add_paper()`: Fetches metadata for unresolved citations
   - Creates Paper objects from Crossref metadata
   - Links citations to resolved papers
   - Handles duplicates (checks if paper already exists by DOI)

5. **Backward Snowballing**:
   - `execute_backward_snowballing()`: Main iteration logic
   - Iteration 0: Process all papers without discovery metadata
   - Subsequent iterations: Process papers from previous iteration
   - Features:
     - Saturation detection (stops if new papers < threshold)
     - Configurable max iterations
     - Rate limiting to Crossref API
     - Comprehensive logging

### Unit Tests
Created comprehensive test suite with 31 tests in `tests/unit/steps/test_expansion.py`:

**Test Coverage:**
- CitationsDatabase: index management, CRUD, resolved papers, statistics, batch ops, edge cases
- ExpansionStatistics: initialization, duration tracking, export
- Configuration validation: valid/invalid configs
- Year extraction from Crossref metadata
- Citation extraction from papers (with/without DOI)
- Paper fetching and addition (new papers, existing papers, failures)
- Backward snowballing iterations and saturation detection
- Main execute function with various configurations

Added CitationsDatabase tests to `tests/unit/core/test_database.py`:
- 15 additional tests covering all CitationsDatabase operations
- All existing PapersDatabase tests still passing

### Test Results
✅ All 31 expansion tests pass
✅ All 73 database tests pass (58 existing + 15 new CitationsDatabase tests)

## Configuration Format

```yaml
- step: Snowball first selection
  builtin.expansion:
    backward:
      extraction_methods:
        - "crossref"
      max_iterations: 3
      saturation_threshold: 0.05  # Stop if new papers < 5% of first iteration
```

## Key Features Implemented

1. **Citation Extraction**: Extracts all references from papers using Crossref API
2. **DOI Resolution**: Checks if referenced papers already exist in database
3. **Metadata Fetching**: Fetches full paper metadata from Crossref
4. **Iteration & Saturation**: Iteratively expands with automatic saturation detection
5. **Statistics Tracking**: Monitors papers expanded, citations found, new papers added
6. **Discovery Metadata**: Links new papers with iteration number and discovery method
7. **Error Handling**: Gracefully handles failed API calls and duplicate citations

## Architecture Decisions

1. **CitationsDatabase**: Separate from PapersDatabase to track intermediate citation objects before resolution
2. **DOI Normalization**: Lowercase and whitespace trimming for consistent lookups
3. **Discovery Metadata**: Uses `iteration` counter to track which expansion wave added each paper
4. **Rate Limiting**: 0.1 second delay between API calls to respect Crossref fair use policy
5. **Idempotency**: Checks for existing papers by DOI to avoid duplicates

## Future Enhancements

The foundation is in place for:
- Forward snowballing (finding papers that cite papers in database)
- Literature review mining (extracting references from excluded reviews)
- Alternative extraction methods (grobid, semantic scholar, llm_fallback)
- Multiple extraction methods with fallback strategy

## Files Modified/Created

### Created:
- `src/paper_scanner/steps/expansion.py` - Main expansion step implementation
- `tests/unit/steps/test_expansion.py` - Comprehensive test suite

### Modified:
- `src/paper_scanner/__init__.py` - Version bump to 2.3.0
- `src/paper_scanner/core/database.py` - Added CitationsDatabase class
- `src/paper_scanner/core/enum.py` - Added BACKWARD_SNOWBALLING and FORWARD_SNOWBALLING
- `tests/unit/core/test_database.py` - Added CitationsDatabase tests
