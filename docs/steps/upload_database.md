# Upload Database Step

Loads papers from the in-memory database into PostgreSQL with conflict handling, transaction management, and detailed reporting.

**Status**: v3.1.0+  
**Category**: Persistence  
**Mode**: Requires database connectivity

## Overview

The `upload_database` step bridges the in-memory `PapersDatabase` with PostgreSQL storage. It:

- Validates paper model conversion to SQL rows
- Handles cite_key and DOI deduplication conflicts
- Executes bulk inserts with configurable strategies
- Supports dry-run validation and detailed conflict reporting
- Manages transactions and connection pooling for reliability

## Configuration

### Option 1: Full Database URL (Simplest)

```yaml
- step: Upload to database
  builtin.upload_database:
    database_url: "postgresql://user:password@localhost:5432/pdfdb"
```

### Option 2: Environment Variables via dotenv (Recommended for Security)

Create a `.env` file in your project root:

```env
DB_USER=pdfuser
DB_PASSWORD=securepassword
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pdfdb
```

Then reference in YAML:

```yaml
- step: Upload to database
  builtin.upload_database:
    db_username: "$DB_USER"
    db_password: "$DB_PASSWORD"
    db_host: "$DB_HOST"
    db_port: "$DB_PORT"
    db_name: "$DB_NAME"
    conflict_strategy: "skip"
```

### Option 3: Database URL from Environment Variable

```yaml
- step: Upload to database
  builtin.upload_database:
    database_url: "$DATABASE_URL"  # Full connection string in env var
```

### Required Parameters

One of the following must be provided:
- `database_url`: Full PostgreSQL connection string (with optional `$` prefix for env var)
- OR all of: `db_username`, `db_password`, `db_host`, `db_port`, `db_name`

### Optional Parameters

```yaml
- step: Upload to database
  builtin.upload_database:
    database_url: "postgresql://user:password@localhost:5432/pdfdb"
    conflict_strategy: "skip"           # Default: "skip"
    batch_size: 100                     # Default: 100
    verbose_conflicts: true             # Default: false
```

#### Parameter Details

- **database_url** (optional, string)  
  PostgreSQL connection string. Format: `postgresql://user:password@host:port/database`  
  Can use environment variable reference: `$DATABASE_URL`

- **db_username**, **db_password**, **db_host**, **db_port**, **db_name** (optional, strings)  
  Individual database connection parameters. Can be literal values or environment variable references: `$DB_USER`  
  `.env` file is automatically loaded via dotenv

- **conflict_strategy** (optional, string)  
  How to handle papers with duplicate `cite_key`:
  - `skip`: Skip papers with existing cite_key (default)
  - `update`: Update all fields of existing papers
  - `raise`: Stop and raise error on conflict

- **batch_size** (optional, integer)  
  Number of papers to upload per batch. Default: 100

- **verbose_conflicts** (optional, boolean)  
  If true, include sample error messages in results. Default: false

## Examples

### Basic PostgreSQL Upload (Direct URL)

```yaml
project:
  name: "My Literature Review"

steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch_001"
      imports:
        - file_path: "data/papers.bib"
          source_type: "scopus"

  - step: Remove duplicates
    builtin.deduplication:
      method: "all"

  - step: Upload to PostgreSQL
    builtin.upload_database:
      database_url: "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
      conflict_strategy: "skip"
```

### With Environment Variables (Secure)

Create `.env` file:
```env
DB_USER=pdfuser
DB_PASSWORD=mySecurePassword123
DB_HOST=db.example.com
DB_PORT=5432
DB_NAME=pdfdb
```

Then in your workflow:
```yaml
- step: Upload to database
  builtin.upload_database:
    db_username: "$DB_USER"
    db_password: "$DB_PASSWORD"
    db_host: "$DB_HOST"
    db_port: "$DB_PORT"
    db_name: "$DB_NAME"
    conflict_strategy: "update"    # Update existing papers
    batch_size: 50
    verbose_conflicts: true        # Show errors in output
```

### With Full URL from Environment Variable

```yaml
- step: Upload to database
  builtin.upload_database:
    database_url: "$DATABASE_URL"  # Uses DATABASE_URL environment variable
```

### Dry-Run Validation

To validate papers before uploading without making changes:

```bash
python -m paper_scanner.cli run definition.yml --dry-run
```

