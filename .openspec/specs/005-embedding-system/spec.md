# Embedding System Specification

**Domain:** Semantics
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

## Overview

The Embedding System provides semantic representation of academic papers through dense vector embeddings. It implements a hierarchical approach to transform paper text into multi-level semantic vectors suitable for similarity search, document clustering, and adaptive classification. The system integrates text extraction, citation removal, hierarchical chunking, batch embedding generation, and Rocchio-based vector math for incremental classifier adaptation.

### Philosophy

1. **Hierarchical Representation**: Papers are decomposed into three hierarchy levels (paper → section → paragraph) to capture semantic meaning at multiple granularities, enabling both coarse-grained paper-level similarity and fine-grained chunk-level retrieval.

2. **Domain-Specific Structure**: The system recognizes canonical academic paper sections (Introduction, Methods, Results, Discussion, Conclusion, etc.) enabling structure-aware embedding and semantic consistency across heterogeneous papers.

3. **Efficient Batch Processing**: Embeddings are generated in batches using GPU acceleration (MPS for Apple Silicon, CUDA for NVIDIA, CPU fallback) to minimize latency and maximize throughput during large-scale paper analysis.

### Key Capabilities

- **SentenceTransformers Embeddings**: Generate 768-dimensional dense vectors using the `all-mpnet-base-v2` pre-trained model, optimized for semantic similarity in academic and technical domains.
- **Hierarchical Chunking**: Decompose papers into three levels (Level 0: paper root, Level 1: canonical sections, Level 2: paragraphs >20 chars) for multi-granularity semantic analysis.
- **Automatic Text Extraction**: Extract text from PDF documents using `pdfplumber` with page-by-page processing and section detection.
- **Citation Removal**: Strip in-text citations (e.g., `[Author, Year]`, `(Author et al., 2024)`) before embedding to reduce noise and improve semantic representation.
- **Canonical Section Detection**: Identify 15+ standard academic sections (Introduction, Methods, Results, etc.) using 70+ regex patterns, normalizing diverse paper structures.
- **Batch Embedding Generation**: Process up to 32 chunks per batch with device selection (MPS→CUDA→CPU) for optimal performance across hardware platforms.
- **Rocchio Vector Math**: Implement incremental centroid-based classification with adaptive decision boundaries using weighted query vectors: `α·q + β·c_relevant - γ·c_irrelevant`.
- **pgvector Storage**: Store embeddings in PostgreSQL with pgvector extension for fast similarity search across papers and chunks.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: Embedding Model Selection and Initialization

The system MUST use SentenceTransformers to load pre-trained embedding models, with `all-mpnet-base-v2` as the default model. The system MUST initialize the model with device selection priority: MPS (Apple Silicon) → CUDA (NVIDIA GPU) → CPU (fallback).

#### Scenario: Load Embedding Model on Apple Silicon
- GIVEN a system with Apple Silicon GPU (MPS available)
- WHEN the `GenerateEmbeddingsStep` initializes without explicit device specification
- THEN the system SHALL detect MPS availability via `torch.backends.mps.is_available()` and set device to `"mps"`
- AND the model SHALL be moved to MPS device via `model.to("mps")`
- AND the dimension property SHALL return `768` for `all-mpnet-base-v2`

#### Scenario: Fallback to CPU When CUDA Not Available
- GIVEN a system without CUDA or MPS
- WHEN the `GenerateEmbeddingsStep` initializes
- THEN the system SHALL set device to `"cpu"`
- AND embeddings SHALL be generated using CPU-based SentenceTransformers encoding

#### Scenario: Explicit Device Override
- GIVEN a `GenerateEmbeddingsStep` with config `{"device": "cuda"}`
- WHEN the step executes
- THEN the system SHALL use the device specified in config, overriding auto-detection

### Requirement: Vector Dimension and Model Metadata

The embedding vectors MUST be 768-dimensional for `all-mpnet-base-v2`. The system MUST store model metadata (model name, dimension) alongside each embedding vector.

