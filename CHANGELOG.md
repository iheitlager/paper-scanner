# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-12-11

### Added

- **Unified Step-Based Processing Pipeline**: Generic, composable step framework replacing single-use processors
  - Unified command: `paper-processor` for flexible pipeline composition
  - Built-in steps: `bibtex_import`, `categorization`, `checkpoint`, `deduplication`, `echo`, `export`, `halt`, `keyword_screening`, `semantic_screening`, `summarize`
  - Step YAML configuration with chainable processing logic
  - New `PaperProcessor` class with step registration and execution engine
  - Step-specific documentation in [`docs/steps/`](docs/README.md) directory

- **Modular Step Architecture**: Each step is independently configurable and testable
  - Input/output contracts defined per step for predictable data flow
  - Extensible step registry for easy addition of custom processing steps
  - Comprehensive error handling and validation within step execution

- **Enhanced CLI Interface**: Improved command structure with step-based processing
  - Backward compatibility maintained with legacy single-purpose CLI tools
  - New step parameters configuration via YAML or CLI flags
  - Integrated step help and documentation

### Changed

- Processing architecture evolved from single-purpose tools to flexible step-based system
- Configuration management now unified across all processing steps
- Improved code organization with dedicated step implementations

### Technical Details

- `PaperProcessor` in `core/processor.py`: step registry, execution engine, validation logic
- Step base class in `steps/base.py`: abstract interface for all step implementations
- Individual step modules: `bibtex_import.py`, `categorization.py`, `checkpoint.py`, etc.
- Configuration dataclass evolved to support step-specific parameters

## [1.0.0] - 2025-12-04

### Added

- **Vector Embedding Support** (In Development)
  - Foundation for semantic search capabilities
  - Integration layer for embedding models

## [0.9.0] - 2025-12-03

### Added

- **Small Language Model (SLM) Support via Ollama**: Local LLM processing with Phi, TinyLlama, Llama2
  - Dual handler architecture for both Claude API and local models
  - No API key required for local inference; works offline
  - Intelligent model routing with automatic handler selection
  - Character limit enforcement (`--max-chars`) for SLM text extraction
  - Token usage tracking for both Claude and SLM models
  - Same CLI/YAML config interface for both model types
  - Enhanced `--list-models` with both Claude and SLM categories

### Technical Details

- Added `SLM_MODELS` constant (Phi/TinyLlama: 2048 tokens, Llama2: 4096 tokens)
- New `_call_ollama()` method: subprocess-based execution with 300s timeout
- Optional Anthropic client (only required for Claude models)
- Token estimation for SLM models (chars ÷ 4 approximation)
- Comprehensive feature documentation in `docs/SLM_FEATURE.md` and `docs/SLM_QUICK_REFERENCE.md`

### Changed

- **Refactored Handler System to Pluggable Registry Pattern**
  - Created abstract `LLMHandler` base class in `handlers/base.py` with registry mechanism
  - Extracted Claude handler implementation to `handlers/anthropic.py` (`ClaudeHandler` class)
  - Extracted Ollama handler implementation to `handlers/ollama.py` (`OllamaHandler` class)
  - Each handler class maintains its own `MODELS` dictionary
  - Model-to-handler routing via dynamic registry lookup instead of hardcoded conditionals
  - Moved JSON response parsing to shared utility in base handler module
  - Decoupled handler logic from paper_processor, improving maintainability and testability
  - Paper processor now uses `initialize_handlers()` and `get_handler()` for handler setup
  - CLI parser dynamically generates model choices from registered handlers



## [0.8.0] - 2025-12-03

### Added

- **Generic paper-processor CLI Tool**: Flexible, configurable LLM processor for enriching JSONLines records
  - Support for multiple Claude models (Opus 4, Sonnet 4.5, Haiku 4.5, and legacy models) with configurable output token limits
  - Two PDF processing modes: native PDF documents (base64-encoded to Claude) or text extraction with character limits (`-c/--max-chars`)
  - YAML configuration support with intelligent CLI override precedence
  - Flexible input sources: PDF files, record content field, or any custom record field
  - Add or replace enrichment modes for modifying JSONLines records
  - Optional processing metadata: timing, actual token usage from API, model name, prompt file path
  - Skip already-processed records with `--skip-existing` flag
  - Advanced logging modes: verbose (`-v`) with per-record details or quiet (`-q`) for silent operation
  - Comprehensive statistics output: success/error/skipped counts, actual token usage tracking, per-record averages
  - YAML definition generation (`-x/--definition`) to export configs as reproducible templates
  - External prompt file support for custom system instructions
  - Rate limit handling with automatic retry logic (5 retries + 61s exponential backoff)
  - Graceful error handling and recovery during batch processing

- **file-scanner SIGPIPE Handling**: Fixed broken pipe error when piping to commands like `first`
  - Signal handler gracefully handles pipe closure without throwing errors

### Changed

- Boolean CLI flags (`--add-metadata`, `--skip-existing`, `-v/--verbose`, `-q/--quiet`) now properly respect YAML config values
  - YAML configuration takes precedence unless explicitly overridden on command line
  - Enables cleaner config-driven operation without CLI flag repetition

### Technical Details

