# Quick Start

Get up and running with paper-scanner in 5 minutes.

## Prerequisites

- Python 3.11+
- `uv` installed ([installation guide](installation.md))
- Claude API key (get from [Anthropic](https://console.anthropic.com))

## Step 1: Clone and Setup (2 min)

```bash
git clone https://github.com/your-org/paper-scanner.git
cd paper-scanner

# Install dependencies
uv sync --all-groups

# Set up environment
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
PAPERS_DB=papers.db
EOF
```

Replace `sk-ant-YOUR_KEY_HERE` with your actual Claude API key.

## Step 2: Create Your First Pipeline (1 min)

Create `my-first-pipeline.yml`:

```yaml
general:
  db_path: papers.db
  
steps:
  - name: run_template
    template: basic_metadata_extraction
    dry_run: false
    
  - name: summarize
    summary: true
```

## Step 3: Run the Pipeline (1 min)

```bash
# Preview what will happen (dry run)
uv run paper-processor my-first-pipeline.yml --verbose --dry-run

# Run the actual pipeline
uv run paper-processor my-first-pipeline.yml --verbose
```

You should see output like:
```
[INFO] Loading workflow definition...
[INFO] Initializing database...
[INFO] Executing step 1: run_template
[SUCCESS] Template execution complete
[INFO] Executing step 2: summarize
...
```

## Step 4: Import Papers from BibTeX

Create `import-papers.yml`:

```yaml
general:
  db_path: papers.db

steps:
  - name: bibtex_import
    file: references.bib
    batch_size: 10

  - name: summarize
    summary: true
```

Run it:
```bash
uv run paper-processor import-papers.yml
```

## Step 5: Export Results

Add to your pipeline:

```yaml
steps:
  # ... previous steps ...
  
  - name: export
    format: bibtex
    output: processed_papers.bib
    filter: '{"year": {"$gte": 2020}}'
```

## Next Examples

### Extract Citation Networks
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
      continue_on_not_found: true
```

### Find Duplicates
```yaml
steps:
  - name: deduplication
    strategy: doi_title_year
```

### Extract Findings
```yaml
steps:
  - name: run_template
    template: extract_findings
```

## Common Commands

```bash
# View available steps
uv run paper-processor --help

# Check database info
uv run paper-processor info

# Clear database
uv run paper-processor --db papers.db --init --force

# Validate workflow
uv run paper-processor my-pipeline.yml --validate-only

# Resume from checkpoint
uv run paper-processor my-pipeline.yml --checkpoint step_name
```

## Using Python API

Instead of YAML, use Python:

```python
from paper_scanner.definition import Definition, BibtexSource

# Create pipeline
pipeline = (Definition("My Review")
    .bibtex_import("references.bib")
    .deduplication(strategy="doi_title_year")
    .export("bibtex", output="cleaned.bib")
)

# Run it
result = pipeline.run()

# Access results
print(f"Processed: {result['processed_count']} papers")
print(f"Duplicates: {result['duplicates_found']}")
```

## Troubleshooting

### "No such file or directory: references.bib"
Make sure your BibTeX file exists in the current directory or provide full path

### "ANTHROPIC_API_KEY not found"
Set it in `.env` file or environment:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Pipeline runs but produces no output
Check that input files contain valid data and your API key is correct

### Database is locked
```bash
# Delete old database
rm papers.db

# Re-run pipeline
uv run paper-processor my-pipeline.yml
```

## Next Steps

1. 📖 Read [Architecture Overview](../architecture/overview.md) to understand how it works
2. 🔍 Explore [all available steps](../steps/overview.md)
3. 📚 Check [API reference](../api/core.md) for Python usage
4. 🤔 Review [ADRs](../adr/index.md) to understand design decisions

## Need Help?

- Check logs: Add `--debug` flag
- See [Contributing Guide](../contributing/setup.md)
- Open an [issue on GitHub](https://github.com/your-org/paper-scanner/issues)
