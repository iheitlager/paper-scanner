# AI Coding Agent Instructions for paper-scanner

## Project Overview
**paper-scanner** is a Python LLM-powered literature review tool (v3.7.0, pre-alpha). It uses Claude API to analyze academic PDFs, extract structured information (metadata, research questions, findings), and organize papers via PostgreSQL backend with a web UI.

## Architecture

### Core Data Flow
```
PDF Input → Claude Analysis → Structured JSON → PostgreSQL DB → Web Interface
```

### Major Components
- **Core**: `src/paper_scanner/core/` - Database, models, DOI handling, normalization
- **IO**: `src/paper_scanner/io/` - File handling (PDF, BibTeX, RIS, JSON)
- **Models**: `src/paper_scanner/models/` - LLM interactions
- **Definition API**: `src/paper_scanner/definition/` - Fluent Python API for building pipelines (alternative to YAML)
- **Steps**: `src/paper_scanner/steps/` - Pipeline processors (bibtex_import, deduplication, export, etc.)
- **CLI**: `src/paper_scanner/cli/paper_processor.py` - Main entry point with subcommands: repl, run, validate, info, cache
- **Web**: `src/paper_scanner/web/` - Flask UI with PDF viewer, analysis, references, tags

### Pipeline Architecture
- **Two approaches**: YAML definition files (primary) or Pythonic fluent API (Definition class)
- **Steps inherit from BaseStep** in `src/paper_scanner/steps/base.py` - implements validation, execution, result handling
- **Step execution flow**: Validate config → Instantiate step → Execute with general_config + step_config + runtime flags → Return results dict
- **Checkpointing**: Resume pipelines from specific steps (see `src/paper_scanner/steps/checkpoint.py`)

## Critical Developer Workflows

### Setup & Testing
```bash
uv sync --all-groups    # Install all dependencies
make test               # Run all tests (Python + JS)
make lint              # Ruff linting
make type-check        # mypy type checking
make format            # Code formatting
```

### Running Pipelines
```bash
# YAML-based (primary)
uv run paper-processor definition.yml --verbose

# Resume from checkpoint
uv run paper-processor definition.yml --checkpoint last

# Pythonic API (tests/spikes/007_new_approach/)
from paper_scanner.definition import Definition, BibtexSource
pipeline = Definition("Review").bibtex_import(...).export(...).run()
```

### Adding a New Pipeline Step
1. Create `src/paper_scanner/steps/my_step.py` extending `BaseStep`
2. Implement `validate(config)` → returns (bool, List[str] errors)
3. Implement `execute(config, verbose, dry_run, debug)` → returns StepResult with status, message, stats dict
4. **Update `src/paper_scanner/cli/__init__.py`** with step registration in STEP_REGISTRY_PATHS dict
5. Register in `src/paper_scanner/cli/tasks/run.py` StepExecutor.BUILTIN_STEPS if needed
6. DO NOT create extra markdown documentation files unless specifically requested

## Project-Specific Patterns

### JSONLines Format
All streaming data uses JSONLines (one JSON object per line). No commas between objects - essential for efficient batch processing:
```python
# Read JSONLines
import json
with open("file.jsonl") as f:
    for line in f:
        record = json.loads(line)

# Write JSONLines
with open("file.jsonl", "w") as f:
    for record in records:
        f.write(json.dumps(record) + "\n")
```

### Configuration Three-Level Model
1. **general_config**: Project-level (passed to all steps)
2. **step_config**: Step-specific from YAML
3. **Runtime flags**: verbose, dry_run, debug (passed during execution)

### Paper Model
Located in `src/paper_scanner/core/models.py` - Paper dataclass with fields: id, title, authors, year, doi, batch_id, file_path, tags, and analysis metadata. Database uses indexed lookups by DOI, title, year for deduplication.

### Error Handling Pattern
Return structured StepResult:
```python
from paper_scanner.core.step_result import StepResult
from paper_scanner.core.enum import StepStatus

return StepResult(
    status=StepStatus.SUCCESS,  # or ERROR, HALTED, WARNING
    message="Summary message",
    stats={
        "count": 42,           # Processed count
        "skipped": 5,
        "papers_count": 100,   # DB total
    },
    error="Error message if status is ERROR",
    details="Detailed markdown-formatted result"
)
```

Backward compatibility: `StepResult` supports dict-like access via `__getitem__` for legacy code.

## Versioning & Branching

**Semantic Versioning**: MAJOR.MINOR.PATCH in `src/paper_scanner/__init__.py`

- `feat/`: New features → MINOR bump + `### Added` in CHANGELOG
- `fix/`: Bug fixes → PATCH bump + `### Fixed` in CHANGELOG
- `docs/`, `test/`, `refactor/`, `chore/`: No version bump
- 'spike/': Experimental, may be discarded, no version bump, most like a new folder in tests/spikes/XXX_name
- Always update `CHANGELOG.md`, `README.md`, `src/paper_scanner/__init__.py` and `docs/index.md` with new version

## Key Files Reference
- Database schema: `src/paper_scanner/core/models.py` (Paper dataclass)
- Step result class: `src/paper_scanner/core/step_result.py` (StepResult dataclass)
- Step base class: `src/paper_scanner/steps/base.py` with documentation in `docs/steps/base_step.md`
- Pipeline executor: `src/paper_scanner/core/executor.py` (StepExecutor)
- Step examples: `src/paper_scanner/steps/{export,deduplication,bibtex_import}.py`
- Tests: `tests/unit/` (run with `make test` or `uv run pytest`)
- ALWAYS USE `uv` when running/testing commands
- CLI entry point: `src/paper_scanner/cli/paper_processor.py` (main CLI)
- Documentation: `docs/` directory (MkDocs with Material theme, deployed to ReadTheDocs)
- Documentation config: `mkdocs.yml` at project root, deployed to https://paper-scanner.readthedocs.io
- Step docs: `docs/steps/` (reference when implementing, automatically included in sidebar)

## Important: Pre-Alpha Status
- Breaking changes may occur between minor versions
- Limited to Claude API (Anthropic integration in `src/paper_scanner/core/llm.py`)
- Test coverage critical before merging (`pytest` with coverage tracking)
- Always update CHANGELOG.md with changes
- Always use `uv` when testing/running commands
- Documentation is built with MkDocs and deployed to ReadTheDocs
- **NEVER generate extra markdown documentation files unless explicitly requested by the user**
  - Do not create summary files, implementation guides, or reference docs
  - User-facing documentation goes in `docs/` only (and only if requested)
  - Focus on code implementation, testing, and git commits