#### Scenario: Embedding Vector Dimension Validation
- GIVEN a paper chunk with text "This is a research paper abstract"
- WHEN the `_generate_embedding()` method encodes the text with `all-mpnet-base-v2`
- THEN the returned vector SHALL have exactly 768 elements
- AND the `Embedding` object SHALL store `model="all-mpnet-base-v2"` and `text_source="section"` or `text_source="aggregated_paragraphs"`

#### Scenario: Dimension Mismatch Handling
- GIVEN an embedding vector with fewer than 768 dimensions (e.g., 384 from a different model)
- WHEN the vector is validated in `_generate_embedding()`
- THEN the system SHALL pad the vector with zeros to reach 768 dimensions
- AND if the vector exceeds 768 dimensions, the system SHALL truncate to 768 elements

### Requirement: PDF Text Extraction and Structure Detection

The system MUST extract text from PDF documents page-by-page using `pdfplumber`. The system MUST detect canonical paper sections using regex patterns covering markdown headers, numbered sections, ALL CAPS headers, and common academic section names.

#### Scenario: Extract Text from Multi-Page Academic PDF
- GIVEN a PDF file at `/path/to/paper.pdf` with 15 pages
- WHEN `PDFExtractor.extract()` is called
- THEN the system SHALL iterate through all pages using `pdfplumber.open(pdf_path)`
- AND each page text SHALL be extracted via `page.extract_text()`
- AND pages SHALL be concatenated with `"\n\n"` separator
- AND the result SHALL contain `"raw_sections"` detected by `detect_sections(text)`

#### Scenario: Detect Canonical Sections with Multiple Naming Conventions
- GIVEN paper text with sections named "Research Methods", "1.1. Methods", and "METHODOLOGY"
- WHEN `detect_sections(text)` is called
- THEN the system SHALL match "Research Methods" via pattern `r"^(Research\s+Methods?)$"`
- AND "1.1. Methods" via pattern `r"^(\d+\.\d+\.?\s+[A-Z][^.!?]+)$"`
- AND "METHODOLOGY" via pattern `r"^([A-Z][A-Z\s]{2,}:?)$"`
- AND all three MUST be recognized as equivalent to canonical section "methods"

#### Scenario: Map Detected Sections to Canonical Hierarchy
- GIVEN raw sections `[{"title": "Related Work", "content": "..."}, {"title": "Results", "content": "..."}]`
- WHEN `group_sections_hierarchically(sections)` is called
- THEN "Related Work" SHALL map to canonical "literature"
- AND "Results" SHALL map to canonical "findings"
- AND the output SHALL be `{"literature": [...], "findings": [...], "other": []}`

### Requirement: Citation Removal

The system MUST detect and remove in-text citations from paper text before embedding. Citation patterns MUST include brackets citations `[Author, Year]`, parenthetical citations `(Author et al., Year)`, and author-year citations `Author (Year)`. The system MUST track removal statistics (characters and tokens removed).

#### Scenario: Remove Multiple Citation Formats
- GIVEN text: "Smith et al. [Smith, 2023] found that technology (Jones et al., 2022) improves [efficiency]. Brown (2021) concluded..."
- WHEN `CitationRemover.remove_citations(text)` is called
- THEN the result SHALL have:
  - `"[Smith, 2023]"` removed
  - `"(Jones et al., 2022)"` removed
  - `"[efficiency]"` removed (brackets citation format)
  - `"Brown (2021)"` removed
- AND the returned dict SHALL include `"citations_found": 4`
- AND `"removed_chars"` SHALL be > 0
- AND `"removed_tokens"` SHALL be > 0

#### Scenario: Track Citation Removal Statistics
- GIVEN original text with 5000 characters and 800 tokens
- WHEN citations are removed, leaving 4800 characters and 750 tokens
- THEN the stats dict SHALL contain:
  - `"original_chars": 5000`
  - `"original_tokens": 800`
  - `"removed_chars": 200`
  - `"removed_tokens": 50`
  - `"removed_percentage_chars": 4.0`
  - `"removed_percentage_tokens": 6.25`

### Requirement: Hierarchical Text Chunking

The system MUST create a 3-level hierarchy of text chunks: Level 0 (paper root), Level 1 (canonical sections), Level 2 (paragraphs >20 characters). Each chunk MUST store metadata including chunk index, section name, hierarchy level, and parent-child relationships.

