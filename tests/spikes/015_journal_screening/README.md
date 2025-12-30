# Journal Screening Spike 015 - Test Framework

## Structure Created

### 1. **test_01_harmonize_journal.py**
Core test suite for journal harmonization logic. Tests extracted from real BibTeX bibliography data.

**Test Coverage:**
- ✅ Extract journals from BibTeX files (8 test files, 56 unique journals)
- ✅ Exact match (case-insensitive)
- ✅ Exact match with aliases and abbreviations
- ✅ Case insensitivity handling
- ✅ Whitespace normalization (collapse internal spaces)
- ✅ Missing journal field detection → `EXCLUDED_INCOMPLETE`
- ✅ Empty/None journal handling
- ✅ Real-world journal from BibTeX corpus

**All 8 Tests Pass:**
```
test_extract_real_journals ........................ PASSED
test_exact_match_simple ........................... PASSED
test_exact_match_with_abbreviations .............. PASSED
test_case_insensitivity ........................... PASSED
test_whitespace_normalization ..................... PASSED
test_missing_journal_field ........................ PASSED
test_empty_journal_field .......................... PASSED
test_real_journal_from_bibdata .................... PASSED
```

### 2. **journal_definitions.yml**
Complete journal registry extracted from test corpus (56 journals).

**Format:**
```yaml
step_config:
  fuzzy_match_threshold: 0.85
  fuzzy_match_strategy: "token_set_ratio"

screening:
  included_journals: []    # Optional whitelist
  excluded_journals: []    # Optional blacklist

journals:
  "Full Journal Name":
    aliases:
      - "Short Name"
      - "Abbrev."
    iso4: "Short Name"    # ISO4 abbreviation
```

**Extracted Journals (56 unique):**

Top by frequency:
1. Multidisciplinary Reviews (3)
2. Journal of Business Research (3)
3. Technology in Society (2)
4. Lecture Notes in Mechanical Engineering (2)
5. Lecture Notes in Networks and Systems (2)
6. IEEE Transactions on Engineering Management (2)
7. Frontiers in Psychology (2)
8. ... 48 more

## Test Data Source

All journals extracted from:
- `/tests/data/eight_cases.bib` (8 entries)
- `/tests/data/ieee_sample_20.bib` (20 entries)
- `/tests/data/scopus_sample_20.bib` (20 entries)
- `/tests/data/wos_sample_20.bib` (varies)

## Key Implementation Insights

### 1. Normalization Rules Discovered
From test data analysis:
```python
def normalize(name: str) -> str:
    # 1. Strip leading/trailing whitespace
    # 2. Collapse internal multiple spaces to single space
    # 3. Convert to lowercase
    # 4. Ready for matching
    return " ".join(name.strip().lower().split())
```

### 2. Journal Matching Strategy
Three-tier approach:
1. **Exact match** on normalized journal name
2. **Alias match** against all defined aliases (case-insensitive)
3. **Fuzzy match** using token_set_ratio (0.85 threshold)

### 3. Missing Journal Handling
Papers without journal field → immediately marked `EXCLUDED_INCOMPLETE`
- No processing continues
- Recorded in stats as separate counter

## Next Steps for Implementation

### Phase 1: ISO4 Generator
- Create `src/paper_scanner/core/iso4_generator.py`
- Implement ISO4 abbreviation logic
- Unit tests for abbreviation accuracy

### Phase 2: JournalScreeningStep
- Extend `BaseStep` in `src/paper_scanner/steps/journal_screening.py`
- Implement validation (ConfigurationError on invalid config)
- Implement execution (fuzzy matching, stats tracking)
- Unit tests for all matching scenarios

### Phase 3: Integration
- Register in `run.py` STEP_REGISTRY_PATHS
- Create config example (this yml file)
- Integration tests with real pipeline

## Running Tests

```bash
# All tests in spike
uv run pytest tests/spikes/015_journal_screening/ -v

# Specific test
uv run pytest tests/spikes/015_journal_screening/test_01_harmonize_journal.py::TestJournalHarmonization::test_extract_real_journals -v

# With output
uv run pytest tests/spikes/015_journal_screening/test_01_harmonize_journal.py -v -s
```

## Dependencies

- ✅ `bibtexparser` - Added to dev group for BibTeX parsing
- ✅ `pytest` - Already available
- ⏳ `rapidfuzz` - To be added for fuzzy matching
