# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.6.0] - 2026-01-03

### Added

- **RIS File Import Step** (`ris_import`): Support for importing papers from RIS format files
  - Compatible with ProQuest and other RIS exporters
  - Automatic DOI extraction and paper metadata normalization
  - Bidirectional journal name harmonization using ISO4 abbreviations

- **Journal Screening Step** (`journal_screening`): Quality-based journal filtering
  - Configurable journal tiers (A, B, C, Other) with inclusive/exclusive lists
  - Automatic journal name harmonization to handle variant names
  - ISO4 abbreviation support for journal identification
  - Marks papers with excluded journals as EXCLUDED_JOURNAL

- **Step Enable/Disable Feature**: Control pipeline execution dynamically
  - Configurable via YAML with `enabled: true/false` for each step
  - Allows flexible pipeline composition without code changes
  - Maintains checkpoint compatibility

### Changed

- **Normalization System**: Complete refactor and standardization
  - Extracted normalization logic into centralized `src/paper_scanner/core/normalization.py`
  - Applied consistently across bibtex_import, ris_import, and all screening steps
  - Removed duplicate normalization code throughout the codebase
  - Improved whitespace handling and special character processing

- **BibTeX Export**: Refactored with improved organization and error handling
  - Better handling of papers with missing required fields
  - Improved special character escaping and ampersand normalization
  - Cleaner code structure with better separation of concerns

- **Cite Key Generation**: Refactored for better maintainability
  - Moved DOI-based and collision-detection logic to dedicated `cite_key.py`
  - Improved handling of cite key collisions in deduplication
  - Better support for papers with varying metadata availability

- **Paper Model**: Enhanced database schema and model
  - Improved tracking of screening decision origins
  - Better support for journal metadata and ISO4 abbreviations

### Fixed

- **Unit Tests**: Comprehensive test suite updates and fixes
  - Removed backward compatibility functions (fully migrated to new APIs)
  - Fixed all remaining warnings and test issues
  - Updated spike tests for normalization and journal screening

- **Export Step**: Bug fixes for edge cases
  - Proper handling of papers with incomplete metadata
  - Improved robustness in BibTeX generation
  - Fixed issues with special character handling

- **Rocchio Screening**: Improved algorithm implementation
  - Fixed edge cases in centroid calculation
  - Better handling of uncertain classifications
  - Enhanced documentation and examples

### Removed

- **Backward Compatibility Functions**: Deprecated old normalization APIs
  - Fully migrated to centralized normalization system
  - Cleaned up legacy code paths

## [3.5.0] - 2025-12-30

### Added

- **EXCLUDED_INCOMPLETE Screening Decision**: New decision type for papers with incomplete metadata
  - Validates title, abstract, and keywords completeness as first-pass screening
  - Papers failing validation are marked with EXCLUDED_INCOMPLETE decision
  - Prevents downstream processing of papers with insufficient metadata
  - Updated `Paper.is_excluded` property to recognize EXCLUDED_INCOMPLETE

- **Rocchio Screening Step** (`rocchio_screening`): Adaptive semantic classification using Rocchio algorithm
  - Persistent centroid-based decision boundaries that evolve as papers are labeled
  - Bootstraps from keyword_screening results for initial seed labels
  - Extended to classify on title, abstract, and keywords for richer semantic features
  - Configurable Rocchio weights and accept/reject thresholds
  - Routes papers to ACCEPT, REJECT, or UNCERTAIN decisions
  - State persists in executor.step_state between steps within a session

### Changed

- **BibTeX Import/Export**: Improved handling of special characters
  - Normalize ampersands in imported papers: convert `\&` and `&amp;` to regular `&`
  - Applied to title, abstract, journal, booktitle, and publisher fields
  - Properly escape ampersands when exporting to BibTeX format (`&` → `\&`)
  - Prevent double-escaping of already-escaped ampersands

- **Abstract Processing**: Enhanced whitespace normalization
  - Collapse multi-line abstracts with newlines, tabs, and multiple spaces to single line
  - Improve readability and consistency of abstract text

### Fixed

### Removed