#### Scenario: Create Hierarchical Chunk Structure for Paper
- GIVEN a paper with title, abstract, introduction, methods, and results sections
- WHEN `GenerateEmbeddingsStep._create_chunks(paper)` is called
- THEN the system SHALL create:
  - **Level 0 (1 chunk)**: Paper root chunk with `hierarchy_level=0`, `text="[Paper root]"`, `parent_chunk=None`
  - **Level 1 (5 chunks)**: One section chunk per canonical section with `hierarchy_level=1`, `section="<section_name>"`, `parent_chunk=paper_chunk`
  - **Level 2 (N chunks)**: Paragraph chunks with `hierarchy_level=2`, `section="<section_name>"`, `parent_chunk=section_chunk`
- AND all Level 2 paragraphs MUST have length > 20 characters

#### Scenario: Preserve Parent-Child Chunk Relationships
- GIVEN a section chunk representing "Methods" section
- WHEN paragraph chunks are created from that section
- THEN each paragraph chunk SHALL have:
  - `parent_chunk` pointing directly to the Methods section chunk
  - The section chunk SHALL have all paragraphs in `children_chunks` list
  - Traversing `children_chunks` SHALL reconstruct the hierarchy

#### Scenario: Skip Root-Level Embedding Generation
- GIVEN the chunk hierarchy with Level 0, 1, and 2 chunks
- WHEN `_aggregate_embeddings()` generates embeddings
- THEN the root chunk (Level 0) SHALL NOT be embedded
- AND only Level 1 (sections) and Level 2 (paragraphs) chunks MUST be embedded

### Requirement: Batch Embedding Generation

The system MUST generate embeddings in batches for efficiency. The default batch size MUST be 32. The system MUST support configurable batch sizes. The system MUST use multi-pass processing: Pass 1 creates chunk structure, Pass 2 generates embeddings, then aggregates paragraph embeddings to section level.

#### Scenario: Generate Embeddings in Batches
- GIVEN 65 chunks to embed (sections and paragraphs)
- WHEN `model.encode(texts, batch_size=32)` is called
- THEN the system SHALL process:
  - Batch 1: chunks 1-32
  - Batch 2: chunks 33-64
  - Batch 3: chunk 65
- AND all batches SHALL produce 768-dimensional vectors

#### Scenario: Multi-Pass Embedding Generation
- GIVEN 10 papers with hierarchical chunk structure created in Pass 1
- WHEN `execute()` runs Pass 2
- THEN:
  - **Pass 2a**: Embed Level 1 (sections) and Level 2 (paragraphs) chunks directly
  - **Pass 2b**: Aggregate paragraph embeddings to create section embeddings via `np.mean(para_embeddings, axis=0)`
  - **Statistics**: Track `sections_embedded`, `paragraphs_embedded`, `section_aggregations` separately

#### Scenario: Skip Papers Without Chunks
- GIVEN a paper with `text_chunks=None` or empty
- WHEN Pass 2 processes papers
- THEN the system SHALL skip this paper and not generate embeddings
- AND no stats SHALL be incremented for this paper

### Requirement: Section Embedding Aggregation

The system MUST create section-level embeddings by averaging the embeddings of all paragraphs within that section. Section embeddings MUST be marked with `text_source="aggregated_paragraphs"`. Section embeddings MUST NOT replace individual paragraph embeddings; both MUST coexist.

#### Scenario: Aggregate Paragraph Embeddings to Section Embedding
- GIVEN a Methods section with 5 paragraphs, each with 768-dimensional embedding
- WHEN `_aggregate_embeddings()` processes the section
- THEN:
  - Extract all 5 paragraph embeddings as numpy arrays
  - Compute `np.mean(para_embeddings, axis=0)` to get 768-dimensional section vector
  - Create new `Embedding` object with `text_source="aggregated_paragraphs"`
  - Attach to section chunk: `section_chunk.embedding = aggregated_embedding`
- AND each paragraph SHALL retain its original embedding

