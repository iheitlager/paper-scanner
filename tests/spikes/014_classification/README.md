# Spike 014: Classification

## Screening Pipeline: Five-Stage Process

Development of a comprehensive screening model with distinct stages from attribute-based to manual review.

### Overview

The screening pipeline implements five sequential stages, each progressively refining paper selection:

1. **Metadata Screening** (Deterministic)
   - Attribute-based filtering on structured fields (language, paper type, quality tier, DOI, publication year, journal)
   - Implements tri-state logic with hard INCLUDE/EXCLUDE/OMITTED rules
   - Uses YAML configuration with `NOT: value` syntax for "exclude everything except"

2. **Keyword Screening** (Content Pattern Matching)
   - Text pattern matching on title/abstract/keywords
   - Searches for specific terms or phrases (simple regex/string matching)
   - Probabilistic relevance scoring, deterministic term detection

3. **Semantic Screening** (ML + LLM-based)
   - Analyzes embeddings from title/abstract/keywords
   - Both machine learning (embedding similarity) and LLM-based relevance assessment
   - Higher sophistication than keyword screening, probabilistic scoring

4. **Full Paper Review** (LLM/Manual Inclusion)
   - LLM-based analysis of complete paper content
   - Manual review fallback or confirmation
   - Deterministic inclusion decisions after comprehensive assessment

5. **Knowledge Extraction** (Post-Inclusion)
   - Begins after paper inclusion is confirmed
   - Extracts structured information (research questions, findings, methodology)

### Key Distinction: Metadata vs. Content Screening

| Aspect | Metadata Screening | Content Screening (Keyword/Semantic) |
|--------|-------------------|-------------------------------------|
| **Input** | Structured attributes (language, type, year, journal) | Title, abstract, keywords, full text |
| **Mechanism** | Deterministic attribute matching | Probabilistic relevance scoring |
| **Complexity** | Simple boolean logic | Pattern matching or embedding analysis |
| **Decision Type** | Binary include/exclude | Scoring-based inclusion threshold |

**Title/Abstract/Keywords are content, not metadata.** They enable keyword-based and semantic screening—not metadata screening.

### Implementation Files

- **test_01_metadata_screening_parse.py** (24 tests)
  - Metadata screening YAML configuration parsing and validation
  - NOT operator parsing (both dict and string syntax)
  - Exclude criteria validation for attribute-based filtering
  - Logic extraction for metadata-only screening

- **test_01_metadata_screening_parse.yml**
  - Example pipeline configuration for metadata screening stage
  - Demonstrates tri-state logic (Hard INCLUDE/EXCLUDE/OMITTED)
  - Shows pipeline and steps organization with attributes only

- **test_02_metadata_screening_screen_files.py** (17 tests)
  - Metadata screening logic implementation
  - BibTeX file integration with attribute filtering
  - Enum value validation (PaperType, StudyType, ScreeningDecision)
  - Combined attribute criteria testing

- **test_03_keyword_screening.py** (21 tests)
  - Wildcard keyword matching (exact, prefix*, *suffix, *both*)
  - Implicit study type detection from content
  - Keyword-based screening with scoring mechanism
  - Three screening modes: inclusion_required, exclusion_only, soft
  - KeywordScreening model population with all fields
  - Integration with existing categorization patterns

### Metadata Screening YAML Configuration

Example of the first screening stage—attribute-based filtering:

```yaml
pipeline:
  version: "1.0"
  name: "Metadata Screening Classification Test"
  description: "Filters papers on structured metadata attributes"

steps:
  - step: "Metadata screening - attribute-based filtering"
    builtin.metadata_screening:
      exclude:
        language:
          - NOT: "en"  # Exclude everything that is NOT English
        paper_types:
          - NOT: "journal_article"  # Keep only journal articles
        study_types:
          - "editorial"  # Hard exclude editorial papers
          - "conceptual"
          - "theoretical"
```

**Tri-state logic within metadata screening:**
- **Hard INCLUDE**: Implicitly included (all papers with matching attributes)
- **Hard EXCLUDE**: Explicitly excluded via `NOT: "value"` (exclude everything except value) or direct listing
- **OMITTED**: No exclusion rule (no requirement on that attribute)

### Keyword Screening

Keyword screening is the second stage—content-based filtering with implicit study_type detection.

**Key features:**

1. **Wildcard Keyword Matching**
   - Exact: `"software"` - matches word boundary
   - Suffix: `"test*"` - matches "testing", "tests", etc.
   - Prefix: `"*test"` - matches "contest", "pretest", etc.
   - Both: `"*test*"` - matches anywhere

