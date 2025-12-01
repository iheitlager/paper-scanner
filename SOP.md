# Standard Operating Procedures - paper-scanner

This document defines standardized workflows for AI agents working with the paper-scanner codebase. These procedures use RFC 2119 requirement levels (MUST, SHOULD, MAY) to ensure consistent and reliable agent behavior while maintaining flexibility for intelligent adaptation.

**Version**: 0.2.0  
**Last Updated**: 2025-12-01

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119):

- **MUST** / **REQUIRED** / **SHALL**: Absolute requirement
- **MUST NOT** / **SHALL NOT**: Absolute prohibition
- **SHOULD** / **RECOMMENDED**: Valid reasons may exist to ignore in particular circumstances, but implications must be understood
- **SHOULD NOT** / **NOT RECOMMENDED**: Valid reasons may exist when behavior is acceptable, but implications must be understood
- **MAY** / **OPTIONAL**: Truly optional item

---

## SOP-001: Development Setup and Validation

**Purpose**: Initialize development environment and validate setup for paper-scanner project.

### Parameters
- `workspace_path` (REQUIRED): Path to paper-scanner repository
- `python_version` (OPTIONAL): Target Python version (default: 3.11)
- `install_dev_deps` (OPTIONAL): Install development dependencies (default: true)

### Prerequisites
- Python 3.11+ installed
- `uv` package manager available
- Git repository cloned

### Steps

#### Step 1: Validate Environment
1. Agent MUST verify workspace_path exists and contains `pyproject.toml`
2. Agent MUST check Python version is >= 3.11
3. Agent MUST verify `uv` command is available in PATH
4. Agent SHOULD document current Python version and uv version

#### Step 2: Install Dependencies
1. Agent MUST run `uv sync` to install core dependencies
2. If install_dev_deps is true, agent MUST run `uv sync --all-groups`
3. Agent MUST verify installation succeeded without errors
4. Agent SHOULD list installed package versions

#### Step 3: Validate Installation
1. Agent MUST run `make test` to verify tests pass
2. Agent MUST run `make lint` to verify code quality checks pass
3. Agent MAY run `make type-check` to verify type annotations
4. Agent MUST document any test or lint failures

#### Step 4: Environment Configuration
1. If `.env` file does not exist, agent SHOULD create it from `.env.example`
2. Agent MUST warn if `ANTHROPIC_API_KEY` is not set
3. Agent MAY prompt for API key if interactive mode enabled

### Success Criteria
- All dependencies installed successfully
- All tests pass
- Linting produces no errors
- Environment variables configured

### Failure Handling
- If Python version < 3.11, agent MUST report error and MUST NOT proceed
- If tests fail, agent MUST report failed tests and SHOULD suggest fixes
- If lint fails, agent SHOULD run `make format` and retry

---

## SOP-002: Feature Implementation Workflow

**Purpose**: Implement new features following project standards with test-driven development.

### Parameters
- `feature_name` (REQUIRED): Short descriptive name for the feature
- `feature_description` (REQUIRED): Detailed description of requirements
- `target_component` (REQUIRED): Which component to modify (core, tools, tests)
- `update_docs` (OPTIONAL): Update documentation (default: true)
- `interaction_mode` (OPTIONAL): "interactive" or "auto" (default: "interactive")

### Prerequisites
- Development environment validated (SOP-001)
- Working on a feature branch (`feat/feature-name`)

### Steps

#### Step 1: Branch Creation and Planning
1. Agent MUST verify current branch is not `main`
2. If not on feature branch, agent MUST create branch: `git checkout -b feat/{feature_name}`
3. Agent MUST document feature requirements in `.sop/planning/{feature_name}.md`
4. Agent SHOULD analyze existing code structure to understand integration points
5. Agent MUST identify files that need modification

#### Step 2: Test Development (Test-Driven Development)
1. Agent MUST create test file in `tests/unit/test_{feature_name}.py`
2. Agent MUST write failing tests that describe expected behavior
3. Tests MUST follow existing test patterns in the codebase
4. Agent MUST run tests to verify they fail: `make test`
5. If interaction_mode is "interactive", agent SHOULD request review of tests

#### Step 3: Implementation
1. Agent MUST implement minimal code to make tests pass
2. Implementation MUST follow existing code patterns:
   - Use argparse for CLI tools
   - Follow stdin/stdout pattern for JSONLines processing
   - Add type annotations
   - Include docstrings
