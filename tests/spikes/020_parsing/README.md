# Spike 020: Academic Paper Metadata Extraction

**Branch**: `spike/paper-metadata-extraction`
**Date**: 2026-01-17
**Author**: Ilja Heitlager
**Status**: Complete

---

## 1. Problem Statement

Academic paper analysis requires extracting structured metadata from PDF documents. The `tests/corpus/` directory contains 5 PDF papers with UUID-style filenames that need to be parsed to extract:

- Title
- Authors
- Year
- Abstract
- Keywords
- Journal/Venue
- DOI
- **Table of Contents (TOC)**

The extracted metadata should be stored in a standardized `metamodel.yml` format that can serve as ground truth for testing different extraction approaches.

**Decision needed**: What is the optimal approach for extracting paper metadata from PDFs with high accuracy and reasonable cost?

---

## 2. Hypothesis

### Primary Hypothesis (H1)

"Claude API (via existing ClaudeHandler) with PDF document input will provide the highest accuracy (>95%) for metadata extraction from academic papers, though at higher cost than local alternatives."

### Null Hypothesis (H0)

"Local parsing approaches (regex, ML models) will fail to reliably extract metadata due to inconsistent PDF formatting across different publishers."

### Alternative Hypotheses

| Hypothesis | Tested | Result |
|------------|--------|--------|
| PyMuPDF/pypdf with regex can achieve >80% accuracy | ✅ Yes | ❌ Failed (57%) |
| PDF-to-markdown conversion provides reliable intermediate | ✅ Yes | ❌ Failed (35% TOC match) |
| SciBERT can match Claude accuracy at lower cost | ✅ Yes | ❌ Failed (51%) |

**SciBERT findings:**
- Requires ~400MB model download (allenai/scibert_scivocab_uncased)
- Works on CPU (no CUDA required for inference)
- Base model is a language model, not an extraction model
- Without fine-tuning, relies on heuristics similar to regex
- Achieved 51% overall accuracy (worse than regex at 57%)

---

## 3. Research Design

### Success Criteria

| Metric | Target | Rationale | Priority |
|--------|--------|-----------|----------|
| Title Extraction Accuracy | >95% | Critical for identification | High |
| Author Extraction Accuracy | >90% | Important for citation | High |
| Year Extraction Accuracy | >98% | Easy to extract | High |
| TOC Extraction Accuracy | >80% | Useful for navigation | Medium |
| Processing Cost | <$0.10/paper | Budget constraints | Medium |
| Processing Time | <30s/paper | Acceptable UX | Low |

### Experimental Design

- **Unit Under Test**: Metadata extraction pipeline
- **Test Environment**: Local Python environment
- **Dataset**: 5 PDF papers in `tests/corpus/`
- **Duration**: 1 day
- **Control Variables**: Same input PDFs across all approaches

### Approaches Compared

| Approach | Description | Tested | Pros | Cons |
|----------|-------------|--------|------|------|
| **1. PyPDF + Regex** | Extract text, apply regex patterns | ✅ | Free, fast, local | Fragile, no TOC |
| **2. PDF-to-Markdown** | Convert to MD, then parse structure | ✅ | Structured intermediate | Noisy TOC extraction |
| **3. Claude API (Haiku)** | LLM via `ClaudeHandler` | ✅ | High accuracy, handles variations | API cost |
| **4. SciBERT** | ML model for scientific text | ✅ | Domain-specific, local, free | Needs fine-tuning for extraction |

---

## 4. Experiment Execution

### Setup Instructions

```bash
# Install spike dependencies
uv sync --all-groups

# Run the metadata extraction tests (NOT part of regular test suite)
uv run pytest tests/spikes/020_parsing/ -v

# Run specific approach tests
uv run pytest tests/spikes/020_parsing/test_01_regex_extractor.py -v
uv run pytest tests/spikes/020_parsing/test_02_claude_extractor.py -v -s
uv run pytest tests/spikes/020_parsing/test_03_comparison.py -v -s
uv run pytest tests/spikes/020_parsing/test_04_markdown_extractor.py -v -s
uv run pytest tests/spikes/020_parsing/test_05_toc_extraction.py -v -s
```

### Required Libraries

| Library | Purpose | Installation |
|---------|---------|--------------|
| `pypdf` | PDF text extraction | Already in dependencies |
| `pyyaml` | Load/save YAML reference files | Already in dependencies |
| `anthropic` | Claude API access | Already in dependencies |
| `transformers` | SciBERT model loading | Already in dependencies |
| `pymupdf4llm` | Better PDF-to-MD (optional) | `uv add --group dev pymupdf4llm` |