2. **Implicit Study Type Detection** (automatic, no configuration needed)
   
   Uses sophisticated regex pattern matching to detect research type from text:
   
   **Priority Order (important!):**
   1. **Editorial** (news, commentary, letters) - highest priority
   2. **Empirical** (interviews, surveys, case studies, experiments, etc.)
      - Uses scoring: quantitative patterns (n=123, t-tests, p<0.05) vs qualitative patterns (interviews, case studies, thematic analysis)
      - Requires minimum 2 pattern matches for classification
      - **Design Note**: Empirical is checked BEFORE literature review because many papers combine both.
        When a paper is both a literature review AND empirical (e.g., "systematic review of empirical studies"),
        the empirical nature is more important for research synthesis and screening decisions.
   3. **Literature Review** (systematic review, meta-analysis, scoping review)
      - Only specific review keywords to avoid false positives with survey-based empirical studies
   4. **Conceptual/Theoretical** (frameworks, theories, opinions - no empirical indicators)
   5. **Unknown** (default when no patterns match)
   
   **Quantitative Indicators**: Sample size notation (n=123), statistical tests (ANOVA, t-test, chi-square), correlation, regression, hypothesis testing (p < 0.05)
   
   **Qualitative Indicators**: Interviews, surveys (with participants), case studies, ethnography, grounded theory, thematic analysis, content analysis, observational studies, focus groups, phenomenological approaches
   
   **Method Indicators**: Data collection, experimental design, quasi-experimental, longitudinal/cross-sectional studies, methodology

3. **Screening Modes**
   - `inclusion_required` (default): Paper must pass both gates - no exclusions AND has inclusion keywords
   - `exclusion_only`: Filter out exclusions only, include everything else
   - `soft`: Keywords for ranking only, never exclude

4. **Scoring Mechanism**
   - Score = count of matched inclusion keywords
   - Confidence = score / total inclusion keywords
   - Exclusion keywords cause immediate rejection (in inclusion_required/exclusion_only modes)

**YAML configuration example:**

```yaml
- step: "Keyword screening - exclude editorials, conceptual, theoretical"
  description: "Exclude papers based on keywords and implicit study type detection"
  builtin.keyword_screening:
    mode: "inclusion_required"  # Both gates must pass
    
    exclude:
      keywords:
        domains:
          - "medical"
          - "healthcare"
          - "patient"
        other:
          - "agriculture"
          - "military"
      study_types:
        - "editorial"  # Hard exclude editorial papers
    
    include:
      keywords:
        practices:
          - "agile"
          - "scrum"
          - "devops"
        domains:
          - "software"
          - "it"
```

### Running Tests

```bash
# All classification tests
uv run pytest tests/spikes/014_classification/ -v

# YAML parsing tests only
uv run pytest tests/spikes/014_classification/test_01_metadata_screening_parse.py -v

# Metadata screening logic tests
uv run pytest tests/spikes/014_classification/test_02_metadata_screening_screen_files.py -v

# Keyword screening tests
uv run pytest tests/spikes/014_classification/test_03_keyword_screening.py -v

# LLM classification tests (requires ANTHROPIC_API_KEY)
uv run pytest tests/spikes/014_classification/test_05_llm_classification.py -v

# Manual demos (with output)
uv run python tests/spikes/014_classification/test_03_keyword_screening.py --manual
```

### Test Files Summary

| File | Purpose | Tests |
|------|---------|-------|
| `test_01_metadata_screening_parse.py` | YAML parsing & validation | 24 |
| `test_02_metadata_screening_screen_files.py` | Metadata filtering logic | 17 |
| `test_03_keyword_screening.py` | Keyword pattern matching & study type detection | 21 |
| `test_05_llm_classification.py` | Claude-based paper classification | ✓ |

---

# Spike 014: Multi-Pass Screening with Confidence Thresholds

**Status**: In Progress  
**Date**: 2025-12-24  
**Branch**: `spike/screening-thresholds`  
**Author**: Research Team

---

## 1. Problem Statement

We have a 4-pass snowballing literature review process that potentially generates 27,000+ papers to screen:

1. **Initial database search**: 2,000 papers (keyword search from databases)
2. **Snowball pass 1**: ~100,000 citations from initial 2,000 (at avg 50 citations per paper) → 15,000 unique papers
3. **Snowball pass 2**: ~16,000 citations from pass 1 → 8,000 new unique papers  
4. **Snowball pass 3**: ~6,000 citations from pass 2 → 2,000 new unique papers (yield drops to <5%, stop)

**Total**: ~27,000 unique papers to screen across all passes

**Goal**: Reduce to ~150 unique papers interesting for full-text review to include in the final dataset.

### Current Challenge

- **Cannot manually review 27,000 papers** (infeasible time/resource requirement)
- **Cannot afford Claude on all papers** ($27+ cost for 27K papers)
- **Must NOT miss relevant papers** (false negatives are costly - missed research!)
- **Can accept some irrelevant papers** (caught in full-text review later)

### Key Constraint

**"When in doubt, include"** - False positives are cheap (caught later), false negatives are expensive (missed research).

