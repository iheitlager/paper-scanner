# Plan: Implement Journal Screening Step

## Overview

Minimal journal screening step that validates paper journals against a curated include list. Papers without a journal field are marked `EXCLUDED_INCOMPLETE`. Matching is case-insensitive with fuzzy fallback. Fields `journal`, `journal_acronym`, `journal_iso4` already exist and will be populated.

## YAML Configuration Proposal

**File:** `etc/journal_screening.yaml`

```yaml
# Step configuration - fuzzy matching behavior
step_config:
  fuzzy_match_threshold: 0.85  # Minimum similarity score (0.0-1.0)
  fuzzy_match_strategy: "token_set_ratio"  # token_set_ratio or jaro_winkler
  case_sensitive: false

# Include/Exclude rules - match on full name, alias, or ISO4
# Matching is case-insensitive
screening:
  # Journals to explicitly INCLUDE (optional whitelist)
  # If defined, only papers with journals in this list are selected
  # Leave empty or remove to include all journals not in excluded list
  included_journals: []
    # - "Academy of Management Journal"
    # - "AMJ"
    # - "Acad. Manag. J."
  
  # Journals to explicitly EXCLUDE (reject specific journals)
  # Match on canonical name, alias, or ISO4
  excluded_journals:
    # - "Nature News"
    # - "Popular Science"

# Curated list of accepted journals with ISO4 abbreviations
# Format: journal_name (canonical) -> aliases, ISO4
# ISO4 codes can be auto-generated (see ISO4 Generator section)
journals:
  "Academy of Management Journal":
    aliases:
      - "Acad. Manag. J."
      - "AMJ"
    iso4: "Acad. Manag. J."
  
  "Organization Science":
    aliases:
      - "Organ. Sci."
      - "OS"
    iso4: "Organ. Sci."
  
  "MIS Quarterly":
    aliases:
      - "MIS Q."
      - "MISQ"
    iso4: "MIS Q."
  
  "Journal of Management":
    aliases:
      - "J. Manage."
    iso4: "J. Manag."
  
  "Information Systems Research":
    aliases:
      - "Inf. Syst. Res."
      - "ISR"
    iso4: "Inf. Syst. Res."
  
  "Strategic Management Journal":
    aliases:
      - "Strateg. Manag. J."
      - "SMJ"
    iso4: "Strateg. Manag. J."
```

## ISO4 Generator

Auto-generate ISO4 abbreviations from journal titles to improve fuzzy matching accuracy.

**Implementation:** Utility function `src/paper_scanner/core/iso4_generator.py`

```python
def generate_iso4(journal_name: str) -> str:
    """
    Generate ISO4 abbreviation from journal title.
    
    Rules (ISO 4 standard):
    - Keep first word
    - Abbreviate subsequent significant words (4+ chars) to first 3 chars
    - Remove stop words (of, the, and, etc.)
    - End with period
    
    Examples:
    - "Academy of Management Journal" → "Acad. Manag. J."
    - "Organization Science" → "Organ. Sci."
    - "Journal of Management Studies" → "J. Manag. Stud."
    """
```

**Benefits:**
- Fuzzy matching works better on ISO4 codes (standardized abbreviations)
- Can pre-compute ISO4 for both input journals and curated list
- Handles typos and variations in journal titles more reliably

### ISO 4 Standard & Journal Abbreviation References