3. Agent MUST run tests frequently during implementation
4. Agent SHOULD commit working increments with descriptive messages

#### Step 4: Code Quality Verification
1. Agent MUST run `make format` to format code
2. Agent MUST run `make lint` and fix any errors
3. Agent SHOULD run `make type-check` and address type issues
4. Agent MUST ensure all tests pass: `make test`
5. Agent MAY add additional edge case tests

#### Step 5: Documentation Updates
1. If update_docs is true, agent MUST update relevant documentation:
   - Add tool to README.md if new CLI tool created
   - Update CLAUDE.md if workflow patterns changed
   - Add docstrings to all public functions
2. Agent MUST update CHANGELOG.md with new feature in `### Added` section
3. Agent MUST update version in `src/paper_scanner/__init__.py` (increment MINOR)
4. Agent SHOULD update README.md badges if version changed

#### Step 6: Final Validation
1. Agent MUST run full test suite: `make test`
2. Agent MUST verify linting passes: `make lint`
3. Agent MUST review all modified files for completeness
4. If interaction_mode is "interactive", agent MUST present summary for review
5. Agent SHOULD suggest PR description text

### Success Criteria
- All tests pass
- Linting produces no errors
- Documentation updated
- CHANGELOG.md updated
- Version incremented appropriately

### Failure Handling
- If tests fail after implementation, agent MUST debug and fix
- If lint errors persist, agent SHOULD request clarification
- If version conflict detected, agent MUST resolve before proceeding

---

## SOP-003: Bug Fix Workflow

**Purpose**: Fix bugs following best practices with regression test coverage.

### Parameters
- `bug_description` (REQUIRED): Description of the bug behavior
- `bug_reproduction` (OPTIONAL): Steps to reproduce
- `affected_files` (OPTIONAL): Files suspected to contain bug
- `interaction_mode` (OPTIONAL): "interactive" or "auto" (default: "interactive")

### Prerequisites
- Development environment validated (SOP-001)
- Working on a fix branch (`fix/bug-description`)

### Steps

#### Step 1: Bug Analysis and Branch Setup
1. Agent MUST verify current branch is not `main`
2. If not on fix branch, agent MUST create branch: `git checkout -b fix/{bug-name}`
3. Agent MUST document bug details in `.sop/planning/fix-{bug-name}.md`
4. Agent SHOULD search codebase for related functionality
5. If affected_files provided, agent MUST examine those files first

#### Step 2: Reproduction Test Creation
1. Agent MUST create or modify test that reproduces the bug
2. Test MUST fail before fix is applied
3. Agent MUST run test to verify it captures the bug: `make test`
4. Agent MUST document expected vs actual behavior
5. If interaction_mode is "interactive", agent SHOULD confirm reproduction

#### Step 3: Root Cause Analysis
1. Agent MUST identify root cause by analyzing:
   - Relevant source code
   - Existing tests
   - Code patterns and dependencies
2. Agent SHOULD trace execution path that leads to bug
3. Agent MUST document root cause in planning document
4. Agent MAY identify related potential issues

#### Step 4: Fix Implementation
1. Agent MUST implement minimal fix for root cause
2. Fix MUST NOT introduce breaking changes
3. Agent MUST maintain existing code patterns and style
4. Agent MUST run tests frequently during fix implementation
5. Agent MUST verify reproduction test now passes

#### Step 5: Regression Testing
1. Agent MUST run full test suite: `make test`
2. Agent MUST verify no existing tests were broken
3. Agent MAY add additional tests for edge cases
4. Agent MUST ensure test coverage for fixed code

#### Step 6: Code Quality and Documentation
1. Agent MUST run `make format`
2. Agent MUST run `make lint` and fix any issues
3. Agent MUST update CHANGELOG.md with fix in `### Fixed` section
4. Agent MUST update version in `src/paper_scanner/__init__.py` (increment PATCH)
5. Agent SHOULD add code comments explaining fix if non-obvious

#### Step 7: Validation
1. Agent MUST run all quality checks:
   - `make test`
   - `make lint`
   - `make type-check`
2. If interaction_mode is "interactive", agent MUST present summary
3. Agent SHOULD suggest PR description with bug details and fix explanation

### Success Criteria
- Bug reproduction test created and passes after fix
- All existing tests still pass
- No new lint errors introduced
- CHANGELOG.md updated
- Version incremented appropriately