- ProcessorConfig dataclass: 19 configuration fields for flexible processor operation
- PDF text extraction via pypdf with character limit support and page-by-page efficiency
- Token tracking from Anthropic API `response.usage` object for accurate cost calculation
- Sys.argv inspection for intelligent YAML/CLI config merging
- Cross-platform color support via colorama in verbose output and statistics

## [0.7.0] - 2025-12-02

### Added

- **References Feature**: Extract and manage paper citations with PostgreSQL backend
  - New `file-processor-references` CLI tool for dedicated reference extraction as separate pipeline stage
  - Accepts JSONLines with pre-analyzed papers via stdin or `-i/--input` argument
  - Claude Haiku model for cost-efficient reference extraction (4x cheaper than Sonnet)
  - Immediate stdout flush after each record for streaming reliability
  - Three new database tables: `references`, `citation_edges`, `citation_metadata`
  - Reference data persisted alongside paper analysis in JSONLines pipeline
  - Graceful error handling: reference extraction failures log warning and continue
  - New References tab in web interface displaying extracted citations
  - Reference metadata: type, authors, year, title, DOI, URL, and publication source
  - Tee-based checkpointing in `run.sh` for safe intermediate analysis output
  - Foundation for future citation network analysis and paper deduplication

### Changed

- Reference extraction removed from `file-processor` tool (now separate `file-processor-references` stage)
- Pipeline architecture refactored: analysis → tee checkpoint → references extraction as optional stage
- Extract-references prompt simplified and optimized for Haiku model

### Removed

- `--extract-references` flag from `file-processor` CLI (use separate tool instead)

## [0.6.3] - 2025-12-02

### Added

- **Year Overview Feature**: New dashboard view showing publication timeline analysis
  - Year-based grouping and filtering of papers in the collection
  - Visual distribution of papers by publication year
  - API endpoint `/api/year-overview` for fetching aggregated yearly statistics
  - Interactive year selection for quick filtering by publication period
  - Helps researchers understand research trends across different time periods

## [0.6.2] - 2025-12-03

### Added

- **DatabaseManager Extraction**: Isolated database layer into `web/database.py` with connection pooling and retry logic
- **Configuration System**: Multi-source config management with CLI args, environment variables, and .env file support
  - Config class with LRU caching, `get_config()` factory function
  - Precedence: CLI args > environment variables > .env > defaults
- **Flask Application Factory**: `create_app(config)` factory for testability and WSGI compatibility
- **Test Coverage**: 25 config tests, 30 exception tests, 18 HTTP handler tests (99% web coverage)

### Changed

- DatabaseManager separated from Flask server logic
- Configuration centralized and environment-aware
- Error handling standardized with custom exception hierarchy
- Flask application more modular and testable

### Fixed

- Test timing metadata assertions in `test_paper_details.py`

## [0.6.1] - 2025-12-02

### Added

- **Dedicated Analysis Tab**: Separated analysis display into its own tab in the web interface for better organization
  - Analysis now displayed in independent 🔬 Analysis tab alongside PDF, Details, and Tags tabs
  - Cleaner Details tab focused on bibliographic information and file metadata
- **Tab Persistence**: Selected tab state saved to browser localStorage
  - Active tab automatically restored when returning to the application
  - Persists across browser sessions for improved user experience
- **Deeplinking Support**: Share direct links to specific papers
  - 🔗 Share button in toolbar generates shareable URL with paper reference
  - Uses citekey if available, falls back to file_name for URL parameter
  - Deeplinking via `?paper=<citekey_or_filename>` auto-loads and selects specified paper
  - Smooth scrolling to paper in sidebar when accessed via deeplink

### Changed

- **Improved Paper Content Styling**: Enhanced visual hierarchy with white section titles, blue accent for definitions, and grey body text
- **Enhanced Toolbar Header**: Redesigned metadata display showing author/year above title, with title in blue accent color and DOI link when available

## [0.6.0] - 2025-12-02

### Added

- **Paper Analysis Storage and Display**:
  - Database schema extended with `analysis` JSONB column to store complete paper analysis
  - Server automatically extracts and stores analysis data from incoming records
  - Web interface displays analysis including summary, research questions, methodology, results, and key concepts
  - Styled analysis sections in details tab with expandable subsections
  - Analysis data fully integrated with bibliographic details

## [0.5.0] - 2025-12-02

### Added

- **paper-details CLI Tool**: New command-line tool for extracting bibliographic metadata from academic papers
  - Reads JSONLines records with `file_path` field pointing to PDF files
  - Extracts text from PDFs and sends to Claude API for bibliographic detail extraction
  - Generates structured JSON with: APA citation, citekey (FirstAuthorLastNameYear format), DOI, authors array, year, title, journal, volume, issue, pages, and publisher
  - Automatic rate-limit retry logic with configurable API key and model selection
  - Adds `title-details` field to each record with extracted bibliographic information
  - Optional timing metadata for performance monitoring

- **Web Interface Enhancements for Bibliographic Details**:
  - Sidebar displays citekey (or filename if citekey not available) for quick reference
  - Header shows paper title with DOI link when available (opens DOI URL in new tab)
  - Details tab displays full bibliographic information including authors, journal, volume, pages, and APA citation
  - Seamless integration with extracted paper metadata from paper-details tool

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
