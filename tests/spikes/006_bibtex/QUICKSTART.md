# Quick Start Guide

## Installation

No additional installation needed beyond project dependencies. Requires:
- Python 3.8+
- `psycopg2-binary` (already in project)
- PostgreSQL database (already running in docker-compose)

## Quick Examples

### 1. Parse and Display Papers (No Database)

```bash
cd /Users/iheitlager/wc/paper-scanner
source .venv/bin/activate

python tests/spikes/006_bibtex/load_bibtex_cli.py path/to/file.bib --list
```

Output: Shows first 5 papers with title, authors, year, journal, DOI

### 2. Load Papers into Database

```bash
# Load first 10 papers
python tests/spikes/006_bibtex/load_bibtex_cli.py path/to/file.bib --sample 10

# Load all papers
python tests/spikes/006_bibtex/load_bibtex_cli.py path/to/file.bib
```

### 3. Use Programmatically

```python
from tests.spikes.006_bibtex.load_bibtex import BibtexReader, PostgreSQLLoader

# Read papers
reader = BibtexReader('papers.bib')
papers = reader.parse()
print(f"Parsed {len(papers)} papers")

# Load to database
loader = PostgreSQLLoader()
loader.connect()
loader.load_papers(papers)
loader.disconnect()
```

## File Structure

```
tests/spikes/006_bibtex/
├── load_bibtex.py              # Main module (classes: BibtexReader, PostgreSQLLoader, Paper)
├── load_bibtex_cli.py          # Command-line tool
├── example_load_bibtex.py      # Usage examples
├── test_bibtex_loader.py       # Unit tests
├── test_integration.py         # Integration test (loads data)
├── README.md                   # Detailed documentation
└── PROJECT_SUMMARY.md          # Architecture overview
```

## Running Tests

```bash
source .venv/bin/activate

# Run all tests
python tests/spikes/006_bibtex/test_bibtex_loader.py

# Run integration test (loads 20 papers)
python tests/spikes/006_bibtex/test_integration.py
```

Expected output: All 4 tests pass ✓

## Core Classes

### BibtexReader
```python
reader = BibtexReader('file.bib')
papers = reader.parse()  # Returns List[Paper]
```

### PostgreSQLLoader
```python
loader = PostgreSQLLoader(connection_string)
loader.connect()
count = loader.load_papers(papers)
loader.disconnect()
```

### Paper
```python
paper.citekey         # str: Unique identifier
paper.title           # str: Paper title
paper.authors         # List[Dict]: Author list with first/last names
paper.year            # int: Publication year
paper.journal         # str: Journal name
paper.doi             # str: Digital Object Identifier
paper.abstract        # str: Full abstract text
paper.keywords        # List[str]: Keywords/tags
paper.source_details  # Dict: Extra metadata
```

## Configuration

### Database Connection

Default: `postgresql://pdfuser:pdfpass@localhost:5432/pdfdb`

Override with environment variable:
```bash
export DATABASE_URL="postgresql://user:pass@host:port/db"
python load_bibtex_cli.py file.bib
```

Or command-line argument:
```bash
python load_bibtex_cli.py file.bib --db postgresql://user:pass@host/db
```

## Workflow

1. **Prepare BibTeX file** (usually from Web of Science, CrossRef, etc.)
2. **Run CLI** to preview papers: `python load_bibtex_cli.py file.bib --list`
3. **Test load** small batch: `python load_bibtex_cli.py file.bib --sample 10`
4. **Load all** papers: `python load_bibtex_cli.py file.bib`
5. **Query results** in PostgreSQL:
   ```sql
   SELECT citekey, title, year FROM papers WHERE paper_type = 'article';
   ```

## Performance

- Parsing: ~0.1ms per paper (692 papers in ~80ms)
- Loading: ~7ms per paper (10 papers in ~70ms)
- Both operations are fast enough for production use

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "File not found" | Check path is correct, use absolute path |
| "Cannot connect to database" | Ensure PostgreSQL is running, check connection string |
| "Papers not loading" | Check DATABASE_URL env var is set correctly |
| "Parse errors" | Check file encoding is UTF-8 |

## Next Steps

After this spike works, integrate into main package:

```
src/paper_scanner/tools/
├── bibtex_reader.py
├── database_loader.py
└── __init__.py
```

Then import from main package:
```python
from paper_scanner.tools import BibtexReader, PostgreSQLLoader
```

## Testing the Real File

The project includes a test with 692 real papers:

```bash
python tests/spikes/006_bibtex/load_bibtex_cli.py \
  "/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib" \
  --list --sample 5
```

This parses successfully and shows real paper data.
