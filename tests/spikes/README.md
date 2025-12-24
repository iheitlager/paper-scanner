# Spike Tests: Hypothesis-Driven Experimentation

This directory contains hypothesis-driven exploratory tests for evaluating new technologies, approaches, and architectural decisions before committing to implementation. Each spike follows a rigorous experimental methodology to answer specific research questions.

## Spike Index

| Spike | Hypothesis | Date | Status | Outcome |
|-------|-----------|------|--------|---------|
| [001_first_tests](001_first_tests/) | Batch JSON processing with flush semantics is viable | 2024-07-19 | Complete | ✅ Confirmed |
| [002_browser](002_browser/) | PostgreSQL + Flask provides scalable browser interface | 2024-12-02 | Integrated | ✅ Confirmed |
| [003_local_llm](003_local_llm/) | Ollama local LLM integration achieves acceptable latency | 2024-12-03 | Integrated | ✅ Confirmed |
| [004_embedding](004_embedding/) | Vector embeddings enable semantic paper similarity search | 2024-12-04 | In Progress | ⏳ Testing |
| [006_bibtex](006_bibtex/) | Crossref API can populate missing reference metadata | 2024-12-06 | Integrated | ✅ Confirmed |
| [007_new_approach](007_new_approach/) | Pythonic fluent API is more maintainable than YAML | 2024-12-11 | Completed | ⚠️  Deferred |
| [008_fetchers](008_fetchers/) | Multi-source metadata fetching improves coverage | 2024-12-22 | Integrated | ✅ Confirmed |
| [009_retrieve_pdf](009_retrieve_pdf/) | DOI-based PDF retrieval achieves >80% success rate | 2024-12-19 | Integrated | ✅ Confirmed |
| [010_cite_key](010_cite_key/) | Author+Year cite keys prevent collision better than UUIDs | 2025-12-22 | Complete | ✅ Confirmed |
| [011_step_executor](011_step_executor/) | Plugin-based step architecture enables extensibility | 2025-12-20 | In Progress | ⏳ Testing |

## Methodology: Hypothesis-Driven Experimentation

Each spike follows a structured experimental methodology:

```
Problem Statement → Hypothesis → Research Design → Experiment → Analysis → Conclusion
```

### 1. Problem Statement
Clear definition of the decision or question being addressed.

### 2. Hypothesis
Testable prediction (usually binary):
- **Hypothesis**: "Technology/approach X will achieve Y with Z constraints"
- **Null Hypothesis**: "Technology/approach X will NOT achieve Y"

### 3. Research Design
- **Success Criteria**: Quantifiable metrics (latency, accuracy, compatibility)
- **Test Strategy**: What tests prove/disprove the hypothesis?
- **Constraints**: Budget (time, resources), scope limitations
- **Control Variables**: What are we holding constant?

### 4. Experiment
Execute tests, collect metrics, document findings as discovered.

### 5. Analysis
Compare results against success criteria. Interpret findings.

### 6. Conclusion
Accept/reject hypothesis. Document decision pathway.

---

## Spike Structure

### Directory Layout

```
tests/spikes/
├── NNN_descriptive_name/
│   ├── README.md           # Hypothesis statement and findings
│   ├── test_NNN_main.py    # Primary test executable
│   ├── fixtures/           # Test data (optional)
│   └── outputs/            # Results/logs (optional)
```

### Required Documentation Format

Every spike test MUST contain a `README.md` with this structure:

```markdown
# Spike NNN: [Title]

**Branch**: `spike/branch-name`  
**Date**: YYYY-MM-DD  
**Author**: Name  
**Status**: In Progress | Complete | Integrated | Rejected | Deferred

---

## 1. Problem Statement

[What decision are we making? What gap in knowledge exists?]

Example:
"We need to determine if PostgreSQL can scale to 1M+ documents while maintaining <100ms query latency for full-text search across all papers."

---

## 2. Hypothesis

**Primary Hypothesis (H1)**:  
[Testable prediction]

Example:
"PostgreSQL with full-text search indices will achieve <100ms query latency on 1M+ documents with keyword queries."

**Null Hypothesis (H0)**:  
[Opposite prediction]

Example:
"PostgreSQL will NOT achieve <100ms query latency or query latency will exceed 100ms."

---

## 3. Research Design

### Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| Query Latency | <100ms | User-facing UI responsiveness |
| Index Size | <2GB | Storage/cost constraints |
| Update Latency | <500ms | Re-indexing performance |
| False Positive Rate | <5% | Search result quality |

### Experimental Design

- **Unit Under Test**: PostgreSQL full-text search
- **Test Environment**: [Docker/Local/Cloud]
- **Dataset**: [Type and size of test data]
- **Duration**: [How long will tests run?]
- **Replicates**: [How many times to repeat?]
- **Control Conditions**: [What variables are held constant?]

### Test Strategy

1. **Baseline Test**: Measure current state (if applicable)
2. **Configuration Test**: Try different configurations
3. **Load Test**: Stress test with production-like load
4. **Edge Case Test**: Boundary conditions

---

## 4. Experiment Execution

### Setup
```bash
# Instructions to reproduce
```

### Results

#### Test 1: Basic Query Performance
- **Condition**: 100K documents, simple keyword query
- **Result**: 45ms average latency ✅
- **Notes**: Within target range

#### Test 2: Complex Query Performance
- **Condition**: 1M documents, multi-keyword phrase query
- **Result**: 250ms average latency ⚠️
- **Notes**: Exceeds target by 2.5x

#### Test 3: Index Size
- **Condition**: 1M documents with full-text index
- **Result**: 1.2GB index size ✅
- **Notes**: Within acceptable range

---

## 5. Analysis

### Hypothesis Evaluation

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Query Latency (simple) | <100ms | 45ms | ✅ PASS |
| Query Latency (complex) | <100ms | 250ms | ❌ FAIL |
| Index Size | <2GB | 1.2GB | ✅ PASS |

### Key Findings

**Finding 1**: [What did we discover?]
- Evidence: [Supporting data]
- Interpretation: [What does this mean?]

**Finding 2**: [Next finding]

### Limitations

- [What wasn't tested?]
- [What are the constraints?]
- [What assumptions did we make?]

---

## 6. Conclusion

### Hypothesis Verdict

**Result**: ✅ ACCEPTED | ⚠️ PARTIALLY ACCEPTED | ❌ REJECTED

**Summary**: [1-2 sentences on whether hypothesis was supported]

### Decision

Based on findings:
- **Proceed**: [If hypothesis accepted, what's next?]
- **Iterate**: [If partially accepted, what to try next?]
- **Reject**: [If hypothesis failed, why and what alternative to try?]
- **Defer**: [If good idea but not now, when to revisit?]

---

## 7. Recommendations

### Immediate Action
1. [Specific next step]
2. [Specific next step]

### If Proceeding
- Create feature branch: `feat/feature-name`
- Create ADR: `ADR-NNN: [Decision Title]`
- Estimate effort: [T-shirt size]

### If Rejected
- Document why in CHANGELOG
- Suggest alternative approach
- Note for future reference

---

## 8. References

- [Documentation link]
- [Benchmark article]
- [Related ADR or issue]

---

## Test Results

**Last Run**: YYYY-MM-DD HH:MM UTC  
**Environment**: [Python X.X, PostgreSQL X, Docker, etc.]  
**Status**: ✅ All tests pass | ⚠️ Some failures | ❌ Major issues

```

---

## Spike Test Code Structure

### Minimal Test File (`test_NNN_main.py`)

```python
"""
Spike NNN: [Title]

Hypothesis: [One line hypothesis]
"""

import pytest
from hypothesis import given, strategies as st


class TestBasicFunctionality:
    """Core functionality tests."""
    
    def test_proves_hypothesis(self):
        """Validates the primary hypothesis."""
        # Setup
        # Act
        # Assert
        pass


class TestPerformance:
    """Benchmark and performance tests."""
    
    def test_meets_latency_requirement(self, benchmark):
        """Query latency <100ms."""
        # Use pytest-benchmark for measurements
        pass
    
    def test_meets_throughput_requirement(self, benchmark):
        """Throughput requirement."""
        pass


class TestEdgeCases:
    """Boundary condition tests."""
    
    @given(st.integers(min_value=0, max_value=1000000))
    def test_large_dataset_handling(self, size):
        """Hypothesis property test for various sizes."""
        pass


if __name__ == "__main__":
    # Can run tests directly
    pytest.main([__file__, "-v", "--tb=short"])
```

---

## Running Spike Tests

```bash
# Run all spikes with results
uv run pytest tests/spikes/ -v --tb=short

# Run specific spike
uv run pytest tests/spikes/001_tree_sitter_evaluation/ -v

# Run with benchmarking
uv run pytest tests/spikes/002_browser/ -v --benchmark-only

# Generate spike report
uv run pytest tests/spikes/ --html=spike_report.html --self-contained-html
```

---

## Spike Outcomes and Pathways

### Pathway 1: Hypothesis Confirmed → Feature Branch

```
spike/tree-sitter-evaluation (findings support approach)
    ↓
ADR-010: Use Tree-Sitter for Multi-Language Parsing
    ↓
feat/tree-sitter-integration (production implementation)
    ↓
Merge to main with comprehensive tests
```

**Action**:
1. Create ADR referencing spike findings
2. Create feature branch from spike
3. Rewrite with production quality standards
4. Full test coverage before merge

