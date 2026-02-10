# Screening Workflow Specification

**Domain:** Filtering
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

## Overview

The Screening Workflow implements a multi-stage progressive filtering pipeline for systematic literature reviews. Papers flow sequentially through deduplication, journal screening, metadata screening, keyword screening, semantic screening, and LLM/Rocchio classification stages. Each stage can include, exclude, or pass papers to the next stage. Results are tracked in `Paper.screening` with a full audit trail of decisions at each stage.

The workflow enables:
- **Reproducible filtering**: Each stage documents its decision rationale and confidence
- **Progressive refinement**: Later stages use results from earlier stages
- **Human oversight**: Decisions flagged for manual review at confidence boundaries
- **Multi-criterion filtering**: Combine keyword, semantic, and ML-based classification approaches
- **Dimension-aware classification**: Classify papers against research dimensions, not just binary relevance

### Philosophy

The screening workflow embodies three core principles:

1. **Progressive Filtering with Confidence Bands**: Papers flow through stages in sequence, with each stage potentially including/excluding/passing to the next. Confidence bands mark uncertain papers for manual review rather than hard binary decisions.

2. **Separation of Concerns**: Each stage has a single responsibility (deduplicate, validate journals, extract metadata, etc.) and operates independently. Cross-stage dependencies are minimal.

3. **Full Auditability**: Every screening decision is recorded with timestamps, scoring details, and method attribution, enabling reproducibility and post-hoc analysis of filtering decisions.

### Key Capabilities

- **Deduplication**: Exact DOI matching and fuzzy title/author matching with configurable thresholds
- **Journal Screening**: Filter by journal quality tiers and enrich with ISO4 abbreviations
- **Metadata Screening**: Tri-state logic (INCLUDE/EXCLUDE/OMIT) filtering by language, paper type, quality tier, with NOT operator support
- **Keyword Screening**: Wildcard patterns (*test*, test*, *test), inclusion/exclusion modes, implicit study type detection
- **Study Type Detection**: Pattern-based detection (editorial, empirical, literature review, conceptual) from title/abstract with configurable modes
- **Semantic Screening**: Embedding-based cosine similarity to research question with thresholds
- **Rocchio Classification**: Centroid-based adaptive classification with zero-seed initialization from research question
- **LLM Classification**: Claude-powered dimension scoring with dominance metrics and confidence bands
- **Screening Decision Model**: Aggregated decision tracking with current_stage, final_decision, and decision attribution

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: Deduplication with Multi-Method Matching

The system MUST identify and mark duplicate papers using three prioritized methods: DOI exact match, title+author fuzzy match (default threshold 0.90), and title-only fuzzy match (default threshold 0.95).

#### Design Details

**Matching Methods (Priority Order)**:
1. **DOI Exact Match** (confidence=1.0): Papers with identical DOIs are marked duplicates during import via `PapersDatabase.resolve_duplicates()`. Deduplication step records results in `screening.deduplication` with method="doi_exact".
2. **Title+Author Fuzzy Match** (default threshold=0.90): Normalized titles compared with SequenceMatcher; must match first author's family name exactly (case-insensitive). Confidence = similarity score.
3. **Title-Only Fuzzy Match** (default threshold=0.95): Fallback when author data missing; uses higher threshold to reduce false positives.

**Update Chain**:
- Sets `paper.duplicate_of` reference to primary paper
- Sets `paper.screening.final_decision = ScreeningDecision.EXCLUDED_DUPLICATE`
- Creates `paper.screening.deduplication = DeduplicationResult(...)` with full audit trail
- Updates `paper.screening.current_stage = "deduplication_complete"`

**Idempotency**: Only processes papers where `screening.deduplication == None`.

#### Scenario: Exact DOI Duplicate Detection
- GIVEN papers P1 and P2 with identical DOI "10.1234/example"
- WHEN deduplication executes with methods including "doi_exact"
- THEN P2.duplicate_of = P1 reference is set during import, deduplication records result with confidence=1.0

