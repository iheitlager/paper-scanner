# CLI Tools for Paper Scanner

## Crossref Reference Fetcher

The Crossref Reference Fetcher is a comprehensive system for automatically fetching paper references from the Crossref API and loading them into your paper-scanner database.

### What It Does

1. **Queries your database** for papers with DOIs in screening stages
2. **Fetches references** from Crossref's comprehensive API
3. **Loads new papers** from references as new database records
4. **Creates citation edges** to build a citation network
5. **Tracks statistics** on success rates and errors

### Quick Start

#### 1. Prerequisites

Ensure you have:
- PostgreSQL running with paper-scanner database
- Papers in screening stages 'stage2_pass' or 'stage2_review'
- Network access to api.crossref.org

#### 2. Migrate Database (if using existing database)

```bash
make migrate-source-type
```

This adds the `source_type` field needed to track paper origins.

#### 3. Test the Setup

```bash
make test-crossref
```

This runs a 4-part test suite:
- ✓ Crossref API connectivity
- ✓ Reference parsing
- ✓ Database connection
- ✓ Full pipeline (1 paper)

#### 4. Run Limited Test

```bash
make fetch-crossref-limit
```

Processes 10 papers to verify everything works.

#### 5. Run Interactive Fetcher

```bash
make fetch-crossref-quick
```

Asks for confirmation, then fetches all papers.

#### 6. Run Full Fetch (Non-Interactive)

```bash
make fetch-crossref
```

Runs the full fetcher without prompts.

### Usage Options

```bash
# Limit to N papers
python -m paper_scanner.cli.fetch_crossref_references --max-papers 100

# Custom database URL
python -m paper_scanner.cli.fetch_crossref_references \
  --db-url postgresql://user:pass@host:5432/db

# Custom email for Crossref API
python -m paper_scanner.cli.fetch_crossref_references \
  --email your.email@example.com
```

### Environment Variables

```bash
# Database connection
export DATABASE_URL="postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"

# Then run
python -m paper_scanner.cli.fetch_crossref_references
```

### Output

The script provides:
- Real-time progress updates
- Per-paper reference counts
- Summary statistics on completion
- Error tracking and logging

Example output:
```
[1] smith_2020
  DOI: 10.1234/example.doi
  Found 42 references
  Added 38/42 references

[2] jones_2021
  DOI: 10.5678/another.doi
  Found 28 references
  Added 27/28 references

...

======================================================================
SUMMARY
======================================================================
Papers processed:         10
Papers with references:   9
Total references found:   280
New papers created:       250
Citation edges created:   250
Papers skipped:           1
Errors:                   0

Success rate: 90.0%
```

### Understanding the Schema

#### New Papers from Crossref

Papers loaded from Crossref have:
- `source_type = 'crossref'`
- Basic metadata from Crossref (title, authors, year, DOI)
- `processing_status = 'metadata_extracted'` (references not yet fetched for these)

#### Citation Edges

The `citation_edges` table links papers:
- `citing_paper_id` - The paper that cites
- `cited_paper_id` - The paper being cited

Example:
```sql
SELECT 
  p1.citekey as "Paper",
  COUNT(ce.id) as "References"
FROM papers p1
LEFT JOIN citation_edges ce ON p1.id = ce.citing_paper_id
WHERE p1.source_type = 'file'
GROUP BY p1.id
ORDER BY COUNT(ce.id) DESC;
```

### API Reference

#### CrossrefReferenceFetcher

```python
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceFetcher

fetcher = CrossrefReferenceFetcher(email="your@email.com")

# Fetch references for a DOI
result = fetcher.fetch_references_for_doi("10.1038/s41586-020-2012-7")
# Returns: {doi, title, year, references, reference_count}

# Parse a single reference
parsed = fetcher.parse_reference(ref_dict, source_paper_id=1)
# Returns: {title, year, authors, doi, journal, pages_range, ...}
```

#### CrossrefReferenceLoader

```python
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceLoader

loader = CrossrefReferenceLoader(db_url)

# Get papers to process
papers = loader.get_papers_for_processing()

# Run full pipeline
stats = loader.run(max_papers=None)

# stats contains:
# {
#   'papers_processed': N,
#   'papers_with_references': N,
#   'total_references_found': N,
#   'new_papers_created': N,
#   'citation_edges_created': N,
#   'papers_skipped': N,
#   'errors': N
# }
```