#### Scenario: Handle Sections With No Paragraph Embeddings
- GIVEN a section with 3 paragraphs, but none have embeddings (e.g., all text < 5 chars)
- WHEN `_aggregate_embeddings()` processes the section
- THEN the section SHALL NOT receive an aggregated embedding
- AND the aggregation count SHALL NOT be incremented

### Requirement: Citation Removal Before Embedding

The system MUST remove citations from paper text before generating embeddings. Citation removal SHALL be applied at the section level before paragraph-level embeddings are generated.

#### Scenario: Apply Citation Removal During Chunk Creation
- GIVEN a section with text containing citations: "Smith [2023] found that methods (Jones et al., 2022) work well"
- WHEN `_create_chunks()` creates a section chunk
- THEN:
  - Call `self.citation_remover.remove_citations(section_content)`
  - Use the cleaned text for creating paragraph chunks
  - Generate embeddings from the cleaned text (without citations)

### Requirement: Rocchio Vector Math

The system MUST implement the Rocchio algorithm for adaptive query expansion. The system MUST maintain persistent centroids for relevant and irrelevant papers. The classification formula MUST be: `query_vector = α·q + β·c_relevant - γ·c_irrelevant` where α=1.0 (query weight), β=0.75 (relevant weight), γ=0.15 (irrelevant weight). The system MUST support incremental centroid updates in O(dimension) time without recomputing from scratch.

#### Scenario: Initialize Rocchio Screener With Query Embedding
- GIVEN a research question embedding vector (768-dimensional)
- WHEN `AdaptiveRocchioScreener.initialize_from_research_question(rq_embedding)` is called
- THEN `self.state.query_centroid` SHALL store the research question vector
- AND the state SHALL be ready for classification

#### Scenario: Bootstrap Centroids From Seed Labeled Papers
- GIVEN 10 accepted paper embeddings and 5 rejected paper embeddings
- WHEN `bootstrap_from_seeds(accepted_embeddings, rejected_embeddings)` is called
- THEN:
  - `centroid_relevant = np.mean(accepted_embeddings, axis=0)` (768-dimensional)
  - `centroid_irrelevant = np.mean(rejected_embeddings, axis=0)` (768-dimensional)
  - `count_relevant = 10`
  - `count_irrelevant = 5`

#### Scenario: Classify Paper Using Rocchio Query Vector
- GIVEN:
  - Query centroid q (768-dimensional)
  - Relevant centroid c_rel (768-dimensional)
  - Irrelevant centroid c_irrel (768-dimensional)
  - Paper embedding d (768-dimensional)
  - Weights: α=1.0, β=0.75, γ=0.15
- WHEN `classify(paper_embedding)` is called
- THEN:
  - Compute `query_vector = 1.0·q + 0.75·c_rel - 0.15·c_irrel`
  - Normalize: `q_norm = ||query_vector||`, `d_norm = ||d||`
  - Compute cosine similarity: `score = (d · query_vector) / (d_norm · q_norm)`
  - Normalize to [0,1]: `score = (score + 1) / 2`
  - Make decision:
    - IF `score >= 0.7` THEN return `"ACCEPT"`
    - ELSE IF `score <= 0.3` THEN return `"REJECT"`
    - ELSE return `"UNCERTAIN"`

#### Scenario: Incrementally Update Relevant Centroid
- GIVEN current relevant centroid c_rel for 10 papers
- WHEN a new paper embedding p is classified as relevant via `update_centroid(p, is_relevant=True)`
- THEN incrementally compute:
  - `count_new = 10 + 1 = 11`
  - `c_rel_new = c_rel + (p - c_rel) / 11`
- AND this O(768) operation SHALL NOT require recomputing centroid from all 11 papers

#### Scenario: Persist Rocchio State Across Sessions
- GIVEN an `AdaptiveRocchioScreener` with populated centroids
- WHEN `get_state()` is called
- THEN return `ScreeningState` with:
  - `centroid_relevant` as list (for JSON serialization)
  - `centroid_irrelevant` as list
  - `query_centroid` as list
  - `count_relevant`, `count_irrelevant`, `iteration` tracking
  - `alpha=1.0`, `beta=0.75`, `gamma=0.15` (Rocchio weights)
  - `accept_threshold=0.7`, `reject_threshold=0.3`