### Context from Previous Spikes

- **Spike 012**: Established classification methods and costs
  - Claude Haiku on BibTeX: 57.1% accuracy at $0.001/paper
  - SPECTER embeddings: 42.9% accuracy, free
  - Enhanced regex: 62.5% accuracy, free
  - **Key insight**: Structured data (title+abstract) enables cheap AI

- **Spike 013**: Citations workflow integration

### The Core Question

This spike is NOT about whether the methods work (012 proved that).  
This spike IS about: **What confidence thresholds and cascade logic minimize false negatives while maximizing efficiency across 4 snowballing passes?**

Specifically:
1. At what confidence levels do we exclude vs pass forward?
2. Should downstream stages re-examine upstream rejects (feedback loops)?
3. How do we balance cost vs recall across 27,000 papers?

---

## 2. Hypothesis

### Primary Hypothesis (H1)

**A confidence-based cascade with selective feedback** (where uncertain papers from keyword screening get semantic review, and low-confidence semantic rejects get LLM review) will achieve:

- **Recall ≥95%** (miss ≤5% of relevant papers)
- **LLM usage ≤20%** (~5,400 papers to Haiku, cost control)
- **Total cost <$5** for 27,000 papers
- **Processing time <2 hours** per pass (for iteration speed)

### Alternative Hypothesis (H2)

