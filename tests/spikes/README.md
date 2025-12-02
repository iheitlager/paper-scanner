# Spike Tests

This directory contains exploratory tests for future features and experimental work. Spikes help us evaluate new technologies, approaches, or ideas before committing to implementation.

## Spike Index

| Spike | Description | Addition Date | Status |
|-------|-------------|--------------|--------|
| [001_first_tests](001_first_tests/README.md) | Initial batch processing, flush, JSON, and parser experiments | 2025-07-19 | Complete |
| [002_browser](002_browser/README.md) | Flask + React frontend with PostgreSQL and Docker for file browser | 2025-12-02 | Integrated |

## Purpose

- **Exploration**: Try out new ideas and technologies
- **Evaluation**: Compare different approaches
- **Proof of Concept**: Demonstrate feasibility
- **Documentation**: Record findings for future reference
- **Decision Support**: Inform architecture decisions and ADRs

## When to Create Spike Tests

Create a spike test when:
- Evaluating a new library or framework
- Exploring alternative implementations
- Investigating performance optimizations
- Testing feasibility of a feature
- Researching new technologies



## Spike Workflow

### 1. Create Spike Branch

```bash
git checkout -b spike/tree-sitter-evaluation
```

**Important**:
- Branch prefix: `spike/`
- **NO version update**
- No requirement to merge to main

### 2. Create Spike Test Folder

Naming: `NNN_descriptive_name` where NNN is a sequential number

```python
# mkdir tests/spikes/001_tree_sitter_evaluation/
```

### 3. Document Exploration in README.md

```python
"""
Spike: Evaluate tree-sitter for multi-language parsing.

Branch: spike/tree-sitter-evaluation
Date: 2025-11-19
Author: Claude

## Goals

Explore whether tree-sitter could replace our current language-specific
parsers with a unified multi-language solution.

## Research Questions

1. How does tree-sitter performance compare to ast module?
2. Does it preserve comments and formatting?
3. How difficult is multi-language support?
4. What's the installation/deployment complexity?

## Approach

- Install tree-sitter-python
- Parse sample Python files
- Compare performance with current parser
- Test comment preservation
- Evaluate API complexity

## Findings

### Performance
- ✅ 3x faster than ast module on large files
- ✅ Handles 10K LOC in ~50ms vs ~150ms

### Comment Preservation
- ✅ Comments are preserved in syntax tree
- ✅ Easy to extract and associate with nodes

### Multi-Language Support
- ✅ Excellent - same API for all languages
- ✅ Just need language-specific grammar
- ⚠️  Grammars need to be installed separately

### API Complexity
- ⚠️  More complex than ast module
- ✅ Well documented
- ✅ Active community

### Installation
- ⚠️  Requires C compiler for building
- ⚠️  Language grammars are separate packages
- ❌ Harder to deploy than pure Python

## Conclusions

Tree-sitter is promising for v2.0 multi-language support:

**Pros:**
- Significantly faster
- Unified API for all languages
- Good comment preservation
- Active development

**Cons:**
- C dependency complicates deployment
- More complex API than ast
- Would require rewriting existing parser

## Recommendations

1. ⏸️  Not for v0.x - too disruptive
2. ✅ Consider for v2.0 major rewrite
3. ✅ Create ADR if we decide to proceed
4. ✅ Keep monitoring project for improvements

## Next Steps

If we proceed:
1. Create ADR-0XX: Migration to tree-sitter
2. Create feat/tree-sitter-integration branch
3. Implement incrementally alongside current parsers
4. Deprecate old parsers after migration

## References

- [tree-sitter documentation](https://tree-sitter.github.io/tree-sitter/)
- [tree-sitter-python](https://github.com/tree-sitter/tree-sitter-python)
"""

import pytest

# Spike tests below...
```

## Spike Test Structure

### Filestructure

1. README.md with description and test hypothesis
2. `XXXX_main.py` with the experiment
3. `test_XXXX_experiment_name.py` with a minimal test to be included in `pytest`. We want the spike to evolve with us.

### Required Documentation

Every spike test MUST include:

```python
"""
Spike: <Title>

Branch: spike/<branch-name>
Date: <YYYY-MM-DD>
Author: <Name>

## Goals
[What are we trying to learn?]

## Research Questions
[Specific questions to answer]

## Approach
[How we'll explore this]

## Findings
[What we discovered - add as we go]

## Conclusions
[Summary of learnings]

## Recommendations
[What should we do next?]

## Next Steps
[If we proceed, what's the path?]

## References
[Links to docs, articles, etc.]
"""
```

