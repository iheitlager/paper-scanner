# ADR-0004: Source Code Structure & Test Organization

**Status**: Accepted  
**Date**: 2025-01-04  
**Authors**: Development Team

---

## Context

The paper-scanner project has grown to include multiple functional modules, development workflows, and test strategies. There is a need to establish clear documentation around:

1. How the source code (`src/paper_scanner/`) is organized into modules
2. How each module serves a specific purpose in the pipeline
3. How tests are organized across unit, spike, and explore categories
4. How developers should add new code and tests

Currently, developers must infer module structure and test patterns from directory browsing. This creates friction for:
- Onboarding new contributors
- Understanding where to place new functionality
- Determining which test strategy fits different work types
- Validating test coverage across the codebase

---

## Decision

We establish a formal module structure with documented responsibilities and a three-tier test strategy:

### Source Modules Structure

```
src/paper_scanner/
├── cli/                          # Command-line interface
│   ├── tasks/                   # Task-specific CLI commands (run.py, repl.py, etc.)
│   └── __init__.py              # Step registry and CLI setup
├── core/                        # Core infrastructure & models
│   ├── database.py              # PostgreSQL wrapper, transaction handling
│   ├── models.py                # Paper dataclass, schema definitions
│   ├── executor.py              # StepExecutor: pipeline execution engine
│   ├── step_result.py           # StepResult: structured result container
│   ├── enum.py                  # StepStatus, shared enums
│   ├── exceptions.py            # Custom exceptions (PipelineExecutionError, StepError)
│   ├── general_config.py        # Project-level configuration model
│   ├── cache.py                 # Caching layer (file-based)
│   ├── query.py                 # Query API for searching papers
│   ├── reporter.py              # Reporting/statistics collection
│   ├── normalization.py         # Data normalization (authors, titles, etc.)
│   ├── doi.py                   # DOI handling and validation
│   ├── cite_key.py              # Citation key generation and validation
│   ├── iso4.py                  # ISO 4 journal abbreviation support
│   └── advanced_section_parser.py # Complex PDF section parsing
├── definition/                  # Fluent API for pipeline building
│   ├── __init__.py              # Definition class (Pythonic alternative to YAML)
│   └── ...                      # Step-specific fluent classes (BibtexSource, etc.)
├── io/                          # Input/Output format handlers
│   ├── bibtex.py                # BibTeX parsing and serialization
│   ├── ris.py                   # RIS format support
│   ├── json.py                  # JSON Lines format (streaming)
│   └── sql.py                   # Database I/O operations
├── models/                      # LLM integration layer
│   ├── base.py                  # BaseLLM: abstract interface
│   ├── anthropic.py             # Claude/Anthropic implementation
│   └── ollama.py                # Local Ollama implementation
├── steps/                       # Pipeline step implementations
│   ├── base.py                  # BaseStep: abstract step class
│   ├── checkpoint.py            # Checkpoint: pipeline resumption
│   ├── bibtex_import.py         # Import from BibTeX files
│   ├── ris_import.py            # Import from RIS files
│   ├── deduplication.py         # Duplicate paper detection & removal
│   ├── metadata_screening.py    # Filter by metadata criteria
│   ├── journal_screening.py     # Filter by journal properties
│   ├── download_pdfs.py         # Fetch PDFs from multiple sources
│   ├── fix_cite_keys.py         # Standardize citation keys
│   ├── llm_classification.py    # LLM-based paper categorization
│   ├── rocchio_classifier.py    # Vector-based classification (Rocchio)
│   ├── generate_embeddings.py   # Create vector embeddings
│   ├── citations.py             # Extract and link citations
│   ├── citations_backward.py    # Find backward citation links
│   ├── empirical_qualification.py # Determine empirical methods
│   ├── report.py                # Display statistics & findings
│   ├── export.py                # Export to BibTeX, JSON, RIS
│   ├── run_template.py          # Execute template-based steps
│   ├── halt.py                  # Halt pipeline execution
│   ├── upload_database.py       # Upload to remote database
│   └── base.py                  # NOT a step; base class + utilities
├── tools/                       # Utility modules for specific tasks
│   ├── documents/               # Document processing (PDF text extraction)
│   ├── embedding/               # Embedding generation utilities
│   ├── fetchers/                # PDF fetcher implementations (CrossRef, etc.)
│   └── __init__.py
├── viewer/                      # PDF viewer component
├── web/                         # Flask web UI
│   ├── static/                  # CSS, JavaScript, assets
│   ├── templates/               # Jinja2 templates
│   └── ...                      # Flask routes and views
├── old/                         # Deprecated code (do not use)
└── __init__.py                  # Version info (__version__)
```

#### Module Responsibilities