## [3.4.1] - 2025-12-30

### Added

- **Metadata Screening Step**: New screening step for attribute-based paper filtering
  - Implements tri-state logic: hard INCLUDE, hard EXCLUDE, OMITTED
  - Configurable via YAML with support for multiple filter fields (language, paper_type, quality_tier)
  - Supports NOT operator in both string format (`"NOT: en"`) and dict format (`{"NOT": "en"}`)
  - Outputs MetadataScreening model with language, paper_type, quality_tier, peer review status
  - Automatically updates paper.screening.final_decision when papers are excluded

### Changed

- **Keyword Screening Step**: Completely redesigned with new functionality
  - Added **implicit study type detection** with regex patterns (editorial, empirical, literature review, conceptual)
  - Implemented sophisticated pattern matching for:
    - Quantitative empirical research (14 patterns: sample size, ANOVA, p-values, etc.)
    - Qualitative empirical research (15 patterns: interviews, case studies, surveys, etc.)
    - Research methods (8 patterns: experimental design, longitudinal studies, etc.)
  - Added **wildcard keyword matching** (exact, prefix*, *suffix, *both*)
  - Changed configuration structure to support nested inclusion/exclusion keywords with study type filtering
  - Implemented three screening modes:
    - `inclusion_required`: Must pass both inclusion gate and avoid exclusions
    - `exclusion_only`: Filter exclusions only, include everything else
    - `soft`: Keywords for ranking only, never exclude
  - Empirical-first priority order: when papers mix empirical + literature review, classified as empirical
  - Minimum 2 pattern threshold for empirical classification (prevents false positives)
  - Comprehensive unit test suite (43 tests) covering KeywordMatcher, StudyTypeDetector, KeywordScreener, and step execution

- **Screening Pipeline Architecture**: Refactored for better evaluation and snowballing support
  - Enhanced `Deduplication` step with improved duplicate detection and resolution
  - Refactored `Semantic Screening` step for consistency with metadata/keyword screening outputs
  - Updated `Keyword Screening` step to support LLM-based evaluation mode
  - Improved screening result model to track evaluation confidence and reasoning
  - Papers now maintain explicit `is_duplicate` property for simpler exclusion checking

- **REPL Enhancements**: Improved interactive viewer and show command
  - Better handling of duplicate papers in detail view
  - Added `apa_formatted` property for rich console output (italicized journal names)
  - Fixed console viewer to display strikethrough formatting for excluded papers
  - Improved filtering and search in paginated view

- **Database/Model Updates**: 
  - Added `is_duplicate` property to Paper model for cleaner duplicate checking
  - Split APA citation formatting: `apa_formatted` (rich text) vs `apa` (plain text)
  - Enhanced screening reason tracking across metadata, keyword, and semantic phases

- **Histogram report**
  - Simple histogram showing the iteration / year distribution of papers

### Fixed

- Suppressed pypdf debug output ("Overwriting cache for..." messages) by wrapping PDF operations with stderr context manager
- Fixed Citations step `forward_execute()` method signature mismatch causing missing positional argument error
- Fixed OpenAlex handler NoneType comparison error by adding null check for `_extract_source_key()` when extracting cited_by citations
- Fixed `datetime.utcnow()` deprecation warning by using timezone-aware `datetime.now(timezone.utc)` instead
- Removed `debug` and `verbose` parameters from Fetcher class for cleaner error handling
  - Fetcher now gracefully handles handler exceptions by trying fallback handlers instead of propagating errors
  - Updated error handling in `fetch_paper()` and `fetch_pdf()` methods to continue on handler failures
- Fixed unit test coverage for deduplication, keyword screening, and semantic screening steps
- Corrected duplicate paper filtering logic in console viewer
- Fixed empty database handling in REPL show command
- Resolved issues with screening decision propagation through pipeline

## [3.4.0] - 2025-12-25

### Added

- **Citation Iteration Feature**: Enhanced citations step to support iterative paper discovery
  - Automatically fetches citations from discovered papers to build expanded bibliography
  - Configurable iteration depth and limits to prevent exponential growth
  - Backward and forward citation fetching with duplicate detection
