# RIS Import Spike 016 - File Format Support

## Objective

Implement RIS file format support for paper import pipeline, matching feature parity with existing BibTeX import capabilities.

## Scope

Add RIS format parsing and loading to enable users to import bibliographies from research databases that export RIS files (Zotero, Mendeley, Web of Science, Scopus, etc.).

## Key Tasks

### 1. **RIS Parser Library** (`src/paper_scanner/io/ris.py`)
Core library for parsing and extracting RIS format files.

**Responsibilities:**
- Parse RIS file format (tag-based format with TY, AU, TI, AB, etc.)
- Extract article metadata and convert to Paper model
- Handle missing/incomplete fields gracefully

**Target Fields (Feature Parity with BibTeX):**
- ✓ DOI
- ✓ Authors (AU field, multiple entries)
- ✓ Title (T1 field)
- ✓ Abstract (AB field)
- ✓ Journal (JF field)
- ✓ Year (PY field)
- ✓ Issue (IS field)
- ✓ Volume (VL field)
- ✓ Keywords (KW field, multiple entries)
- ✓ Source Key (derived from AN/DOI/hash)
- ✓ Cite Key (same as source_key at load time)

### 2. **Integration Points**
- Extend `bibtex_import` step or create new `ris_import` step
- Register in CLI as available import format
- Support both RIS files and `.ris` extension detection

### 3. **Error Handling**
- Validation of required fields (title, authors minimum)
- Incomplete record detection
- Format error reporting and recovery

## Implementation Plan

### Phase 1: Core Parser
- Create `src/paper_scanner/io/ris.py` with RIS parsing logic
- Unit tests for field extraction
- Handle multi-value fields (AU, KW)

### Phase 2: Paper Model Integration
- Map RIS fields to Paper model
- DOI standardization (same as BibTeX)
- Date parsing for publication year

### Phase 3: Step Integration
- Create `ris_import` step extending BaseStep
- Add to step registry
- YAML configuration support

### Phase 4: Testing & Validation
- Test data: RIS exports from major academic databases
- Feature parity validation with BibTeX import
- Edge case handling (missing fields, special characters)

## Normalization Strategy (Learned from BibTeX Implementation)

### Shared Normalization Functions (BibTeX → RIS)

### 1. **Title Normalization**
- Convert to title case using `titlecase` library
- Apply lowercase first: `titlecase(title.lower())`
- Normalize ampersands: replace `\&` and `&amp;` with `&`
- **Applied in RIS**: T1 field

### 2. **Abstract Normalization**
- Normalize whitespace: collapse newlines and multiple spaces to single space
  - Pattern: `re.sub(r'\s+', ' ', abstract).strip()`
- Normalize ampersands: replace `\&` and `&amp;` with `&`
- **Applied in RIS**: AB field
- **Result**: Clean, single-line text ready for processing

### 3. **Author Normalization**
Three-part parsing (mirroring BibTeX):
- **Split**: RIS uses "Last, First" format (same as BibTeX)
- **Title case**: Apply titlecase to standardize capitalization
- **Structure**: Extract family_name, given_name, and full_name
- **Multi-author handling**: RIS uses separate AU lines (one author per line)
- **Fallback**: For improperly formatted names, split on spaces and take last word as family name

**BibTeX Format Examples:**
```
"Smith, John and Doe, Jane"       → Split on 'and', parse each
"Smith, J. and Doe, J."           → Same, handles initials
"John Smith and Jane Doe"         → Fallback parser for first-last format
```

**RIS Format Example:**
```
AU  - Sahar, Rahmanwali
AU  - Jahid, Md. Abu
AU  - Fauzi, Hasan
```
(Each author is a separate AU line)

### 4. **Journal Normalization**
- Apply title case: `titlecase(journal.strip().lower())`
- Normalize ampersands (same as title)
- **Applied in RIS**: JF field (Journal Field)
- **BibTeX equivalent**: 'journal' field

