# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-12-02

### Added

- **Document Tagging System**: New tagging feature for organizing and categorizing PDF documents
  - Colon-separated tag storage in database with lookup table for unique tags
  - New "🏷️ Tags" tab in web interface for dedicated tag management
  - Tag display in file list sidebar and details view with visual chip styling
  - RESTful API endpoints for tag management (`GET /api/tags`, `PUT /api/file_tags/<file_name>`)
  - Backend synchronization of tags to centralized lookup table
  - Responsive UI with save/clear functionality and inline tag editing

## [0.3.0] - 2025-12-02

### Added

- **Web-based Output Viewer**: New Flask-based web server for browsing and viewing parsed analysis results
  - Integrated from [spike/002_browser](tests/spikes/002_browser/README.md) with production-ready improvements
  - Two-tab interface: PDF viewer and file metadata/details
  - Search functionality for filtering records across JSONLines output
  - Responsive dark-themed UI with sidebar navigation
  - RESTful API endpoints for data retrieval and querying

- **output-viewer CLI Tool**: New command-line entry point for starting the output viewer server
  - Arguments: `-i/--input` (JSONLines file path), `-p/--port` (server port), `-H/--host` (bind host), `-d/--debug` (debug mode)
  - Automatic data loading from JSONLines files with error recovery
  - Supports searching and filtering parsed paper analysis records

- **Server Dependencies**: Added Flask, Flask-CORS, and psycopg2 for web server and database operations

### Technical Details

- Integration from spike/002_browser branch with typed Python backend and improved error handling
- Flask 3.0.0+ with CORS support for cross-origin requests
- PostgreSQL support via psycopg2 for future database integration
- Custom exception hierarchy for better error handling in server operations

## [0.2.1] - 2025-12-01

### Changed

- Refactored `file-parser` tool with improved error handling and robustness:
  - Changed from generic exception handling to specific `json.JSONDecodeError`
  - Error handling now continues processing remaining lines instead of stopping on first error
  - Enhanced logging with per-line error details and progress metrics
  - Guaranteed file handle closure with try-finally block

### Added

- Added `verbose` flag (`-v`) to `file-parser` for detailed debugging output
- Verbose mode displays: line numbers, raw line content (first 100 chars), item keys on errors
- Progress summary showing count of successfully parsed lines vs total lines processed
- Better help text with example usage in `file-parser` command
- Added `python-dotenv` support to `file-parser` for loading environment variables

### Fixed

- `file-parser` now handles KeyboardInterrupt (Ctrl+C) gracefully with exit code 130
- Improved error messages with specific context about what failed and where
- Better resource management preventing file handle leaks

## [0.2.0] - 2025-12-01

### Added

- Comprehensive versioning strategy with semantic versioning guidelines
- Branch naming conventions for features (`feat/`) and fixes (`fix/`)
- Detailed release workflow documentation
- CLAUDE.md development guidelines with versioning instructions
- Version management guidelines for maintaining CHANGELOG and version number

## [0.1.1] - 2025-12-01

### Changed

- Migrated project configuration to modern `pyproject.toml` format (replacing setup.py)
- Adopted `uv` as the package manager for dependency management and development workflows
- Reorganized project structure to align with Python packaging best practices
- Improved Makefile with cleaner targets for common development tasks
- Fixed academic paper parser to handle multiple markdown formatting variations

### Fixed

- `AcademicPaperParser.extract_paper_header()` now correctly handles multiple markdown formats:
  - Colon inside bold: `**TITLE:** value`
  - Colon outside bold: `**TITLE**: value`
  - Plain text: `TITLE: value`
- `AcademicPaperParser.parse_sections()` improved to properly distinguish between main sections (`##`) and subsections (`###`)
- All unit tests for paper analysis now passing

### Technical Details

- `uv` now handles all dependency management
- Development environment configured via `pyproject.toml` with dependency groups
- Python 3.11+ requirement confirmed and documented

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
