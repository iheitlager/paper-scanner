# paper-scanner

m![Version](https://img.shields.io/badge/version-0.6.0-blue)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)

AI-powered literature review tool for analyzing academic research papers using LLM assistance.

## Overview

`paper-scanner` is a pre-alpha tool designed to streamline the analysis of academic research papers through an LLM-assisted pipeline. It automates the extraction and structuring of key information from PDFs, including paper metadata, research questions, methodology, findings, and innovation mechanisms using the CAMO framework (Context-Agency-Mechanism-Outcome).

## Features

- 🔍 **PDF Scanning**: Recursively scan directories for PDF files with metadata extraction
- 🤖 **LLM Integration**: Leverage Anthropic's Claude API for intelligent paper analysis
- 📊 **Structured Output**: JSONLines-based streaming pipeline for efficient batch processing
- 🔗 **CAMO Framework**: Extract and analyze innovation mechanisms using Context-Agency-Mechanism-Outcome patterns
- 🛠️ **Command-Line Tools**: Composable utilities for each step of the analysis pipeline
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

### Basic Usage

```bash
# Scan a folder for PDFs
file-scanner /path/to/pdfs -o pdfs_found.jsonl

# Process PDFs with Claude
uv run python -m paper_scanner.tools.file_processor \
  -i pdfs_found.jsonl \
  -o analyzed.jsonl \
  --api_key YOUR_ANTHROPIC_API_KEY

# Parse the analysis results
uv run python -m paper_scanner.tools.file_parser \
  -i analyzed.jsonl \
  -o parsed.jsonl

# Convert to CSV for review
uv run python -m paper_scanner.tools.file_reader \
  -i parsed.jsonl \
  -o results.csv
```

## Core Tools

- **file-scanner**: PDF discovery and metadata extraction
- **file-processor**: Claude API integration for paper analysis
- **file-parser**: Structured data extraction from Claude responses
- **file-merge**: JSONLines data merging and filtering with set operations
- **file-reader**: JSON to CSV conversion for report generation
- **file-timer**: Rate limiting utility for API throttling

## Development

### Requirements

- Python 3.11+
- `uv` package manager
- Anthropic API key (for paper processing)

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
make help          # Show all available targets
make install       # Install dependencies
make install-dev   # Install with dev dependencies
make test          # Run tests with coverage
make lint          # Lint code
make format        # Format and fix code
make type-check    # Run type checking
make clean         # Clean up artifacts
```

## Project Structure

```
paper-scanner/
├── src/paper_scanner/
│   ├── core/
│   │   └── advanced_section_parser.py    # Academic paper parsing logic
│   └── tools/
│       ├── file_scanner.py               # PDF discovery
│       ├── file_processor.py             # LLM processing
│       ├── file_parser.py                # Result parsing
│       ├── file_merge.py                 # Data merging
│       ├── file_reader.py                # CSV export
│       └── file_timer.py                 # Rate limiting
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

### Custom Prompts

You can provide custom system prompts to the file-processor tool:

```bash
file-processor -i input.jsonl -o output.jsonl --custom_prompt custom_prompt.txt
```

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
- [ ] Web UI for interactive analysis
- [ ] Export to additional formats (JSON Schema, RDF)