- AND this state SHALL be loadable via `from_dict()` to restore screener in next session

### Requirement: Chunk-to-Chunk Similarity Search

The system MUST support computing cosine similarity between embeddings across papers. The system MUST enable retrieval of semantically similar chunks from the same paper or different papers.

#### Scenario: Compute Cosine Similarity Between Two Chunks
- GIVEN two embeddings from different papers:
  - Chunk A: `v_a = [0.1, 0.2, ..., 0.9]` (768-dimensional)
  - Chunk B: `v_b = [0.15, 0.22, ..., 0.85]` (768-dimensional)
- WHEN similarity is computed as `cos_sim = (v_a · v_b) / (||v_a|| · ||v_b||)`
- THEN the result SHALL be in range [-1, 1] (or [0, 1] after normalization)
- AND higher values indicate greater semantic similarity

### Requirement: pgvector Storage and Retrieval

The system MUST store embeddings in PostgreSQL using the pgvector extension. The system MUST support vector similarity search. The system MUST index embeddings for fast retrieval.

#### Scenario: Store Paper and Chunk Embeddings in pgvector
- GIVEN 100 papers with hierarchical chunks (total 5000 chunks)
- WHEN embeddings are saved to the database
- THEN:
  - Each chunk embedding SHALL be stored in a pgvector column
  - Vector dimension MUST match pgvector index (768 dimensions)
  - Parent-child relationships SHALL be preserved via foreign keys

#### Scenario: Query Similar Chunks Using Vector Similarity
- GIVEN a query chunk embedding `q` (768-dimensional)
- WHEN a similarity search is performed: `SELECT * FROM chunks ORDER BY embedding <-> q LIMIT 10`
- THEN the system SHALL return the 10 most similar chunks across the corpus
- AND results SHALL be ordered by cosine distance (ascending)

### Requirement: Configuration Validation

The system MUST validate the `generate_embeddings` step configuration. The system MUST reject invalid model names, batch sizes, or device specifications.

#### Scenario: Validate Step Configuration
- GIVEN config `{"model": "all-mpnet-base-v2", "device": "mps", "batch_size": 32}`
- WHEN `GenerateEmbeddingsStep.validate(config)` is called
- THEN `is_valid=True` and `errors=[]`

#### Scenario: Reject Invalid Device Configuration
- GIVEN config `{"device": "gpu"}` (invalid device name)
- WHEN `validate(config)` is called
- THEN `is_valid=False` and errors SHALL contain `"'device' must be 'cpu', 'cuda', or 'mps'"`

#### Scenario: Reject Invalid Batch Size
- GIVEN config `{"batch_size": -5}`
- WHEN `validate(config)` is called
- THEN `is_valid=False` and errors SHALL contain `"'batch_size' must be a positive integer"`

### Requirement: Paper Structure Validation

The system MUST validate that extracted paper structure contains expected canonical sections. The system MUST report coverage percentage and list missing sections.

#### Scenario: Report Paper Structure Coverage
- GIVEN a paper with detected sections: `["title", "abstract", "introduction", "methods", "findings", "conclusion"]`
- WHEN `validate_paper_structure(hierarchical)` is called
- THEN the result SHALL contain:
  - `"found": ["title", "abstract", "introduction", "methods", "findings", "conclusion"]` (6 sections)
  - `"missing": ["keywords", "background", ...]` (sections not detected)
  - `"coverage_percentage": 50.0` (6 out of 12 canonical sections)
  - `"total_detected": 6` (total section count across all papers)

### Requirement: Paragraph Splitting Heuristics

The system MUST split section content into paragraphs using double-newline delimiters or line-by-line heuristics. The system MUST filter out paragraphs with fewer than 20 characters. Paragraphs MUST be reconstructed from line-level text to preserve readability.

#### Scenario: Split Section Into Valid Paragraphs
- GIVEN section text with multiple paragraphs separated by blank lines:
  ```
  This is paragraph one. It has multiple sentences.
  It continues here.

  This is paragraph two with different content.

  Para3
  ```