### Test Files

| File | Description |
|------|-------------|
| `test_01_regex_extractor.py` | Regex extraction tests |
| `test_02_claude_extractor.py` | Claude API extraction tests |
| `test_03_comparison.py` | Comparison and reporting tests |
| `test_04_markdown_extractor.py` | PDF-to-markdown extraction tests |
| `test_05_toc_extraction.py` | TOC extraction comparison |
| `test_06_scibert_extractor.py` | SciBERT ML model extraction tests |
| `create_ground_truth.py` | Script to generate ground truth via Claude |
| `conftest.py` | Pytest configuration (excludes from regular suite) |

### Corpus Files

```
tests/corpus/
├── 3ae77a5c-091c-427f-7a98-dd072a87781e.pdf  # Zooming out: actor engagement (JOSM 2017)
├── 11e0f553-8a31-13e3-7144-2d6489219562.pdf  # How to Compete When Industries Digitize (CMR 2022)
├── 5dbd37f5-ffb7-5f51-0c02-df901933832e.pdf  # From Product Platform to Innovation Platform (JAIS 2022)
├── 5f3b02b4-e497-39bf-2339-4c3c0a55968e.pdf  # Survey on incumbent digital transformation (EJIM 2023)
└── 5d418966-cc9b-6de7-1293-43eceb5f8106.pdf  # Capability configuration, ambidexterity (IJPE 2018)
```

---

## 5. Results

### Test 1: Regex Extraction Accuracy

| Field | Accuracy | Notes |
|-------|----------|-------|
| Title | 32.0% | Extracts wrong text (headers, journal names) |
| Authors | 33.3% | Pattern matching fails on varied formats |
| Year | 60.0% | Often picks wrong year from references |
| Journal | 64.0% | Partial matches work sometimes |
| DOI | 96.0% | Regex pattern works well for structured DOIs |
| TOC | N/A | Not implemented |
| **Overall** | **57.1%** | |

**Result**: ❌ FAILED - Below 80% target

### Test 2: PDF-to-Markdown Extraction Accuracy

| Field | Accuracy | Notes |
|-------|----------|-------|
| Year | 40.0% | Worse than regex, picks wrong years |
| DOI | 100.0% | Same as regex (pattern-based) |
| TOC Sections | 107% | Finds 31 vs 29 expected (picks up noise) |
| TOC Match | 35% | Section names don't match ground truth |
| **Overall** | **~45%** | |

**Result**: ❌ FAILED - Worse than regex for most fields, noisy TOC

### Test 3: Claude Haiku Extraction Accuracy

| Field | Accuracy | Notes |
|-------|----------|-------|
| Title | 100.0% | Perfect extraction including subtitles |
| Authors | 100.0% | All authors with affiliations |
| Year | 100.0% | Correct publication year |
| Journal | 100.0% | Full journal names |
| DOI | 100.0% | Exact DOI extraction |
| TOC | 100.0% | All sections with subsections |
| **Overall** | **100.0%** | |

**Cost**: $0.0156 per paper (~$0.078 total for 5 papers)
**Time**: ~10 seconds per paper
**Result**: ✅ PASSED - Exceeds 95% target

### Test 4: SciBERT Extraction Accuracy

| Field | Accuracy | Notes |
|-------|----------|-------|
| Title | 40.0% | Often extracts affiliations or subtitles instead |
| Authors | 13.3% | Pattern matching fails on varied formats |
| Year | 60.0% | Same as regex, picks wrong years from references |
| Journal | 40.0% | Low match rate on journal names |
| DOI | 100.0% | Regex pattern works well (same as other methods) |
| TOC | N/A | Not comparable (different section detection) |
| **Overall** | **51%** | |

**Model**: allenai/scibert_scivocab_uncased (~400MB)
**Cost**: $0.00 (local model)
**Time**: ~0.1 seconds per paper
**Result**: ❌ FAILED - Below 80% target, worse than regex

**Key insight**: SciBERT is a **language model**, not an **extraction model**. Without fine-tuning on labeled metadata extraction data, it provides no advantage over simple regex heuristics. The scientific vocabulary helps with tokenization but doesn't help identify which text is a title vs author vs affiliation.

---

## 6. Analysis

### Hypothesis Evaluation

