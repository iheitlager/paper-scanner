# Metadata Screening

### Title
**Metadata Screening** - Filters papers using attribute-based tri-state logic

### Description

The Metadata Screening step performs attribute-based filtering on papers using configurable inclusion and exclusion criteria. It implements tri-state logic where each field can be:

- **Hard EXCLUDE**: Specifies values that automatically reject papers
- **NOT operator**: Specifies "only allow this value" (exclude everything else)
- **OMITTED**: No requirement for this field

This is typically one of the first screening stages, providing fast computational filtering before semantic analysis. Papers can be filtered by language, paper type (journal article, conference paper, book), or quality tier. The step automatically updates the paper's screening status and provides detailed exclusion reasons for auditing.

### Features

- ✅ **Tri-state logic**: Flexible hard exclude, NOT operator, and omitted criteria
- ✅ **Multi-field filtering**: Screen by language, paper_type, and quality_tier
- ✅ **NOT operator support**: Both string format (`"NOT: en"`) and dict format (`{"NOT": "en"}`)
- ✅ **Mixed exclusion rules**: Combine hard excludes with NOT operator in same field
- ✅ **Decision tracking**: Automatically sets `final_decision` to EXCLUDED when papers fail screening
- ✅ **Exclusion reasons**: Detailed reasons logged for audit trail and quality control
- ✅ **Progress reporting**: Inline updates every 100 papers for large databases
- ✅ **Dry-run mode**: Test configuration without persisting changes

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `enabled` | `boolean` | No | `true` | Enable/disable this step |
| `exclude` | `object` | No | `{}` | Object with exclusion criteria by field |
| `exclude.language` | `list[string]` | No | - | Language codes to exclude (or NOT operator) |
| `exclude.paper_types` | `list[string]` | No | - | Paper types to exclude (or NOT operator) |
| `exclude.quality_tier` | `list[string]` | No | - | Quality tiers to exclude (or NOT operator) |

#### YAML Definition

```yaml
# Example 1: Only accept English journal articles
- step: Screen by metadata
  builtin.metadata_screening:
    enabled: true
    exclude:
      language: ["NOT: en"]
      paper_types:
        - conference_paper
        - book

# Example 2: Accept only Tier 1 and Tier 2 papers
- step: Quality filter
  builtin.metadata_screening:
    exclude:
      quality_tier: ["NOT: tier_1", "NOT: tier_2"]

# Example 3: Mixed hard excludes and NOT operator
- step: Complex screening
  builtin.metadata_screening:
    exclude:
      paper_types:
        - editorial
        - news
        - "NOT: journal_article"  # Only journal articles allowed
```

### Exclusion Criteria

#### Hard EXCLUDE (Plain Strings)
Papers with ANY of these values in the field are rejected:

```yaml
exclude:
  paper_types: ["conference_paper", "book"]  # Reject conference papers and books
```

#### NOT Operator (String Format)
Only papers with this exact value are accepted; all others rejected:

```yaml
exclude:
  language: ["NOT: en"]  # Only English papers accepted
```

#### NOT Operator (Dict Format)
Same functionality as string format, alternative syntax:

```yaml
exclude:
  paper_types: [{"NOT": "journal_article"}]  # Only journal articles accepted
```

#### Mixed Rules
Same field can have both hard excludes and NOT operator:

```yaml
exclude:
  paper_types:
    - editorial       # Hard exclude these specific types
    - "NOT: journal_article"  # And only allow this type
    # Result: Accept ONLY journal articles
```

### Input/Output

#### Input
- **Format**: Papers from database
- **Source**: Prior import or screening stages
- **Requirements**: Papers must have language, paper_type, or other fields being screened

#### Output
- **Format**: Papers with metadata screening results
- **Database**: Updates `Paper.screening.metadata_screening` with:
  - `language`: ISO language code
  - `paper_type`: JOURNAL_ARTICLE, CONFERENCE_PAPER, BOOK
  - `quality_tier`: Quality assessment
  - `is_peer_reviewed`: Peer review status
  - `exclusion_reason`: Why paper was excluded (if applicable)
- **Decision**: Updates `Paper.screening.final_decision` to EXCLUDED when paper fails
- **Metrics**: Count of passed/failed papers and breakdown of exclusion reasons

### Field Values

#### Language
ISO 639-1 language codes: `en`, `fr`, `de`, `es`, `zh`, etc.

#### Paper Types
- `journal_article` - Published in peer-reviewed journal
- `conference_paper` - Published in conference proceedings
- `book` - Complete book publication

#### Quality Tiers
- `tier_1` - High-impact publication venues
- `tier_2` - Mid-tier publication venues
- `unknown` - Not assessed

### Validation

The step validates:
- `enabled`: Must be boolean (if present)
- `exclude`: Must be a dictionary (if present)
- Each field in exclude must have a list value
- Each criterion must be string or dict with "NOT" key
- NOT operator values must not be empty

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "enabled must be boolean" | Invalid enabled type | Change to `true` or `false` |
| "exclude must be dict" | Invalid exclude type | Use YAML object/dict format |
| "field must be list" | Field criteria not a list | Wrap criteria in square brackets |
| "dict must have NOT key" | Dict format missing "NOT" | Use `{"NOT": "value"}` format |

### Examples

#### Example 1: English-only filtering

```yaml
- step: Screen for English papers
  builtin.metadata_screening:
    exclude:
      language: ["NOT: en"]
```

**Result**: Only papers with `language="en"` are accepted.

#### Example 2: Journal articles only

```yaml
- step: Journal articles only
  builtin.metadata_screening:
    exclude:
      paper_types: ["conference_paper", "book"]
```

**Result**: Only `journal_article` papers pass. Conference papers and books are rejected with reason: `paper_types: conference_paper (hard excluded)`.

#### Example 3: Complex screening

```yaml
- step: Multi-criteria screening
  builtin.metadata_screening:
    exclude:
      language: ["NOT: en"]           # Only English
      paper_types: ["editorial"]      # No editorials
      quality_tier: ["NOT: tier_1", "NOT: tier_2"]  # Only Tier 1 or 2
```

**Result**: Papers must satisfy ALL criteria:
- Be in English, AND
- Not be editorial, AND
- Be Tier 1 or Tier 2

Papers failing ANY criterion are excluded.

### Status Codes

Returns one of:

- `SUCCESS`: Screening completed, papers updated with results
- `SKIPPED`: Step disabled in configuration
- `ERROR`: Validation or processing error occurred

### Performance

- **Speed**: ~1000s papers per second on typical hardware
- **Memory**: Minimal (streaming processing, no large buffers)
- **Scaling**: Linear with number of papers

### See Also

- [Keyword Screening](keyword_screening.md) - Stage 2: content-based filtering
- [Semantic Screening](semantic_screening.md) - Stage 3: similarity-based filtering
- [Overview](overview.md) - Screening pipeline stages