- **Documentation Infrastructure**: MkDocs and ReadTheDocs integration
  - Documentation now built with MkDocs (Material theme) and deployed to ReadTheDocs
  - Configuration in `mkdocs.yml` at project root, deployed to https://paper-scanner.readthedocs.io
  - `.readthedocs.yml` updated with explicit MkDocs configuration for compliance with ReadTheDocs deprecation policy
  - Auto-generated sidebar includes all step documentation from `docs/steps/`
- **Controller Feature**: New controller system for managing pipeline workflows
  - interactive switch setting for `verbose`, `debug`, `timings`, `dry-run`
  - `reset` option to start new in the interactive session
- **Paper APA Citation Property**: New `apa` property on Paper model for formatted APA-style citations
  - Automatically formats: authors (with "et al." for >3), year, title, journal, volume, issue, pages, DOI
- **REPL Show Command** (`show`, `v`): Interactive paginated viewer for database papers
  - Displays up to 10 papers per page with APA-formatted citations
  - allow copy of paper to `json`, `bibtex`, `apa` or only `doi`
- **JSON Viewer Feature**: Interactive JSON viewer for detailed paper analysis in console viewer
  - Search functionality with bracket escaping for special characters
  - Copy to clipboard support (macOS via pbcopy)

### Fixed

- **Fetcher Return Value Unpacking**: Fixed 3-tuple unpacking in `citations.py` and `retrieve_metadata.py`
  - `fetcher.fetch_paper()` now correctly unpacks `(paper, cache_hit, handler)` instead of 2-tuple
  - Updated all test mocks to use correct 3-tuple return format


## [3.3.0] - 2025-12-24

### Added

- **ManualHandler** (`manual`): Fourth citation handler for local cache of user-curated papers
  - Cache-only handler (no API calls) for papers from local bibtex files
  - Bibtex parser supporting custom fields: `cites`, `citedby`, `studytype`, `lastchecked`
  - Validates required fields: title, abstract, keywords (skips invalid entries with logging)
  - Automatic `citedbycount` calculation from `citedby` field if not provided
  - Citation objects created with `extraction_method="manual"` and `confidence=1.0`
  - CLI commands: `paper-processor cache manual load <file.bib>` and `paper-processor cache manual clear` to preload the cache
  - Comprehensive unit tests covering bibtex parsing, cache storage/retrieval, citation creation

- **JSONCache Expiration Support**: Enhanced `JSONFileCache` with configurable time-to-live (TTL)
  - Default TTL of 30 days for cached API responses
  - Support for custom TTL values (int days or timedelta)
  - Special TTL values: `-1` (never expire, default for `get()`), `0` (never expire), `None` (use default)
  - Automatic cache file deletion when expired

- **404 Not Found Caching**: Cache 404 responses to reduce redundant API calls
  - Supports TTL expiration for cache invalidation
  - Works across all API handlers (Crossref, OpenAlex, Semantic Scholar)

### Changed

- Fixed bracket parsing in paper metadata extraction

## [3.2.1] - 2025-12-23

### Added

- **Fix Cite Keys Step** (`fix_cite_keys`): Standardize citation keys across primary papers
  - Regenerates citation keys in `LastnameYear` format from first author and publication year
  - Automatic collision resolution using character suffixes (a, b, c, ..., aa, ab, ...)
- **DB CLI Task** (`db clear`): removes all records from all tables

### Changed

- Fileloader paths in database for clear reference and tracking, including sparse `exclude_none` model dumps

## [3.2.0] - 2025-12-22

### Added

- **PDF Cache Loader CLI Task** (`cache load`): Pre-fill PDF cache from local folder indexed by DOI
  - New subcommand: `paper-processor cache load <folder>`
  - Scans PDFs, extracts DOI using FileReader, and caches without database operations
  - Supports dry-run mode and verbose progress reporting


## [3.1.0] - 2025-12-22

### Added

- **PostgreSQL Database Loader**: New `upload_database` step for persisting papers to PostgreSQL
  - Bulk paper upload with transaction management
  - Configurable conflict resolution strategies: `skip`, `update`, `raise`