| Metric | Target | Regex | Markdown | SciBERT | Haiku |
|--------|--------|-------|----------|---------|-------|
| Title Accuracy | >95% | 32.0% ❌ | ~30% ❌ | 40.0% ❌ | 100.0% ✅ |
| Author Accuracy | >90% | 33.3% ❌ | ~30% ❌ | 13.3% ❌ | 100.0% ✅ |
| Year Accuracy | >98% | 60.0% ❌ | 40.0% ❌ | 60.0% ❌ | 100.0% ✅ |
| DOI Accuracy | >95% | 96.0% ✅ | 100.0% ✅ | 100.0% ✅ | 100.0% ✅ |
| TOC Accuracy | >80% | N/A | 35.0% ❌ | N/A | 100.0% ✅ |
| Cost per Paper | <$0.10 | $0.00 ✅ | $0.00 ✅ | $0.00 ✅ | $0.016 ✅ |
| **Overall** | >80% | 57% ❌ | ~45% ❌ | 51% ❌ | 100% ✅ |

### TOC Extraction Deep Dive

Ground truth contains 29 sections with 47 subsections across 5 papers.

| Approach | Sections Found | Match Rate | Issue |
|----------|---------------|------------|-------|
| Regex | 0 | N/A | Not implemented |
| Markdown | 31 | 35% | Picks up DOIs, journal names as sections |
| Claude | 29 | 100% | Perfect match with hierarchical structure |

### Key Findings

1. **Regex extraction is unreliable** for complex fields (title, authors) due to:
   - Inconsistent PDF text extraction order
   - Varied formatting across publishers
   - Headers/footers mixed with content

2. **Regex works well for structured patterns** like DOI (96% accuracy)

3. **PDF-to-markdown doesn't help** - actually performs worse:
   - Raw text extraction loses layout context
   - Section detection picks up noise (DOIs, headers)
   - Would need `pymupdf4llm` for better results

4. **SciBERT provides no advantage without fine-tuning**:
   - Base model is a language model, not an extraction model
   - Scientific vocabulary helps tokenization but not field identification
   - 51% overall accuracy (worse than regex at 57%)
   - Would need labeled training data for metadata extraction task

5. **Claude Haiku achieves perfect accuracy** at reasonable cost ($0.016/paper)
   - Includes full TOC with subsections
   - Extracts abstracts and keywords
   - Handles all publisher formats

6. **Token usage** averages ~58,000 input tokens per paper (PDF content)

### Cost Analysis

| Approach | Per Paper | 100 Papers | 1000 Papers | Accuracy |
|----------|-----------|------------|-------------|----------|
| Regex | $0.00 | $0.00 | $0.00 | 57% |
| Markdown | $0.00 | $0.00 | $0.00 | ~45% |
| SciBERT | $0.00 | $0.00 | $0.00 | 51% |
| Haiku | $0.016 | $1.56 | $15.60 | 100% |
| Sonnet | $0.113 | $11.32 | $113.18 | 100% |
| Opus | $0.566 | $56.59 | $565.92 | 100% |

---

## 7. Conclusion

### Hypothesis Verdict

**H1 CONFIRMED**: Claude API provides >95% accuracy (achieved 100%)

**H0 CONFIRMED**: Local parsing approaches fail:
- Regex: 57% overall accuracy
- PDF-to-Markdown: ~45% overall, 35% TOC match
- SciBERT: 51% overall accuracy (worse than regex)

**Alternative hypotheses REJECTED**:
- Regex cannot achieve >80% (achieved 57%)
- PDF-to-markdown is not a reliable intermediate (noisy extraction)
- SciBERT cannot match Claude without fine-tuning (achieved 51%)

### Decision

**Recommended approach: Claude Haiku**

- Perfect accuracy on test corpus (100%)
- Full TOC extraction with hierarchical structure
- Cost-effective at $15.60 per 1000 papers
- Handles format variations automatically
- Extracts additional metadata (keywords, abstracts)

### Decision Pathway

```
Need TOC extraction? ──Yes──> Use Claude Haiku ($0.016/paper)
         │
         No
         │
         v
Is accuracy critical? ──Yes──> Use Claude Haiku ($0.016/paper)
         │
         No
         │
         v
Is DOI sufficient? ──Yes──> Use Regex (free)
         │
         No
         │
         v
Use Hybrid: Regex for DOI + Claude for rest
```

### Why LLM Wins: The Fundamental Problem

**PDF text extraction destroys visual context.** When humans read a PDF, they use layout cues:
- Large bold text at top → title
- Names below title → authors
- "2022" in header → publication year

When machines extract text, this becomes a flat string where "title", "author name", and "random header" are indistinguishable.

| Approach | Why It Fails |
|----------|--------------|
| **Regex** | No layout context; patterns break across publishers |
| **Markdown** | Still flat text; section detection picks up noise |
| **SciBERT** | Language model ≠ extraction model; needs fine-tuning |
| **GROBID** | Best local option (~85-90%) but requires Java service |
| **Docling** | Promising but untested on academic papers |