- WHEN `_split_paragraphs(text)` is called
- THEN return:
  - Paragraph 1: "This is paragraph one. It has multiple sentences. It continues here."
  - Paragraph 2: "This is paragraph two with different content."
  - Paragraph 3: NOT included (only 5 chars, < 20 char minimum)

---

## Metadata

### Implementation Files

- [src/paper_scanner/tools/embedding/embedder.py](../../../src/paper_scanner/tools/embedding/embedder.py) - SentenceTransformers model initialization and embedding generation
- [src/paper_scanner/tools/embedding/chunker.py](../../../src/paper_scanner/tools/embedding/chunker.py) - PDF extraction, sentence-level chunking with overlap, section-aware hybrid chunking
- [src/paper_scanner/tools/embedding/citation_remover.py](../../../src/paper_scanner/tools/embedding/citation_remover.py) - Citation detection and removal with statistical tracking
- [src/paper_scanner/tools/embedding/extractor.py](../../../src/paper_scanner/tools/embedding/extractor.py) - PDF text extraction using pdfplumber with hierarchical section grouping
- [src/paper_scanner/tools/embedding/sections.py](../../../src/paper_scanner/tools/embedding/sections.py) - Canonical section detection (70+ patterns), section normalization, hierarchy validation
- [src/paper_scanner/tools/documents/rocchio.py](../../../src/paper_scanner/tools/documents/rocchio.py) - Rocchio algorithm implementation, persistent state management, incremental centroid updates
- [src/paper_scanner/steps/generate_embeddings.py](../../../src/paper_scanner/steps/generate_embeddings.py) - Pipeline step for multi-pass embedding generation, device selection, batch processing

### Test Coverage

The following test files verify the requirements in this specification:

**Embedding Generation:**
- [tests/unit/steps/test_generate_embeddings_hierarchical.py](../../../tests/unit/steps/test_generate_embeddings_hierarchical.py) - Hierarchical embedding generation
- [tests/unit/io/test_embedding_persistence.py](../../../tests/unit/io/test_embedding_persistence.py) - Embedding storage and retrieval

**Caching:**
- [tests/unit/core/test_jsoncache.py](../../../tests/unit/core/test_jsoncache.py) - JSON cache implementation
- [tests/unit/core/test_jsoncache_expire.py](../../../tests/unit/core/test_jsoncache_expire.py) - Cache expiration logic
- [tests/unit/core/test_pdfcache.py](../../../tests/unit/core/test_pdfcache.py) - PDF cache management
- [tests/unit/core/test_cache_404_marker.py](../../../tests/unit/core/test_cache_404_marker.py) - Cache miss handling

### Related Specifications

- [001-data-models](../001-data-models/spec.md) — Core data structures: Paper, TextChunk, Embedding models
- [002-pipeline-engine](../002-pipeline-engine/spec.md) — Step execution framework, pipeline orchestration
- [003-screening-workflow](../003-screening-workflow/spec.md) — Screening pipeline using embeddings for adaptive classification
- [004-metadata-fetching](../004-metadata-fetching/spec.md) — Metadata sources that provide paper titles and abstracts for embedding

### Architectural Decision Records

- [ADR-0004: Source Structure & Test Organization](../../../docs/adr/0004-source-setup.md) — Module layout and three-tier test strategy

---

## References

- **SentenceTransformers Library**: https://www.sbert.net/
  - Model: `all-mpnet-base-v2` — 768-dimensional sentence embeddings optimized for semantic similarity
  - https://huggingface.co/sentence-transformers/all-mpnet-base-v2

- **RFC 2119 - Key words**: https://datatracker.ietf.org/doc/html/rfc2119

- **Rocchio Algorithm**: Rocchio Jr., J. J. (1971). "Relevance feedback in information retrieval."
  - Formula: `q' = α·q + β·∑(rel) - γ·∑(nonrel)`
  - Standard weights: α=1.0, β=0.75, γ=0.15

- **pgvector Extension**: https://github.com/pgvector/pgvector
  - PostgreSQL extension for vector similarity search
  - Operators: `<->` (L2 distance), `<#>` (negative inner product), `<=>` (cosine distance)

- **pdfplumber Library**: https://github.com/jsvine/pdfplumber
  - Python library for extracting text and structure from PDFs

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