### Test Code

Spike tests can be messy - that's okay:

```python
def test_basic_functionality():
    """Just prove it works."""
    # Quick and dirty proof of concept
    pass


def test_performance_comparison():
    """Rough benchmark."""
    import time
    # Compare approaches
    pass


def test_edge_case_that_concerns_us():
    """Check if our concern is valid."""
    pass
```

## Naming Convention

```
NNN_descriptive_name.py
```

Where:
- `NNN` = Sequential number (001, 002, 003, ...)
- `descriptive_name` = What you're exploring

Examples:
- `001_tree_sitter_evaluation`
- `002_graph_database_migration`
- `003_llm_integration_patterns`
- `004_performance_optimization_strategies`

## Spike Outcomes

Spikes can lead to different outcomes:

### 1. Feature Branch

```
spike/tree-sitter → feat/tree-sitter-integration
```

Findings are positive, create feature branch:
- Use spike as reference
- Create proper implementation
- Write ADR documenting decision
- Add comprehensive tests

### 2. Rejection

```
spike/graphql-schema → [Closed, not proceeding]
```

Findings show it's not viable:
- Document why in spike test
- Close spike branch
- Keep test for future reference
- Update CHANGELOG [Unreleased] with findings

### 3. Deferred

```
spike/performance-opt → [Deferred to v2.0]
```

Good idea but not now:
- Document findings
- Note in CHANGELOG
- Reference in roadmap
- Keep test for future

## Example Spike Tests

### Example 1: Library Evaluation

```python
# tests/spikes/001_esprima_vs_acorn/README.md
"""
Spike: Compare Esprima vs Acorn for JavaScript parsing.

Branch: spike/js-parser-comparison
Date: 2025-11-19

## Goals
Choose the best JavaScript parser for our needs.

## Findings

### Esprima
- ✅ More mature
- ✅ Better error messages
- ⚠️  Slower

### Acorn
- ✅ Faster
- ✅ Smaller
- ❌ Less helpful errors

## Conclusion
Choose Esprima for better developer experience.
"""
```

### Example 2: Performance Investigation

```python
# tests/spikes/002_graph_serialization_formats.py
"""
Spike: Compare JSON vs MessagePack vs Protocol Buffers.

Branch: spike/serialization-performance

## Findings
- JSON: Easy, slow, large
- MessagePack: Fast, compact, harder to debug
- Protocol Buffers: Fastest, smallest, most complex

## Conclusion
Stick with JSON for now. Add MessagePack as option later.
"""
```

### Example 3: Architecture Exploration

```python
# tests/spikes/003_event_driven_parsing.py
"""
Spike: Explore event-driven parser architecture.

Branch: spike/event-driven-arch

## Findings
- More complex than current approach
- Would enable streaming large files
- Not needed for current use cases

## Conclusion
Defer to v2.0 if we need to handle very large files.
"""
```

## Guidelines

### DO

✅ Document your exploration thoroughly
✅ Include findings as you discover them
✅ Note both successes and failures
✅ Provide clear conclusions
✅ Recommend next steps

### DON'T

❌ Worry about code quality (it's exploratory)
❌ Write comprehensive tests (just prove concepts)
❌ Spend time on edge cases
❌ Merge incomplete spikes to main

## Running Spike Tests

```bash
# Run all spikes
uv run pytest tests/spikes/

# Run specific spike test
uv run python tests/spikes/001_tree_sitter_evaluation/test_001.py

# Run specific spike
uv run python tests/spikes/001_tree_sitter_evaluation/001_main.py
```

## Relationship to ADRs

Spikes often inform ADRs:

```
1. Create spike branch
2. Run experiments in spike test
3. Document findings
4. If proceeding → Create ADR
5. Create feature branch
6. Reference spike in ADR
```

Example:
```markdown
# ADR-010: Use Tree-sitter for Multi-Language Parsing

## Context
Investigation in spike/tree-sitter-evaluation (see tests/spikes/001_tree_sitter_evaluation.py)
showed significant performance benefits...
```

## Archive Policy

- Keep all spikes indefinitely
- They serve as historical record
- Future developers can learn from past explorations
- May become relevant again later

## Questions?

- Spikes are meant to be exploratory
- Don't overthink them
- Document findings
- Help future decision making
