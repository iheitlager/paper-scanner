# Crossref Implementation - File Organization

## Location Changes

### Moved Files

#### Main Script
- **From**: `src/paper_scanner/cli/fetch_crossref_references.py`
- **To**: `tests/spikes/006_bibtex/fetch_crossref_references.py`
- **Purpose**: Research/exploration spike for Crossref integration with BibTeX loading

#### Test Suite
- **From**: `src/paper_scanner/cli/test_crossref_fetcher.py`
- **To**: `tests/unit/test_crossref_fetcher.py`
- **Purpose**: Unit tests for the Crossref fetcher

### Removed Files (Cleanup)
- ~~`src/paper_scanner/cli/fetch_crossref_references_quickstart.py`~~ (removed - redundant example)
- ~~`src/paper_scanner/cli/crossref_fetcher.py`~~ (removed - unused wrapper module)

### Retained Files

#### Migration Script
- **Location**: `src/paper_scanner/cli/migrate_add_source_type.py`
- **Purpose**: Utility to add source_type field to existing databases

#### Documentation
- `docs/CROSSREF_REFERENCE_FETCHING.md` - Comprehensive user guide
- `docs/CROSSREF_SQL_QUERIES.md` - SQL query reference
- `docs/CLI_TOOLS.md` - CLI tools documentation
- `CROSSREF_IMPLEMENTATION.md` - Implementation summary

## Usage

### Run Tests
```bash
make test-crossref
# or
uv run pytest tests/unit/test_crossref_fetcher.py -v
```

### Run Fetcher (Limited)
```bash
make fetch-crossref-limit
# Runs: cd tests/spikes/006_bibtex && uv run python fetch_crossref_references.py --max-papers 10
```

### Run Fetcher (Full)
```bash
make fetch-crossref
# Runs: cd tests/spikes/006_bibtex && uv run python fetch_crossref_references.py
```

### Migrate Database
```bash
make migrate-source-type
# Runs: uv run python -m paper_scanner.cli.migrate_add_source_type
```

## File Organization Rationale

- **Spike location**: Research/exploration code belongs in `tests/spikes/` for tracking experiments
- **Unit tests**: Tests belong in `tests/unit/` following standard project structure
- **Migration utility**: Keeps database schema utilities in `src/paper_scanner/cli/`
- **Documentation**: All guides remain in `docs/` for user access

## Integration Points

The Crossref fetcher integrates with:
- Database schema: `etc/init-db.sql` (has source_type field)
- Database utilities: `src/paper_scanner/web/database.py`
- Paper screening: `paper_screening` table
- Citation network: `citation_edges` table

## Next Steps

- Review spike results and integrate successful patterns
- Consider promoting to production if needed
- Extend with additional sources (arXiv, Google Scholar)
- Add to main CLI if production-ready