| Module | Purpose | Key Classes/Functions | Dependencies |
|--------|---------|----------------------|--------------|
| **cli** | Entry point, command routing | CLI groups, subcommand registration | core, executor, steps |
| **core** | Infrastructure & data layer | StepExecutor, Paper, Database | database drivers, pydantic |
| **definition** | Fluent pipeline API | Definition, BibtexSource, etc. | steps, yaml |
| **io** | Format converters | BibTeXHandler, RISHandler, JSONHandler | bibtexparser, ris libraries |
| **models** | LLM backends | BaseLLM, AnthropicModel, OllamaModel | anthropic, ollama |
| **steps** | Pipeline operations | BaseStep subclasses (26 total) | core, io, models |
| **tools** | Domain-specific utilities | Fetchers, DocumentParser, Embedder | requests, sentence-transformers |
| **viewer** | PDF viewing interface | PdfViewer components | pypdf, flask |
| **web** | Web UI server | Flask app, routes, templates | flask, flask-cors |

---

### Test Organization Strategy

#### 1. **Unit Tests** (`tests/unit/`)

**Purpose**: Isolated, fast, reproducible tests for individual units (functions, methods, classes)

**Structure**: Mirrors `src/` layout
```
tests/unit/
├── cli/
├── core/
├── io/
├── models/
├── steps/
├── tools/
├── viewer/
└── web/
```

**Characteristics**:
- Mock external dependencies (database, API calls, file I/O)
- No database setup required (use fixtures)
- Fast execution (<50ms per test ideal)
- High coverage target (>80%)
- Use `pytest` with `pytest-mock`

**Example**:
```python
# tests/unit/core/test_executor.py
def test_executor_loads_definition(temp_cache_dir, general_config):
    """Test that StepExecutor can load a YAML definition"""
    executor = StepExecutor(general_config, cache_dir=temp_cache_dir)
    # ... assertions
```

**When to Write**:
- Testing step validation logic
- Testing configuration parsing
- Testing database query builders
- Testing format handlers (BibTeX parsing, etc.)
- Testing utility functions

---

#### 2. **Spikes** (`tests/spikes/`)

**Purpose**: Exploratory, experimental work; testing new features before full integration

**Characteristics**:
- Numbered directories (`001_`, `002_`, etc.) indicate development sequence
- Not part of CI/CD pipeline
- May be deleted after feature integration (except key patterns)
- Larger, more realistic scenarios than unit tests
- Can use real external APIs, databases (with explicit setup)
- Often include integration tests across multiple modules
- Use narrative naming: `001_first_tests`, `011_step_executor`, `014_classification`

**Example Structure**:
```
tests/spikes/011_step_executor/
├── 01_basic_setup.py            # Minimal executor setup
├── 02_batch_execution.py        # Multi-step pipelines
├── 03_single_step_mode.py       # Interactive step testing
├── 04_statistics.py             # Stats collection
├── 05_template_expansion.py     # Template system
├── 06_error_handling.py         # Exception scenarios
├── 07_halt_test.py              # Pipeline halt behavior
├── 08_python_interpreter.py     # Dynamic code execution
└── INTEGRATION_EXAMPLE.py       # End-to-end demo
```

