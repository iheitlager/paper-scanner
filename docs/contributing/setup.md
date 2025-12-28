# Development Setup

Getting set up to contribute to paper-scanner.

## Prerequisites

- Python 3.11+
- Git
- PostgreSQL 12+ (optional, for testing)
- Claude API key (for testing LLM features)

## Setup Steps

### 1. Clone Repository
```bash
git clone https://github.com/iheitlager/paper-scanner.git
cd paper-scanner
```

### 2. Create Virtual Environment
```bash
# Using uv (recommended)
uv venv

# Or using standard venv
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
# Install all dependencies including dev tools
uv sync --all-groups

# Or manually with pip
pip install -e ".[dev,test,docs]"
```

### 4. Set up Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Set up git hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### 5. Configure Environment
```bash
# Create .env file
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
PAPERS_DB=test.db
DATABASE_URL=postgresql://user:password@localhost/paper_scanner
EOF
```

### 6. Initialize Database
```bash
# For testing
uv run paper-processor --init

# With PostgreSQL
export DATABASE_URL=postgresql://user:password@localhost/paper_scanner
uv run paper-processor --init
```

## Development Workflow

### Running Tests
```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/unit/steps/test_citations.py -v

# Run with coverage
uv run pytest --cov=src/paper_scanner tests/

# Run in watch mode
make test-watch
```

### Code Quality
```bash
# Run linter
make lint

# Format code
make format

# Type checking
make type-check

# All checks
make check
```

### Building Documentation
```bash
# Build mkdocs
mkdocs build

# Serve locally
mkdocs serve
# Visit http://localhost:8000
```

## Project Structure

```
paper-scanner/
├── src/paper_scanner/          # Main package
│   ├── core/                   # Core models and database
│   ├── steps/                  # Pipeline steps
│   ├── cli/                    # Command-line interface
│   ├── definition/             # Fluent Python API
│   ├── tools/                  # External integrations
│   ├── viewer/                 # Web interface
│   └── __init__.py
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── spikes/                 # Experimental code
├── docs/                       # Documentation
│   ├── guide/                  # User guides
│   ├── architecture/           # Architecture docs
│   ├── steps/                  # Step documentation
│   ├── adr/                    # Architecture decisions
│   └── contributing/           # Contributing guidelines
├── pyproject.toml              # Project metadata
├── mkdocs.yml                  # Documentation config
├── .readthedocs.yml            # RTD configuration
├── Makefile                    # Development tasks
└── README.md                   # Project overview
```

## Making Changes

### Creating a Branch
```bash
# Create feature branch
git checkout -b feature/my-feature

# Or bug fix branch
git checkout -b fix/my-bug
```

### Committing Code
```bash
# Stage changes
git add .

# Commit (pre-commit hooks run automatically)
git commit -m "feat: add new feature"

# Commit types: feat, fix, docs, test, refactor, chore, spike
```

### Running Tests Before Push
```bash
# Run all checks
make check

# Or individually
make lint
make type-check
make test
```

### Creating a Pull Request
1. Push to your branch
2. Create PR on GitHub with:
   - Clear title and description
   - Reference related issues
   - Checklist of changes

## Code Standards

See [Code Standards](standards.md) for:
- Naming conventions
- Type hints
- Documentation requirements
- Test requirements

## Testing Guide

See [Testing Guide](testing.md) for:
- Writing unit tests
- Writing integration tests
- Test coverage requirements
- Mocking strategies

## Documentation

### Adding Step Documentation
1. Create file in `docs/steps/`
2. Follow [template](../STEP_DOCUMENTATION_TEMPLATE.md)
3. Add to `docs/steps/.pages`

### Adding Architecture Decision
1. Create ADR in `docs/adr/`
2. Use format from [template](../adr/0000-template.md)
3. Add to `docs/adr/index.md`

### Updating mkdocs
Edit `mkdocs.yml` to add new pages.

## Debugging

### Enable Debug Output
```bash
# CLI
uv run paper-processor definition.yml --debug

# Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Using Debugger
```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or in Python 3.7+
breakpoint()
```

### Inspecting Database
```bash
# SQLite
sqlite3 papers.db

# PostgreSQL
psql paper_scanner
```

## Build System

### Using Make
```bash
make help          # Show all targets
make test          # Run tests
make lint          # Run linter
make format        # Format code
make type-check    # Type checking
make docs          # Build documentation
make clean         # Clean build artifacts
```

### Using uv
```bash
# Run commands in uv environment
uv run pytest tests/
uv run mypy src/
uv run ruff check src/
```

## Performance Testing

```bash
# Profile execution
uv run -m cProfile -s cumtime -m paper_scanner.cli definition.yml

# Memory profiling
uv run -m memory_profiler main.py
```

## Release Process

For maintainers:
1. Update version in `src/paper_scanner/__init__.py`
2. Update CHANGELOG.md
3. Create git tag: `git tag v2.4.0`
4. Push: `git push origin v2.4.0`
5. CI/CD builds and publishes automatically

## Troubleshooting

### Tests Failing
```bash
# Clean cache
rm -rf .pytest_cache __pycache__ .mypy_cache

# Reinstall dependencies
uv sync --all-groups --refresh

# Run specific test with verbose output
uv run pytest tests/unit/test_file.py::test_function -vv
```

### Import Errors
```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Reinstall package in editable mode
pip install -e .
```

### Database Locked
```bash
# Remove test database
rm papers.db papers.db-shm papers.db-wal

# Reset database
uv run paper-processor --init --force
```

## Getting Help

- 📖 Read the [main README](../../README.md)
- 🏗️ Check [Architecture Overview](../architecture/overview.md)
- 🧪 Review existing [tests](../../tests/)
- 💬 Open a [discussion](https://github.com/iheitlager/paper-scanner/discussions)

## Next Steps

- [Code Standards](standards.md)
- [Testing Guide](testing.md)
- [Architecture Overview](../architecture/overview.md)