### Failure Handling
- If fix causes test regressions, agent MUST revise approach
- If root cause unclear, agent SHOULD request more information
- If fix requires breaking changes, agent MUST escalate for discussion

---

## SOP-004: Code Review and PR Preparation

**Purpose**: Prepare code changes for pull request review.

### Parameters
- `branch_name` (REQUIRED): Name of feature/fix branch
- `pr_title` (OPTIONAL): Pull request title
- `related_issues` (OPTIONAL): Related GitHub issue numbers

### Prerequisites
- All code changes committed
- All tests passing
- Documentation updated

### Steps

#### Step 1: Pre-Review Validation
1. Agent MUST verify current branch is not `main`
2. Agent MUST run full test suite: `make test`
3. Agent MUST run linting: `make lint`
4. Agent MUST run type checking: `make type-check`
5. All checks MUST pass before proceeding

#### Step 2: Change Analysis
1. Agent MUST run `git status` to list modified files
2. Agent MUST review each modified file for:
   - Unintended changes
   - Debug statements or temporary code
   - Proper formatting
   - Complete documentation
3. Agent SHOULD verify CHANGELOG.md updated appropriately
4. Agent SHOULD verify version number updated correctly

#### Step 3: Commit Quality Review
1. Agent MUST review commit messages for clarity
2. Commit messages SHOULD follow format: `{type}: {description}`
3. Types MUST be: feat, fix, docs, test, refactor, chore
4. Agent MAY suggest squashing commits if history is messy

#### Step 4: Documentation Verification
1. Agent MUST verify README.md updated if new features added
2. Agent MUST verify CLAUDE.md updated if workflows changed
3. Agent MUST verify all public functions have docstrings
4. Agent SHOULD check for broken links in documentation

#### Step 5: PR Description Generation
1. Agent MUST generate PR description including:
   - Summary of changes
   - Motivation and context
   - Testing performed
   - Related issues (if provided)
   - Breaking changes (if any)
2. Agent SHOULD include test results summary
3. Agent SHOULD highlight any areas needing special review

#### Step 6: Final Checklist
1. Agent MUST verify checklist completion:
   - [ ] Tests added/updated and passing
   - [ ] Code linted and formatted
   - [ ] Type checking passes
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated
   - [ ] Version number incremented
   - [ ] No debug code or TODOs
   - [ ] Commit messages clear
2. Agent MUST report any incomplete items

### Success Criteria
- All validation checks pass
- PR description generated
- All documentation complete
- Commit history clean

### Failure Handling
- If validation fails, agent MUST identify and report issues
- Agent SHOULD suggest fixes for common issues
- Agent MUST NOT proceed with PR if critical checks fail

---

## SOP-005: Parser Update and Testing

**Purpose**: Update AcademicPaperParser to handle new markdown formatting variations.

### Parameters
- `format_example` (REQUIRED): Example of new format to support
- `format_description` (REQUIRED): Description of formatting pattern
- `backwards_compatible` (OPTIONAL): Maintain compatibility (default: true)

### Prerequisites
- Development environment validated (SOP-001)
- Working on appropriate branch (feat/ or fix/)

### Steps

#### Step 1: Format Analysis
1. Agent MUST analyze format_example to identify pattern
2. Agent MUST compare with existing supported formats in parser
3. Agent MUST determine if regex pattern modification or new pattern needed
4. Agent SHOULD document format requirements in `.sop/planning/parser-update.md`

#### Step 2: Test Case Creation
1. Agent MUST create test case in `tests/unit/test_advanced_section_parser.py`
2. Test MUST include format_example as input
3. Test MUST specify expected parsed output
4. Agent MUST run test to verify it fails before implementation
5. If backwards_compatible is true, agent MUST verify existing tests still pass

#### Step 3: Parser Modification
1. Agent MUST modify `src/paper_scanner/core/advanced_section_parser.py`
2. If updating regex, agent MUST:
   - Test pattern with format_example
   - Ensure pattern doesn't break existing formats
   - Add comments explaining pattern
3. Agent MAY add format-specific extraction logic if needed
4. Agent MUST maintain existing method signatures

#### Step 4: Comprehensive Testing
1. Agent MUST run new test to verify it passes
2. Agent MUST run full test suite: `make test`
3. If backwards_compatible is true, agent MUST verify all existing tests pass
4. Agent SHOULD test with various input variations
5. Agent MAY add edge case tests