#### Scenario: Fuzzy Title+Author Match
- GIVEN papers P1 (title="Machine Learning in Healthcare", author="Smith") and P2 (title="Machin Learning in Healthcare", author="Smith", similarity score=0.91)
- WHEN deduplication executes with title_author_fuzzy (threshold=0.90)
- THEN P2 marked duplicate of P1 with similarity_score=0.91, method="title_author_fuzzy"

#### Scenario: Conservative Title-Only Fallback
- GIVEN papers P1 (title="Digital Transformation") and P2 (title="Digital Transformation", no author)
- WHEN deduplication executes with title_fuzzy (threshold=0.95) and no title+author match
- THEN P2 marked duplicate of P1 with similarity_score >= 0.95, method="title_fuzzy"

#### Configuration
```yaml
deduplication:
  methods:
    - method: "doi_exact"
    - method: "title_author_fuzzy"
      threshold: 0.90
      priority: 1
    - method: "title_fuzzy"
      threshold: 0.95
      priority: 2
```

#### Validation
- Methods list MUST be a list of dicts
- Each method dict MUST contain 'method' field in {"doi_exact", "title_author_fuzzy", "title_fuzzy"}
- If 'threshold' present, MUST be float in [0.0, 1.0]
- If 'priority' present, MUST be integer

---

### Requirement: Journal Screening with Quality Tier Filtering

The system MUST validate journal presence in curated journal definitions and enrich papers with standardized acronyms and ISO4 abbreviations.

#### Design Details

**Journal Lookup Strategy**:
1. Exact match against journal definitions in YAML file (default: `etc/journal_definitions.yml`)
2. ISO4 generation fallback for unmatched journals (configurable via `generate_iso4: bool`, default=true)
3. Optional view filtering (e.g., Academy, AIS Basket, VHB rankings, Innovation)

**Result Storage**:
- Updates `paper.journal` with standardized name
- Creates `paper.screening.journal_screening = JournalScreeningResult(...)` with journal_name, acronym, iso4, lookup_type
- Records lookup_type as "exact_match" or "iso4_generation"

**Options**:
- `journal_definitions_path`: Path to YAML file (optional, uses default if omitted)
- `required_views`: List of view names to filter journals (optional)
- `generate_iso4`: bool (default true) - Generate ISO4 for unmatched journals
- `skip_missing`: bool (default false) - Skip papers with missing journal name instead of error

#### Scenario: Exact Journal Lookup
- GIVEN paper with journal="Nature Machine Intelligence"
- WHEN journal_screening executes with exact journal definition
- THEN paper.screening.journal_screening.lookup_type="exact_match", acronym="NMI", iso4="Nature Mach. Intell."

#### Scenario: ISO4 Generation Fallback
- GIVEN paper with journal="Obscure Domain Journal"
- WHEN journal_screening executes with generate_iso4=true and journal not found in definitions
- THEN paper.screening.journal_screening.lookup_type="iso4_generation", iso4 generated algorithmically

#### Scenario: View Filtering
- GIVEN papers from journals in {"Nature", "Science", "Obscure Journal"}
- WHEN journal_screening executes with required_views=["Academy"]
- THEN only papers from journals in Academy view are retained

#### Configuration
```yaml
journal_screening:
  journal_definitions_path: "etc/journal_definitions.yml"
  required_views: ["Academy"]
  generate_iso4: true
  skip_missing: false
```

#### Validation
- If 'journal_definitions_path' provided, MUST be string and file MUST exist
- If 'required_views' provided, MUST be list of strings
- 'generate_iso4' and 'skip_missing' MUST be booleans if present

---

### Requirement: Metadata Screening with Tri-State Logic

The system MUST filter papers by language, paper type, quality tier, and peer review status using tri-state inclusion logic with NOT operator support.