### 5. **Keywords Normalization**
- Convert to lowercase: `keyword.strip().lower()`
- **Multi-keyword handling**: 
  - **BibTeX**: Semicolon/comma/and separated in single field
  - **RIS**: Separate KW line per keyword
- **Result**: List of normalized keyword strings
- **Applied in RIS**: KW fields (multiple lines)

### 6. **Ampersand Normalization** (Shared Function)
```python
def normalize_ampersands(text):
    text = text.replace(r'\&', '&')  # LaTeX escaped
    text = text.replace('&amp;', '&')  # HTML encoded
    return text
```
Applied to: title, abstract, journal, booktitle, publisher

### 7. **Year Extraction**
- Try direct integer conversion: `int(year_str)`
- Fallback: Extract from date fields using regex: `r'\b(\d{4})\b'`
- **Applied in RIS**: PY field
- **Applied in BibTeX**: 'year' or 'date' fields

### BibTeX-Specific Normalization (Not in RIS)

| Function | BibTeX | RIS | Reason |
|----------|--------|-----|--------|
| Remove LaTeX braces | ✓ Applied | ✗ Not needed | RIS is plain text format, no LaTeX markup |
| `re.sub(r'[{}]', '', text)` | Remove `{Title}`, `{Author's}` | N/A | BibTeX requires braces for special chars; RIS doesn't |



## Implementation Status

### ✓ Phase 1: Core Parser - COMPLETE
**File**: `src/paper_scanner/io/ris.py` (421 lines)

**Includes:**
- RISRecord data structure for multi-value field handling
- RISParser class for file parsing
- All 7 normalization functions (shared with BibTeX patterns)
- ris_record_to_paper() for Paper model conversion
- ris_to_papers() and ris_file_to_papers() functions
- import_ris_files() for batch import

**Features:**
- ✅ Parse RIS files and convert to Paper models
- ✅ Handle multi-value fields (AU, KW as separate lines)
- ✅ Normalize all fields: title case, ampersands, whitespace
- ✅ Cite key/source key strategy with 3-tier fallback
- ✅ Discovery metadata tracking
- ✅ Graceful error handling (skips invalid records)

### ✓ Phase 2: Unit Tests - COMPLETE
**File**: `tests/unit/io/test_ris.py` (432 lines, 38 tests)

**Test Coverage:**
- RISRecord data structure: 4 tests
- Normalization functions: 5 tests
- Author parsing: 6 tests  
- Keyword parsing: 5 tests
- Paper type inference: 6 tests
- RIS parser: 3 tests
- RIS to Paper conversion: 7 tests
- File loading: 2 tests

**Test Results**: ✅ 38 passed in 0.10s

### ✓ Phase 3: Spike Integration Test - COMPLETE
**File**: `test_01_ris_parse_proquest_updated.py`

**Test Results (ProQuest dataset):**
- ✅ Successfully loaded 20 papers from ProQuestDocuments-2025-12-31.ris
- ✅ Paper 1: Organizational Sustainability (4 authors, 26 keywords, 2399 char abstract)
- ✅ Paper 2: Ukrainian Retailers (5 authors, 16 keywords, 1647 char abstract)
- ✅ All 20 papers have accession number-based source_key
- ✅ 18/20 papers have DOI
- ✅ All 20 papers have abstracts
- ✅ Average 25.4 keywords per paper
- ✅ Year range: 2024-2025

**Run**: `uv run python tests/spikes/016_RIS_import/test_01_ris_parse_proquest_updated.py`

### ✓ Completed: Prototype Test
**File**: `test_01_ris_parse_proquest.py` (deprecated - see updated version above)

**Includes:**
- Minimal RIS parser (RISParser class)
- RISRecord data structure
- All 7 normalization functions matching BibTeX patterns
- ProQuest test data loading and validation
- Field statistics generation

**Run**: `uv run python tests/spikes/016_RIS_import/test_01_ris_parse_proquest.py`

