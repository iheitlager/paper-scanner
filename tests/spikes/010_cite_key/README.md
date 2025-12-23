# Spike 010: Citation Key Generation Strategies

## Hypothesis

We want to generate **unique, human-readable BibTeX citation keys** for papers using multiple fallback strategies:

1. **Primary**: `{LastName}{Year}` (e.g., `Smith2020`)
2. **Fallback**: DOI slug if no year (e.g., `10-1287-isre`)
3. **Last resort**: UUID suffix if neither available

When keys collide, append suffixes: `a`, `b`, ..., `z`, `aa`, `ab`, etc.

## Questions We're Testing

1. How do we generate cite keys from author/year metadata?
2. What's the best collision resolution strategy?
3. Should we use DOI when metadata is incomplete?
4. How do we handle edge cases (missing authors, missing year, special characters)?

## Test Approach

Use the same pattern as `spikes/011_step_executor/` - Python test files that:
- Import core modules directly (`cite_key.py`, `doi.py`)
- Validate specific ideas with focused assertions
- Remain self-contained (no changes to src/)
- Document learnings for future implementation

## Test Files

- `01_basic_generation.py` - Basic author/year cite key generation (8 tests)
- `02_doi_fallback.py` - DOI slug generation when year missing (7 tests)
- `03_collision_handling.py` - Suffix collision resolution (10 tests)
- `04_combined_strategy.py` - Full three-tier fallback strategy (7 tests)

## Test Results

All spike tests passing ✓ (32 tests total):

```
01_basic_generation.py      ✓ PASS (8 tests)
  - Simple author/year format
  - Multi-word and hyphenated last names
  - Multiple authors (use first only)
  - Error handling (missing authors, year, family name)

02_doi_fallback.py          ✓ PASS (7 tests)
  - Standard DOI to slug conversion
  - Different publisher formats
  - arXiv DOI handling
  - URL prefix normalization
  - Invalid DOI handling
  - DOI object validation

03_collision_handling.py     ✓ PASS (10 tests)
  - Single-letter suffixes (a-z)
  - Double-letter suffixes (aa-az, ba-bz, ...)
  - Triple-letter suffixes (aaa-aaz, ...)
  - Uniqueness validation (200 unique suffixes)
  - No collision scenarios
  - Sequential collision resolution
  - Real-world multi-paper scenarios

04_combined_strategy.py      ✓ PASS (7 tests)
  - Complete metadata → author/year strategy
  - Missing year → DOI fallback
  - Missing authors → DOI fallback
  - Minimal metadata → UUID fallback
  - Invalid DOI handling
  - Integration with collision resolution
  - Strategy preference ordering
```

## Key Findings

### Citation Key Generation
- **Author/year format works well**: Simple, readable, stable
- **Special character handling**: Spaces/hyphens in names are removed automatically
- **First author preference**: Multi-author papers use first author's name
- **Data validation**: Clear errors when required fields missing

### DOI Fallback Strategy
- **Slug generation**: Extract prefix (10-xxxx) + first part of suffix (letters or alphanumeric)
- **Format robustness**: Handles doi:, https://, plain formats
- **Normalization**: DOI class normalizes to lowercase stem format
- **Regex approach**: Separate handling for letter-only vs alphanumeric suffixes

### Collision Resolution
- **Suffix pattern**: a, b, ..., z (single), then aa, ab, ..., az, ba, ... (double), then aaa... (triple)
- **Deterministic**: Same pattern always produces unique keys in sequence
- **Scalability**: Supports hundreds of collisions without issue
- **Simplicity**: No complex hashing, just linear suffix enumeration

### Three-Tier Strategy
- **Preference hierarchy**: Author/Year > DOI > UUID
- **Fallback logic**: Only move to next tier if current tier unavailable or fails
- **Real-world applicability**: Most papers have author/year; DOI catches edge cases
- **UUID as safety net**: Works when all else fails (no data loss)

## Implementation Readiness

The spike validates that the design in `src/paper_scanner/core/cite_key.py` is:
- ✓ Functionally correct (all tests pass)
- ✓ Edge case aware (error handling validated)
- ✓ Integration-ready (DOI class integration confirmed)
- ✓ Collision-resistant (suffix generation verified)

### Next Steps for Integration
1. Consider adding DOI fallback to `fix_cite_keys.py` step
2. Add UUID generation strategy as last resort
3. Document cite key generation logic in step docs
4. Consider exposing three-tier strategy as utility function in core module

## Unit Test Coverage

Parallel test suite in `tests/unit/`:
- `tests/unit/core/test_cite_key.py` - 16 tests for utility functions
- `tests/unit/steps/test_fix_cite_keys.py` - 29 integration tests for step

All 46 tests passing ✓