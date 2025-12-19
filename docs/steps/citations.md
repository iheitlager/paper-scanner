# Citations Step

Extract and resolve backward citations (references) from papers using external APIs.

## Overview

The citations step walks over Paper records in the database and fetches backward citations (references) from configured sources (Crossref by default). It then resolves citations against the Paper database and creates new Paper records for unresolved citations, building a complete citation graph.

**Three-pass architecture for improved testability:**
- **PASS 1**: Fetch citations from external sources and store in papers
- **PASS 2**: Resolve citations to existing papers or create new papers, fetch metadata
- **PASS 3**: Build citation graph (cited_papers, cited_by_papers) in memory

## Configuration

```yaml
pipeline:
  - step: Extract backward citations
    builtin.citations:
      backward:
        sources: ["crossref"]                    # Fetcher source(s): string or list
        continue_on_not_found: true              # Create new Paper for unresolved citations
        limit: null                              # Optional: limit citations per paper
        output_errors: null                      # Optional: file path for error logging
      paper-type:                                # Optional: filter by paper type
        - "journal_article"                      # Default: ["journal_article"]
```

### Parameters

#### `backward` (dict, required)
Configuration for backward citation extraction.

**sub-parameters:**
- `sources` (string or list, default: `["crossref"]`) - Fetcher source(s) to use for citation retrieval
- `continue_on_not_found` (boolean, default: `true`) - If true, create new Paper records for unresolved citations. If false, skip unresolved citations
- `limit` (integer, optional) - Maximum number of citations to fetch per paper
- `output_errors` (string, optional) - File path to write unresolved citations as JSONLines

#### `paper-type` (list, optional)
Filter papers to process by publication type. Default: `["journal_article"]`

Valid values:
- `"journal_article"`
- `"conference_paper"`
- `"book"`
- `"preprint"`
- `"other"`

## Examples

### Basic Citation Extraction
```yaml
- step: Extract citations
  builtin.citations:
    backward:
      sources: "crossref"
      continue_on_not_found: true
```

### With Error Logging
```yaml
- step: Extract and log unresolved citations
  builtin.citations:
    backward:
      sources: ["crossref"]
      continue_on_not_found: true
      output_errors: "results/unresolved_citations.jsonl"
```

### Limited Citation Count
```yaml
- step: Extract up to 10 citations per paper
  builtin.citations:
    backward:
      sources: "crossref"
      limit: 10
```

### Multiple Sources
```yaml
- step: Extract citations from multiple sources
  builtin.citations:
    backward:
      sources: ["crossref", "openalex"]
      continue_on_not_found: true
```

### Filter by Paper Type
```yaml
- step: Extract citations only from journal articles
  builtin.citations:
    backward:
      sources: "crossref"
      paper-type: ["journal_article"]
```

## Process Flow

### PASS 1: Fetch Citations
1. Filter papers by `paper-type` (default: journal_article)
2. For each paper with a DOI:
   - Fetch citations from configured sources
   - Store citations in paper's `citations` list
   - Track cache hits/misses
3. Skip papers without DOI

### PASS 2: Resolve Citations
1. For each paper with citations:
   - For each citation:
     - Try to resolve by DOI from existing papers (primary key lookup)
     - If not found and `continue_on_not_found=true`:
       - Fetch metadata from source via `fetcher.fetch_paper()`
       - Create new Paper record
       - Store full Paper object in `Citation.resolved_paper`
     - If not found and `continue_on_not_found=false`:
       - Leave unresolved
       - Log error if `output_errors` specified
2. Track: resolved, created_new, unresolved citations

### PASS 3: Build Citation Graph
1. Loop over all papers and their citations
2. For each resolved citation:
   - Add resolved_paper to Paper's `cited_papers` list (forward link)
   - Add citing paper to resolved_paper's `cited_by_papers` list (reverse link)
   - Prevent duplicates
3. Batch update all modified papers to database

## Data Structures

### Citation Model
```python
@dataclass
class Citation:
    doi: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    extraction_method: str = "unknown"
    confidence: float = 0.0
    resolved_paper: Optional[Paper] = None  # Full Paper object after PASS 2
```

### Paper Modifications
After citations step, Paper records contain:
- `citations: List[Citation]` - All citations extracted from bibliography
- `cited_papers: List[Paper]` - Papers this one cites (forward links)
- `cited_by_papers: List[Paper]` - Papers that cite this one (reverse links)

## Results

Returns a dictionary with statistics:
```python
{
    "status": "ok",                          # "ok" or "completed_with_errors"
    "total_papers": int,                     # Total papers in database
    "target_papers": int,                    # Papers processed (filtered by type)
    "papers_with_citations": int,            # Papers that had citations fetched
    "citations_fetched": int,                # Total citations extracted
    "citations_resolved": int,               # Citations linked to existing papers
    "citations_created_new_paper": int,      # New papers created for citations
    "citations_unresolved": int,             # Citations that couldn't be resolved
    "forward_links_created": int,            # cited_papers links created
    "reverse_links_created": int,            # cited_by_papers links created
    "cache_hits": int,                       # Cache hits during fetching
    "cache_misses": int,                     # Cache misses during fetching
    "errors": [str]                          # List of error messages
}
```

## Workflow Patterns

### Complete Citation Graph
```
bibtex_import → citations → deduplication → export
```

### Citation Analysis with Filtering
```
bibtex_import → citations → keyword_screening → export
```

### Citation Expansion
```
input → citations → retrieve_metadata → export
```

## Performance Considerations

- **Most expensive operation**: Fetching citations from external APIs
- **Cache**: Automatically caches fetched citations and paper metadata
- **Large datasets**: 5000+ papers may take significant time due to API calls
- **Memory**: Citation graph built in memory; scales with number of citations

## Error Handling

### Unresolved Citations
- Papers without DOI: Skipped in PASS 1
- Citations without DOI: Marked unresolved, not created as new papers
- API failures: Caught and logged, processing continues

### Error Output
When `output_errors` is specified, each unresolved citation is written as JSONLines:
```json
{"paper_id": "uuid", "citation": {"doi": "...", "title": "...", ...}}
```

## Combining with Other Steps

### Retrieve Full Metadata
Use with `retrieve_metadata` step to enrich newly created papers:
```yaml
pipeline:
  - step: Extract citations
    builtin.citations:
      backward:
        sources: "crossref"
  - step: Retrieve metadata for new papers
    builtin.retrieve_metadata:
      methods: ["crossref"]
```

### Export Citation Network
```yaml
pipeline:
  - step: Extract citations
    builtin.citations:
      backward:
        sources: "crossref"
  - step: Export papers with citation links
    builtin.export:
      format: "jsonl"
      output_file: "results/papers_with_citations.jsonl"
```

## Limitations

- Only extracts backward citations (references), not forward citations (citations to this paper)
- Resolution depends on DOI availability in original citation and in database
- New Paper records created from citations have limited metadata (DOI, title, year)
- Citation confidence scores not currently used for filtering

## Related Steps

- [**retrieve_metadata**](./retrieve_metadata.md) - Enrich papers with complete metadata
- [**deduplication**](./deduplication.md) - Remove duplicates created during citation expansion
- [**export**](./export.md) - Export papers with citation information
