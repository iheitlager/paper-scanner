# Journal Screening

### Title
**Journal Screening** - Validate and enrich paper journal metadata using curated journal definitions

### Description

The Journal Screening step performs automated journal-based filtering and metadata enrichment. It matches paper journal names against a curated database of journal definitions, validates journal presence in organizational views (Academy of Management, AIS Basket of Eight, VHB rankings, Innovation journals), and enriches papers with standardized journal acronyms and ISO4 abbreviations.

This step is particularly valuable for:
- **Validating journal presence** in high-impact publication venues
- **Standardizing journal names** across papers with variations in naming
- **Enriching metadata** with ISO4 abbreviations for bibliographic consistency
- **Filtering papers** by journal prestige, ranking, or research domain
- **Quality assurance** in literature review processes

### Features

- ✅ **Exact journal matching** - Case and whitespace insensitive lookup
- ✅ **ISO4 generation** - Automatic fallback abbreviation generation for unmapped journals
- ✅ **Journal views** - Filter by curated journal groupings (Academy, AIS Basket, VHB tiers, Innovation)
- ✅ **Metadata enrichment** - Adds acronyms and ISO4 abbreviations to paper records
- ✅ **Flexible handling** - Skip missing journals or fail on errors
- ✅ **Dry-run mode** - Preview changes without modifying database
- ✅ **Verbose logging** - Track matching and processing decisions

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `journal_definitions_path` | `string` | No | `etc/journal_definitions.yml` | Path to YAML journal definitions file |
| `required_views` | `list[string]` | No | - | Filter papers to only journals in these views (e.g., `["academy", "business"]`) |
| `generate_iso4` | `boolean` | No | `true` | Generate ISO4 abbreviations for journals not in definitions |
| `skip_missing` | `boolean` | No | `false` | Skip papers with missing journal names instead of counting as errors |

#### YAML Definition

```yaml
- step: Enrich papers with journal metadata
  builtin.journal_screening:
    journal_definitions_path: "etc/journal_definitions.yml"
    generate_iso4: true
    skip_missing: false
```

#### Filtering by Journal Views

```yaml
- step: Screen for Academy journals only
  builtin.journal_screening:
    required_views:
      - academy
      - basket_of_eight
```

#### Using Custom Definitions File

```yaml
- step: Validate against proprietary journal list
  builtin.journal_screening:
    journal_definitions_path: "config/my_journals.yml"
    generate_iso4: false  # Only exact matches
```

### Input/Output

#### Input
- **Format**: Papers from database with `journal` field
- **Source**: Current database state (all papers or from prior pipeline step)
- **Requirements**: Papers should have `journal` field populated

#### Output
- **Database**: Updates papers with enriched metadata in `paper.screening.journal_screening`
- **Fields Added**:
  - `journal_name`: Standardized journal name from definitions
  - `acronym`: Journal acronym (e.g., "JBR")
  - `iso4`: ISO4 abbreviation (e.g., "J. Bus. Res.")
  - `metadata`: Processing metadata including lookup type and timestamp
- **Summary**: Returns statistics on matched, skipped, and error papers

### Journal Definitions File Format

The journal definitions YAML file contains:

```yaml
# Journal catalog
journals:
  "Journal of Business Research":
    acronym: "JBR"
    iso4: "J. Bus. Res."
  
  "Management Science":
    acronym: "MS"
    iso4: "Manag. Sci."
  
  "Academy of Management Journal":
    acronym: "AMJ"
    iso4: "Acad. Manag. J."

# Curated journal groupings (views)
views:
  academy:
    - "Academy of Management Journal"
  
  business:
    - "Journal of Business Research"
    - "Management Science"
  
  innovation:
    - "Entrepreneurship Theory and Practice"
    - "Research Policy"
```

### Validation

The step validates:
- ✅ `journal_definitions_path` points to existing YAML file (if provided)
- ✅ `required_views` is a list of strings (if provided)
- ✅ `generate_iso4` is boolean (if provided)
- ✅ `skip_missing` is boolean (if provided)

### Behavior

#### Matching Strategy

1. **Exact match**: Look for journal in definitions (case/whitespace insensitive)
2. **ISO4 generation** (if enabled): Generate abbreviation from journal name
3. **Error handling**:
   - If `skip_missing=true`: Skip paper, don't count as error
   - If `skip_missing=false`: Count as error, continue processing

#### View Filtering

When `required_views` is specified:
- Papers with journals in specified views are kept
- Other papers are skipped
- Useful for filtering to high-impact journals or domain-specific publications

#### Lookup Type Tracking

Each enriched paper tracks how it was matched:
- `exact_match`: Found in journal definitions
- `iso4_generation`: Generated from journal name
- `skipped`: Not processed (missing journal or not in required views)

### Statistics Returned

| Stat | Description |
|------|-------------|
| `total_papers` | Papers processed in this step |
| `papers_matched` | Papers with exact journal match |
| `papers_with_iso4` | Papers with ISO4 abbreviations (generated or from definitions) |
| `papers_skipped` | Papers not processed (missing journal or view filter) |
| `papers_with_errors` | Papers that failed processing |
| `journals_count` | Total journals in definitions |

### Examples

#### Basic Journal Enrichment

```yaml
steps:
  - step: Import papers from BibTeX
    builtin.bibtex_import:
      file: "papers.bib"
  
  - step: Enrich with journal metadata
    builtin.journal_screening: {}
  
  - step: Export enriched papers
    builtin.export:
      format: jsonl
      file: "output/papers_enriched.jsonl"
```

#### Filter to High-Impact Journals

```yaml
steps:
  - step: Load all papers
    builtin.input: {}
  
  - step: Keep only Academy of Management journals
    builtin.journal_screening:
      required_views:
        - academy
  
  - step: Report results
    builtin.report: {}
```

#### Multi-View Filtering

```yaml
steps:
  - step: Screen for top-tier journals
    builtin.journal_screening:
      required_views:
        - academy
        - basket_of_eight
        - vhb_ranking_a_plus
      generate_iso4: true  # Fill gaps with generated abbreviations
```

### Error Handling

**Missing Journal Names**
- `skip_missing: false` (default): Counts as error, processing continues
- `skip_missing: true`: Paper is skipped silently

**Journal Not in Definitions**
- `generate_iso4: true` (default): Generates ISO4 abbreviation, counts as match
- `generate_iso4: false`: Counts as error

**Invalid Definitions File**
- Returns `ERROR` status with file not found message
- Pipeline stops unless `--continue-on-error` is used

### Performance

- **Lookup speed**: O(1) normalized name lookup
- **Batch processing**: All papers processed in single pass
- **Memory**: Definitions cached in memory, ~50KB for typical journal set

### See Also

- [BibTeX Import](bibtex_import.md) - Load papers from BibTeX files
- [Deduplication](deduplication.md) - Remove duplicate papers
- [Metadata Screening](metadata_screening.md) - Filter by paper type, language, quality
- [Export](export.md) - Save enriched papers to various formats