### Troubleshooting

#### "No papers found to process"

**Cause**: No papers in screening stages 'stage2_pass' or 'stage2_review'

**Solution**: 
1. Check you have papers in those stages:
```sql
SELECT COUNT(*) FROM papers p
JOIN paper_screening ps ON p.id = ps.paper_id
WHERE ps.screening_stage IN ('stage2_pass', 'stage2_review')
  AND p.doi IS NOT NULL;
```

2. Run screening pipeline first to populate screening stages

#### "Database connection failed"

**Cause**: PostgreSQL not accessible or wrong credentials

**Solution**:
1. Verify PostgreSQL is running: `psql --version`
2. Test connection: `psql postgresql://pdfuser:pdfpass@localhost:5432/pdfdb`
3. Check DATABASE_URL environment variable
4. Verify credentials in docker-compose.yml

#### "requests library not found"

**Solution**: Install dependencies
```bash
pip install requests
# or
make env
```

#### "Column source_type does not exist"

**Solution**: Run migration
```bash
make migrate-source-type
```

### Performance Notes

- **Typical speed**: ~10 papers/minute
- **Rate limiting**: 0.1 second between API calls (respects Crossref limits)
- **Database performance**: ~50-100ms per paper insert
- **Typical timeline**: 100 papers ≈ 10 minutes

### Advanced Usage

#### Process Specific Papers

```python
from paper_scanner.cli.fetch_crossref_references import CrossrefReferenceLoader
import os

db_url = os.getenv('DATABASE_URL')
loader = CrossrefReferenceLoader(db_url)

# Get all papers
papers = loader.get_papers_for_processing()

# Process only papers from 2020+
recent = [p for p in papers if p['year'] and p['year'] >= 2020]

for paper in recent:
    conn = loader.connect()
    try:
        loader.process_paper(paper, conn)
    finally:
        conn.close()
```

#### Monitor Progress

```python
loader = CrossrefReferenceLoader(db_url)
papers = loader.get_papers_for_processing()

# Process with progress bar
from tqdm import tqdm
for i, paper in enumerate(tqdm(papers)):
    conn = loader.connect()
    try:
        loader.process_paper(paper, conn)
        loader.stats['papers_processed'] += 1
    finally:
        conn.close()
```

#### Export Results

```sql
-- Export citation network as CSV
\COPY (
  SELECT 
    p1.citekey as citing_paper,
    p2.citekey as cited_paper,
    p2.year as cited_year,
    p2.title as cited_title,
    p2.doi as cited_doi
  FROM citation_edges ce
  JOIN papers p1 ON ce.citing_paper_id = p1.id
  JOIN papers p2 ON ce.cited_paper_id = p2.id
  WHERE p1.source_type = 'file'
) TO 'citations.csv' WITH (FORMAT CSV, HEADER);
```

### Architecture Overview

```
User Input (CLI/Script)
        ↓
    Argument Parsing
        ↓
CrossrefReferenceLoader
    ├─ connect() → PostgreSQL
    ├─ get_papers_for_processing() → Query DB
    ├─ process_paper(paper, conn)
    │   ├─ CrossrefReferenceFetcher
    │   │   ├─ fetch_references_for_doi() → Crossref API
    │   │   └─ parse_reference() → Structured data
    │   ├─ insert_referenced_paper() → Insert into DB
    │   └─ create_citation_edge() → Link papers
    └─ run() → Orchestrate all above
        ↓
    Database (papers, citation_edges)
        ↓
    Statistics & Logging
```

### Related Documentation

- **Full User Guide**: `docs/CROSSREF_REFERENCE_FETCHING.md`
- **Implementation Details**: `CROSSREF_IMPLEMENTATION.md`
- **Database Schema**: `etc/init-db.sql`
- **Test Suite**: `src/paper_scanner/cli/test_crossref_fetcher.py`

### Support

- Check logs for detailed error messages
- Run `make test-crossref` for diagnostics
- Review SQL queries in database documentation
- See Crossref API status: https://www.crossref.org/

### License

Follows project license (Apache 2.0)

---

**Last Updated**: 2025-12-05
**Version**: 1.0.0