- **Database Abstraction Layer** (`src/paper_scanner/io/sql.py`):
  - `DatabaseConnectionPool`: Connection pooling with context managers
  - `PaperToRowConverter`: Bidirectional conversion between Pydantic `Paper` model and SQL rows
  - `PaperUploader`: Bulk insert/upsert with conflict handling
  - `DOIDuplicateHandler`: DOI-based duplicate detection utilities
- **PostgreSQL Schema Alignment** (v3.1.0):
  - Updated `papers` table schema aligned with Pydantic `Paper` model
  - UUID `id` column (Python identifier) + auto-increment `db_id` (PK)
  - Global unique `cite_key` constraint
  - JSONB columns for complex objects: `authors`, `discovery`, `screening`, `pdf_info`, `conceptual_analysis`
  - TEXT arrays for `keywords`, `topics`
  - Full-text search indexes on title and abstract
  - Multi-stage `paper_screening` table for Discovery/Screening workflow
- **Database CLI Task** (`db` command):
  - New `paper-processor db stats` command for database statistics overview
  - Shows record counts for papers and citations tables
  - Displays additional metrics: year range, validated papers, screened papers
  - Supports custom database URL via `--database-url` flag
  - Formatted Rich table output
- **Enhanced README**: Added PostgreSQL integration features to documentation



## [3.0.0] - 2025-12-22

### Added

- **Step Navigation API**: New properties and methods for REPL/CLI convenience:
  - `has_steps`: Property checking if definition has any steps
  - `has_next_step`: Property checking if there's a next step to execute
  - `step_progress`: Property returning `(current_index, total_steps)` tuple
  - `describe_next_step()`: Returns dict with step details (name, description, is_template, etc.)
  - `execute_next_step()`: Executes current step and advances index
- **Progress callbacks for run_all()**: `on_step_start` and `on_step_end` callbacks enable UI progress feedback without reimplementing execution loops
  - `on_step_start(step_index, step_config, total_steps)`: Called before each step
  - `on_step_end(step_index, step_config, result)`: Called after each step with result
  - Keeps UI concerns separate from executor logic
- **Unified StepExecutor**: New core execution engine (`src/paper_scanner/cli/executor.py`) that harmonizes workflow execution and interactive REPL modes
  - Definition loading with early template validation
  - Template support (v1: static step sequences, no parameters or nesting)
  - Session state management (database, results, execution history)
  - Checkpoint management (local file-based, explicit control)
  - Single-step and batch execution modes
  - Comprehensive statistics and timing collection
  - Full inventory of available steps and templates
  - **Self-contained step discovery**: Integrated `LazyStepRegistry` for lazy-loading steps on demand without external dependencies
  - **Built-in `get_step()` method**: No longer requires external `get_step_func` callback
- **HaltException handling**: StepExecutor properly catches `HaltException` from halt steps
  - Returns `status: halted` (distinct from `status: error`)
  - Preserves custom halt messages in result
  - Stops `run_all()` gracefully without counting as failure
- **RunTemplateStep builtin**: New `run-template` step for applying predefined template sequences within pipelines
  - Enables mid-pipeline template application (e.g., after citations)
  - Recursive template expansion for sophisticated reuse patterns
  - v1: Static templates only (parameters and nesting planned for future versions)
- **Executor Documentation**: 
  - `docs/executor/explanation.md`: Architecture, three-level config model, template system, checkpoint design
  - `docs/executor/class.md`: Complete API reference with all methods, parameters, return values, and usage examples
  - `docs/executor/main_entry_example.py`: Example implementations (batch mode, single-step mode, template usage)
- **Example Definition**: `src/definitions/supplier_innovation_review.yml` - Full multi-phase pipeline demonstrating templates, checkpoints, and citation expansion
- **Spike tests**: `tests/spikes/011_step_executor/` demonstrating executor patterns
  - `07_halt_test.py`: HaltException handling tests (echo/halt/echo pattern)
