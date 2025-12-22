# Fix Cite Keys Step

Regenerates citation keys for all primary papers in the format `LastnameYear`, handling collisions by appending character suffixes (a, b, c, ..., z, aa, ab, ...). Only processes primary papers (excluding duplicates).

## Features

- **Automatic regeneration**: Creates consistent `LastnameYear` format from first author's family name and publication year
- **Collision handling**: Automatically resolves duplicate keys by appending suffixes (a, b, c, etc.)
- **Primary papers only**: Processes only primary papers (ignores duplicates)
- **Database update**: Updates all papers with new cite_keys in the database
- **Error reporting**: Detailed errors for papers missing required data
- **Dry-run support**: Test changes without updating the database

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| (none) | - | - | No configuration parameters required |

## Cite Key Format

The cite key follows the pattern: `{FirstAuthorLastName}{PublicationYear}{CollisionSuffix}`

### Format Details

- **FirstAuthorLastName**: Last name (family_name) of the first author, with spaces and hyphens removed
- **PublicationYear**: Year of publication (4 digits)
- **CollisionSuffix**: Added only if another paper has the same base key:
  - First collision: `a` → `SmithYear2020a`
  - Second collision: `b` → `SmithYear2020b`
  - After 26 collisions: `aa`, `ab`, ..., `az`, `ba`, etc.

### Examples

- Single author, no collision: `Smith2020`
- Collision (2nd entry): `Smith2020a`
- Collision (3rd entry): `Smith2020b`
- Collision (28th entry): `Smith2020aa`

## Requirements

For a paper to be processed, it must have:

1. **At least one author** with a family_name
2. **A publication year** (year field)

Papers missing either will be skipped with an error message.

## Limitations

- Only primary papers are processed (papers marked as `duplicate_of` are ignored)
- Duplicates retain their original cite_keys
- Requires valid author data (family_name must exist)

## Examples

### Basic YAML Pipeline

```yaml
steps:
  - step: Regenerate citation keys
    builtin.fix_cite_keys:
    description: "Fix all paper citation keys to LastnameYear format"
```

### With Explicit Configuration

```yaml
steps:
  - step: fix_cite_keys
    builtin.fix_cite_keys: {}
    description: "Standardize citation keys across all papers"
```

### Full Pipeline Example

```yaml
project:
  name: "literature-review"
  description: "Organizing papers with standardized citation keys"

steps:
  - step: Import bibliography
    builtin.bibtex_import:
      file: "data/references.bib"
  
  - step: Remove duplicates
    builtin.deduplication: {}
  
  - step: Fix citation keys
    builtin.fix_cite_keys: {}
    description: "Standardize all keys to LastnameYear format"
  
  - step: Export final bibliography
    builtin.export:
      format: "bibtex"
      output: "output/papers_fixed.bib"
```

## Input/Output

### Input

- **Format**: Papers in database
- **Source**: Previous pipeline steps
- **Scope**: All primary papers (duplicate_of is None)
- **Count**: All papers in database matching primary filter

### Output

- **Format**: Updated papers with new cite_keys
- **Updates**: Database records
- **Scope**: Only papers that needed updating
- **Result**: Consistent cite_key format across database

## Validation

The step validates:

- No required configuration parameters
- At step execution time, papers are checked for required fields (authors, year)

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Paper {id} has no authors" | Paper missing authors list | Add authors to paper record |
| "Paper {id} has no publication year" | Paper missing year field | Add publication year to paper |
| "Paper {id} first author has no family name" | Author lacks family_name field | Ensure author has valid family_name |

Errors are collected and reported in the step results. Papers with errors are skipped and retain their original cite_keys.

## Behavior

### Execution Flow

1. **Collect all primary papers** from database (duplicate_of is None)
2. **Generate base keys** for each paper (LastnameYear)
3. **Detect collisions** between papers
4. **Resolve collisions** by appending suffixes (a, b, c, ...)
5. **Update database** with new cite_keys (unless dry_run is enabled)

### Dry Run Mode

With `--dry-run` flag:
- Generate new keys
- Report what would change
- Do NOT update the database
- Show statistics (count, skipped, errors)

## Performance

- **Time Complexity**: O(n) where n = number of primary papers
- **Database Operations**: One update per modified paper
- **Memory**: Stores mapping of paper IDs to new keys in memory

## Database Impact

### Changes Made

- Updates `cite_key` field for papers with new keys
- Updates indexes in PapersDatabase:
  - `_cite_key_index`: Remapped to new keys
  - All other indexes remain unchanged

### Constraints Maintained

- Unique constraint on `cite_key` is maintained
- No foreign key violations (cite_key is not referenced)
- All papers remain in database (no deletions)

## Usage Patterns

### Pattern 1: Fix Keys After Import

```yaml
steps:
  - step: Import papers
    builtin.bibtex_import:
      file: "papers.bib"
  
  - step: Fix keys
    builtin.fix_cite_keys: {}
```

### Pattern 2: Ensure Consistency in Large Reviews

```yaml
steps:
  - step: Load papers
    builtin.load_files:
      folder: "pdfs/"
  
  - step: Deduplicate
    builtin.deduplication: {}
  
  - step: Standardize keys
    builtin.fix_cite_keys: {}
    
  - step: Export
    builtin.export:
      format: "bibtex"
```

### Pattern 3: Preview Changes

```bash
# Test with dry-run
uv run paper-processor pipeline.yml --dry-run

# Review output, then run for real
uv run paper-processor pipeline.yml
```

## See Also

- [Deduplication Step](deduplication.md) - Remove duplicate papers before fixing keys
- [Export Step](export.md) - Export papers with fixed keys
- [Patch Step](patch.md) - Manually adjust individual papers after fixing keys