**When to Use**:
- Developing new features (before they're stable)
- Testing complex integration scenarios
- Validating new libraries or external APIs
- Building proof-of-concepts
- Testing database migrations
- Exploring alternative architectures

**Lifecycle**:
- Spike created → code added → tested locally → insights documented
- After feature stabilization: insights merged into unit tests, spike may be kept as reference
- Do not rely on spikes for CI/CD validation

---

#### 3. **Explore** (`tests/explore/`)

**Purpose**: Interactive, notebook-based investigation and analysis

**Characteristics**:
- Jupyter notebooks (`.ipynb` format)
- User-friendly environment for debugging, visualization
- Not automated test execution
- Useful for:
  - Inspecting data structures
  - Visualizing embeddings or classification results
  - Testing against real APIs interactively
  - Prototyping data transformations

**Example**:
```
tests/explore/
├── 001_explore_pdf.ipynb        # PDF extraction debugging
└── 002_citations.ipynb          # Citation extraction visualization
```

**When to Use**:
- Debugging complex data transformations
- Visualizing embeddings or ML results
- Manual testing of end-to-end workflows
- Exploring query results
- Creating reproducible analysis snapshots

---

### Test Execution & Configuration

**Pytest Configuration** (via `pyproject.toml`):
```toml
[tool.pytest.ini_options]
testpaths = ["tests/unit"]                    # Only run unit tests by default
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--strict-markers"
markers = [
    "unit: fast, isolated unit tests",
    "integration: tests requiring database",
    "slow: long-running tests",
]
```

**Running Tests**:
```bash
# Unit tests only (default, fast CI/CD)
uv run pytest tests/unit

# With coverage
uv run pytest tests/unit --cov=src/paper_scanner --cov-report=html

# Specific spike (for feature development)
uv run pytest tests/spikes/011_step_executor -v

# All except spikes (safety check before commit)
uv run pytest tests/unit tests/classic --tb=short
```

---

### Test Fixtures & Common Patterns

**Fixture Locations** (in `tests/unit/conftest.py` and module-specific `conftest.py`):
```python
# Global fixtures available to all tests
@pytest.fixture
def general_config():
    """Project-level config"""
    return {"project_name": "Test", "researcher": "Test"}

@pytest.fixture
def temp_cache_dir():
    """Temporary directory for cache/temp files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def executor(general_config, temp_cache_dir):
    """StepExecutor instance with mocked database"""
    return StepExecutor(
        general_config=general_config,
        cache_dir=temp_cache_dir,
        step_reporter=NoOpReporter(),
    )

@pytest.fixture
def sample_papers():
    """Realistic test papers"""
    return [
        Paper(id=1, title="...", authors="...", year=2023, doi="..."),
        Paper(id=2, title="...", authors="...", year=2022, doi="..."),
    ]
```

**Testing Steps** (common pattern):
```python
class TestBibtexImportStep:
    def test_validate_accepts_valid_config(self):
        config = {"source_file": "/path/to/file.bib"}
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid
        assert errors == []
    
    def test_execute_imports_papers(self, temp_cache_dir):
        step = BibtexImportStep(config={"source_file": "..."})
        result = step.execute(
            config={...},
            verbose=False,
            dry_run=False,
            debug=False,
        )
        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_count"] > 0
```

---

## Consequences

### Positive
✅ **Clarity**: Developers understand module responsibilities at a glance  
✅ **Test Strategy**: Clear guidance on which test type fits which task  
✅ **Scalability**: Module structure supports adding new IO formats, LLM backends, tools  
✅ **Quality**: Separation of unit tests (fast, CI/CD) from spikes (exploratory)  
✅ **Onboarding**: New contributors quickly understand code organization  
✅ **Maintainability**: Mirrors Python packaging conventions (clear import paths)  

### Negative/Tradeoffs
⚠️ **Coupling**: Some tools modules tightly coupled to external libraries  
⚠️ **Growth**: As steps increase beyond 26, may need subcategories (grouping by type)  
⚠️ **Testing Overhead**: Maintaining unit + spike tests increases coverage work  

### Mitigations
- Periodically review module coupling; extract shared patterns into utils
- Document step groupings in `docs/steps/.pages` for quick reference
- Maintain CI/CD focus on unit tests; use spikes for exploratory work only
- Keep ADR-0002 (Step Architecture) in sync as new patterns emerge

---

## Alternatives Considered

### 1. **Flat Structure** (rejected)
All code in `src/paper_scanner/` root without subdirectories.
- ❌ Difficult to navigate as project grows
- ❌ No clear responsibility separation
- ✅ Simpler imports initially

### 2. **Feature-Based Organization** (rejected)
Organize by feature (e.g., `src/import/`, `src/screening/`, `src/export/`)
- ✅ Maps to user workflows
- ❌ Creates circular dependencies (multiple features need shared core)
- ❌ Duplicates infrastructure code

### 3. **Single Test Suite** (rejected)
Combine unit, spike, and explore into one test directory.
- ✅ Simpler CI/CD setup
- ❌ Slower pipeline (waits for slow spikes)
- ❌ Mixed concerns (isolated vs exploratory)

---

## Implementation

### Phase 1: Documentation (Current)
✅ Create this ADR with module descriptions  
✅ Document test strategy and lifecycle  
✅ Establish fixture patterns  

### Phase 2: Test Hygiene (Planned)
📋 Add `conftest.py` at `tests/unit/` if missing  
📋 Standardize fixture names across test files  
📋 Document "when to write spike vs unit" in contributor guide  

### Phase 3: CI/CD Validation (Planned)
📋 Update CI pipeline to run only `tests/unit/` for speed  
📋 Add optional `tests/spikes` run for full validation  
📋 Enforce coverage targets in `tests/unit` only  

### Phase 4: Growth (Future)
📋 As steps exceed 30, introduce subcategories in `steps/` module  
📋 Introduce tools subcategories for clarity  

---

## References

- ADR-0001: Pipeline Architecture
- ADR-0002: Step Architecture  
- ADR-0003: Executor Setup
- `docs/contributing/setup.md`: Development environment setup
- `docs/steps/.pages`: Step categorization (sidebar)
- `pyproject.toml`: pytest configuration

---

## Questions & Discussion

**Q: Where do I add a new LLM backend?**  
A: Extend `src/paper_scanner/models/base.py`'s `BaseLLM` class (similar to `anthropic.py`, `ollama.py`)

**Q: When should I write a spike vs unit test?**  
A: Unit tests are for stable, isolated logic. Spikes are for new features, integration scenarios, or exploring unknowns.

**Q: Can I delete old spikes?**  
A: Yes, after the insights are merged into unit tests. Keep spikes as long as they represent active development.

**Q: How do I test a new step?**  
A: Create `tests/unit/steps/test_mystep.py` with mocked database/APIs. Optionally add spike in `tests/spikes/0XX_mystep_exploration/`.

**Q: Why is `tests/explore/` not automated?**  
A: Notebooks require manual execution and are better for interactive debugging. Automation belongs in pytest (unit/spikes).