- **Unit tests for HaltException**: 6 new tests in `test_executor.py` covering halt behavior
- **Enhanced step messaging**: REPL displays richer step information from `describe_next_step()` in all output modes
  - Normal mode: Shows step description with type indicator `(builtin: step_name)` or `(template: name)`
  - Verbose mode: Shows full step description with detailed type information
  - Batch mode: Each step displays description with step counter `[n/total]`
  - `get_session_state()` now includes current step details: name, description, step_text, is_template, template_name

### Changed

- **Major Breaking Change**: Steps now use new three-level configuration model (general_config, step_config, runtime flags) replacing simpler config patterns
- **Step Registry**: Added `run-template` to `STEP_REGISTRY_PATHS` in `src/paper_scanner/cli/__init__.py`
- **StepExecutor is now self-contained**: Removed `get_step_func` parameter from constructor; uses internal lazy step registry
- **Removed duplicate `_parse_step_config`**: Consolidated to single static `parse_step_config()` method

### Design Decisions (v3.0.0)

- **v1 Static Templates**: No parameter injection or template nesting; enables safe scoping
- **Local Checkpoints Only**: File-based checkpoints with deterministic naming
- **Explicit Checkpointing in Single-Step**: Manual `executor.checkpoint()` calls prevent accidental data loss in interactive mode
- **Early Template Validation**: All template references validated at definition load time to catch errors immediately
- **Three-Level Configuration**: Project-level (general_config) → Step-level (step_config) → Runtime flags (verbose, dry_run, debug)
- **Self-contained Executor**: No external callbacks needed; lazy loading minimizes startup time

## [2.8.0] - 2025-12-22

### Changed

- **Deduplication test suite**: Updated all test files (`test_deduplication.py`, `test_deduplication_performance.py`, `test_deduplication_circular_fix.py`) to follow new BaseStep class pattern with proper instantiation and method signatures

### Fixed

- Fixed checkpoint restore to maintain duplicate_of references: Added second-pass restoration in `load_checkpoint()` that rebuilds Paper object references from JSON ID strings, ensuring duplicate relationships are preserved when resuming from checkpoints
- Fixed `load_initial_definition()` in REPLSession to properly raise FileNotFoundError when definition file is not found instead of silently returning False

## [2.7.0] - 2025-12-21

### Added

- **Forward citations support in CitationsStep**: Fetch papers that cite the current papers (forward citations)
  - New `forward` configuration option for CitationsStep with `citations` and `details` sources
  - `_fetch_cited_by_for_papers()` method to fetch forward citations from external APIs
  - `_resolve_cited_by_and_fetch_papers()` method to resolve forward citations and enrich database
  - Support for OpenAlex forward citations via `cites:` filter
  - New result metrics: `papers_with_cited_by` to track papers with forward citations

### Changed

- **CitationsStep configuration**: Now supports both backward and forward citation fetching
  - `backward` config: Fetch papers cited by current papers (backward citations)
  - `forward` config: Fetch papers that cite current papers (forward citations)
  - Both can have `citations` sources (e.g., "crossref", "openalex") and optional `details` sources
- **OpenAlexHandler URL encoding**: DOI values in API queries are now properly URL-encoded to handle special characters
- **OpenAlexHandler._parse_cited_by()**: Changed to process single work objects instead of lists for consistency with base handler interface
- **Results dict initialization**: Forward and backward execute methods now initialize all required keys including both `papers_with_citations` and `papers_with_cited_by`
- **Statistics display table**: Now uses `.get()` with defaults for safe access to all result keys, prevents KeyError for missing metrics

### Fixed

- Fixed unpacking of `fetch_metadata()` return tuple (metadata, cache_hit) in OpenAlexHandler._fetch_cited_by_from_api()
- Fixed variable name bug in OpenAlexHandler._parse_cited_by() (was using undefined `item` instead of `work`)
- Fixed URL formatting in OpenAlexHandler._fetch_cited_by_from_api() to avoid line breaks in parameter names
- Fixed `_parse_cited_by()` return type to match base handler interface (single Citation instead of List[Citation])

## [2.6.0] - 2025-12-20

### Added