**A strict cascade without feedback** (trust each stage's excludes, no reconsideration) will:

- Have **lower recall** (85-90% - miss 10-15% of relevant papers)
- But **significantly lower cost** (<$1)
- **Question**: Is the cost savings worth the risk of missing 15-22 papers?

### Null Hypothesis (H0)

No confidence-based cascade can achieve ≥95% recall with <$5 cost, requiring either:
- Manual review of all papers, OR
- LLM review of all papers ($27+ cost)

---

## 3. Research Design

### Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Recall (Sensitivity)** | ≥95% | Must not miss relevant papers (false negatives costly) |
| **False Negative Rate** | ≤5% | Max 7-8 missed papers out of 150 expected |
| **LLM Usage Rate** | ≤20% | Only uncertain papers (cost control: 5.4K × $0.001 = $5.40) |
| **Total Cost** | <$5 | Budget constraint for 27K papers |
| **Processing Time** | <2 hours | Per pass (enables iterative refinement) |
| **False Positive Rate** | Accept up to 90% | Irrelevant papers caught in full-text review |

### Ground Truth Dataset

**Available**: 50 papers already manually classified (retrospective sample)

**Composition**:
- Mix of relevant and irrelevant papers from previous review
- Already classified with domain expertise
- Represents real-world distribution of papers encountered

**Usage in Spike**: Validation only (not training/tweaking)

**Spike Testing Strategy**:
- Use methods **as-is** from Spike 012 (baseline keyword patterns, baseline LLM prompt)
- Test if confidence-based cascade **concept** works
- Measure recall, cost, and LLM usage rates
- **Do NOT optimize** keywords or prompts for this specific domain

**Rationale**:
- Spike proves the **architecture** works (confidence cascade reduces false negatives)
- Domain-specific optimization happens in **CASLR methodology application**
- Keeps spike focused on testing the decision framework, not parameter tuning

**Calibration → CASLR Methodology**:

The refinement process (keyword tuning, prompt optimization) should be **Step 0 of CASLR methodology** when applying the system to a real systematic review:

```
CASLR Step 0: Domain Calibration (before main review)
├─ Take small sample of papers from domain (30-50 papers)
├─ Manually classify them
├─ Run through pipeline with baseline methods
├─ Identify domain-specific keywords to add/remove
├─ Refine LLM prompt with domain criteria
├─ Re-test on sample, iterate until acceptable accuracy
└─ Deploy refined methods on full review dataset

CASLR Step 1: Database Search + Initial Screening
CASLR Step 2: Snowball Pass 1 + Screening
...etc
```

**Why This is Better**:
- ✅ Spike focuses on proving concept, not optimizing for one review
- ✅ Methods tested are general-purpose (transferable)
- ✅ Calibration becomes repeatable process for any review domain
- ✅ Separates "does architecture work" from "is it tuned for my needs"

### Confidence Band Framework

For each screening method, define three confidence bands based on scores/features:

#### Keyword Screening (Enhanced Regex from Spike 012)

```
CONFIDENT EXCLUDE (0-30%):
  - 2+ explicit exclusion keywords ("non-empirical", "book review", etc.)
  - 0 inclusion keywords
  - Stop here, do not pass forward

UNCERTAIN (30-70%):
  - Mixed signals or no strong keywords either way
  - 1 inclusion keyword + 1 exclusion keyword
  - Pass to semantic screening

CONFIDENT INCLUDE (70-100%):
  - 3+ inclusion keywords ("case study", "qualitative", "empirical")
  - 0 exclusion keywords
  - Pass to semantic screening (or skip to LLM if very high confidence)
```

#### Semantic Screening (SPECTER Embeddings)

Calculate cosine similarity to reference papers (seed papers known to be relevant):

```
CONFIDENT EXCLUDE (similarity < 0.4):
  - Very different from all reference papers
  - Stop here, do not pass forward

UNCERTAIN (similarity 0.4-0.6):
  - Borderline similarity to reference papers
  - Pass to LLM screening

CONFIDENT INCLUDE (similarity > 0.6):
  - Very similar to at least one reference paper
  - Pass to LLM screening (or auto-include if very high similarity)
```

#### LLM Screening (Claude Haiku on BibTeX)

Model returns classification + confidence score:

```
CONFIDENT EXCLUDE (confidence < 0.5):
  - Model says "irrelevant" with high confidence
  - Add to manual review queue (human verification)

UNCERTAIN (confidence 0.5-0.7):
  - Model is unsure
  - Add to manual review queue

CONFIDENT INCLUDE (confidence > 0.7):
  - Model says "relevant" with high confidence
  - Auto-include for full-text review
```

#### Citation-Based Screening (PageRank-style Authority)

**Key Insight**: Papers cited by multiple included papers are likely relevant.

```
CITATION COUNT (from included papers):
  - 0 citations: No signal (rely on content-based methods)
  - 1 citation: Weak signal (candidate for inclusion)
  - 2-3 citations: Strong signal (boost confidence scores by 0.2)
  - 4+ citations: Very strong signal (auto-include OR mandatory manual review)

USAGE:
  - Apply as BOOST to existing confidence scores
  - Papers with 4+ citations from included papers → always review (even if excluded by other methods)
  - Citation count accumulated across snowball passes
```

**Rationale**:
- If 5 included papers all cite the same paper → that paper is likely relevant
- Citation = "vote" from domain experts (the authors of included papers)
- Mirrors PageRank algorithm (authority from incoming links)
- Particularly powerful in later snowball passes (more included papers = stronger signal)

### Cascade Strategies to Test

#### Strategy 1: No Feedback (Trust Each Stage)

```
All 27,000 papers
    ↓
[Keyword Screening]
    ├→ Confident Exclude (0-30%) → STOP → ~10,000 papers (37%)
    ├→ Uncertain (30-70%) → Continue → ~12,000 papers (44%)
    └→ Confident Include (70-100%) → Continue → ~5,000 papers (19%)
    
[Continue with 17,000 papers]
    ↓
[Semantic Screening - SPECTER]
    ├→ Confident Exclude (<0.4) → STOP → ~10,000 papers (59%)
    ├→ Uncertain (0.4-0.6) → Continue → ~5,000 papers (29%)
    └→ Confident Include (>0.6) → Continue → ~2,000 papers (12%)

[Continue with 7,000 papers]
    ↓
[LLM Screening - Claude Haiku]
    ├→ Confident Exclude (<0.5) → Manual queue → ~5,500 papers (79%)
    ├→ Uncertain (0.5-0.7) → Manual queue → ~1,000 papers (14%)
    └→ Confident Include (>0.7) → Auto-include → ~500 papers (7%)

Final: ~1,500 papers to full-text review (500 auto + 1000 manual review)
Cost: 7,000 papers × $0.001 = $7
```

#### Strategy 2: Feedback on Uncertain Only

```
All 27,000 papers
    ↓
[Keyword Screening]
    ├→ Confident Exclude → STOP → 10,000 papers
    ├→ Uncertain → Send to Semantic → 12,000 papers
    └→ Confident Include → Send to Semantic → 5,000 papers

[Semantic processes 17,000 papers]
    ↓
[Semantic Screening]
    ├→ Confident Exclude → STOP → 10,000 papers
    ├→ Uncertain → Send to LLM → 5,000 papers
    └→ Confident Include → Send to LLM → 2,000 papers

[LLM processes 7,000 papers]
    ↓
[LLM Screening]
    ├→ Exclude → Manual queue
    ├→ Uncertain → Manual queue
    └→ Include → Auto-include

Cost: 7,000 papers × $0.001 = $7
```

#### Strategy 3: Confidence Cascade with Citation Boost (Recommended)

```
All 27,000 papers
    ↓
[Check Citation Count - New!]
    ├→ Cited by 4+ included papers → MANDATORY MANUAL REVIEW (bypass automation)
    └→ Cited by 0-3 included papers → Continue to content-based screening

[Keyword Screening]
    ├→ Confident Exclude (>2 exclusion keywords) → Check citations
    │   └→ If 2+ citations → RESCUE, send to manual review
    │   └→ If 0-1 citations → STOP
    ├→ Uncertain (mixed/no strong signals) → SEMANTIC
    └→ Confident Include (>3 inclusion keywords) → SKIP SEMANTIC, GO TO LLM
        (Rationale: High keyword confidence may not need semantic validation)

[Semantic Screening - Only processes uncertain from keywords]
    ├→ Confident Exclude (similarity < 0.4) → Check citations
    │   └→ If 2+ citations → RESCUE, send to LLM
    │   └→ If 0-1 citations → STOP
    ├→ Uncertain (similarity 0.4-0.6) → LLM (boost score if citations)
    └→ Confident Include (similarity > 0.6) → LLM (boost score if citations)

[LLM Screening - Processes includes from keywords + uncertain/includes from semantic]
    ├→ Apply citation boost: score' = min(1.0, score + 0.2 * min(citations, 3))
    ├→ Exclude (confidence < 0.5) → Manual review if 2+ citations, else stop
    ├→ Uncertain (confidence 0.5-0.7) → Manual review queue
    └→ Include (confidence > 0.7) → Auto-include for full-text review

Efficiency: 
- Citation count acts as safety net (prevents excluding highly-cited papers)
- Keywords confident includes (5K) skip semantic (saves time)
- Only uncertain keywords (12K) go to semantic
- Citation boost reduces false negatives in later passes
- Reduced LLM load (estimated 5K papers instead of 7K)

Cost: ~5,000 papers × $0.001 = $5
```

### Deduplication Strategy

- **Initial database import**: Explicit deduplication by DOI/title
- **Snowballing passes**: Implicit deduplication via database lookup
  - Before screening, check if paper already in database
  - Only screen NEW papers
  - Track which pass each paper entered (for yield analysis)

---

## 4. Experiments

### Experiment 1: Baseline Performance on Ground Truth

**Objective**: Measure accuracy of baseline methods (from Spike 012) on the 50-paper sample.

**Method**:
1. Use methods **as-is** without domain-specific tuning:
   - Keyword screening: Enhanced regex from Spike 012 test_005
   - Semantic screening: SPECTER embeddings with generic reference papers
   - LLM screening: Claude Haiku with baseline classification prompt
2. Run all 50 papers through each method individually
3. Measure accuracy, precision, recall for each method

**Expected Output**:
```
Baseline Performance:
- Keywords: 60-70% accuracy (general-purpose patterns)
- SPECTER: 40-50% accuracy (without domain-specific references)
- Claude Haiku: 50-60% accuracy (generic prompt)
```

**Key Insight**: These accuracies are acceptable for spike validation. Real CASLR applications would improve them through domain calibration.

---

### Experiment 2: Calibrate Confidence Thresholds

**Objective**: Find threshold values that achieve ≥95% recall with baseline methods.

**Method**:
1. For each method, collect confidence scores for all 50 papers:
   - Keywords: Score based on keyword counts (0-1.0)
   - SPECTER: Cosine similarity to best reference paper (0-1.0)
   - LLM: Confidence from Claude Haiku (0-1.0)
2. Plot precision/recall curves at different threshold values
3. Identify thresholds where recall ≥95%
4. Calculate LLM usage rate (% papers passing thresholds)

**Example Analysis**:
```
Keyword Screening:
- Threshold 0.3: Recall 100%, passes 85% to next stage
- Threshold 0.4: Recall 96%, passes 75% to next stage ← TARGET
- Threshold 0.5: Recall 90%, passes 65% to next stage

Semantic Screening:
- Similarity 0.3: Recall 98%, passes 80%
- Similarity 0.4: Recall 96%, passes 70% ← TARGET
- Similarity 0.5: Recall 88%, passes 55%

LLM Screening:
- Confidence 0.5: Recall 100%, includes all uncertain
- Confidence 0.6: Recall 96%, excludes low-confidence
- Confidence 0.7: Recall 92%, aggressive filtering
```

**Expected Output**:
- Calibrated thresholds for each method
- Validation that ≥95% recall is achievable with baseline methods
- Estimated LLM usage for 27K papers (e.g., 20% = 5,400 papers = $5.40)

### Experiment 3: Compare Cascade Strategies

**Objective**: Determine which cascade strategy best balances recall and cost.

**Prerequisites**: Calibrated thresholds from Experiment 2

**Method**:
1. Apply all 3 cascade strategies to 50-paper validation set
2. Use thresholds from Experiment 2
3. Measure for each strategy:
   - Recall (% of relevant papers captured)
   - Precision (% of captured papers that are relevant)
   - LLM usage rate (% of papers requiring LLM)
   - Total cost (papers × $0.001)
   - False negative rate (% of relevant papers missed)
   - Processing time

**Expected output**:
- Comparison table:

| Strategy | Recall | Precision | LLM Usage | Cost (50 papers) | FNR | Time |
|----------|--------|-----------|-----------|------------------|-----|------|
| 1: No Feedback | 88% | 45% | 35% (18) | $0.018 | 12% | 35s |
| 2: Full Feedback | 96% | 40% | 35% (18) | $0.018 | 4% | 35s |
| 3: Confidence Cascade | 95% | 42% | 25% (13) | $0.013 | 5% | 25s |

- Recommendation: Strategy 3 (best recall/cost balance)
- Projected cost for 27K papers: 25% × 27K × $0.001 = $6.75

### Experiment 4: Simulate 4-Pass Snowballing Process

**Objective**: Model efficiency degradation across snowballing passes.

**Method**:
1. Estimate paper volumes per pass based on citation counts
2. Calculate cumulative cost and recall across all 4 passes
3. Identify when yield drops below 5% (stopping criterion)

**Model assumptions**:
- **Initial search**: 2,000 papers → screen → keep 400 papers
- **Pass 1**: 400 papers × 50 citations/paper = 20,000 citations → dedupe → 15,000 unique papers
  - Track: Each unique paper stores "cited_by_count" (how many of the 400 cite it)
  - Screen 15,000 papers with citation boost
  - Keep 300 papers from Pass 1
- **Pass 2**: 300 papers × 40 citations/paper = 12,000 citations → dedupe → 8,000 new unique papers
  - Track: Accumulate citation counts (papers may be cited by Pass 1 + Pass 2 included papers)
  - Screen 8,000 papers with citation boost
  - Keep 150 papers from Pass 2
- **Pass 3**: 150 papers × 30 citations/paper = 4,500 citations → dedupe → 2,000 new unique papers
  - Track: Accumulate citation counts (papers may be cited across multiple passes)
  - Screen 2,000 papers with citation boost
  - Keep 50 papers from Pass 3
- **Pass 4**: Yield <5%, stop (would only generate ~1,500 citations → ~800 unique papers)

**Expected output**:
- Yield curve showing papers captured per pass
- Cumulative cost across passes
- Validation of 3-pass stopping criterion

### Experiment 5: Error Analysis on False Negatives

**Objective**: Understand which papers are missed by automation and why.

**Method**:
1. Identify all false negatives (relevant papers incorrectly excluded)
2. Classify error types:
   - Keyword failure: Relevant paper had exclusion keywords
   - Semantic failure: Low similarity to reference papers (domain outlier)
   - LLM failure: Model misclassified with high confidence
3. Recommend manual review checkpoints or threshold adjustments

**Expected output**:
- Error taxonomy with examples
- Recommendations for reducing specific error types
- Manual review checkpoint specification (e.g., "Always human-review papers with 2+ citations from included papers")

---

## 5. Expected Deliverables

### Deliverable 1: Confidence Threshold Recommendations

Calibrated threshold values for production use:

```
Keyword Screening:
- Exclude if: 2+ exclusion keywords AND 0 inclusion keywords
- Uncertain if: Mixed signals OR 1 inclusion + 1 exclusion
- Include if: 3+ inclusion keywords AND 0 exclusion keywords

Semantic Screening:
- Exclude if: Cosine similarity < 0.4 to all reference papers
- Uncertain if: Cosine similarity 0.4-0.6 to best reference
- Include if: Cosine similarity > 0.6 to at least one reference

LLM Screening:
- Exclude if: Model confidence < 0.5 for "relevant"
- Uncertain if: Model confidence 0.5-0.7
- Include if: Model confidence > 0.7
```

### Deliverable 2: Cascade Strategy Recommendation

Selected strategy with justification:

**Recommended: Strategy 3 (Confidence Cascade)**

- **Expected recall**: 95-97%
- **Expected cost**: $5 for 27K papers
- **Expected LLM usage**: ~5,000 papers (19%)
- **Rationale**: Best balance of recall and cost, skips unnecessary semantic processing for high-confidence keywords

### Deliverable 3: Snowballing Efficiency Model

Projections for 4-pass process:

| Pass | Papers | Cost | Cumulative | Yield | Stop? |
|------|--------|------|------------|-------|-------|
| Initial | 2,000 | $0.40 | $0.40 | - | No |
| Pass 1 | 15,000 | $3.00 | $3.40 | 400/15K = 2.7% | No |
| Pass 2 | 8,000 | $1.60 | $5.00 | 200/8K = 2.5% | No |
| Pass 3 | 2,000 | $0.40 | $5.40 | 50/2K = 2.5% | Yes (<5% but diminishing) |

**Stopping criterion**: When yield <2% OR new papers <1000, whichever comes first.

### Deliverable 4: Implementation Pseudocode

```python
def screen_paper(paper, reference_papers, included_papers, cascade_strategy="confidence"):
    """
    Screen a single paper through the confidence cascade.
    
    Args:
        paper: Paper to screen
        reference_papers: Seed papers for semantic similarity
        included_papers: Papers already included (for citation counting)
        cascade_strategy: "confidence" (default) | "no_feedback" | "full_feedback"
    
    Returns: (decision, confidence, stage, citation_count)
        decision: "include" | "exclude" | "manual_review"
        confidence: 0.0-1.0 (boosted by citations)
        stage: "keyword" | "semantic" | "llm" | "citation"
        citation_count: Number of included papers citing this paper
    """
    
    # Stage 0: Citation-Based Authority Check
    citation_count = count_citations_from(paper, included_papers)
    
    if citation_count >= 4:
        # Highly cited by included papers → mandatory review
        return ("manual_review", 1.0, "citation", citation_count)
    
    # Stage 1: Keyword Screening
    keyword_score = keyword_screening(paper)
    
    if keyword_score < 0.3:  # Confident exclude
        # Safety net: rescue if cited by 2+ included papers
        if citation_count >= 2:
            return ("manual_review", 0.3 + 0.2 * citation_count, "keyword_rescued", citation_count)
        return ("exclude", keyword_score, "keyword", citation_count)
    
    if keyword_score > 0.7:  # Confident include, skip semantic
        llm_score = llm_screening(paper)
        # Boost by citations
        boosted_score = min(1.0, llm_score + 0.2 * min(citation_count, 3))
        if boosted_score > 0.7:
            return ("include", boosted_score, "llm", citation_count)
        else:
            return ("manual_review", boosted_score, "llm", citation_count)
    
    # Stage 2: Semantic Screening (for uncertain keywords)
    semantic_score = semantic_screening(paper, reference_papers)
    
    if semantic_score < 0.4:  # Confident exclude
        # Safety net: rescue if cited by 2+ included papers
        if citation_count >= 2:
            return ("manual_review", 0.4 + 0.2 * citation_count, "semantic_rescued", citation_count)
        return ("exclude", semantic_score, "semantic", citation_count)
    
    # Stage 3: LLM Screening (for uncertain semantic or confident semantic includes)
    llm_score = llm_screening(paper)
    
    # Boost by citations
    boosted_score = min(1.0, llm_score + 0.2 * min(citation_count, 3))
    
    if boosted_score > 0.7:
        return ("include", boosted_score, "llm", citation_count)
    elif boosted_score < 0.5:
        # Final safety net
        if citation_count >= 2:
            return ("manual_review", boosted_score, "llm_rescued", citation_count)
        return ("exclude", boosted_score, "llm", citation_count)
    else:
        return ("manual_review", boosted_score, "llm", citation_count)


def count_citations_from(paper, included_papers):
    """
    Count how many included papers cite this paper.
    
    This is the PageRank-style authority signal:
    - Paper cited by many included papers → likely relevant
    - Paper cited by few/no included papers → rely on content
    """
    count = 0
    for included_paper in included_papers:
        if paper.doi in included_paper.references or \
           paper.title in [ref.title for ref in included_paper.references]:
            count += 1
    return count


def process_snowball_pass(papers, pass_number):
    """
    Process one snowballing pass.
    """
    results = {
        "include": [],
        "exclude": [],
        "manual_review": []
    }
    
    for paper in papers:
        # Check deduplication
        if paper.doi in database or paper.title in database:
            continue  # Skip duplicates
        
        # Screen paper
        decision, confidence, stage = screen_paper(paper, reference_papers)
        
        results[decision].append({
            "paper": paper,
            "confidence": confidence,
            "stage": stage,
            "pass": pass_number
        })
    
    # Calculate yield
    total_new = len(papers)
    included = len(results["include"]) + len(results["manual_review"])
    yield_rate = included / total_new if total_new > 0 else 0
    
    return results, yield_rate
```

---

## 6. Open Questions to Answer

### Question 1: Should semantic screening re-examine keyword rejects?

**Test**: Do papers marked as "confident exclude" by keywords ever get rescued by high semantic similarity?

- If **YES** (>5% rescue rate): Add feedback loop from keyword excludes to semantic
- If **NO** (<5% rescue rate): Trust keyword stage, save computational time

### Question 2: What's the optimal LLM usage rate?

**Test**: At what usage rate does recall plateau?

- Plot recall vs LLM usage rate (10%, 20%, 30%, etc.)
- Find elbow point where additional LLM usage doesn't improve recall significantly
- Balance cost vs marginal recall gain

### Question 3: How do confidence scores correlate across methods?

**Test**: Are low keyword confidence papers also low semantic confidence?

- Calculate correlation between keyword_score and semantic_score
- If highly correlated: Can skip semantic for very low keyword scores
- If not correlated: Need semantic as independent validation

### Question 4: What's the optimal stopping criterion for snowballing?

**Test**: Does stopping at yield <5% miss important papers?

**Alternative criteria**:
- Yield <5% (current assumption)
- Yield <2% (more conservative)
- New papers <1000 (absolute threshold)
- Diminishing returns: (Yield_n / Yield_n-1) < 0.5

**Validation**: Sample papers from hypothetical Pass 4 to see if any would be relevant

### Question 5: How powerful is citation count as a relevance signal?

**Test**: Do papers cited by multiple included papers have higher relevance rates?

**Analysis**:
- Plot relevance rate vs citation count (0 cites, 1 cite, 2 cites, 3+ cites)
- Calculate: P(relevant | cited by N included papers)
- Expected: Strong positive correlation (PageRank principle)
- If correlation weak: Citation boost may not be worth complexity
- If correlation strong: Citation boost is critical safety net

**Key Metrics**:
- Rescue rate: % of papers excluded by content but rescued by citations
- Precision of citation signal: % of highly-cited papers that are actually relevant
- Citation distribution: How many papers get 0, 1, 2, 3, 4+ citations?

### Question 6: Should we use incoming citations (cited BY included) vs outgoing (paper CITES)?

**Current approach**: Incoming citations (paper is cited BY included papers)

**Alternative**: Outgoing citations (paper CITES many included papers)
- Paper that cites 5 included papers → likely in same domain
- Easier to compute (just count references to included papers)
- But: May not indicate quality/relevance (could be peripheral survey)

**Test**: Compare relevance rates for:
- High incoming citations (cited by many)
- High outgoing citations (cites many)
- Both (cited by many AND cites many)

---

## 7. Implementation Notes

### Cost Estimates (27K papers)

Based on Spike 012 findings:

| Method | Cost per Paper | Usage Rate | Total Cost |
|--------|----------------|------------|------------|
| Keyword Screening | $0 | 100% | $0 |
| SPECTER Semantic | $0 | 44% (12K) | $0 |
| Claude Haiku | $0.001 | 19% (5K) | $5 |
| **Total** | | | **$5** |

### Performance Estimates

| Method | Time per Paper | Papers | Total Time |
|--------|----------------|--------|------------|
| Keyword Screening | <1ms | 27,000 | <30s |
| SPECTER Semantic | 130ms | 12,000 | 26 min |
| Claude Haiku | 1.8s | 5,000 | 150 min |
| **Total** | | | **~3 hours** |

### Integration Points

**Dependencies**:
- `src/paper_scanner/steps/deduplication.py` - Explicit dedup for initial import
- `src/paper_scanner/steps/keyword_screening.py` - Implement enhanced regex from Spike 012
- `src/paper_scanner/steps/semantic_screening.py` - SPECTER embeddings with similarity threshold
- `src/paper_scanner/models/anthropic.py` - Claude Haiku integration (already exists)

**New components needed**:
- Confidence cascade orchestrator
- Manual review queue management
- Pass tracking (which snowball pass each paper entered)
- Yield calculation and stopping criterion logic

---

## Status

**Current Phase**: Ready for Execution  
**Available Resources**: 50 manually classified papers (validation ground truth)

**Workflow**:
```
Experiment 1: Baseline Performance Testing
         ↓ (measure accuracy of methods as-is)
Experiment 2: Calibrate Confidence Thresholds  
         ↓ (find thresholds for ≥95% recall)
Experiment 3: Compare Cascade Strategies
         ↓ (test all 3 approaches on validation set)
Experiment 4: Simulate Multi-Pass Snowballing
         ↓ (model 4-pass system behavior)
Experiment 5: Error Analysis
         ↓ (understand false negatives)
Deploy → CASLR Step 0: Domain Calibration
         ↓ (refine keywords/prompts for specific review)
Deploy → CASLR Steps 1-4: Full Literature Review
```

**Next Steps**:
1. ⏳ Run Experiment 1: Test baseline methods (keywords, SPECTER, Haiku) on 50 papers
2. ⏳ Run Experiment 2: Find optimal thresholds for ≥95% recall
3. ⏳ Run Experiment 3: Compare 3 cascade strategies (no feedback, full feedback, confidence cascade)
4. ⏳ Run Experiment 4: Model 4-pass snowballing with 27K papers
5. ⏳ Run Experiment 5: Analyze false negatives
6. ⏳ Document findings and deployment recommendations

**CASLR Deployment** (after spike completion):
- **Step 0**: Domain Calibration (30-50 sample papers from target review)
  - Refine keyword patterns for specific domain
  - Optimize LLM prompt with domain criteria
  - Validate calibrated methods on small validation set
- **Steps 1-4**: Apply calibrated methods to full review (database search + 4 snowball passes)

---

## References

- [Spike 012: Empirical Qualification](../012_empirical_qualification/) - Classification methods and costs
- [Spike 013: Citations](../013_citations/) - Citation extraction workflow
- [Enhanced Regex Patterns](../012_empirical_qualification/test_005_improved_regex.py) - Keyword screening implementation
- [SPECTER Model](https://huggingface.co/allenai/specter) - Scientific paper embeddings