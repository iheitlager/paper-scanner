# LLM-First Parsing and Screening Specification

**Domain:** AI Processing
**Version:** 1.0.0
**Status:** Proposed
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

## Overview

The LLM-First Parsing and Screening system establishes Claude Haiku as the primary intelligence layer for both paper screening and content parsing. This specification defines how Haiku analyzes titles, keywords, and abstracts for screening decisions, and how it extracts and structures paper sections for semantic embedding generation.

This layer is responsible for:
- LLM-based rapid screening of paper metadata (title, abstract, keywords)
- Intelligent section extraction and boundary detection from PDF text
- Structured parsing of academic paper components (introduction, methods, results, etc.)
- Quality assessment and confidence scoring for screening decisions
- Section-aware chunking that respects paper structure

### Philosophy

1. **LLM-First Architecture**: Haiku is the default and primary engine for both screening and parsing, replacing rule-based and pattern-matching approaches with intelligent natural language understanding.

2. **Fast and Cost-Effective**: Haiku provides the optimal balance of speed, accuracy, and cost for high-volume paper processing, enabling real-time screening and parsing at scale.

3. **Structured Output**: LLM responses are structured and validated, providing deterministic outputs (JSON schemas) for downstream processing while maintaining the flexibility of natural language understanding.

4. **Graceful Degradation**: The system can fall back to traditional pattern-based methods if LLM services are unavailable, ensuring pipeline resilience.

### Key Capabilities

- **Rapid Metadata Screening**: Haiku analyzes title, abstract, and keywords in <2s to determine paper relevance with confidence scores and reasoning
- **Intelligent Section Detection**: Identifies paper sections (abstract, introduction, methods, results, discussion, conclusion) with fuzzy matching and context awareness
- **Semantic Chunking**: Chunks sections intelligently based on semantic meaning and paper structure, not just token limits
- **Multi-Criteria Evaluation**: Screens papers against research questions, inclusion criteria, and quality thresholds with explainable decisions
- **Batch Processing**: Handles multiple papers concurrently with rate limiting and queue management

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: LLM-Based Metadata Screening

The system MUST use Claude Haiku to analyze paper title, abstract, and keywords for screening decisions before applying rule-based filters.

#### Scenario: Screen paper with clear relevance

- GIVEN a paper with title="Machine Learning for Systematic Reviews", abstract="This study presents...", keywords=["systematic review", "machine learning"]
- AND screening criteria="Include papers about ML in systematic reviews"
- WHEN LLM screening is invoked
- THEN Haiku SHALL return decision="INCLUDE", confidence=0.95, reasoning="Paper directly addresses ML in systematic reviews"
- AND processing SHALL complete in <2 seconds

#### Scenario: Screen paper with ambiguous relevance

- GIVEN a paper with title="Neural Networks in Healthcare", abstract="...", keywords=["deep learning", "medical diagnosis"]
- AND screening criteria="Include papers about systematic reviews"
- WHEN LLM screening is invoked
- THEN Haiku SHALL return decision="UNCERTAIN", confidence=0.60, reasoning="Paper is about ML in healthcare but not specifically systematic reviews"
- AND recommendation="MANUAL_REVIEW"

#### Scenario: Screen paper with clear exclusion

- GIVEN a paper with title="A Survey of Database Indexing", abstract="...", keywords=["databases", "b-tree"]
- AND screening criteria="Include papers about ML in systematic reviews"
- WHEN LLM screening is invoked
- THEN Haiku SHALL return decision="EXCLUDE", confidence=0.98, reasoning="Paper is about database systems, not relevant to ML or systematic reviews"

---

### Requirement: Structured LLM Response Format

The system MUST request and validate structured JSON responses from Haiku with predefined schemas.

#### Scenario: Screening response validation

- GIVEN a screening request to Haiku
- WHEN the response is received
- THEN the response MUST conform to schema:
```json
{
  "decision": "INCLUDE|EXCLUDE|UNCERTAIN",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "relevant_keywords": ["string"],
  "recommendation": "PROCEED|MANUAL_REVIEW|FULL_TEXT_NEEDED"
}
```
- AND the system SHALL reject responses that don't match schema

#### Scenario: Section parsing response validation

- GIVEN a section parsing request to Haiku
- WHEN the response is received
- THEN the response MUST conform to schema:
```json
{
  "sections": [
    {
      "type": "abstract|introduction|methods|results|discussion|conclusion|other",
      "title": "string",
      "start_page": integer,
      "content_summary": "string",
      "chunk_boundaries": [integer]
    }
  ],
  "paper_type": "research_article|review|meta_analysis|case_study",
  "quality_indicators": {
    "has_clear_structure": boolean,
    "sections_detected": integer
  }
}
```