**Standards Organizations:**
- [ISO 4 Standard](https://en.wikipedia.org/wiki/ISO_4) - Official international standard for journal abbreviation
- [ISSN - List of Title Word Abbreviations (LTWA)](https://www.issn.org/services/online-services/access-to-the-ltwa/) - Maintained by ISSN International Centre

**Key Abbreviation Rules:**

There is no single universal four-letter abbreviation for "journal"; rather, abbreviations are specific to individual journal titles and the citation standard being used. Common conventions include using "J." or "Jour." for the word "Journal" within a longer title abbreviation.

Examples:
- Single-word titles like "Nature" may not be abbreviated in some styles
- "The American Journal of the Medical Sciences" → "Am J Med Sci."
- Some styles omit punctuation: "SAMJ" (South African Medical Journal)
- Others retain periods: "Int. J. Prod. Econ." (International Journal of Production Economics)

**How to Find Official Journal Abbreviations:**

Journal abbreviations are standardized by:
1. **ISO (International Organization for Standardization)** - ISO 4 standard
2. **NLM (National Library of Medicine)** - For biomedical/life sciences
3. **CASSI (CAS Source Index)** - For chemistry and related fields
4. **ISSN International Centre** - LTWA (List of Title Word Abbreviations)

**Recommended Search Tools:**
1. **CAS Source Index (CASSI) Search Tool** - Highly recommended for chemistry and related fields
2. **LTWA (ISSN)** - Universal ISO 4 standard-based list
3. **NLM Catalog** - For journals in biomedical and life sciences

**Important Notes:**
- The required abbreviation often depends on the specific citation style (AMA, ACS, MLA, etc.)
- Always follow the priority list provided by your specific style guide or publisher
- Omit punctuation and spaces in some older styles; retain periods in modern styles
- Implementation should normalize to common convention with periods after abbreviated words

## Fuzzy Matching Strategy

### Options & Recommendation

1. **Token Set Ratio** (PRIMARY CHOICE)
   - Splits strings into tokens, compares regardless of order
   - Best for journal names with variable word order
   - Library: `rapidfuzz` (faster, more accurate than fuzzywuzzy)
   - Example: "Journal of Management Studies" vs "Management Studies Journal" → 100% match
   - **Recommendation:** Use this as primary strategy

2. **Jaro-Winkler**
   - Good for abbreviations and typos
   - Less order-sensitive than Levenshtein
   - Fallback option if Token Set Ratio fails

3. **Sequence Matcher**
   - Simple, no external dependency (Python stdlib `difflib`)
   - Adequate for simple name variations
   - Slower for large datasets

**Decision:** Use `rapidfuzz.distance.JaroWinkler.normalized_similarity()` with threshold 0.85, fallback to exact match on aliases first.

## Implementation Steps

### 1. Create branch & implement JournalScreeningStep

File: `src/paper_scanner/steps/journal_screening.py`

Extend `BaseStep` with:
- Load and validate YAML config (step_config, screening, journals)
- For each paper:
  - If journal field missing → set `final_decision = EXCLUDED_INCOMPLETE`
  - Skip if already excluded
  - Check against `screening.excluded_journals` (match on name/alias/iso4, case-insensitive)
  - If excluded → skip to next paper
  - If `screening.included_journals` defined, check if paper's journal is in the list
  - Attempt exact match (case-insensitive) against journal canonical names + aliases + iso4
  - If no match, attempt fuzzy match against canonical names + iso4 (generated)
  - If found, populate `journal_acronym` and `journal_iso4` from config
  - Record result for stats
- Return StepResult with stats

### 2. Create journal configuration at etc/journal_screening.yaml

Pre-populate with 20-30 tier-1 English-language journals (strategic management + information systems focus). See YAML proposal above.

### 3. Configuration Validation (raises ConfigurationError)

Validate on step instantiation:
- `step_config.fuzzy_match_threshold` between 0.0 and 1.0
- `step_config.fuzzy_match_strategy` in ["token_set_ratio", "jaro_winkler"]
- `journals` dict not empty
- Canonical journal names not duplicated (case-insensitive)
- Aliases don't conflict with other canonical names (case-insensitive)
- `iso4` field present for each journal
- `screening.included_journals` and `screening.excluded_journals` reference only valid journals (by name, alias, or iso4) - if not, raise ConfigurationError
- No journal appears in both included and excluded lists
- No missing required fields in config

### 4. Register in run.py STEP_REGISTRY_PATHS

```python
"journal_screening": "paper_scanner.steps.journal_screening:JournalScreeningStep"
```

## Execution Flow

1. Validate config (raise `ConfigurationError` on invalid schema/values)
2. Load journal list, fuzzy matching parameters, and include/exclude rules
3. For each paper in batch:
   - Skip if already excluded
   - If no journal → mark `final_decision = EXCLUDED_INCOMPLETE`
   - Check if journal in `screening.excluded_journals` → skip (exclude)
   - If `screening.included_journals` defined, check if journal in list → exclude if not
   - Attempt exact match (case-insensitive) against canonical names + aliases + iso4
   - If no match, generate ISO4 from paper journal name, attempt fuzzy match against canonical names + iso4 (generated)
   - If match found → populate `journal_acronym`, `journal_iso4` from config
   - Record result for stats
4. Return StepResult

## StepResult Stats

```python
{
    "papers_processed": 150,
    "papers_selected": 132,
    "papers_excluded": 18,
    "papers_excluded_incomplete": 10,
    "journals_not_found": 8,
    "fuzzy_matches": 5,
}
```

## View Suggestion

Add journal screening results to UI:
- Show journal name (canonical + original if different)
- Show journal abbreviation and ISO4
- Highlight excluded papers with reason (INCOMPLETE)
- Filter/search by journal

## Implementation Action Plan

### Phase 1: Foundation (Day 1-2)

**Task 1.1: Create ISO4 Generator utility**
- File: `src/paper_scanner/core/iso4_generator.py`
- Implement `generate_iso4(journal_name: str) -> str` function
- Handle stop words, abbreviations, period placement
- Add comprehensive unit tests for various journal names
- Estimated: 2-3 hours

**Task 1.2: Create JournalScreeningStep skeleton**
- File: `src/paper_scanner/steps/journal_screening.py`
- Extend `BaseStep` with stub methods
- Define `validate_config()` method signature
- Define `execute()` method signature
- Add config dataclass/type hints
- Estimated: 1 hour

### Phase 2: Core Implementation (Day 2-3)

**Task 2.1: Implement configuration validation**
- Parse YAML schema (step_config, screening, journals)
- Validate all constraints (thresholds, strategy, duplicates, conflicts)
- Raise `ConfigurationError` with descriptive messages
- Test with valid and invalid configs
- Estimated: 3 hours

**Task 2.2: Implement fuzzy matching logic**
- Install `rapidfuzz` dependency
- Create helper function `_fuzzy_match(input_name: str, candidates: List[str]) -> Optional[Tuple[str, float]]`
- Support token_set_ratio and jaro_winkler strategies
- Implement exact match (case-insensitive) as primary strategy
- Generate ISO4 for input journal name
- Estimated: 3 hours

**Task 2.3: Implement paper processing logic**
- Iterate through papers, skip already excluded
- Handle missing journal → mark `EXCLUDED_INCOMPLETE`
- Check exclude list, check include list (if defined)
- Exact match against canonical names + aliases + iso4
- Fuzzy match against canonical names + generated iso4
- Populate `journal_acronym`, `journal_iso4` from config
- Track stats (processed, selected, excluded, not_found, fuzzy_matches)
- Estimated: 4 hours

### Phase 3: Integration & Testing (Day 3-4)

**Task 3.1: Create YAML configuration file**
- File: `etc/journal_screening.yaml`
- Pre-populate with 20-30 tier-1 journals
- Include aliases and ISO4 codes
- Leave include/exclude lists empty (for now)
- Estimated: 2 hours

**Task 3.2: Register step in CLI**
- File: `src/paper_scanner/cli/tasks/run.py`
- Add to `STEP_REGISTRY_PATHS`
- Test step loading and instantiation
- Estimated: 1 hour

**Task 3.3: Comprehensive unit tests**
- File: `tests/unit/steps/test_journal_screening.py`
- Test exact match (case variations, aliases, iso4)
- Test fuzzy match (typos, word order, abbreviations)
- Test missing journal → EXCLUDED_INCOMPLETE
- Test invalid config → ConfigurationError
- Test include/exclude lists
- Test stats accuracy
- Test edge cases (empty, None, whitespace, duplicates)
- Run tests: `uv run pytest tests/unit/steps/test_journal_screening.py -v`
- Estimated: 5-6 hours

**Task 3.4: Integration testing**
- Create test pipeline definition with journal_screening step
- Test end-to-end with sample PDF metadata
- Verify stats and final_decision updates
- Estimated: 2 hours

### Phase 4: Optimization & Polish (Day 4-5)

**Task 4.1: Performance optimization**
- Profile fuzzy matching on large journal lists (1000+ papers)
- Cache normalized journal names
- Consider pre-computing ISO4 for all config journals
- Use `rapidfuzz` C backend for speed
- Estimated: 2 hours

**Task 4.2: Documentation**
- Create `docs/steps/journal_screening.md` with:
  - Step overview and purpose
  - Configuration guide (YAML structure)
  - Examples (exact match, fuzzy match, include/exclude)
  - Stats and results explanation
  - Troubleshooting (journals not found, false negatives)
- Estimated: 2 hours

**Task 4.3: Code review & refinement**
- Add type hints throughout
- Docstrings for all public methods
- Code style/lint checks: `make lint`
- Type checking: `make type-check`
- Estimated: 1-2 hours

### Phase 5: Deployment & Rollout (Day 5)

**Task 5.1: Merge to main**
- Create branch: `feat/journal_screening`
- Commit with conventional commit messages
- Create pull request with test results
- Code review & approval
- Merge to main
- Estimated: 1 hour

**Task 5.2: Version bump & changelog**
- Update `src/paper_scanner/__init__.py` (MINOR version bump)
- Update `CHANGELOG.md` with new features
- Update `README.md` if needed
- Estimated: 30 minutes

**Task 5.3: Manual testing on real data**
- Test with actual paper batch (50-100 papers)
- Verify journal matching accuracy
- Adjust fuzzy threshold if needed
- Validate stats reporting
- Estimated: 1-2 hours

### Summary

| Phase | Tasks | Estimated Days |
|-------|-------|-----------------|
| 1: Foundation | ISO4 generator, skeleton | 1-2 |
| 2: Core Implementation | Validation, fuzzy matching, processing | 2-3 |
| 3: Integration & Testing | Config file, registration, unit tests | 2-3 |
| 4: Optimization & Polish | Performance, docs, code review | 1-2 |
| 5: Deployment | Merge, version bump, manual testing | 0.5-1 |
| **Total** | | **7-11 days** |

### Dependencies & Prerequisites

- [ ] `rapidfuzz` library available (add to pyproject.toml)
- [ ] `BaseStep` class and `StepResult` understood
- [ ] Access to existing paper dataset for testing
- [ ] Knowledge of paper-scanner YAML pipeline format
- [ ] Familiarity with pytest framework

### Success Criteria

- ✅ All unit tests pass (70+ test cases)
- ✅ ConfigurationError raised on invalid configs
- ✅ 95%+ accuracy on exact journal matches
- ✅ Fuzzy matching handles 80%+ of typos/variations (threshold 0.85)
- ✅ Performance: <100ms per paper (1000+ papers)
- ✅ Stats tracked accurately
- ✅ No papers lost or duplicated during processing
- ✅ Documentation complete and examples working

## Unit Tests (to be added)

- Exact match (various casings)
- Fuzzy match (typos, abbreviations, word order)
- Missing journal field → EXCLUDED_INCOMPLETE
- Invalid config → ConfigurationError
- Alias resolution
- Stats accuracy
- Edge cases (empty journal, None, whitespace)