#### Design Details

**Tri-State Logic**:
- **Hard INCLUDE**: Explicitly required values (when listed without NOT)
- **Hard EXCLUDE**: Values that trigger exclusion (plain string in exclude list)
- **OMIT**: No requirement (field not mentioned)

**NOT Operator (Negation)**:
- Format: `{"NOT": "value"}` OR `"NOT:value"`
- Inverts logic: exclude everything EXCEPT the specified value
- Example: `{"NOT": "OPINION"}` means "exclude all except OPINION papers"

**Priority Logic**:
Papers screened in order: paper_types → language → quality_tier → is_peer_reviewed. First match excludes paper.

**Missing Metadata**: Treated as passing (don't exclude without information).

#### Scenario: Hard Exclude by Language
- GIVEN paper with language="de" (German)
- WHEN metadata_screening executes with exclude: {language: ["de", "fr"]}
- THEN paper excluded with exclusion_reason="language: de (hard excluded)"

#### Scenario: NOT Operator (Exclude All Except)
- GIVEN papers with paper_types={"OPINION", "JOURNAL_ARTICLE", "CONFERENCE"}
- WHEN metadata_screening executes with exclude: {paper_types: [{"NOT": "OPINION"}]}
- THEN only OPINION papers pass; JOURNAL_ARTICLE and CONFERENCE excluded

#### Scenario: Quality Tier Filtering
- GIVEN paper with quality_tier="UNKNOWN"
- WHEN metadata_screening executes with exclude: {quality_tier: ["UNKNOWN"]}
- THEN paper excluded with exclusion_reason="quality_tier: UNKNOWN (hard excluded)"

#### Configuration
```yaml
metadata_screening:
  enabled: true
  exclude:
    language:
      - "de"
      - "fr"
    paper_types:
      - {"NOT": "JOURNAL_ARTICLE"}  # Exclude all except journal articles
    quality_tier:
      - "UNKNOWN"
    is_peer_reviewed:
      - false
```

#### Validation
- 'enabled' MUST be boolean
- 'exclude' MUST be dict if present
- Each field in exclude MUST be list
- Each item in exclude list MUST be string OR dict with "NOT" key

---

### Requirement: Keyword Screening with Wildcard Patterns and Study Type Detection

The system MUST perform keyword-based screening with three modes (inclusion_required, exclusion_only, soft) and implicit study type detection with configurable minimum pattern match thresholds.

#### Design Details

**Wildcard Support**:
- **Exact match**: "keyword" → matches word boundary
- **Suffix wildcard**: "keyword*" → matches "keywords", "keywording", etc.
- **Prefix wildcard**: "*keyword" → matches "thekeyword", "prekeyword", etc.
- **Both sides**: "*keyword*" → matches anywhere

**Three Screening Modes**:
1. **inclusion_required** (default): Papers MUST match inclusion keywords to pass; exclusion keywords trigger failure
2. **exclusion_only**: Inclusion keywords optional; exclusion keywords trigger failure only
3. **soft**: Pass all papers regardless of keywords (used for soft filtering only)

**Study Type Detection** (Implicit):
Automatically detects study type from title/abstract/keywords using pattern matching:
- **Editorial**: news, commentary, letter, correction, erratum
- **Literature Review**: systematic review, literature review, bibliometric analysis, meta-analysis
- **Conceptual**: conceptual, theoretical, framework, taxonomy, opinion
- **Empirical**: quantitative or qualitative patterns
  - **Quantitative indicators**: n=X, survey with participants, statistical analysis, regression, questionnaire, hypothesis testing
  - **Qualitative indicators**: interviews, ethnography, grounded theory, content analysis, focus groups
  - **Case Study indicators**: case study, case-based, comparative case studies
  - **Minimum threshold**: 2+ pattern matches required for empirical classification

**Empirical Priority**: Papers with both literature review indicators AND empirical signals (score ≤ 2) default to LITERATURE_REVIEW. Papers with case study indicators (case_score > 0) classify as CASE_STUDY despite review signals.

**Completeness Check**: Papers missing title, substantive abstract, or keywords (strict mode) marked EXCLUDED_INCOMPLETE.

**Substantive Abstract Detection**: Rejects boilerplate (conflict of interest declarations, author acknowledgments) and very short abstracts (< 20 characters).

#### Scenario: Wildcard Keyword Matching
- GIVEN paper title="Testing Machine Learning Models"
- WHEN keyword_screening executes with include: {general: ["test*", "*validation"]}
- THEN "testing" matches "test*", paper passed with matched keywords

#### Scenario: Study Type Detection - Empirical
- GIVEN paper title="Survey of IT Adoption" abstract="We surveyed 150 companies using regression analysis"
- WHEN KeywordScreener detects study type
- THEN detected_study_type=EMPIRICAL_QUANTITATIVE (quant_score=2, qual_score=0, total=2)

#### Scenario: Study Type Detection - Literature Review with Weak Empirical
- GIVEN paper title="Bibliometric Analysis of Digital Transformation" abstract="analyzed 200+ publications using text mining"
- WHEN StudyTypeDetector detects study type
- THEN detected_study_type=LITERATURE_REVIEW (has explicit "bibliometric", empirical_score=2 triggers review classification)

#### Scenario: Completeness Validation
- GIVEN paper with title="Example" abstract=None keywords=[]
- WHEN keyword_screening executes with complete="strict"
- THEN paper excluded with decision=EXCLUDED_INCOMPLETE, reason="incomplete metadata: missing 'abstract, keywords'"

#### Scenario: Study Type Exclusion
- GIVEN paper with detected_study_type=EDITORIAL
- WHEN keyword_screening executes with exclude: {study_types: ["EDITORIAL"]}
- THEN paper excluded regardless of keyword matches

#### Configuration
```yaml
keyword_screening:
  mode: "inclusion_required"  # inclusion_required | exclusion_only | soft
  complete: "strict"  # strict
  inclusion_is_final: false
  include:
    general:
      - "machine learning"
      - "artificial*"
      - "*neural network*"
    methodology:
      - "empirical"
      - "case study"
    thresholds:
      auto_accept: 0.8
      manual_review: 0.5
  exclude:
    keywords:
      biology:
        - "dna"
        - "protein"
    study_types:
      - "EDITORIAL"
```

#### Validation
- 'mode' MUST be one of: "inclusion_required", "exclusion_only", "soft"
- 'complete' MUST be "strict" if present
- 'inclusion_is_final' MUST be boolean
- 'include' and 'exclude' MUST be dicts

---

### Requirement: Semantic Screening with Embedding-Based Similarity

The system MUST classify papers using embedding-based cosine similarity to the research question with configurable thresholds defining INCLUDED/MANUAL_REVIEW/EXCLUDED bands.

#### Design Details

**Embedding Model**:
- Default: "all-mpnet-base-v2" (multilingual, 768 dimensions)
- Options: "specter2" (academic domain-specific), "sciBERT", "all-MiniLM-L6-v2" (lightweight)

**Similarity Computation**:
- Embeds research question once, reuses for all papers (O(1) per-paper after load)
- Combines paper title + abstract for embedding
- Computes cosine similarity [0, 1] scale

**Three-Tier Decision Logic**:
1. similarity >= auto_include (default 0.65) → INCLUDED
2. similarity >= manual_review (default 0.55) → MANUAL_REVIEW (border cases)
3. similarity < manual_review → EXCLUDED

**Note**: Semantic screening is the sole decision criterion for this stage (unlike keyword screening which combines signals).

#### Scenario: High Semantic Similarity
- GIVEN research_question="Cloud computing security frameworks" and paper title="Security Architectures for Cloud Infrastructure" abstract="We propose..."
- WHEN semantic_screening executes with auto_include=0.65
- THEN similarity_score=0.78, decision=INCLUDED

#### Scenario: Borderline Semantic Similarity
- GIVEN research_question="IT adoption" and paper title="Digital transformation in supply chains" abstract="..."
- WHEN semantic_screening executes with manual_review=0.55, auto_include=0.65
- THEN similarity_score=0.62, decision=MANUAL_REVIEW

#### Scenario: Low Semantic Similarity
- GIVEN research_question="Cloud computing" and paper title="Ancient Philosophy" abstract="..."
- WHEN semantic_screening executes
- THEN similarity_score=0.25, decision=EXCLUDED

#### Configuration
```yaml
semantic_screening:
  model: "all-mpnet-base-v2"
  thresholds:
    auto_include: 0.65
    manual_review: 0.55
    auto_exclude: 0.55
```

#### Validation
- 'model' MUST be string if present
- 'thresholds' MUST be dict if present
- Each threshold (auto_include, manual_review, auto_exclude) MUST be float in [0, 1]

---

### Requirement: Rocchio Classification with Adaptive Centroid-Based Screening

The system MUST implement centroid-based adaptive semantic screening that maintains evolving centroids for accepted/rejected papers using the Rocchio algorithm with configurable weights.

#### Design Details

**Zero-Seed Initialization**:
- Initializes from research question embedding (no manual labels required to start)
- Optionally bootstraps from keyword_screening results (INCLUDED papers → relevant centroid, EXCLUDED → irrelevant)

**Rocchio Formula**:
```
score = alpha * query_centroid + beta * relevant_centroid - gamma * irrelevant_centroid
```
- **alpha** (default 1.0): Weight for research question centroid
- **beta** (default 0.75): Weight for relevant papers centroid
- **gamma** (default 0.15): Weight for irrelevant papers centroid

**Three-Tier Decision Logic**:
1. score >= accept_threshold (default 0.7) → ACCEPTED
2. score < reject_threshold (default 0.3) → REJECTED
3. score in [reject_threshold, accept_threshold) → UNCERTAIN

**State Persistence**: Centroids stored in `executor.step_state["semantic_classification_rocchio_state"]` across iterations within a session.

**Research Dimensions Support**: Can weight research question centroid by combining RQ embedding (70%) + dimension embeddings (30% split).

#### Scenario: Zero-Seed Rocchio with RQ Initialization
- GIVEN research_question="Machine learning in healthcare" with no manual seeds
- WHEN rocchio_screening executes with initialize_from_keyword_screening=false
- THEN query_centroid initialized from RQ embedding, relevant_centroid and irrelevant_centroid empty (equivalent to zero)

#### Scenario: Bootstrapped Rocchio from Keyword Screening
- GIVEN papers P1-P10 with keyword_screening results: P1,P2,P3 marked INCLUDED, P4,P5 marked EXCLUDED
- WHEN rocchio_screening executes with initialize_from_keyword_screening=true
- THEN relevant_centroid = mean(embed(P1), embed(P2), embed(P3)), irrelevant_centroid = mean(embed(P4), embed(P5))

#### Scenario: Rocchio Classification with Uncertainty Band
- GIVEN paper P with embedding, accept_threshold=0.7, reject_threshold=0.3
- WHEN rocchio_screening computes Rocchio score=0.45 for P
- THEN classification="UNCERTAIN" (in band [0.3, 0.7)), decision=UNCERTAIN

#### Configuration
```yaml
rocchio_screening:
  model: "sentence-transformers/allenai-specter"
  rocchio_weights:
    alpha: 1.0
    beta: 0.75
    gamma: 0.15
  thresholds:
    accept: 0.7
    reject: 0.3
  initialize_from_keyword_screening: true
```

#### Validation
- 'model' MUST be string if present
- 'rocchio_weights' dict: alpha, beta, gamma MUST be non-negative numbers
- 'thresholds' dict: accept, reject MUST be in [0, 1]
- 'initialize_from_keyword_screening' MUST be boolean

---

### Requirement: Rocchio-Based Dimension Classifier

The system MUST classify papers using multi-dimensional Rocchio classification where each research dimension becomes its own centroid, enabling dominance detection.

#### Design Details

**Dimension Centroid Strategy**:
- Each research dimension gets its own centroid in embedding space
- Centroids initialized from dimension name text combined with research question (if initialize_from_research_question=true)
- Papers classified by similarity to each dimension separately

**Classification Decision Logic**:
- **EXCLUDED**: No dimensions exceed similarity threshold
- **INCLUDED**: Exactly one dimension above threshold (clear dominant dimension)
- **MANUAL_REVIEW**: Multiple dimensions above threshold (uncertain which is dominant)

**Output Vector**:
- `classification_vector`: List of similarity scores for each dimension [d1_sim, d2_sim, ...]
- `classification_labels`: List of applicable dimensions (those above threshold)
- `dominant_dimension`: Single dimension with highest similarity (if exactly one above threshold)

#### Scenario: Clear Dominant Dimension
- GIVEN paper, dimensions=["Cloud Computing", "Security", "Machine Learning"], dimension_threshold=0.5
- GIVEN paper_sims=[0.72, 0.45, 0.38] (Cloud above threshold, others below)
- WHEN rocchio_classifier executes
- THEN classification_labels=["Cloud Computing"], dominant_dimension="Cloud Computing", decision=INCLUDED, confidence=0.72

#### Scenario: Multiple Applicable Dimensions
- GIVEN paper_sims=[0.68, 0.62, 0.38] (Cloud and Security above threshold)
- WHEN rocchio_classifier executes
- THEN classification_labels=["Cloud Computing", "Security"], decision=MANUAL_REVIEW, needs human judgment on dominance

#### Scenario: No Applicable Dimensions
- GIVEN paper_sims=[0.42, 0.35, 0.28] (all below 0.5 threshold)
- WHEN rocchio_classifier executes
- THEN classification_labels=[], decision=EXCLUDED, confidence=1.0 - max_sim

#### Configuration
```yaml
rocchio_classifier:
  model: "all-mpnet-base-v2"
  dimension_threshold: 0.5
  initialize_from_research_question: true
```

#### Validation
- 'model' MUST be string if present
- 'dimension_threshold' MUST be float in [0, 1]
- 'initialize_from_research_question' MUST be boolean

---

### Requirement: LLM-Based Dimension Classification with Dominance Scoring

The system MUST classify papers using Claude with per-dimension dominance scoring and aggregated confidence bands for INCLUDED/MANUAL_REVIEW/EXCLUDED decisions.

#### Design Details

**Classification Output Format**:
Claude returns JSON with per-dimension classifications:
```json
{
  "classifications": {
    "dimension_name": {
      "applies": true,
      "dominance": 0.0 | 0.5 | 1.0,
      "reasoning": "explanation"
    }
  },
  "overall_decision": "include|exclude|review",
  "summary": "summary text"
}
```

**Dominance Scoring**:
- **1.0**: Dimension is PRIMARY FOCUS or explicitly dominant in paper
- **0.5**: Dimension is ADDRESSED or discussed but not dominant
- **0.0**: Dimension NOT addressed or not relevant

**Decision Logic**:
- Normalizes dominance scores: >=0.75 → 1.0, >=0.25 → 0.5, else 0.0
- Computes average confidence = sum(classification_vector) / num_dimensions
- Applies threshold logic:
  - avg_confidence >= auto_include (default 0.75) → INCLUDED
  - avg_confidence >= manual_review (default 0.55) → MANUAL_REVIEW
  - avg_confidence < auto_exclude (default 0.55) → EXCLUDED

**Model**: Default "claude-opus-4-20250514" (can override via config).

**Cost Tracking**: Records output tokens and costs in results stats.

#### Scenario: Single Dominant Dimension
- GIVEN paper clearly focused on "Cloud Security", other dimensions addressed minimally
- WHEN llm_classification executes
- THEN classifications={"Cloud Security": 1.0, "Machine Learning": 0.0, ...}, avg_confidence=0.33, decision=MANUAL_REVIEW (or EXCLUDED if threshold=0.55)

#### Scenario: Multiple Applicable Dimensions
- GIVEN paper discussing "Cloud Security" AND "ML Privacy"
- WHEN llm_classification executes
- THEN classifications={"Cloud Security": 0.5, "ML Privacy": 0.5, ...}, avg_confidence=0.33, likely decision=MANUAL_REVIEW

#### Scenario: High Confidence Multi-Dimensional
- GIVEN paper addressing three dimensions substantively
- WHEN llm_classification executes
- THEN classifications={"Dim1": 0.5, "Dim2": 0.5, "Dim3": 1.0}, avg_confidence=0.67, decision depends on thresholds

#### Configuration
```yaml
llm_classification:
  model: "claude-opus-4-20250514"
  thresholds:
    auto_include: 0.75
    manual_review: 0.55
    auto_exclude: 0.55
```

#### Validation
- 'model' MUST be string if present
- 'thresholds' dict: auto_include, manual_review, auto_exclude MUST be float in [0, 1]
- ANTHROPIC_API_KEY environment variable MUST be set

---

### Requirement: Screening Decision Tracking and Aggregation

The system MUST track paper screening decisions across all stages with full audit trail, maintain current_stage indicator, and aggregate final_decision based on multi-stage results.

#### Design Details

**Decision Tracking Model** (`Paper.screening`):
```python
class Screening:
  deduplication: DeduplicationResult  # Output from deduplication step
  journal_screening: JournalScreeningResult  # Output from journal_screening
  metadata_screening: MetadataScreening  # Output from metadata_screening
  keyword_screening: KeywordScreening  # Output from keyword_screening
  semantic_screening: SemanticScreening  # Output from semantic/rocchio/llm screening

  current_stage: str  # "deduplication_complete", "keyword_screening_passed", etc.
  final_decision: ScreeningDecision  # INCLUDED, EXCLUDED, PENDING, UNCERTAIN, MANUAL_REVIEW
  final_decision_by: str  # "automated:stage_name" or "manual"
```

**ScreeningDecision Enum**:
- **INCLUDED**: Paper passes all screening stages
- **EXCLUDED**: Paper failed a screening stage
- **EXCLUDED_DUPLICATE**: Paper marked duplicate of another paper
- **EXCLUDED_INCOMPLETE**: Paper missing required metadata (title, abstract, keywords)
- **PENDING**: No screening decision yet
- **UNCERTAIN**: Multiple stages provided conflicting signals
- **MANUAL_REVIEW**: Borderline case requiring human judgment

**Decision Aggregation**:
1. Deduplication step sets final_decision=EXCLUDED_DUPLICATE if duplicate
2. Metadata step sets final_decision=EXCLUDED if exclusion rule matched
3. Keyword step sets final_decision if EXCLUDED_INCOMPLETE or if inclusion_is_final=true AND screening_decision=INCLUDED
4. Semantic/Rocchio/LLM steps set final_decision for PENDING/UNCERTAIN papers

**Idempotency**: Each step only processes papers where screening result is None (hasn't been run before).

#### Scenario: Full Pipeline Decision Tracking
- GIVEN a new paper P with all screening steps enabled
- WHEN the pipeline executes deduplication (pass), then metadata screening detects P.language matches the exclude list
- THEN P.screening.metadata_screening SHALL be created with exclusion reason
- AND P.screening.final_decision SHALL be EXCLUDED
- AND P.screening.final_decision_by SHALL be "automated:metadata_screening"
- AND subsequent screening steps SHALL be skipped since final_decision != PENDING

#### Scenario: Uncertain Paper to Manual Review
- GIVEN a paper P that passes deduplication, journal, and metadata screening with final_decision=PENDING
- WHEN keyword screening passes (inclusion_is_final=false) and semantic screening computes similarity_score=0.57 (in range [manual_review=0.55, auto_include=0.65])
- THEN P.screening.final_decision SHALL be MANUAL_REVIEW
- AND P.screening.final_decision_by SHALL be "automated:semantic_screening"
- AND P.screening.current_stage SHALL be "semantic_screening_complete"

#### Scenario: Early Termination at Deduplication
- GIVEN papers with 30% duplicates
- WHEN deduplication runs
- THEN duplicate papers set final_decision=EXCLUDED_DUPLICATE immediately, skip remaining stages
- RESULT: Only unique papers flow to subsequent stages

#### Configuration (Pipeline Order)
```yaml
stages:
  - step: "Deduplication"
    builtin.deduplication: {...}
  - step: "Journal Screening"
    builtin.journal_screening: {...}
  - step: "Metadata Screening"
    builtin.metadata_screening: {...}
  - step: "Keyword Screening"
    builtin.keyword_screening: {...}
  - step: "Semantic Screening"
    builtin.semantic_screening: {...}
  - step: "Rocchio Classification"
    builtin.rocchio_screening: {...}
```

---

### Requirement: Citation Boost for Rocchio Classification

When a paper has 4+ citations, Rocchio-based classification MUST mark it for manual review to account for potential impact despite embedding-based uncertainty.

#### Design Details

**Citation Threshold**: Papers with citation_count >= 4 treated as high-impact.

**Manual Review Elevation**: If Rocchio classification would mark paper UNCERTAIN or EXCLUDED, but citation_count >= 4, override final_decision to MANUAL_REVIEW with reasoning "High-citation paper (X citations) requires manual decision".

#### Scenario: High-Citation Paper with Low Rocchio Score
- GIVEN paper P with citation_count=5, Rocchio score=0.25 (below reject_threshold=0.3)
- WHEN rocchio_screening executes
- THEN normally would classify as REJECTED, but citation_count >= 4 elevates decision=MANUAL_REVIEW

---

## Metadata

### Implementation Files

- [deduplication.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/deduplication.py)
- [journal_screening.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/journal_screening.py)
- [metadata_screening.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/metadata_screening.py)
- [keyword_screening.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/keyword_screening.py)
- [semantic_screening.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/semantic_screening.py)
- [rocchio_screening.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/rocchio_screening.py)
- [rocchio_classifier.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/rocchio_classifier.py)
- [llm_classification.py](/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/llm_classification.py)

### Test Coverage

Tests located in `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/tests/unit/` (reference existing test patterns).

### Related Specifications

- [001-data-models](../001-data-models/spec.md) — Paper, Screening, ScreeningDecision models and data structures
- [002-pipeline-engine](../002-pipeline-engine/spec.md) — Pipeline orchestration and step execution
- [005-embedding-system](../005-embedding-system/spec.md) — Embedding models and sentence-transformers integration

### Architectural Decision Records

- [ADR-0002: Step Architecture](../../../docs/adr/0002-step-architecture.md) — Class-based BaseStep with validate/execute, step registry used by screening steps
- [ADR-0004: Source Structure & Test Organization](../../../docs/adr/0004-source-setup.md) — Module layout and three-tier test strategy

---

## References

- **RFC 2119**: https://datatracker.ietf.org/doc/html/rfc2119
- **Rocchio Algorithm**: https://nlp.stanford.edu/IR-book/html/htmledition/rocchio-classification-1.html
- **Sentence Transformers**: https://www.sbert.net/
- **Python difflib.SequenceMatcher**: https://docs.python.org/3/library/difflib.html

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