---

### Requirement: Section Detection and Extraction

The system MUST use Haiku to identify and extract paper sections from raw PDF text with context-aware boundary detection.

#### Scenario: Detect standard IMRaD structure

- GIVEN a research paper with PDF text containing "ABSTRACT", "1. Introduction", "2. Methods", "3. Results", "4. Discussion"
- WHEN section detection is invoked
- THEN Haiku SHALL identify sections: abstract, introduction, methods, results, discussion
- AND provide page numbers and approximate word counts for each section
- AND detect section boundaries even with non-standard formatting

#### Scenario: Handle non-standard section naming

- GIVEN a paper with sections "Background", "Experimental Design", "Findings", "Implications"
- WHEN section detection is invoked
- THEN Haiku SHALL map to canonical types: introduction, methods, results, discussion
- AND note original section titles in metadata

#### Scenario: Identify missing sections

- GIVEN a paper with only abstract, introduction, and conclusion
- WHEN section detection is invoked
- THEN Haiku SHALL identify present sections
- AND flag missing_sections=["methods", "results", "discussion"]
- AND set quality_indicator="incomplete_structure"

---

### Requirement: Semantic Chunking for Embeddings

The system MUST use Haiku to chunk paper sections based on semantic coherence, not just token limits.

#### Scenario: Chunk introduction section semantically

- GIVEN an introduction section with 3000 tokens containing: background (800 tokens), research gap (600 tokens), objectives (400 tokens), contributions (500 tokens)
- WHEN semantic chunking is invoked with target=512 tokens, max=768 tokens
- THEN Haiku SHALL create chunks:
  - Chunk 1: Background (800 tokens, slightly over target but semantically complete)
  - Chunk 2: Research gap + objectives (1000 tokens, combined related content)
  - Chunk 3: Contributions (500 tokens)
- AND respect semantic boundaries over strict token limits

#### Scenario: Preserve citation context

- GIVEN a results section containing "...significant improvement (Smith et al., 2020)..."
- WHEN chunking is performed
- THEN Haiku SHALL keep citations with their context
- AND not split "improvement" and "(Smith et al., 2020)" into separate chunks

---

### Requirement: Confidence Scoring and Reasoning

The system MUST provide confidence scores (0.0-1.0) and human-readable reasoning for all LLM decisions.

#### Scenario: High confidence inclusion

- GIVEN a paper clearly matching criteria
- WHEN screening completes
- THEN confidence >= 0.90
- AND reasoning explains key matching factors
- AND recommendation="PROCEED"

#### Scenario: Low confidence requiring review

- GIVEN a borderline paper
- WHEN screening completes
- THEN confidence < 0.70
- AND reasoning explains ambiguity
- AND recommendation="MANUAL_REVIEW"
- AND the paper SHALL be flagged for human review in screening results

---

### Requirement: Batch Processing and Rate Limiting

The system MUST support batch processing of multiple papers with automatic rate limiting and queue management.

#### Scenario: Process batch within rate limits

- GIVEN 50 papers to screen
- AND Haiku rate limit = 100 requests/minute
- WHEN batch screening is invoked
- THEN system SHALL process papers concurrently with max=80 requests/minute
- AND implement exponential backoff on rate limit errors
- AND complete batch in <1 minute

#### Scenario: Handle API failures gracefully

- GIVEN a batch of 20 papers
- AND Haiku API returns 503 for paper #5
- WHEN batch processing encounters error
- THEN system SHALL retry paper #5 with exponential backoff (1s, 2s, 4s, 8s)
- AND continue processing remaining papers
- AND report failed papers with error details

---

### Requirement: Fallback to Pattern-Based Methods

The system SHOULD fall back to traditional pattern-matching when LLM services are unavailable.

#### Scenario: LLM service unavailable

- GIVEN Haiku API is unreachable
- AND paper screening is requested
- WHEN LLM call fails after retries
- THEN system SHALL fall back to keyword-based screening (spec 003)
- AND log fallback event with severity=WARNING
- AND flag results as fallback_method=true

#### Scenario: Section detection fallback

- GIVEN Haiku API timeout during section parsing
- WHEN fallback is triggered
- THEN system SHALL use regex-based section detection (spec 005)
- AND proceed with reduced confidence scores
- AND recommend manual validation