### Pathway 2: Hypothesis Partially Confirmed → Refinement

```
spike/postgres-performance (latency mostly acceptable)
    ↓
feat/postgres-index-optimization (refine configuration)
    ↓
Re-run spike with optimized setup
    ↓
If confirmed, proceed to feature branch
```

**Action**:
1. Identify what partially failed
2. Try alternative configuration or technology
3. Create follow-up spike or feature branch

### Pathway 3: Hypothesis Rejected → Document and Archive

```
spike/graphql-integration (performance unacceptable)
    ↓
Close spike branch, document findings
    ↓
Add to CHANGELOG rejected approaches
    ↓
Keep test for historical reference
    ↓
Suggest alternative in recommendations
```

**Action**:
1. Document why hypothesis failed clearly
2. Note in CHANGELOG under "Investigated but Rejected"
3. Keep test for future reference
4. Recommend alternative approach

### Pathway 4: Good Idea, Wrong Timing → Deferred

```
spike/event-driven-arch (confirmed to work, but not needed now)
    ↓
Document decision and timing constraints
    ↓
Reference in roadmap for v2.0
    ↓
Archive spike for future use
```

**Action**:
1. Document feasibility clearly
2. Note why we're deferring
3. Add to future roadmap with estimated timeline
4. Periodically review for timing shift

---

## When to Create a Spike

✅ **CREATE SPIKE WHEN:**
- Making significant architectural decision
- Evaluating new technology/framework
- Investigating performance bottleneck
- Exploring alternative implementation strategy
- Testing feasibility of requested feature
- Assessing integration complexity

❌ **DON'T CREATE SPIKE WHEN:**
- Obvious solution exists
- Decision is low-impact
- Similar spike already exists
- Feature is already well-understood

---

## Spike Development Workflow

### 1. Initialize Spike
```bash
# Create branch
git checkout -b spike/NNN-descriptive-name

# Create directory
mkdir -p tests/spikes/NNN_descriptive_name

# Create template files
touch tests/spikes/NNN_descriptive_name/README.md
touch tests/spikes/NNN_descriptive_name/test_NNN_main.py
```

### 2. Document Hypothesis
Write README.md with problem statement and hypothesis BEFORE running experiments.

### 3. Execute Experiments
Run tests, collect data, update findings in README as discoveries are made.

### 4. Analyze Results
Compare against success criteria, document conclusions.

### 5. Decide and Communicate
Determine next action and update spike status.

### 6. Archive
Keep spike indefinitely as historical record.

---

## Best Practices

### DO ✅
- **Document hypothesis first** before running experiments
- **Record results as discovered** - don't wait until end
- **Be honest about findings** - both positive and negative
- **Test boundaries** - not just happy path
- **Include failures** - they're informative
- **State assumptions** - make implicit knowledge explicit
- **Recommend action** - don't just report findings
- **Reference related work** - spikes, ADRs, issues

### DON'T ❌
- Start coding before hypothesis is clear
- Ignore results that contradict hypothesis
- Over-engineer spike tests
- Spend weeks on single spike
- Make it production code
- Forget to document constraints and limitations
- Leave spike status ambiguous

---

## Integration with ADRs

Spikes inform Architecture Decision Records:

```markdown
# ADR-010: Use PostgreSQL Full-Text Search

## Context
Investigation in spike/001_postgres_performance (see 
tests/spikes/001_first_tests/README.md) confirmed that
PostgreSQL full-text search achieves <100ms latency on
typical datasets...
```

Every spike that leads to decision should reference ADR, and every ADR making technology decision should reference supporting spike.

---

## Archive and Future Reference

- **Keep all spikes indefinitely** - they're learning artifacts
- **Historical record** - document what we've tried
- **Future reconsideration** - situations change, may revisit
- **Knowledge transfer** - new team members see past explorations
- **Pattern recognition** - helps identify recurring problems

---

## FAQ

**Q: Can spike tests be messy?**  
A: Yes, absolutely. They're exploratory. Quality matters less than learning.

**Q: Do spikes need full test coverage?**  
A: No - just enough to prove/disprove hypothesis.

**Q: What if hypothesis is ambiguous?**  
A: Rewrite it until it's testable and binary.

**Q: How long should a spike take?**  
A: 1-5 days typically. If it's taking weeks, it should be a feature.

**Q: Can we merge spike code to main?**  
A: No. If findings justify it, create feature branch and rewrite properly.

**Q: What if results are inconclusive?**  
A: Document constraints that prevented conclusion. Recommend refinements.

---

## Template Reference

Create new spike from template:
```bash
cp -r tests/spikes/000_template/ tests/spikes/NNN_descriptive_name/
# Edit README.md and test_NNN_main.py
```