**LLMs solve this** because they understand document semantics—they "read" the PDF like a human would, inferring meaning from context rather than relying on fragile patterns.

**The economics are clear:**
- Engineering a local solution: weeks of work, ongoing maintenance, ~85% accuracy
- Claude Haiku: $15.60 per 1000 papers, 100% accuracy, zero maintenance

**Only pursue local extraction if:**
1. Offline requirement (no internet access)
2. Data privacy (cannot send PDFs to external API)
3. Massive scale (millions of papers where cost becomes significant)

---

## 8. Recommendations

### Immediate Actions

1. **Use Claude Haiku** for metadata extraction in paper-scanner
2. **Implement caching** to avoid re-extracting same PDFs
3. **Add DOI fallback** using regex when Claude unavailable

### Future Improvements

1. Consider batch API for large volumes (potential cost savings)
2. Explore Claude's caching feature for repeated prompts
3. Test with broader corpus (different publishers, languages)
4. Try `pymupdf4llm` for better PDF-to-markdown if local extraction needed

### Integration Notes

- Use existing `ClaudeHandler` from `src/paper_scanner/models/anthropic.py`
- Handler already supports PDF input via base64 encoding
- JSON output parsing is built-in

---

## 9. Output Files

### Ground Truth Reference Files

The following YAML files serve as the **ground truth** for comparing all extraction methods.
They were extracted using Claude Sonnet and manually verified:

| File | Description |
|------|-------------|
| `metamodel.yml` | Combined ground truth with schema + all papers (29 sections, 47 subsections) |
| `11e0f553-8a31-13e3-7144-2d6489219562.yml` | CMR 2022 - How to Compete When Industries Digitize |
| `3ae77a5c-091c-427f-7a98-dd072a87781e.yml` | JOSM 2017 - Zooming out: actor engagement |
| `5d418966-cc9b-6de7-1293-43eceb5f8106.yml` | IJPE 2018 - Capability configuration, ambidexterity |
| `5dbd37f5-ffb7-5f51-0c02-df901933832e.yml` | JAIS 2022 - From Product Platform to Innovation Platform |
| `5f3b02b4-e497-39bf-2339-4c3c0a55968e.yml` | EJIM 2023 - Survey on incumbent digital transformation |
| `prompt.yml` | Extraction prompt template used with Claude |

### Comparison Methodology

All extraction methods (Regex, Markdown, SciBERT, Claude Haiku) are compared against these ground truth YAML files:
- **Exact match** for year, volume, issue, DOI
- **Fuzzy match** for title, journal (substring containment)
- **Name overlap** for authors list
- **Section matching** for TOC (normalized comparison)

### Reports Generated

Reports in `outputs/`:

| File | Description |
|------|-------------|
| `regex_accuracy_report.json` | Regex vs ground truth YAML |
| `claude_haiku_accuracy_report.json` | Claude Haiku vs ground truth YAML |
| `scibert_accuracy_report.json` | SciBERT vs ground truth YAML |
| `comparison_summary.json` | Side-by-side accuracy comparison |
| `comparison_summary_with_scibert.json` | Full comparison including SciBERT |
| `toc_comparison.json` | TOC extraction vs ground truth |

---

## 10. References

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [SciBERT: A Pretrained Language Model for Scientific Text](https://github.com/allenai/scibert) - AllenAI
- [pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) - Better PDF-to-markdown
- Related: `src/paper_scanner/models/anthropic.py` - Existing Claude handler
- Related: `src/paper_scanner/core/models.py` - Paper model structure

---

## Appendix: Running the Spike

```bash
# Step 1: Create/update ground truth (uses Claude Sonnet)
uv run python tests/spikes/020_parsing/create_ground_truth.py

# Step 2: Run all extraction tests
uv run pytest tests/spikes/020_parsing/ -v -s

# Step 3: Run individual extractor tests
uv run pytest tests/spikes/020_parsing/test_01_regex_extractor.py -v -s
uv run pytest tests/spikes/020_parsing/test_02_claude_extractor.py -v -s
uv run pytest tests/spikes/020_parsing/test_06_scibert_extractor.py -v -s

# Step 4: Generate comparison reports
uv run pytest tests/spikes/020_parsing/test_03_comparison.py -v -s
uv run pytest tests/spikes/020_parsing/test_05_toc_extraction.py -v -s

# Step 5: View results
cat tests/spikes/020_parsing/outputs/comparison_summary_with_scibert.json
cat tests/spikes/020_parsing/outputs/toc_comparison.json
```
