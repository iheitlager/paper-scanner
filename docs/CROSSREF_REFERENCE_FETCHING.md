# Crossref Reference Fetching Guide

## Overview

This guide explains how to use the Crossref Reference Fetcher to automatically fetch references for papers with DOIs from your screening database and load them as new papers with citation edges.

## What It Does

The Crossref fetcher performs the following workflow:

1. **Queries papers** in screening stages `stage2_pass` or `stage2_review` that have DOIs
2. **Fetches references** for each paper using the Crossref API
3. **Loads referenced papers** as new records in the papers table with `source_type='crossref'`
4. **Creates citation edges** linking the original paper to each referenced paper
5. **Tracks statistics** on success rates and errors

## Setup

### Prerequisites

```bash
# Install required dependencies
pip install requests psycopg2-binary
```

### Database Migration

If you're using an existing database, run the migration to add the `source_type` field:

```bash
python -m paper_scanner.cli.migrate_add_source_type
```

This will:
- Add the `source_type` VARCHAR(100) column to the papers table
- Create an index on source_type for performance
- Set existing papers' source_type to 'file'

## Usage

### Quick Test

Before running on all papers, test the setup:

```bash
python -m paper_scanner.cli.test_crossref_fetcher
```

This will:
1. Test Crossref API connectivity
2. Test reference parsing
3. Test database connection
4. Run a test pipeline on 1 paper

### Run on Limited Dataset

```bash
python -m paper_scanner.cli.fetch_crossref_references --max-papers 10
```

This processes the first 10 papers (sorted by screening similarity, descending).

### Run on All Papers

```bash
python -m paper_scanner.cli.fetch_crossref_references
```

### Custom Database URL

```bash
python -m paper_scanner.cli.fetch_crossref_references \
  --db-url postgresql://user:pass@host:5432/dbname
```

### Custom Email (for Crossref User-Agent)

```bash
python -m paper_scanner.cli.fetch_crossref_references \
  --email your.email@example.com
```

## Database Schema Changes

### New Column in `papers` Table

```sql
ALTER TABLE papers ADD COLUMN source_type VARCHAR(100);
CREATE INDEX idx_papers_source_type ON papers(source_type);
```

### Source Types

Papers can have the following source_type values:

- `'file'` - Original PDF files in your collection
- `'crossref'` - References fetched from Crossref
- `'arxiv'` - References from arXiv (future expansion)
- `'scholar'` - References from Google Scholar (future expansion)

### Citation Edges

The script creates records in the `citation_edges` table:

```sql
INSERT INTO citation_edges (citing_paper_id, cited_paper_id)
VALUES (original_paper_id, referenced_paper_id);
```

## API Reference

### CrossrefReferenceFetcher

Main class for interacting with the Crossref API.

```python
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceFetcher

fetcher = CrossrefReferenceFetcher(email="your@email.com")

# Fetch references for a DOI
result = fetcher.fetch_references_for_doi("10.1038/s41586-020-2012-7")

# result contains:
# {
#   'doi': '10.1038/s41586-020-2012-7',
#   'title': 'Paper title',
#   'year': 2020,
#   'references': [...],
#   'reference_count': 42,
#   'fetched_at': timestamp
# }

# Parse a reference into database format
parsed = fetcher.parse_reference(reference_dict, source_paper_id=1)
```

### CrossrefReferenceLoader

Main class for loading references into the database.

```python
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceLoader

loader = CrossrefReferenceLoader(db_url)

# Get papers to process
papers = loader.get_papers_for_processing()

# Run full pipeline
stats = loader.run(max_papers=None)

# stats contains:
# {
#   'papers_processed': 10,
#   'papers_with_references': 8,
#   'total_references_found': 320,
#   'new_papers_created': 280,
#   'citation_edges_created': 280,
#   'papers_skipped': 2,
#   'errors': 0
# }
```

## Performance Considerations

### Rate Limiting

The script uses a 0.1-second delay between API calls to respect Crossref's rate limits. This can be customized:

