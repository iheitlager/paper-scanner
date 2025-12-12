# Dump DB Step

Prints database contents and index statistics for debugging and inspection. Useful for understanding the current state of the paper database during pipeline execution.

## Features

- **Print all records**: Display DOI, type, and title for each paper in the database
- **Index statistics**: Show sizes of all internal indexes (_papers, _doi_index, _cite_key_index, _id_index)
- **Formatted output**: Rich tables for easy readability
- **No configuration needed**: Step has no parameters

## Parameters

This step has no parameters.

## Examples

### Basic Usage

```yaml
steps:
  - name: dump
    dump_db: {}
```

Or even simpler:

```yaml
steps:
  - name: dump
    dump_db:
```

## Output

The step prints two tables:

### Database Records Table

Shows all papers in the database with:
- **DOI**: Digital Object Identifier (displays "—" if missing)
- **Type**: Paper type (journal_article, conference_paper, etc.)
- **Title**: First 60 characters of the title (truncated with "...")

### Index Statistics Table

Shows the size of each internal index:
- **papers**: Total number of records in the papers list
- **_doi_index**: Number of unique DOIs
- **_cite_key_index**: Number of unique citation keys
- **_id_index**: Number of unique paper IDs

## Return Value

```python
{
    "status": "success",
    "records_printed": 42,           # Number of papers displayed
    "index_sizes": {
        "papers": 42,                 # Total papers
        "_doi_index": 41,             # Unique DOIs
        "_cite_key_index": 42,        # Unique citation keys
        "_id_index": 42               # Unique IDs
    }
}
```

## Use Cases

- **Debugging**: Verify papers were imported correctly
- **Inspection**: Check paper types and DOIs after imports
- **Index Health**: Ensure index sizes match expectations
- **Pipeline checkpoints**: Inspect data at different stages
- **Data quality**: Identify missing DOIs or malformed data

## Notes

- Titles are truncated at 60 characters for readability
- DOI display shows "—" for papers without a DOI
- Paper type shows "—" if not set
- All papers are shown, including duplicates
- No modifications are made to the database
- Index sizes should match the total papers count for consistency