This validates paper model-to-SQL conversion without connecting to the database.

## Data Mapping

The step maps Pydantic `Paper` model fields to PostgreSQL `papers` table columns:

### Identifiers
- `id` (UUID) → `papers.id` (VARCHAR 36)
- `db_id` (auto-increment) → `papers.db_id` (SERIAL PRIMARY KEY)
- `cite_key` (unique) → `papers.cite_key` (VARCHAR UNIQUE)
- `source_key` → `papers.source_key` (VARCHAR)

### Bibliographic Data
- `title` → `papers.title` (VARCHAR 1000)
- `abstract` → `papers.abstract` (TEXT)
- `authors` (list) → `papers.authors` (JSONB array of Author objects)
- `keywords`, `topics` (lists) → `papers.keywords`, `papers.topics` (TEXT arrays)
- `year` → `papers.year` (INTEGER)
- `journal`, `volume`, `issue`, `pages` → corresponding VARCHAR columns
- `doi`, `arxiv_id`, `pmid`, `isbn`, `issn` → corresponding VARCHAR columns

### Complex Objects
- `discovery` → `papers.discovery` (JSONB)
- `screening` → `papers.screening` (JSONB)
- `pdf_info` → `papers.pdf_info` (JSONB)
- `conceptual_analysis` → `papers.conceptual_analysis` (JSONB)

### Metadata
- `created_at`, `updated_at` → timestamps (TIMESTAMP)
- `manually_validated`, `validation_notes`, `validated_by`, `validated_at` → validation fields

## Output

### Success Result
```json
{
  "status": "success",
  "message": "Upload complete: inserted 42, updated 5, skipped 2 (strategy: skip)",
  "count": 47,
  "details": {
    "total_papers": 49,
    "inserted": 42,
    "updated": 5,
    "skipped": 2,
    "errors": 0,
    "conflict_strategy": "skip"
  }
}
```

### With Errors
```json
{
  "status": "warning",
  "message": "Upload complete: inserted 40, errors: 2 (strategy: skip)",
  "count": 40,
  "details": {
    "total_papers": 42,
    "inserted": 40,
    "updated": 0,
    "skipped": 0,
    "errors": 2,
    "conflict_strategy": "skip"
  },
  "error_samples": [
    "Paper 15 (SmithA2024): Invalid authors JSONB structure",
    "Paper 32 (JonesB2024): Missing required cite_key"
  ],
  "total_error_count": 2
}
```

### Dry-Run Result
```json
{
  "status": "success",
  "message": "Dry-run: validated 42 papers (no upload)",
  "count": 42,
  "details": {
    "mode": "dry-run",
    "validation": "passed"
  }
}
```

## Error Handling

- **Missing database_url**: Configuration validation error
- **Database connection failure**: Cannot connect to PostgreSQL (check credentials, host, port)
- **Duplicate cite_key with conflict_strategy="raise"**: Stops execution
- **Paper model validation error**: Cannot convert paper to SQL row (check data types)
- **Transaction rollback**: All papers in batch are rolled back on error

## Schema Requirements

The step requires PostgreSQL database with:
- `pgvector` extension for embedding support
- `papers` table with proper schema (auto-created by `etc/init-db.sql`)
- Proper indexes for cite_key uniqueness and DOI lookups

Initialize database:
```bash
# Via Docker
docker-compose up -d postgres

# Or manually
psql -U pdfuser -d pdfdb -f etc/init-db.sql
```

## Performance

- **Batch processing**: Papers uploaded in configurable batches (default: 100)
- **Connection pooling**: Manages 1-5 connections by default
- **Transactions**: Batch transactions for consistency
- **Dry-run speed**: O(n) validation without database I/O

Typical performance:
- 1000 papers: ~2-5 seconds (with network latency)
- 10000 papers: ~20-50 seconds

## Related Steps

- [bibtex_import](bibtex_import.md) - Import papers from BibTeX files
- [deduplication](deduplication.md) - Remove duplicate papers before upload
- [export](export.md) - Export papers to files
- [checkpoint](checkpoint.md) - Save in-memory database state

## See Also

- [Step Architecture (ADR-0002)](../adr/0002-step-architecture.md)
- [PostgreSQL Setup](../../README.md#postgresql)
- [sql.py Module](../../src/paper_scanner/io/sql.py) - Database abstraction layer
