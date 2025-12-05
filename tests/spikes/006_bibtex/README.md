# BibTeX Loader for Paper Scanner

This module provides a clean separation between **reading BibTeX files** and **loading them into PostgreSQL**, making it easy to eventually convert these classes into tools in the main package.

## Architecture

### BibtexReader Class
Handles all BibTeX parsing logic:
- **Input**: BibTeX file path
- **Output**: List of `Paper` dataclass objects
- **Responsibilities**:
  - Extracts BibTeX entries using regex-based parsing
  - Maps BibTeX fields to database schema
  - Handles author parsing ("First Last" and "Last, First" formats)
  - Parses keywords/tags into lists
  - Stores extra fields in `source_details` JSONB

**Key Methods**:
- `parse()`: Main entry point, returns List[Paper]
- `_extract_entries()`: Splits file into individual @entries
- `_parse_entry()`: Converts single entry to Paper object
- `_parse_fields()`: Handles complex field parsing with nested braces
- `_parse_authors()`: Extracts author list with first/last names
- `_parse_keywords()`: Converts semicolon/comma-separated keywords

### PostgreSQLLoader Class
Handles database operations:
- **Input**: List of `Paper` objects and database connection string
- **Output**: Count of successfully loaded papers
- **Responsibilities**:
  - Manages PostgreSQL connection lifecycle
  - Converts Python objects to database-compatible types
  - Implements upsert logic (ON CONFLICT)
  - Transaction management with rollback on error
  - Comprehensive error logging

**Key Methods**:
- `connect()`: Establishes database connection
- `disconnect()`: Closes connection gracefully
- `load_papers()`: Loads all papers with transaction handling
- `_insert_paper()`: Inserts single paper with error handling

### Paper Dataclass
Represents a paper with:
- **Required**: `citekey` (unique identifier)
- **Mapped Fields**: title, authors, year, journal, volume, issue, pages, doi, publisher, abstract, keywords, paper_type
- **Flexible Storage**: `source_details` and `title_details` JSONB fields for extra data
- **Raw Data**: `raw_data` dict for debugging

## Database Schema Mapping

| BibTeX Field | Database Column | Type | Notes |
|---|---|---|---|
| @article, @inproceedings, etc. | paper_type | VARCHAR | Entry type (article, inproceedings, etc.) |
| {citekey} | citekey | VARCHAR(100) | Unique identifier |
| title | title | VARCHAR(500) | - |
| author | authors | JSONB | Parsed as [{last_name, first_name, initials, order}] |
| year | year | INTEGER | Extracted as number |
| journal | journal | VARCHAR(500) | - |
| journal-iso | journal_iso | VARCHAR(500) | ISO abbreviation |
| volume | volume | VARCHAR(50) | - |
| number | issue | VARCHAR(50) | Issue number |
| pages | pages_range | VARCHAR(100) | Full range like "123-456" |
| doi | doi | VARCHAR(255) | - |
| publisher | publisher | VARCHAR(255) | - |
| abstract | abstract | TEXT | - |
| keywords | keywords | TEXT[] | Parsed as array |
| keywords-plus | keywords | TEXT[] | Merges with keywords |
| * (other) | source_details | JSONB | Captured for reference |

## Usage

### Basic Reading (no database)

```python
from load_bibtex import BibtexReader

reader = BibtexReader('/path/to/file.bib')
papers = reader.parse()

for paper in papers:
    print(f"{paper.citekey}: {paper.title} ({paper.year})")
    print(f"  Authors: {paper.authors}")
```

### Loading into Database

```python
from load_bibtex import BibtexReader, PostgreSQLLoader

# Read papers
reader = BibtexReader('/path/to/file.bib')
papers = reader.parse()

# Load into database
loader = PostgreSQLLoader('postgresql://user:pass@localhost/pdfdb')
try:
    loader.connect()
    count = loader.load_papers(papers)
    print(f"Loaded {count} papers")
finally:
    loader.disconnect()
```

### Command Line

```bash
# Read and print BibTeX (see example_load_bibtex.py)
python example_load_bibtex.py /path/to/file.bib

# Load into database (requires DATABASE_URL env var)
export DATABASE_URL="postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
python load_bibtex.py /path/to/file.bib
```

## Future Integration

These classes are designed to become tools in `src/paper_scanner/tools/`:

```python
# src/paper_scanner/tools/bibtex_reader.py
from load_bibtex import BibtexReader  # Import and re-export

# src/paper_scanner/tools/database_loader.py
from load_bibtex import PostgreSQLLoader  # Import and re-export
```

## Dependencies

```
psycopg2-binary>=2.9.0
```

## Error Handling

The loader gracefully handles:
- **Missing files**: FileNotFoundError with clear message
- **Parse errors**: Logs warning and continues with next entry
- **Database errors**: Rolls back transaction and logs details
- **Encoding issues**: Assumes UTF-8, handles gracefully

## Testing

```bash
# Test parsing only (no database needed)
python -m pytest tests/spikes/006_bibtex/ -v -k "parse"

# Test with real database (requires running postgres)
python -m pytest tests/spikes/006_bibtex/ -v
```

## Files

- `load_bibtex.py`: Main module with BibtexReader and PostgreSQLLoader
- `example_load_bibtex.py`: Usage examples
- `README.md`: This file