---

### Requirement: Cost Tracking and Optimization

The system MUST track LLM API usage costs and provide optimization recommendations.

#### Scenario: Track per-paper costs

- GIVEN a paper screened with Haiku
- WHEN processing completes
- THEN system SHALL record:
  - Input tokens used
  - Output tokens used
  - Estimated cost (input_tokens * $0.00025/1K + output_tokens * $0.00125/1K)
  - Processing time
- AND store in paper metadata

#### Scenario: Batch cost reporting

- GIVEN a batch of 100 papers processed
- WHEN batch completes
- THEN system SHALL report:
  - Total cost: $X.XX
  - Average cost per paper: $Y.YY
  - Papers screened vs. full-text processed
  - Potential savings from early screening: $Z.ZZ

---

### Requirement: Integration with Existing Pipeline

The system MUST integrate with existing screening workflow (spec 003) and embedding system (spec 005) as a drop-in replacement.

#### Scenario: Replace keyword screening step

- GIVEN pipeline step "keyword_screening" (spec 003)
- WHEN LLM screening is enabled
- THEN step SHOULD be replaced with "llm_screening"
- AND produce identical output schema (ScreeningDecision, passed, reasoning)
- AND maintain backward compatibility with existing checkpoints

#### Scenario: Enhance embedding generation

- GIVEN embedding generation step (spec 005)
- WHEN LLM parsing is enabled
- THEN section detection SHALL use Haiku instead of pattern matching
- AND chunking SHALL use semantic boundaries
- AND produce same TextChunk outputs with added metadata

---

## Metadata

### Implementation Files

**LLM Screening:**
- [src/paper_scanner/steps/llm_screening.py](../../../src/paper_scanner/steps/llm_screening.py) - Main LLM screening step
- [src/paper_scanner/models/haiku_handler.py](../../../src/paper_scanner/models/haiku_handler.py) - Haiku API integration

**Section Parsing:**
- [src/paper_scanner/tools/llm_parser.py](../../../src/paper_scanner/tools/llm_parser.py) - LLM-based section parser
- [src/paper_scanner/tools/llm_chunker.py](../../../src/paper_scanner/tools/llm_chunker.py) - Semantic chunking with Haiku

**Schema Validation:**
- [src/paper_scanner/core/llm_schemas.py](../../../src/paper_scanner/core/llm_schemas.py) - Pydantic schemas for LLM responses

### Test Coverage

**Unit Tests:**
- [tests/unit/steps/test_llm_screening.py](../../../tests/unit/steps/test_llm_screening.py) - LLM screening logic
- [tests/unit/tools/test_llm_parser.py](../../../tests/unit/tools/test_llm_parser.py) - Section detection
- [tests/unit/tools/test_llm_chunker.py](../../../tests/unit/tools/test_llm_chunker.py) - Semantic chunking
- [tests/unit/models/test_haiku_handler.py](../../../tests/unit/models/test_haiku_handler.py) - Haiku integration

**Integration Tests:**
- [tests/integration/test_llm_screening_pipeline.py](../../../tests/integration/test_llm_screening_pipeline.py) - End-to-end screening
- [tests/integration/test_llm_parsing_pipeline.py](../../../tests/integration/test_llm_parsing_pipeline.py) - End-to-end parsing

**Cost Tests:**
- [tests/unit/test_llm_cost_tracking.py](../../../tests/unit/test_llm_cost_tracking.py) - Cost calculation accuracy

### Related Specifications

- [003-screening-workflow](../003-screening-workflow/spec.md) - Screening pipeline that LLM screening extends
- [005-embedding-system](../005-embedding-system/spec.md) - Embedding generation that uses LLM parsing
- [002-pipeline-engine](../002-pipeline-engine/spec.md) - Pipeline orchestration for LLM steps

### Architectural Decision Records

- [ADR-0008: LLM-First Architecture](../../../docs/adr/0008-llm-first-architecture.md) - Rationale for choosing Haiku and LLM-first approach

---

## References

- **RFC 2119**: https://datatracker.ietf.org/doc/html/rfc2119
- **Claude Haiku Documentation**: https://docs.anthropic.com/claude/docs/models-overview#claude-haiku
- **Anthropic API Rate Limits**: https://docs.anthropic.com/claude/reference/rate-limits
- **Structured Output Guide**: https://docs.anthropic.com/claude/docs/structured-outputs

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
**Co-Authored-By:** Claude Sonnet 4.5 <noreply@anthropic.com>