- **Fluent query builder (PapersQuery)**: Interactive database query mechanism with chainable filters
  - Three API levels for different use cases (explicit, shorthand, implicit)
  - Filter methods: `filter_by_topic()`, `filter_by_author()`, `filter_by_year()`, `grep()`, `filter()`, `exclude_duplicates()`
  - Sort methods: `order_by_year()`, `order_by_title()`, `order_by()`
  - Limit methods: `top()`, `limit()`
  - Terminal operations: `execute()`, `list()`, `first()`, `count()`
  - Magic methods for implicit execution: `__iter__`, `__len__`, `__getitem__`, `__bool__`
  - Shorthand database methods: `by_topic()`, `by_author()`, `by_year()`, `grep()`, `filter()`, `search()`
  - Convenience list-returning methods: `find_by_topic()`, `find_by_author()`, `find_by_year()`, `search()`
  - Lazy evaluation of filters for efficient large dataset filtering
  - Full test suite with 32 tests covering all methods and magic method behaviors

- **Enhanced PDF handling**: Improved PDF metadata extraction and filename handling
  - Better cite_key based filename generation for downloaded PDFs
  - Improved error handling in PDF download and processing steps
  - More robust path handling for PDFs with special characters

- **Query API documentation**: Comprehensive guides for fluent query usage
  - Three-level API guide showing explicit, shorthand, and implicit usage patterns
  - Quick reference guide with method signatures and examples
  - Magic methods demo showing Python dunder method usage

### Changed

- Database paper queries now support interactive fluent API alongside traditional access patterns
- `PapersDatabase.query()` method now returns `PapersQuery` builder for chainable operations

## [2.5.0] - 2025-12-19

### Added

- **Interactive REPL command loop**: Full-featured Python REPL with integrated paper-scanner macro commands
  - Dual-mode interface: Macro mode (`\command` prefix) for high-level operations and Micro mode (plain Python) for programmatic access
  - Built-in macro commands: `\run`, `\list`, `\steps`, `\export`, `\db`, `\help`, `\exit`
  - Macro command auto-completion with step suggestion
  - Paper-scanner Definition API integration for building and running pipelines interactively
  - Command history persistence across sessions (stored in `~/.cache/paper-scanner/.repl_history`)
  - Full Python introspection with rich IDE-like environment containing:
    - Direct database access (`db` object)
    - All paper-scanner modules pre-imported
    - Helper functions for common tasks
    - Access to pipeline definition API
  - Comprehensive help system (`\help` command) with examples and reference
  - Support for multiline Python input with syntax validation
  - Graceful error handling with informative error messages
  - Cross-platform compatibility with optional `prompt_toolkit` for enhanced UX (readline fallback on Unix)
  - Full test suite with 55+ tests covering all REPL modes and commands

- **OpenAlex API handler**: New metadata and citation fetcher for OpenAlex API
  - DOI-based work lookup with inverted index abstract reconstruction
  - Metadata extraction: title, authors, abstract, keywords, venue, open access status
  - Citation fetching with counts and references
  - Cache integration for efficient lookups
  - Full test suite with 15+ tests

- **Complete step documentation**: Added comprehensive documentation for two previously undocumented steps
  - `citations.md`: Three-pass citation extraction and graph building with examples and patterns
  - `retrieve_metadata.md`: Metadata enrichment from external APIs with workflow patterns

- **Test improvements**:
  - Comprehensive test suite for `test_citations_backward.py` with 25 tests covering all three citation passes (fetch, resolve, link) and execute integration
  - Enhanced mock setup for database fixtures with proper return value configuration
  - Full coverage of validation, execution, error handling, and edge cases

### Changed

- **Fetcher architecture expansion**: Extended pluggable handler design to support OpenAlex alongside Crossref
  - Unified interface for both citation and metadata fetching
  - Configurable primary and fallback fetcher sources
  - Seamless integration with existing cache layer

- **Documentation organization**: Updated docs/README.md and main README.md with complete step inventory
  - Organized all 15 documented main steps with descriptions
  - Clarified distinction between main steps and utility steps (dump_db, paper)
  - Added cross-references between related steps
  - Enhanced workflow pattern examples

