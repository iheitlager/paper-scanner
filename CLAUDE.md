# Claude Instructions for paper-scanner

This document provides guidelines for working with the paper-scanner codebase.

## Project Overview

**paper-scanner** is a Python tool for analyzing academic research papers using LLM assistance. It uses Anthropic's Claude API to extract structured information from PDFs including:
- Paper metadata (title, authors, year)
- Research questions and methodology
- Key findings and limitations
- Innovation mechanisms using the CAMO framework (Context-Agency-Mechanism-Outcome)
- Vendor and supplier information

**Current Version**: 0.2.0 (Pre-alpha)

## Development Setup

### Prerequisites
- Python 3.11+
- `uv` package manager

### Getting Started
```bash
# Install dependencies
uv sync --all-groups

# Run tests
make test

# Check code quality
make lint
make type-check
```

## Key Components

### Core Module
- **`src/paper_scanner/core/advanced_section_parser.py`**: Parses academic paper analysis using regex patterns to extract structured data from markdown-formatted Claude responses.

### Tools (in `src/paper_scanner/tools/`)
1. **file_scanner.py**: Scans directories for PDFs and generates JSONLines output with file metadata
2. **file_processor.py**: Sends PDFs to Claude API for analysis with automatic retry/rate-limit handling
3. **file_parser.py**: Parses Claude responses using AcademicPaperParser
4. **file_merge.py**: Combines and filters JSONLines data with set operations
5. **file_reader.py**: Converts parsed JSON to CSV format
6. **file_timer.py**: Rate limiting utility for API throttling

### Testing
- Test files are in `tests/unit/`
- Main test file: `test_advanced_section_parser.py`
- Run with: `make test` or `uv run pytest`

## Important Patterns

### JSONLines Format
All tools communicate via JSONLines (JSON Lines) format for streaming data:
- One JSON object per line
- No commas between objects
- Efficient for batch processing

### Parser Format Handling
The `AcademicPaperParser` handles multiple markdown formatting variations:
- `**TITLE:** value` (colon inside bold)
- `**TITLE**: value` (colon outside bold)  
- `TITLE: value` (plain text)
- Works with both `##` section headers and `###` subsection headers

### Configuration
- **Environment**: Set `ANTHROPIC_API_KEY` for Claude API access
- **Dependencies**: Managed via `pyproject.toml` and `uv`
- **Build System**: Uses hatchling via pyproject.toml

## Development Workflow

### Making Changes
1. Create a feature branch
2. Run tests before and after changes: `make test`
3. Ensure linting passes: `make lint`
4. Format code: `make format`
5. Verify types: `make type-check`
6. Update CHANGELOG.md with your changes
7. Submit PR

### Code Quality
- Use `ruff` for linting and formatting
- Use `mypy` for type checking
- Aim for clear, documented code
- Write tests for new functionality

## Common Tasks

### Add a New Tool
1. Create new file in `src/paper_scanner/tools/`
2. Implement with argparse for CLI interface
3. Follow stdin/stdout pattern for JSONLines compatibility
4. Add to `pyproject.toml` `[project.scripts]` section
5. Add tests in `tests/unit/`

### Update Parser
- Regex patterns in `advanced_section_parser.py` handle multiple formats
- Test with `make test` to ensure backward compatibility
- Document format variations in code comments

### Fix Bugs
1. Write a test case that reproduces the bug
2. Implement the fix
3. Verify test passes
4. Update CHANGELOG.md with bug fix

## Versioning & Branch Strategy

This project follows **Semantic Versioning** (MAJOR.MINOR.PATCH) with a structured git workflow.

### Version Format
- **MAJOR**: Breaking changes or complete rewrites (e.g., 1.0.0)
- **MINOR**: New features, backward compatible (e.g., 0.2.0)
- **PATCH**: Bug fixes, backward compatible (e.g., 0.1.2)

### Branch Naming Convention

#### Feature Branches (Minor Version Increment)
Use `feat/` prefix for new features and enhancements:
```
feat/parser-improvements
feat/new-tool-csv-export
feat/caching-layer
feat/web-ui
```

When merged to main:
- Updates `MINOR` version (e.g., 0.1.0 → 0.2.0)
- Add `### Added` section to CHANGELOG.md
- Requires all tests passing and PR review

#### Bug Fix Branches (Patch Version Increment)
Use `fix/` prefix for bug fixes:
```
fix/regex-parsing-edge-case
fix/rate-limit-handling
fix/unicode-filename-support
```

When merged to main:
- Updates `PATCH` version (e.g., 0.2.0 → 0.2.1)
- Add `### Fixed` section to CHANGELOG.md
- Requires all tests passing

#### Other Branch Types (No Version Change)
- `docs/`: Documentation updates (no version bump)
- `test/`: Test additions/improvements (no version bump)
- `refactor/`: Code refactoring (no version bump)
- `chore/`: Build, dependencies, etc. (no version bump)

### Release Workflow

1. **Start work on a feature or fix:**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Develop and test:**
   ```bash
   make test
   make lint
   make format
   make type-check
   ```

3. **Update files:**
   - Implement your changes
   - Add/update tests
   - Update docstrings

4. **Prepare for merge:**
   - Update `src/paper_scanner/__init__.py` with new version
   - Update CHANGELOG.md with your changes
   - Update README.md if needed (for major features)

5. **Commit and push:**
   ```bash
   git add .
   git commit -m "feat: descriptive commit message"
   git push origin feat/your-feature-name
   ```

6. **Create Pull Request:**
   - Reference any related issues
   - Include test results
   - Link to updated CHANGELOG section

### Updating Version Number

Edit `src/paper_scanner/__init__.py`:
```python
__version__ = "X.Y.Z"
```

### Updating CHANGELOG.md

Add a new version section at the top:
```markdown
## [0.2.0] - YYYY-MM-DD

### Added
- Feature description
- Another feature

### Fixed
- Bug fix description

### Changed
- Breaking change or modification
```

## Versioning

Using Semantic Versioning:
- **MAJOR.MINOR.PATCH** (e.g., 0.1.1)
- Version is defined in `src/paper_scanner/__init__.py`
- Update CHANGELOG.md for every release

## Resources

- **Changelog**: See [CHANGELOG.md](CHANGELOG.md) for version history
- **README**: See [README.md](README.md) for user documentation
- **License**: Apache 2.0 (see LICENSE file)

## Known Limitations & Future Work

### Current Limitations
- Pre-alpha stage - breaking changes may occur
- Limited to Claude models (could extend to other LLMs)
- No caching of API responses yet
- CLI-only interface

### Planned Features
- [ ] Enhanced paper section detection
- [ ] Support for additional document formats
- [ ] Response caching layer
- [ ] Web UI for interactive analysis
- [ ] Additional export formats (JSON Schema, RDF)

## Questions or Issues?

Refer to the GitHub repository: https://github.com/iheitlager/paper-scanner