#### Step 5: Documentation
1. Agent MUST update docstrings to document new format support
2. Agent SHOULD add code comments explaining regex patterns
3. Agent MUST update CLAUDE.md with format handling details
4. Agent SHOULD add examples to parser documentation

### Success Criteria
- New format successfully parsed
- All tests pass including existing ones
- Code documented
- No regressions in existing functionality

### Failure Handling
- If new pattern breaks existing tests, agent MUST revise approach
- If pattern too complex, agent SHOULD consider alternative parsing strategy
- Agent MUST NOT sacrifice backwards compatibility unless explicitly allowed

---

## SOP-006: Tool Addition Workflow

**Purpose**: Add new command-line tool to paper-scanner pipeline.

### Parameters
- `tool_name` (REQUIRED): Name of new tool (e.g., "file-validator")
- `tool_purpose` (REQUIRED): What the tool does
- `input_format` (REQUIRED): Input data format (e.g., "JSONLines")
- `output_format` (REQUIRED): Output data format
- `requires_api` (OPTIONAL): Requires external API (default: false)

### Prerequisites
- Development environment validated (SOP-001)
- Working on feature branch (`feat/new-tool-{tool_name}`)

### Steps

#### Step 1: Tool Design
1. Agent MUST create design document in `.sop/planning/tool-{tool_name}.md`
2. Document MUST include:
   - Purpose and use case
   - Input/output specifications
   - Command-line arguments
   - Integration with existing pipeline
3. Agent SHOULD identify existing tools with similar patterns to follow

#### Step 2: Implementation
1. Agent MUST create `src/paper_scanner/tools/{tool_name}.py`
2. Tool MUST follow standard structure:
   - Shebang: `#!/usr/bin/env -S python`
   - Module docstring
   - Imports (include `argparse`, `sys`)
   - Main functionality class/functions
   - `main()` function with argparse
   - `if __name__ == "__main__":` block
3. Tool MUST support stdin/stdout for pipeline compatibility
4. If requires_api is true, agent MUST add dotenv loading
5. Agent MUST add type annotations
6. Agent MUST include comprehensive docstrings

#### Step 3: CLI Interface
1. Agent MUST implement argparse with arguments:
   - `-i/--input` for input (default: stdin)
   - `-o/--output` for output (default: stdout)
   - `-v/--verbose` for verbose mode
   - Additional tool-specific arguments
2. Help text MUST be clear and complete
3. Agent MUST handle stdin/stdout appropriately
4. Agent SHOULD add input validation

#### Step 4: Testing
1. Agent MUST create `tests/unit/test_{tool_name}.py`
2. Tests MUST cover:
   - Basic functionality
   - Edge cases
   - Error handling
   - Input validation
3. Agent MUST ensure tests pass: `make test`

#### Step 5: Integration
1. Agent MUST add tool to `pyproject.toml` `[project.scripts]`:
   ```toml
   {tool_name} = "paper_scanner.tools.{tool_name}:main"
   ```
2. Agent MUST add any new dependencies to `dependencies` list
3. Agent MUST run `uv sync` to update environment

#### Step 6: Documentation
1. Agent MUST add tool to README.md:
   - Tool description in "Core Tools" section
   - Usage example in "Basic Usage" section
2. Agent MUST add tool to CLAUDE.md "Tools" list
3. Agent MUST update CHANGELOG.md with new feature
4. Agent MUST increment MINOR version in `__init__.py`
5. Agent SHOULD create usage examples

### Success Criteria
- Tool implemented following patterns
- Tests pass
- Tool accessible via command line
- Documentation complete
- Integrates with pipeline

### Failure Handling
- If tool doesn't follow patterns, agent MUST revise to match
- If tests fail, agent MUST debug and fix
- If integration issues occur, agent MUST resolve before proceeding

---

## SOP-007: Dependency Management

**Purpose**: Add, update, or remove project dependencies safely.

### Parameters
- `action` (REQUIRED): "add", "update", or "remove"
- `package_name` (REQUIRED): Name of package
- `package_version` (OPTIONAL): Specific version or constraint
- `is_dev_dependency` (OPTIONAL): Development dependency (default: false)

### Prerequisites
- Development environment validated (SOP-001)
- Working on appropriate branch (feat/ or chore/)

### Steps

