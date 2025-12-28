# Frequently Asked Questions

## Getting Started

### What do I need to get started?
You need:
- Python 3.11 or higher
- A Claude API key (from Anthropic)
- Git (to clone the repository)

PostgreSQL is optional; SQLite is used by default.

### How do I get a Claude API key?
1. Go to [Anthropic's Console](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to API keys
4. Create a new API key
5. Copy it to your `.env` file

### How long does it take to set up?
About 5 minutes with the [Quick Start Guide](guide/quick-start.md).

## Usage

### Can I use my own PDF files?
Yes! The tool can analyze PDFs directly using Claude. Use the `run_template` step with appropriate templates for your use case.

### What formats can I import from?
Currently supported:
- BibTeX (.bib files)
- JSON/JSONLines
- CSV (with configuration)

Custom importers can be added as steps.

### What formats can I export to?
Currently supported:
- BibTeX
- JSON
- CSV

See the [export step](steps/overview.md) documentation.

### Can I process papers without Claude?
Not fully - Claude is used for structured analysis. However, you can import papers and use other steps (citations, deduplication, etc.) that don't require Claude.

## Citation Networks

### What's the difference between backward and forward citations?
- **Backward**: Papers that this paper cites (references)
- **Forward**: Papers that cite this paper (cited by)

Both are called "citations" but refer to different directions.

### Why do some citations not resolve?
Citations may fail to resolve if:
- The DOI is incorrect or malformed
- The cited paper is not in any citation source (Crossref, OpenAlex, etc.)
- The citation source is temporarily unavailable

Set `continue_on_not_found: true` to skip unresolved citations instead of failing.

### Which citation sources are available?
- **Crossref** - Journal articles, books, conference papers
- **OpenAlex** - Broad academic coverage
- **Semantic Scholar** - Research paper indexing

### How long does citation extraction take?
Depends on:
- Number of papers
- Citation sources used
- API rate limits

For 100 papers with Crossref: typically 2-5 minutes.

## Database

### What database should I use?
For most users:
- **Development/Testing**: SQLite (default) - no setup needed
- **Production**: PostgreSQL - more features, better performance

### Can I migrate from SQLite to PostgreSQL?
Yes, but there's currently no built-in migration tool. You can:
1. Export papers from SQLite
2. Set up PostgreSQL
3. Import papers into PostgreSQL

### How do I back up my data?
```bash
# SQLite
cp papers.db papers.db.backup

# PostgreSQL
pg_dump paper_scanner > backup.sql
```

### How do I reset my database?
```bash
# SQLite
rm papers.db

# PostgreSQL
dropdb paper_scanner
createdb paper_scanner
```

Then reinitialize:
```bash
uv run paper-processor --init
```

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Set your API key:
```bash
export ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
# or in .env file
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
```

### "Module not found" errors
Reinstall dependencies:
```bash
uv sync --all-groups --refresh
```

### Tests are failing
```bash
# Clean cache
rm -rf .pytest_cache __pycache__ .mypy_cache

# Reinstall
uv sync --all-groups

# Run tests
make test
```

### Pipeline hangs or is very slow
- Check API rate limits (Crossref, etc.)
- Reduce `batch_size` in configuration
- Check network connectivity
- Try running with `--debug` flag

### "Database is locked"
```bash
# Remove lock files
rm papers.db-shm papers.db-wal

# Try again
uv run paper-processor definition.yml
```

### "Too many open files"
Increase file descriptor limit:
```bash
# Temporary (current shell)
ulimit -n 2048

# Permanent (macOS)
echo "ulimit -n 4096" >> ~/.zshrc
```

## Development

### How do I create a custom step?
See [Step Development Guide](architecture/pipeline.md#step-development).

### How do I contribute?
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

See [Contributing Guide](contributing/setup.md).

### What's the test coverage?
Aim for:
- 80%+ overall
- 90%+ for core modules
- 70%+ for UI/CLI

Check current coverage:
```bash
uv run pytest --cov=src/paper_scanner tests/
```

### How do I run tests?
```bash
# All tests
make test

# Specific test
uv run pytest tests/unit/steps/test_citations.py -v

# With coverage
uv run pytest --cov=src/paper_scanner tests/
```

### How do I build documentation?
```bash
# Build
mkdocs build

# Serve locally
mkdocs serve
# Visit http://localhost:8000
```

## Architecture

### Why three-level configuration?
Separates concerns:
- **General**: Project-level settings (database, cache)
- **Step**: Step-specific configuration (what to do)
- **Runtime**: Execution options (verbose, dry-run)

See [ADR-0001](adr/0001-pipeline-architecture.md).

### Why pipelines instead of direct API?
Pipelines provide:
- Reproducibility (version control workflows)
- Checkpointing (resumable execution)
- Composability (chain steps together)
- Extensibility (add new steps easily)

### Can I use the Python API directly?
Yes! The [Definition API](api/core.md) provides a Pythonic interface:

```python
from paper_scanner.definition import Definition

pipeline = (Definition("Review")
    .bibtex_import("refs.bib")
    .citations(backward={"citations": ["crossref"]})
    .export("bibtex", output="out.bib")
)

result = pipeline.run()
```

## Performance

### How many papers can I process?
Depends on:
- Available RAM
- Processing steps
- Database backend

Typically: 1000+ papers efficiently with PostgreSQL.

### How can I speed things up?
1. Use PostgreSQL instead of SQLite
2. Reduce batch size if memory is limited
3. Use specific citation sources only
4. Filter papers before processing
5. Cache results (default behavior)

### What's the memory usage?
Typically:
- SQLite: 100-500 MB
- PostgreSQL: 200-500 MB
- Plus step-specific memory

## Legal and Ethics

### Is this tool for academic use only?
No, but it's designed with academic workflows in mind.

### Can I use this for web scraping?
The tool uses official APIs (Crossref, OpenAlex, etc.). Respect their terms of service.

### What about data privacy?
- Papers are stored locally (SQLite) or on your PostgreSQL server
- API calls go to Anthropic, Crossref, etc.
- No data is shared with third parties beyond necessary API calls

## Licensing and Support

### What license is paper-scanner under?
MIT License - see LICENSE file.

### Is there commercial support?
Currently community-supported. For commercial needs, please contact the maintainers.

### How do I report bugs?
1. Check [existing issues](https://github.com/iheitlager/paper-scanner/issues)
2. Create a new issue with:
   - Detailed reproduction steps
   - Expected vs. actual behavior
   - System information (OS, Python version)
   - Relevant logs/screenshots

### How do I request features?
Open a [discussion](https://github.com/iheitlager/paper-scanner/discussions) or issue describing:
- The desired feature
- Why you need it
- How it should work

## Still Have Questions?

- 📚 [Full Documentation](https://paper-scanner.readthedocs.io)
- 💬 [Open a Discussion](https://github.com/iheitlager/paper-scanner/discussions)
- 🐛 [Report an Issue](https://github.com/iheitlager/paper-scanner/issues)
- 📧 Contact maintainers