```python
fetcher = CrossrefReferenceFetcher(rate_limit_delay=0.05)
```

### Expected Timeline

- ~10 papers/minute with default rate limiting
- 100 papers = ~10 minutes
- 1000 papers = ~100 minutes

### Database Performance

The script commits transactions per paper to avoid long-running transactions. Large batches may take longer:

- Query speed: Usually fast for screening stage lookup
- Insert speed: ~50-100ms per paper
- Index updates: Automatic (IVFFlat index on citation_edges)

## Troubleshooting

### "No papers found to process"

**Cause**: No papers in screening stages 'stage2_pass' or 'stage2_review'

**Solution**: Run screening pipeline first to populate paper_screening table

```sql
SELECT * FROM paper_screening 
WHERE screening_stage IN ('stage2_pass', 'stage2_review');
```

### "Database connection failed"

**Cause**: PostgreSQL not accessible

**Solution**: Check connection string and database status

```bash
psql postgresql://pdfuser:pdfpass@localhost:5432/pdfdb -c "SELECT 1"
```

### "No references found in Crossref"

**Cause**: Paper's DOI not in Crossref database

**Solution**: This is normal for some papers. They're skipped and logged. Check logs for details.

### "requests library not found"

**Solution**: Install requests

```bash
pip install requests
```

## Querying Results

### See fetched papers

```sql
SELECT * FROM papers WHERE source_type = 'crossref' LIMIT 10;
```

### See citation network

```sql
SELECT 
  p1.citekey as citing_paper,
  p2.citekey as cited_paper,
  p2.year,
  p2.title
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
LIMIT 20;
```

### Count references by paper

```sql
SELECT 
  p.citekey,
  p.title,
  COUNT(ce.id) as reference_count
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
GROUP BY p.id, p.citekey, p.title
ORDER BY reference_count DESC;
```

### Find missing references

```sql
SELECT 
  p.citekey,
  COUNT(ce.id) as references_fetched
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
  AND p.doi IS NOT NULL
GROUP BY p.id, p.citekey
HAVING COUNT(ce.id) = 0;
```

## Limitations and Known Issues

1. **Crossref Coverage**: Not all papers have complete reference lists in Crossref
2. **Duplicate Detection**: Papers are deduplicated by DOI within the 'crossref' source type
3. **Author Parsing**: Author information may be incomplete for some papers
4. **Rate Limits**: Respects Crossref's polite pooling (0.1s between requests)

## Future Enhancements

- [ ] Support for arXiv references
- [ ] Support for Google Scholar references  
- [ ] Duplicate detection across source_type values
- [ ] Citation count aggregation
- [ ] Reference validation (check if referenced paper exists locally)
- [ ] Batch API support (fetch multiple DOIs at once)

## Examples

### Complete Pipeline Example

```python
#!/usr/bin/env python3
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceLoader
import os

# Setup
db_url = os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb')
loader = CrossrefReferenceLoader(db_url)

# Get papers
papers = loader.get_papers_for_processing()
print(f"Found {len(papers)} papers to process")

# Run fetcher
stats = loader.run(max_papers=50)

# Print summary
print(f"\n✓ Success! Fetched references for {stats['papers_with_references']} papers")
print(f"  Total references: {stats['total_references_found']}")
print(f"  New papers created: {stats['new_papers_created']}")
```

### Selective Processing

```python
# Process only papers from after 2020
papers = loader.get_papers_for_processing()
recent_papers = [p for p in papers if p['year'] and p['year'] >= 2020]

for paper in recent_papers[:10]:
    print(f"Processing {paper['citekey']}...")
    conn = loader.connect()
    loader.process_paper(paper, conn)
    conn.close()
```

## Support

For issues or questions:
1. Check the logs in the application directory
2. Run the test suite to diagnose problems
3. Review the database schema in `etc/init-db.sql`
4. Check Crossref API status: https://www.crossref.org/

## References

- Crossref API Documentation: https://github.com/CrossRef/rest-api-doc
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Paper Scanner Documentation: See docs/ folder
