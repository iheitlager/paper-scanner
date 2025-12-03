# paper-scanner

![Version](https://img.shields.io/badge/version-0.9.0-blue)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)

AI-powered literature review tool for analyzing academic research papers using LLM assistance.

## Overview

`paper-scanner` is a pre-alpha tool designed to streamline the analysis of academic research papers through an LLM-assisted pipeline. It automates the extraction and structuring of key information from PDFs, including bibliographic metadata, research questions, methodology, findings, and key concepts. Features a PostgreSQL-backed web interface for browsing, analyzing, and organizing research papers.

## Features

- 🔍 **PDF Scanning**: Recursively scan directories for PDF files with metadata extraction
- 🤖 **LLM Integration**: Leverage Anthropic's Claude API for intelligent paper analysis with structured extraction
- 📊 **Structured Output**: JSONLines-based streaming pipeline for efficient batch processing
- 🔬 **Paper Analysis**: Automated extraction of summaries, research questions, methodology, results, and key concepts
- 📚 **Bibliographic Metadata**: Extract and store titles, authors, DOI, citations, and publication details
- 🌐 **Web Interface**: PostgreSQL-backed web browser for viewing, searching, and managing papers
  - Multi-tab interface: PDF viewer, Analysis, Details, and Tags
  - Author/year header with DOI links
  - Bibliographic information display
  - Paper analysis with consistent styling (white titles, blue definitions, grey text)
- 🏷️ **Tagging System**: Organize papers with colon-separated tags and centralized tag lookup
- 🔗 **Deeplinking**: Generate shareable links to specific papers (e.g., `?paper=SmithA2025`)
- 📖 **Reference Extraction**: Extract and organize paper citations with optional Claude-powered bibliography parsing
  - Opt-in `--extract-references` flag for reference extraction during processing
  - Structured reference metadata: authors, year, title, DOI, URL, publication source
  - PostgreSQL-backed reference storage and citation relationships
  - References tab in web interface for browsing extracted citations
- ⚡ **Rate Limiting**: Built-in automatic retry logic and request throttling for API limits

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/iheitlager/paper-scanner.git
cd paper-scanner

# Install with uv (recommended)
uv sync

# Or install with development dependencies
uv sync --all-groups
```

### Basic Usage - CLI Pipeline

```bash
# Scan a folder for PDFs
$ file-scanner /path/to/pdfs -o pdfs_found.jsonl

# Process PDFs with Claude using the generic paper-processor
$ paper-processor \
  -i pdfs_found.jsonl \
  -o analyzed.jsonl \
  --config config.yml \
  -v

# Or use it in a pipeline with file-scanner
$ file-scanner /path/to/pdfs | paper-processor --config config.yml -q >| analyzed.jsonl

# Extract limited text from large PDFs (first 25000 chars)
$ paper-processor \
  -i pdfs_found.jsonl \
  -o analyzed.jsonl \
  --config config.yml \
  -c 25000 \
  --add-metadata

# Parse the analysis results
$ uv run python -m paper_scanner.tools.file_parser \
  -i analyzed.jsonl \
  -o parsed.jsonl

# Convert to CSV for review
$ uv run python -m paper_scanner.tools.file_reader \
  -i parsed.jsonl \
  -o results.csv
```

### Web Interface
# Start the web server (requires PostgreSQL database)
#### Web Interface Features

- **📄 PDF Tab**: View full paper PDFs with embedded viewer
- **🔬 Analysis Tab**: Read structured paper analysis (summary, research questions, methodology, results, concepts)
- **📋 Details Tab**: Browse bibliographic information (title, authors, DOI, citation, file metadata)
- **📖 References Tab**: View extracted references from the paper's bibliography with structured metadata
- **🏷️ Tags Tab**: Manage paper tags for organization and filtering
- **🔗 Share**: Generate deeplinks to share specific papers via URL
- **📄 PDF Tab**: View full paper PDFs with embedded viewer
- **🔬 Analysis Tab**: Read structured paper analysis (summary, research questions, methodology, results, concepts)
- **📋 Details Tab**: Browse bibliographic information (title, authors, DOI, citation, file metadata)
- **🏷️ Tags Tab**: Manage paper tags for organization and filtering
- **🔗 Share**: Generate deeplinks to share specific papers via URL

## Core Tools

- **file-scanner**: PDF discovery and metadata extraction with recursive directory scanning
- **paper-processor**: Generic LLM processor for enriching JSONLines records (replaces legacy file-processor)
  - Multiple Claude model support with configurable token limits
  - Native PDF documents (base64-encoded) or text extraction mode with character limits
  - YAML configuration with CLI override precedence
  - Flexible data sources: PDF files, record content, custom fields
  - Metadata enrichment: timing, actual token usage, model used, prompt file
  - Skip already-processed records, verbose/quiet logging modes
  - Statistics output with token tracking and averages
  - Rate limit retry logic with automatic backoff
- **paper-details**: Bibliographic metadata extraction from PDFs using Claude
- **file-parser**: Structured data extraction from Claude responses
- **file-merge**: JSONLines data merging and filtering with set operations
- **file-reader**: JSON to CSV conversion for report generation
- **file-timer**: Rate limiting utility for API throttling
- **output-viewer**: Web server for browsing analyzed papers

## Paper-Processor Configuration

The generic `paper-processor` tool is highly configurable via YAML files:

```yaml
# config.yml - Example configuration
model: claude-sonnet-4-5-20250929           # Claude model to use
max_tokens: 2048                             # Output token limit
text_source: pdf                             # 'pdf', 'content', or field name
max_chars: null                              # Limit PDF text extraction (null for native PDF)
prompt_file: src/prompts/paper-metadata.md   # Custom system prompt
output_key: processed                        # Key to store results
add_metadata: true                           # Include timing/token metadata
skip_existing: false                         # Skip already-processed records
verbose: false                               # Detailed logging
```

**Usage Examples:**

```bash
# Basic processing with YAML config
paper-processor -i input.jsonl -o output.jsonl --config config.yml

# Verbose mode showing per-record details and token usage
paper-processor -i input.jsonl -o output.jsonl --config config.yml -v

# Quiet mode (no statistics output)
paper-processor -i input.jsonl -o output.jsonl --config config.yml -q

# Extract first 10000 chars from PDFs instead of sending native documents
paper-processor -i input.jsonl -o output.jsonl --config config.yml -c 10000

# Skip already-processed records
paper-processor -i input.jsonl -o output.jsonl --config config.yml --skip-existing

# Generate YAML definition from current config
paper-processor --config config.yml -x template.yml

# Override config with CLI flags
paper-processor -i input.jsonl -o output.jsonl --config config.yml --model claude-opus-4-20250514 --max-tokens 4096
```

**Available Models:**
- `claude-opus-4-20250514` (16k output tokens) - Most capable
- `claude-sonnet-4-5-20250929` (16k output tokens) - Best balance (default)
- `claude-haiku-4-5-20251001` (16k output tokens) - Most economical
- `claude-3-5-sonnet-20241022` (8k output tokens) - Previous generation
- `claude-3-5-haiku-20241022` (8k output tokens) - Previous generation
- `claude-3-opus-20240229` (4k output tokens) - Legacy

## Database

The web interface requires a PostgreSQL database. Configure via environment variables:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/pdfdb"
export PDF_BASE_DIR="/path/to/pdf/files"
```

Database schema is automatically initialized on first run.

## Development

### Requirements

- Python 3.11+
- `uv` package manager
- Anthropic API key (for paper processing)
- PostgreSQL (for web interface)

### Setting Up Development Environment

```bash
# Install all dependencies including dev tools
uv sync --all-groups

# Run tests
make test

# Run linting
make lint

# Format code
make format

# Type checking
make type-check
```

### Available Make Targets

```bash
# Development & Code Quality
make help          # Show all available targets
make check         # Verify required tooling is installed
make version       # Show project version
make env           # Create and setup development virtual environment
make sync          # Sync dependencies
make lock          # Lock dependencies into uv.lock
make test          # Run tests with coverage
make lint          # Lint code with ruff
make format        # Format code with ruff
make type-check    # Run type checks with mypy
make clean         # Clean up artifacts and caches

# Docker Commands
make start         # Start Colima (Docker runtime)
make stop          # Stop Colima and cleanup
make docker-up     # Start services with Docker Compose
make docker-down   # Stop Docker containers
make docker-logs   # View Docker logs
make docker-again  # Rebuild from cache and restart
make docker-rebuild # Rebuild web container
make docker-fresh  # Fresh database initialization
make cleanup       # Clean up all Docker resources
```

## Project Structure

```
paper-scanner/
├── src/paper_scanner/
│   ├── core/
│   │   └── advanced_section_parser.py    # Academic paper parsing logic
│   ├── tools/
│   │   ├── file_scanner.py               # PDF discovery
│   │   ├── paper_details.py              # Bibliographic extraction
│   │   ├── file_processor.py             # LLM processing
│   │   ├── file_parser.py                # Result parsing
│   │   ├── file_merge.py                 # Data merging
│   │   ├── file_reader.py                # CSV export
│   │   └── file_timer.py                 # Rate limiting
│   └── web/
│       ├── server.py                     # Flask web server
│       ├── exceptions.py                 # Error handling
│       ├── http_handlers.py              # HTTP route handlers
│       ├── templates/
│       │   └── index.html                # Web UI
│       └── static/
│           ├── style.css                 # Styling
│           └── script.js                 # Client logic
├── tests/
│   └── unit/
│       └── test_advanced_section_parser.py
├── pyproject.toml                        # Project configuration
├── Makefile                              # Development tasks
└── README.md                             # This file
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required for processing)
- `DATABASE_URL`: PostgreSQL connection string (required for web interface, default: `postgresql://pdfuser:pdfpass@localhost:5432/pdfdb`)
- `PDF_BASE_DIR`: Base directory for PDF files (default: `/Users/iheitlager/wc/papers`)
- `PORT`: Web server port (default: `8080`)
- `ENV`: Environment (default: `local`, set to `docker` for container deployment)

### Custom Prompts

You can provide custom system prompts to the file-processor tool:

```bash
file-processor -i input.jsonl -o output.jsonl --custom_prompt custom_prompt.txt
```

## Deployment

### Docker

A `docker-compose.yml` and `Dockerfile` are provided for containerized deployment:

```bash
docker-compose up
```

This starts both the web server and PostgreSQL database.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a complete history of changes

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

Ilja Heitlager (iheitlager@schubergphilis.com)

## Contributing

Contributions are welcome! This project is in pre-alpha, so expect breaking changes.

## Roadmap

- [ ] Enhanced paper section detection
- [ ] Support for additional document formats
- [ ] Caching layer for API responses
- [x] Web UI for interactive analysis (completed in v0.3+)
- [ ] Export to additional formats (JSON Schema, RDF)
- [ ] Full-text search across papers
- [ ] Paper recommendation based on analysis