#### Step 1: Dependency Analysis
1. Agent MUST verify package exists on PyPI
2. Agent SHOULD check package for:
   - Active maintenance
   - License compatibility (Apache 2.0 compatible)
   - Security vulnerabilities
3. Agent MUST check if package already in dependencies
4. Agent SHOULD identify transitive dependencies

#### Step 2: Configuration Update
1. For action "add":
   - Agent MUST add to `pyproject.toml` dependencies or dev group
   - Agent SHOULD use version constraint (e.g., `>=1.0.0`)
2. For action "update":
   - Agent MUST update version in `pyproject.toml`
   - Agent MUST note version in CHANGELOG.md
3. For action "remove":
   - Agent MUST remove from `pyproject.toml`
   - Agent MUST verify no code depends on package

#### Step 3: Environment Update
1. Agent MUST run `uv sync` (or `uv sync --all-groups` for dev deps)
2. Agent MUST verify sync completes without errors
3. Agent SHOULD verify installed version matches specification

#### Step 4: Testing and Validation
1. Agent MUST run full test suite: `make test`
2. Agent MUST verify no tests broken by dependency change
3. Agent MUST run linting: `make lint`
4. Agent SHOULD run type checking: `make type-check`
5. For new dependencies, agent SHOULD verify functionality works

#### Step 5: Documentation
1. Agent MUST update CHANGELOG.md:
   - Add under `### Changed` for updates
   - Add under `### Added` for new dependencies
   - Add under `### Removed` for removals
2. Agent SHOULD update README.md if user-facing impact
3. Agent MAY update version number based on change impact

#### Step 6: Security and Compatibility Check
1. Agent SHOULD run security audit if available
2. Agent MUST verify license compatibility
3. Agent SHOULD check Python version requirements
4. Agent MUST ensure no conflicts with existing dependencies

### Success Criteria
- Dependency updated in pyproject.toml
- Environment synchronized
- All tests pass
- Documentation updated

### Failure Handling
- If version conflicts occur, agent MUST resolve or report
- If tests fail, agent MUST investigate if dependency-related
- If security issues found, agent MUST report and SHOULD suggest alternatives

---

## Appendix A: File Structure Reference

```
paper-scanner/
├── .claude                          # Agent configuration
├── .env                            # Environment variables (not committed)
├── .env.example                    # Environment template
├── CHANGELOG.md                    # Version history
├── CLAUDE.md                       # Agent development guidelines
├── LICENSE                         # Apache 2.0 license
├── Makefile                        # Development commands
├── README.md                       # User documentation
├── SOP.md                          # This file
├── pyproject.toml                  # Project configuration
├── src/paper_scanner/
│   ├── __init__.py                # Version definition
│   ├── core/
│   │   ├── __init__.py
│   │   └── advanced_section_parser.py
│   └── tools/
│       ├── __init__.py
│       ├── file_merge.py
│       ├── file_parser.py
│       ├── file_processor.py
│       ├── file_reader.py
│       ├── file_scanner.py
│       └── file_timer.py
└── tests/
    └── unit/
        └── test_advanced_section_parser.py
```

## Appendix B: Common Error Resolutions

### Import Errors
- MUST verify package in dependencies
- MUST run `uv sync`
- SHOULD check Python version compatibility

### Test Failures
- MUST isolate failing test
- MUST verify test setup correct
- SHOULD check for environment differences

### Linting Errors
- SHOULD run `make format` first
- MUST address reported issues
- MAY suppress with inline comments if justified

### Version Conflicts
- MUST check dependency constraints
- SHOULD use `uv` resolver to identify conflicts
- MAY need to adjust version specifications

## Appendix C: Workflow Chaining

SOPs can be chained for complex workflows:

1. **New Feature Development**:
   - SOP-001 (Setup) → SOP-002 (Feature) → SOP-004 (PR Prep)

2. **Bug Fix**:
   - SOP-001 (Setup) → SOP-003 (Fix) → SOP-004 (PR Prep)

3. **Parser Enhancement**:
   - SOP-001 (Setup) → SOP-005 (Parser) → SOP-004 (PR Prep)

4. **New Tool Addition**:
   - SOP-001 (Setup) → SOP-006 (Tool) → SOP-007 (Dependencies) → SOP-004 (PR Prep)

---

**Document Control**
- Maintained by: Ilja Heitlager
- Review Frequency: Each minor version release
- Last Review: 2025-12-01