**Test Results (ProQuest dataset):**
- ✓ Successfully parsed 20 records from ProQuestDocuments-2025-12-31.ris
- ✓ Record 1: 4 authors, 26 keywords, title case normalization applied
- ✓ Record 2: 5 authors, 16 keywords, ampersand normalization working
- ✓ All field types extracted: TY, T1, AU, AB, JF, PY, KW, DO, etc.
- ✓ Multi-line AU and KW fields properly handled as lists

**Next Milestones:**
1. **Phase 4: Step Integration** - Create `ris_import` step extending BaseStep
2. **Phase 5: CLI Support** - Register in CLI and YAML configuration
3. **Phase 6: Integration Testing** - Full pipeline validation

## Source Key & Cite Key Strategy

**Critical for deduplication and tracking**

### BibTeX Pattern (Reference)
```python
cite_key = entry.get('ID')  # From @article{cite_key_here, ...}
source_key = cite_key       # Same at load time, transformed later in pipeline
```

### RIS Challenge
RIS format has no native "cite key" equivalent (unlike BibTeX's @article{KEY}).

**Available identifiers in RIS:**
- **AN** (Accession Number): Database-specific ID (e.g., ProQuest document ID)
- **DOI**: Persistent identifier (when available)
- **UR** (URL): Database-specific URL

### RIS Load-Time Strategy
**Both cite_key and source_key initially set to the same value:**

```python
# Strategy: Use Accession Number as primary source
if record.get('AN'):  # Accession Number
    source_key = f"ris_an_{record.get('AN')}"
    cite_key = source_key  # Same at load time
elif record.get('DO'):  # DOI fallback
    source_key = f"ris_doi_{record.get('DO')}"
    cite_key = source_key
else:
    # Ultimate fallback: hash of title + authors
    source_key = f"ris_auto_{generate_hash(title, authors)}"
    cite_key = source_key
```

**Rationale:**
- **Accession Number preferred**: Unique per database, stable across exports
- **DOI fallback**: Persistent but may not exist for all records
- **Auto-generated fallback**: Last resort for records without stable IDs
- **Prefixing** (`ris_an_`, `ris_doi_`): Distinguishes RIS-sourced papers from BibTeX at load time
- **Same at load time**: Both point to same value; pipeline can later normalize/transform cite_key (e.g., remove prefix, shorten to human-readable form)

### Transformation Pipeline (Later)
The spike handles **load-time identity**. Downstream steps can:
1. Generate human-readable `cite_key` from title + authors
2. Maintain `source_key` for deduplication (immutable)
3. Track lineage through discovery metadata

## RIS Field Mapping Reference

| RIS Tag | Field Name | BibTeX Equiv | Notes | cite_key Role |
|---------|-----------|--------------|-------|---|
| TY | Publication Type | ENTRYTYPE | JOUR=article, CONF=inproceedings | - |
| T1 | Title | title | Normalized with titlecase | Fallback hash input |
| AU | Author | author | One line per author, "Last, First" format | Fallback hash input |
| AB | Abstract | abstract | Whitespace normalized | - |
| JF | Journal Name | journal | Title case applied | - |
| PY | Publication Year | year | Extracted as integer | - |
| VL | Volume | volume | String field | - |
| IS | Issue | number | String field | - |
| SP | Start Page | pages | Page range | - |
| KW | Keywords | keywords | One line per keyword | - |
| DO | DOI | doi | Cleaned format | **Secondary source_key** |
| UR | URL | url | Direct link to paper | - |
| PB | Publisher | publisher | Title case applied | - |
| CY | City/Place | address | Publication location | - |
| N1 | Note | note | Metadata/copyright info | - |
| AN | Accession Number | - | Database ID | **Primary source_key** |
| LA | Language | language | ISO language code | - |
| DB | Database | - | Source database | Metadata tracking |

**ProQuest Specific Notes:**
- Accession Number (AN) contains ProQuest document ID → use as primary source_key
- Multiple N1 lines: copyright + last updated
- DA field: Human-readable date (redundant with PY)
- L2 fields: resolver URLs (ignored in Paper model)
- DB field: "Coronavirus Research Database; Publicly Available Content Database"