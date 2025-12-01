# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-06-19

### Added

Initial pre-alpha release of paper-scanner, a tool for LLM-assisted analysis of academic research papers.

#### Core Tools

- **file-scanner** (`file_scanner.py`): Scans folders for PDF files and outputs JSONLines file with file metadata including size, timestamps, and relative paths. Supports recursive scanning and optional filtering.

- **file-processor** (`file_processor.py`): PDF to Claude processor that extracts text from PDF files and sends them to Claude API for analysis. Includes automatic retry logic for rate limiting and support for custom system prompts.

- **file-parser** (`file_parser.py`): Parses Claude.ai output containing academic paper analysis. Processes JSONLines input to structure and extract analyzed content using the AcademicPaperParser.

- **file-merge** (`file_merge.py`): JSONLines combiner that adds fields based on data dictionaries. Supports MERGE, INTERSECT, and EXCEPT set operations for combining and filtering data across JSONLines files.

- **file-reader** (`file_reader.py`): Transforms parsed JSON output into CSV format. Extracts CAMO (Context-Agency-Mechanism-Outcome) configurations and generates human-readable reports.

- **file-timer** (`file_timer.py`): Rate limiting utility that adds controlled delays between processing each line in a JSONLines file. Useful for managing API rate limits during batch processing.

#### Features

- JSONLines-based pipeline architecture for streaming data processing
- Integration with Anthropic Claude API for academic paper analysis
- CAMO framework (Context-Agency-Mechanism-Outcome) for structured research synthesis
- Flexible command-line interface with stdin/stdout support
- Batch PDF processing with metadata extraction
- Research paper analysis extraction including title, authors, methodology, results, vendors, and innovation mechanisms

### Technical Details

- Python 3.11+ required
- Dependencies: Anthropic SDK, PyPDF, Requests
- Development dependencies: pytest, pytest-cov, pytest-mock, ruff, mypy
- License: Apache-2.0
