# Retrieve Metadata Step

Enrich Paper records with complete metadata from external APIs.

## Overview

The retrieve_metadata step walks over all Paper records in the database and fetches complete bibliographic metadata from configured sources (Crossref, OpenAlex, etc.). It translates API responses into Paper model fields, updating records with titles, authors, publication details, and other enriched information.

This step is useful after creating new papers from citations or imports where only partial metadata is available.

## Configuration

```yaml
pipeline:
  - step: Retrieve complete metadata
    builtin.retrieve_metadata:
      methods: ["crossref"]                  # Fetcher source(s) to use
      continue_on_not_found: true            # Continue if metadata not found
      paper-type:                            # Optional: filter by paper type
        - "journal_article"
```

### Parameters

#### `methods` (string or list, default: `["crossref"]`)
Fetcher source(s) to use for metadata retrieval.

Valid values:
- `"crossref"` - Crossref API (primary source)
- `"openalex"` - OpenAlex API
- Other configured fetcher names

#### `continue_on_not_found` (boolean, default: `true`)
If true, continue processing when metadata is not found for a paper. If false, halt pipeline on missing metadata.

#### `paper-type` (list, optional)
Filter papers to process by publication type. Default: processes all papers regardless of type.

Valid values:
- `"journal_article"`
- `"conference_paper"`
- `"book"`
- `"preprint"`
- `"other"`

## Examples

### Basic Metadata Retrieval
```yaml
- step: Get paper metadata
  builtin.retrieve_metadata:
    methods: "crossref"
```

### With Multiple Sources
```yaml
- step: Retrieve metadata from multiple sources
  builtin.retrieve_metadata:
    methods: ["crossref", "openalex"]
    continue_on_not_found: true
```

### Filter by Paper Type
```yaml
- step: Enrich only journal articles
  builtin.retrieve_metadata:
    methods: "crossref"
    paper-type: ["journal_article"]
```

### After Citation Expansion
```yaml
pipeline:
  - step: Extract citations
    builtin.citations:
      backward:
        sources: "crossref"
        continue_on_not_found: true
  
  - step: Enrich newly created papers
    builtin.retrieve_metadata:
      methods: ["crossref"]
      continue_on_not_found: true
```

## Process Flow

1. Get all Paper records from database (optionally filtered by paper_type)
2. For each paper:
   - Check if metadata already complete (skip if cached)
   - Check cache first (local metadata cache)
   - Fetch from primary source
   - If not found and multiple methods configured, try secondary sources
   - Translate API response to Paper fields
   - Update database record
   - Track cache hits/misses
3. Batch update all modified papers to database

## Fetched Metadata Fields

The step enriches Papers with:

### Bibliographic Information
- `title` - Paper title
- `authors` - List of author names
- `year` - Publication year
- `publication_venue` - Journal/conference name
- `volume`, `issue`, `pages` - Publication details

### Identifiers
- `doi` - Digital Object Identifier (normalized)
- `issn` - International Standard Serial Number
- `isbn` - International Standard Book Number

### Content Information
- `abstract` - Paper abstract
- `keywords` - Keywords from metadata
- `open_access_status` - Open access information

### Citation Information
- `citation_count` - Number of citations
- `reference_count` - Number of references

## Results

Returns a dictionary with statistics:
```python
{
    "status": "ok",                          # "ok" or "completed_with_errors"
    "total_papers": int,                     # Total papers processed
    "papers_enriched": int,                  # Papers successfully enriched
    "papers_not_found": int,                 # Papers where metadata not found
    "cache_hits": int,                       # Cache hits
    "cache_misses": int,                     # Cache misses
    "errors": [str]                          # List of error messages
}
```

## Workflow Patterns

### Enrich After Import
```
bibtex_import → retrieve_metadata → export
```

### Complete Citation Expansion
```
input → citations → retrieve_metadata → deduplication → export
```

### Selective Enrichment
```
bibtex_import → deduplication → retrieve_metadata → keyword_screening → export
```

## Performance Considerations

- **API calls**: One call per paper (unless cached)
- **Caching**: Metadata automatically cached; subsequent runs use cache
- **Large datasets**: 5000+ papers may take significant time
- **Rate limiting**: Automatic retry logic handles API rate limits
- **Memory**: Scales with dataset size

## Error Handling

### Missing Metadata
- If `continue_on_not_found=true`: Paper proceeds without enrichment
- If `continue_on_not_found=false`: Pipeline halts on first missing paper
- Errors logged in results dictionary

### API Failures
- Temporary failures: Automatic retry with backoff
- Permanent failures: Logged in error list, processing continues

## Data Quality

### Before Enrichment
Papers may have:
- Only DOI (from partial imports)
- Minimal fields (from citations expansion)
- Limited author information

### After Enrichment
Papers have:
- Complete metadata
- Full author lists
- Abstract and keywords
- Publication venue details
- Citation metrics

## Combining with Other Steps

### Before Export
Enrich before exporting to ensure complete data:
```yaml
pipeline:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch_001"
      imports:
        - name: "Papers"
          file_path: "data/papers.bib"
  
  - step: Enrich metadata
    builtin.retrieve_metadata:
      methods: "crossref"
  
  - step: Export complete data
    builtin.export:
      format: "jsonl"
      output_file: "results/complete.jsonl"
```

### With Categorization
```yaml
pipeline:
  - step: Retrieve metadata
    builtin.retrieve_metadata:
      methods: "crossref"
  
  - step: Filter by type
    builtin.categorization:
      exclude_types: true
```

### Citation Network
```yaml
pipeline:
  - step: Extract citations
    builtin.citations:
      backward:
        sources: "crossref"
  
  - step: Enrich new papers from citations
    builtin.retrieve_metadata:
      methods: "crossref"
  
  - step: Build complete graph
    builtin.export:
      format: "jsonl"
      output_file: "results/citation_network.jsonl"
```

## Cache Management

### Automatic Caching
- Metadata automatically cached in `{cache_dir}/metadata/`
- Cache entries expire after 30 days
- Cache shared across pipeline runs

### Force Refresh
To refresh metadata despite cache:
- Delete cache directory: `rm -rf {cache_dir}/metadata/`
- Or specify `--no-cache` flag (if available)

## Troubleshooting

### No Metadata Found
- Verify papers have DOI
- Check source API is accessible
- Review error messages in results

### Slow Performance
- First run slower (populates cache)
- Subsequent runs use cache (faster)
- Consider using checkpoint after metadata retrieval

### Incomplete Fields
- Some papers may not have all metadata in source
- Abstract may be unavailable for old papers
- Keywords may be missing for conference papers

## Related Steps

- [**citations**](./citations.md) - Extract backward citations before enrichment
- [**bibtex_import**](./bibtex_import.md) - Import papers that need enrichment
- [**deduplication**](./deduplication.md) - Remove duplicates after enrichment
- [**export**](./export.md) - Export enriched papers