- **CLI help system**: Extended CLI help to include information about available steps in error messages

### Fixed

- **Citation resolution edge cases**: Improved error handling for unresolved citations
  - Proper exception catching for citations without DOI when `continue_on_not_found=False`
  - Error logging to optional `output_errors` file for audit trail
  - Bidirectional link prevention to avoid duplicate citation relationships

- **Step registry consistency**: Ensured all 17 registered steps (15 main + 2 utility) are properly loaded and available

## [2.4.0] - 2025-12-14

### Added

- **Rebuilt API fetching architecture**: Complete restructuring of metadata fetching system with pluggable API handler design
  - New `BaseFetcherHandler` abstract interface for implementing API-specific metadata extraction
  - Support for multiple API sources (starting with Crossref for metadata)
  - Consistent field translation from API responses to Paper model
  - Automatic caching layer for all API responses
  - Extensible design for adding OpenAlex, PubMed, and other metadata providers
- **New `retrieve_metadata` pipeline step**: Fetch and enrich paper metadata from external APIs
  - Supports DOI-based metadata retrieval from Crossref
  - Configurable fallback behavior for papers without DOI
  - Progress tracking for batch metadata fetching
  - Cache-aware retrieval to avoid redundant API calls
  - Cite key generation with author/year fallback strategy

### Changed

- **Crossref integration refactored**: Migrated from direct API calls to new handler-based architecture with improved separation of concerns
- **Test class naming standardization**: Unified all step test files to use consistent `TestValidate` and `TestExecute` class names instead of step-specific variants (e.g., `TestEchoValidation` → `TestValidate`, `TestStepExecution` → `TestExecute`) for improved clarity and consistency across the test suite

## [2.3.0] - 2025-12-13

### Added

- CLI `--version` flag to display application version from `__version__`
- CLI `--debug` flag for run command to enable detailed step debug output
- Comprehensive checkpoint step test suite (`test_checkpoint.py`) with 23 tests covering serialization, deserialization, and duplicate handling
- **Expansion step improvements**:
  - Progress bar for metadata fetching with real-time progress updates
  - Gross/net citation summary showing total references → unique with DOI → unresolved to fetch
  - Cache-aware fetching that checks cache first before making API calls
  - `continue_on_not_found` configuration option for backward snowballing to gracefully handle 404 errors from Crossref (when true, continues without counting as failures; when false/default, counts as failures for strict error tracking)

### Changed

- Refactored CLI into modular task architecture (`tasks/run.py`, `tasks/validate.py`, `tasks/cache.py`) for better separation of concerns
- **Unified Crossref API client**: Refactored `CrossrefReferenceFetcher` to use a single `PoliteCrossrefClient` instance for all operations (both reference fetching and individual work metadata), eliminating duplicate HTTP clients and ensuring consistent rate limiting and caching across all API calls

### Fixed

- **Expansion step error handling**: Now properly catches HTTP 404 exceptions from Crossref API when fetching paper metadata, allowing `continue_on_not_found=true` to work correctly for graceful handling of unfound papers
- **Expansion step caching**: Fixed cache consistency by:
  - Normalizing DOIs (lowercase, remove URL prefixes) in `PoliteCrossrefClient.get_work()` to match normalization in `fetch_references_for_doi()`
  - Using a shared cache instance between `CrossrefReferenceFetcher` and `PoliteCrossrefClient` so all fetches benefit from the same cache
  - Ensuring all fetched papers are properly cached for reuse across runs
- **Paper type standardization**: Papers created during backward snowballing now use `PaperTypeTranslator` to convert Crossref paper types (e.g., "journal-article", "proceedings-article") to standardized format, ensuring consistent paper type representation across all data sources (Crossref, BibTeX, etc.)
- **Crossref cache directory enforcement**: Made `cache_dir` parameter REQUIRED (not optional) in both `PoliteCrossrefClient` and `CrossrefReferenceFetcher` to eliminate fallback to `~/.crossref` directory. Now raises `ValueError` if `cache_dir` is None, ensuring all Crossref API responses are ONLY cached in `$CACHE_DIR/crossref` with no exceptions or fallbacks. This prevents accidental cache fragmentation and ensures consistent caching behavior across all environments.
- **Expansion step cache_dir parameter**: Added explicit `cache_dir` parameter to `expansion.execute()` function signature so that the step executor properly detects and passes the cache directory to the step. This ensures cache_dir is always propagated from the task runner to the expansion step, fixing "cache_dir is required" errors when executing expansion via the task runner.
- **Expansion step debugging**: Enhanced debug output to show:
  - Papers in database without DOIs (when no papers can be expanded)
  - Which papers have DOIs and will be expanded
  - Console output for each paper being processed showing DOI and reference count from Crossref
  - Detailed logging of Crossref response structure for troubleshooting

## [2.2.0] - 2025-12-12

### Added

- New `input` step for importing JSON Lines data from files or stdin with minimal processing (no enrichment)
- New `patch` step for updating existing paper records by DOI with replace and append field operations

### Fixed

- **Screening summary duplicate awareness**: Screening results table now separates duplicate records from primary papers in the display, preventing double-counting of duplicates in screening statistics. Duplicates are shown as a separate row with "-" for screening stages. Summary statistics (inclusion rate, exclusion counts) now only count primary papers.
- **Deduplication matching**: Enhanced deduplication to properly track and identify duplicate papers across multiple matching methods (DOI exact, title-author fuzzy, title fuzzy)

## [2.1.0] - 2025-12-11

### Added

- Extracted JSON file caching mechanism into reusable `paper_scanner.tools.cache` module with full test suite (21 tests, 95% coverage)
- Implemented `load_files` step for processing PDF files: extracts DOI, fetches Crossref metadata, creates Paper models, stores in database, and copies files with DOI-based naming
- Created `FileReader` utility for PDF file processing with multi-method DOI extraction fallback chain (metadata, content regex, Crossref title lookup)
- Added `AbstractParser` tool to clean [JATS/HTML](https://jats.nlm.nih.gov/) markup from scientific abstracts with full unit test suite

### Changed

- Refactored Crossref API client classes into `paper_scanner.tools.fetchers.crossref_fetcher` module for better code organization

## [2.0.2] - 2025-12-11

### Changed

- **Test Suite Refactoring**: Improved test organization and pytest compatibility
  - Added pytest fixtures for database URL configuration
  - Fixed module naming conflicts between `tests/classic/` and `tests/unit/` directories
  - Activated crossref_fetcher tests with proper fixture injection
  - Added `__init__.py` files to test directories for proper Python package structure
  - Standardized environment variable handling for test database configuration

- **Test Infrastructure Improvements**:
  - Database URL fixture loads from `DATABASE_URL` environment variable
  - Default fallback to `postgresql://pdfuser:pdfpass@localhost:5432/paper_scanner`
  - Both pytest and legacy script execution modes supported
  - Cleaner separation between pytest tests and standalone test scripts

### Technical Details

- Test fixtures in `tests/classic/test_crossref_fetcher.py` using `@pytest.fixture`
- Database configuration via environment variables with sensible defaults
- Improved test discovery and execution with proper package structure

## [2.0.1] - 2025-12-11

### Investigating

- **Pythonic Definition API** (Spike Investigation - See `tests/spikes/007_new_approach/`)
  - Exploring type-safe Python-based pipeline definitions as alternative to YAML
  - Fluent builder API: `Definition("Project").bibtex_import(...).export(...).run()`
  - Full IDE support with autocomplete and compile-time type checking
  - Comprehensive documentation in `tests/spikes/0007_new_approach/PYTHONIC_DEFINITION_API.md`
  - Working examples in `tests/spikes/0007_new_approach/` directory:
    - Simple import/export workflows
    - Complex multi-source pipelines with deduplication
    - Conditional step logic with factory functions
    - Batch processing across multiple years/topics
  - Detailed comparison with YAML approach in `tests/spikes/0007_new_approach/YAML_VS_PYTHONIC_COMPARISON.md`
  - Spike implementation in `src/paper_scanner/definition/__init__.py`

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
