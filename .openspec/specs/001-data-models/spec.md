# Data Models and Database Specification

**Domain:** Core Data
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

## Overview

The data models and database layer provides the foundational architecture for paper-scanner, defining immutable bibliographic and screening data structures alongside a high-performance, indexed in-memory database for efficient CRUD operations and complex queries.

This layer is responsible for:
- Representing academic papers with comprehensive bibliographic metadata
- Managing multi-stage screening results with decision tracking
- Handling embeddings and text chunks for semantic analysis
- Indexing papers by multiple keys (DOI, citation key, ID, year, title) for O(1) lookups
- Supporting duplicate detection and deduplication workflows
- Providing fluent query capabilities for filtering, searching, and sorting
- Normalizing bibliographic fields according to standardized rules
- Generating deterministic citation keys with collision handling
- Validating and normalizing Digital Object Identifiers (DOIs)

### Philosophy

1. **Immutable Data Structures**: Data models (Paper, Author, Citation, etc.) are Pydantic BaseModels with validation, not mutable objects. Changes are explicit and traceable.

2. **Separation of Concerns**: Normalization logic is centralized in the Normalizer class; models are passive data containers. Database logic is separate from model logic. Query logic uses a builder pattern for composability.

3. **Indexed Efficiency**: The database maintains five concurrent indexes (DOI, cite_key, ID, year, title) to guarantee O(1) or O(log n) lookups without full-table scans. Indexes are automatically updated during CRUD operations.

### Key Capabilities

- Complete bibliographic representation: title, authors, journal, year, DOI, URLs, identifiers (arXiv, PMID, ISBN, ISSN)
- Multi-stage screening pipeline: deduplication → journal screening → metadata screening → keyword screening → semantic screening → LLM screening → full-paper screening
- Duplicate tracking: papers can be marked as duplicates of a primary paper via the `duplicate_of` field
- Embeddings and text chunks: support for semantic embeddings (768-dim vectors), full-text chunking with hierarchy levels
- CAMO framework support: extraction of Context-Agency-Mechanism-Outcome statements with embeddings and clustering
- Fluent query API: chainable filters, sorting, searching, and pagination without requiring SQL
- Set operations: database merging (__add__), subtraction (__sub__), length (__len__), iteration (__iter__)
- Full-text search: grep-style searching in title and abstract fields
- Cite key generation: deterministic "LastnameYear" format with automatic collision resolution

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: Paper Model Structure

The system MUST provide a Paper model with complete bibliographic fields including core metadata, discovery metadata, screening results, and optional supplementary data.

#### Scenario: Create and access paper with standard fields

- GIVEN a Paper created with title="Machine Learning", year=2020, authors=[Author(...)]
- WHEN accessing paper.title, paper.year, paper.authors
- THEN the fields are returned exactly as provided

#### Scenario: Compute derived properties

- GIVEN a Paper with authors=[Author(family_name="Smith"), Author(family_name="Doe")]
- WHEN accessing paper.author_string
- THEN it returns "Smith & Doe"

- GIVEN a Paper with authors=[Author(family_name="Smith")] and duplicate_of=None
- WHEN accessing paper.is_duplicate
- THEN it returns False

- GIVEN a Paper with screening.final_decision=ScreeningDecision.INCLUDED
- WHEN accessing paper.is_included
- THEN it returns True

- GIVEN a Paper with title, abstract, keywords present
- WHEN accessing paper.calculated_quality_score
- THEN the score is at least 0.70 (0.20 base + 0.20 title + 0.25 keywords + 0.25 abstract)

#### Scenario: Generate APA formatted citation

- GIVEN a Paper with authors=[Author(full_name="John Smith"), Author(full_name="Jane Doe")], year=2020, title="ML Survey", journal="AI Review", volume="10"
- WHEN calling paper.apa
- THEN it returns "John Smith & Jane Doe (2020). ML Survey. AI Review, 10."

---

### Requirement: Author Model

The system MUST provide an Author model representing individual paper authors with name components and optional metadata.

#### Scenario: Create author with required and optional fields

- GIVEN an Author created with family_name="Smith", full_name="John Smith"
- WHEN accessing author.family_name and author.full_name
- THEN both fields are accessible

- GIVEN an Author with family_name="Smith"
- WHEN accessing author.last_name
- THEN it returns "Smith" (property alias for family_name)

#### Scenario: Author with affiliation and ORCID

- GIVEN an Author with affiliation="MIT", orcid="0000-0001-2345-6789"
- WHEN accessing those fields
- THEN they are stored and retrievable

---

### Requirement: Citation Model

The system MUST represent bibliographic references with direction metadata, extraction metadata, and optional resolution to known papers.

#### Scenario: Create citation with extraction metadata

- GIVEN a Citation with title="Cited Paper", year=2015, direction=CitationDirection.BACKWARD, extraction_method="grobid", confidence=0.95
- WHEN accessing those fields
- THEN all values are accessible and validation passes

#### Scenario: Citation direction enumeration

- GIVEN citation direction values
- WHEN using CitationDirection.FORWARD or CitationDirection.BACKWARD
- THEN both are valid enum values

#### Scenario: Citation resolution

- GIVEN a Citation with resolved=False
- WHEN accessing resolved_paper
- THEN it is None or a Paper reference if resolved

---

### Requirement: TextChunk Model

The system MUST represent hierarchical text chunks from papers with embedding support and position tracking.

#### Scenario: Create text chunk with hierarchy

- GIVEN a TextChunk with chunk_index=0, text="Introduction...", section="introduction", hierarchy_level=1
- WHEN accessing those fields
- THEN they are stored correctly

#### Scenario: Text chunk comparison by embedding norm

- GIVEN two TextChunks with embeddings
- WHEN comparing chunk1 < chunk2
- THEN comparison uses L2 norm of the embedding vectors

#### Scenario: Compute cosine similarity between chunks

- GIVEN two TextChunks with embeddings (768-dim vectors)
- WHEN calling chunk1.similarity_to(chunk2)
- THEN the result is a float in [0, 1] or None if embedding missing

---

### Requirement: Embedding Model

The system MUST validate embedding vectors to ensure correct dimensionality (768).

#### Scenario: Validate embedding dimensions

- GIVEN an Embedding with vector=[...] (768 floats)
- WHEN creating the embedding
- THEN validation passes

- GIVEN an Embedding with vector=[...] (500 floats)
- WHEN creating the embedding
- THEN a ValueError is raised: "Embedding must be 768 dimensions, got 500"

---

### Requirement: Multi-Stage Screening Model

The system MUST support aggregated screening results from six sequential stages with final decision tracking.

#### Scenario: Complete screening pipeline execution

- GIVEN a Paper with screening.deduplication=DeduplicationResult(is_duplicate=False)
- AND screening.journal_screening=JournalScreeningResult(...)
- AND screening.metadata_screening=MetadataScreening(passed=True, paper_type=PaperType.JOURNAL_ARTICLE)
- AND screening.keyword_screening=KeywordScreening(passed=True, screening_decision=ScreeningDecision.INCLUDED)
- AND screening.semantic_screening=SemanticScreening(passed=True, decision=ScreeningDecision.INCLUDED)
- AND screening.llm_screening=SemanticScreening(passed=True, decision=ScreeningDecision.INCLUDED)
- AND screening.full_paper_screening=FullPaperScreening(decision=ScreeningDecision.INCLUDED)
- AND screening.final_decision=ScreeningDecision.INCLUDED
- WHEN accessing those fields
- THEN all stages are accessible and independent

#### Scenario: Track manual override decision

- GIVEN a Paper with screening.manual_decision=ScreeningDecision.EXCLUDED
- WHEN accessing screening.final_decision
- THEN it may be EXCLUDED (if final_decision was set to manual decision)

---

### Requirement: CAMO Statement Model

The system MUST represent Context-Agency-Mechanism-Outcome statements with embedding support and clustering metadata.

#### Scenario: Create CAMO statement

- GIVEN a CAMOStatement with context="...", agency="...", mechanism="...", outcome="...", confidence=0.92
- WHEN accessing those fields
- THEN all are stored correctly

#### Scenario: CAMO clustering metadata

- GIVEN a CAMOStatement with cluster_id=5, cluster_label="Optimization", distance_to_centroid=0.15
- WHEN accessing those fields
- THEN clustering information is preserved

---

### Requirement: Database CRUD Operations

The system MUST provide safe, atomic CRUD operations with automatic index maintenance.

#### Scenario: Add paper to database

- GIVEN a PapersDatabase and a Paper with unique cite_key and id
- WHEN calling db.add(paper)
- THEN the paper is added and indexed in all five indexes

- GIVEN a PapersDatabase with a paper already having cite_key="Smith2020"
- WHEN calling db.add(paper_with_cite_key="Smith2020")
- THEN a ValueError is raised: "Paper with cite_key 'Smith2020' already exists"

#### Scenario: Retrieve paper by unique identifiers

- GIVEN a database with Paper(id="abc123", cite_key="Smith2020", doi="10.1234/example", year=2020)
- WHEN calling db.get_by_id("abc123")
- THEN the paper is returned (O(1) lookup via _id_index)

- GIVEN the same database
- WHEN calling db.get_by_cite_key("Smith2020")
- THEN the paper is returned (O(1) lookup via _cite_key_index)

#### Scenario: Retrieve papers by DOI

- GIVEN a database with two papers sharing doi="10.1234/example"
- WHEN calling db.get_by_doi("10.1234/example")
- THEN both papers are returned

- GIVEN the same database
- WHEN calling db.get_by_doi("10.1234/example", primary_only=True)
- THEN only papers with duplicate_of=None are returned

#### Scenario: Update paper in database

- GIVEN a paper already in database with doi="10.1234/old"
- WHEN calling db.update(updated_paper_with_doi="10.1234/new")
- THEN the DOI index is updated automatically
- AND the paper remains indexed by cite_key and id

#### Scenario: Delete paper from database

- GIVEN a database with a paper
- WHEN calling db.delete_by_id(paper.id)
- THEN the paper is removed from papers list and all indexes
- AND subsequent lookup returns None

#### Scenario: Filter by predicate

- GIVEN a database with papers
- WHEN calling db.find(lambda p: p.year == 2020)
- THEN only papers from 2020 are returned

---

### Requirement: Database Indexing

The system MUST maintain five concurrent indexes for O(1) or O(log n) lookup performance.

#### Scenario: DOI index with duplicate handling

- GIVEN two papers with identical doi="10.1234/example"
- WHEN resolve_duplicates=True (default)
- THEN the second paper is automatically marked duplicate_of the first
- AND both are indexed under the same DOI key

#### Scenario: Citation key index uniqueness

- GIVEN a cite_key constraint
- WHEN adding a paper with duplicate cite_key
- THEN a ValueError is raised

#### Scenario: Year index for range queries

- GIVEN papers with years [2018, 2019, 2020, 2021, 2022]
- WHEN calling db.get_candidates_by_year_range(2020, tolerance=1)
- THEN papers from 2019, 2020, 2021 are returned (without full table scan)

#### Scenario: Title prefix index for text search

- GIVEN papers with titles ["Machine Learning Overview", "Machine Learning Practice"]
- WHEN calling db.get_candidates_by_title_prefix("Machine Learning")
- THEN both papers are returned (using first 50 chars match)

---

### Requirement: Fluent Query API

The system MUST support chainable query methods with lazy evaluation and terminal operations.

#### Scenario: Filter by topic keyword

- GIVEN a database with papers having keywords=["AI", "ML"]
- WHEN calling db.query().filter_by_topic("AI").execute()
- THEN papers with "AI" in keywords are returned

#### Scenario: Filter by year range

- GIVEN papers with years [2015, 2018, 2020, 2022, 2024]
- WHEN calling db.query().filter_by_year(2020, 2024).execute()
- THEN papers from 2020-2024 (inclusive) are returned

#### Scenario: Filter by author name (partial match)

- GIVEN papers with authors containing "John Smith"
- WHEN calling db.query().filter_by_author("Smith").execute()
- THEN papers with any author containing "Smith" are returned

#### Scenario: Full-text search (grep)

- GIVEN papers with title="Transformers in NLP" and abstract="Neural..."
- WHEN calling db.query().grep("transformer").execute()
- THEN papers matching "transformer" in title or abstract are returned (case-insensitive)

#### Scenario: Exclude duplicates

- GIVEN a database with 10 papers total, 3 duplicates
- WHEN calling db.query().exclude_duplicates().execute()
- THEN 7 papers with duplicate_of=None are returned

#### Scenario: Sort by year (descending)

- GIVEN papers with years [2015, 2020, 2024]
- WHEN calling db.query().order_by_year(descending=True).execute()
- THEN papers are returned in order [2024, 2020, 2015]

#### Scenario: Limit results with top()

- GIVEN papers with 100 matches
- WHEN calling db.query().filter_by_year(2020).top(10).execute()
- THEN at most 10 papers are returned

#### Scenario: Chain multiple filters

- GIVEN papers from various years and topics
- WHEN calling db.query().filter_by_year(2020, 2024).filter_by_topic("AI").exclude_duplicates().top(5).execute()
- THEN up to 5 primary papers from 2020-2024 with "AI" keyword are returned

#### Scenario: Terminal operations on query

- GIVEN a query builder
- WHEN calling query.first()
- THEN the first matching paper is returned or None

- GIVEN a query builder
- WHEN calling query.count()
- THEN the number of matching papers is returned

- GIVEN a query builder
- WHEN calling query.list()
- THEN all matching papers are returned as a list

#### Scenario: Implicit execution via magic methods

- GIVEN a query builder
- WHEN iterating: for paper in db.query().filter_by_year(2020):
- THEN papers are implicitly executed and iterated

- GIVEN a query builder
- WHEN calling len(db.query().filter_by_year(2020))
- THEN count is computed without explicit execute()

- GIVEN a query builder
- WHEN accessing db.query().filter_by_year(2020)[0]
- THEN implicit indexing works and returns first result

---

### Requirement: Database Set Operations

The system MUST support merging and subtracting databases with proper duplicate handling.

#### Scenario: Merge two databases

- GIVEN db1 with papers [A, B, C] and db2 with papers [B, C, D]
- WHEN calling merged = db1 + db2
- THEN merged contains papers [A, B, C, D] (no duplicates by ID)
- AND merged is a new PapersDatabase instance

#### Scenario: Subtract databases

- GIVEN db1 with papers [A, B, C, D] and db2 with papers [B, D]
- WHEN calling result = db1 - db2
- THEN result contains papers [A, C]
- AND result is a new PapersDatabase instance

#### Scenario: Database length and iteration

- GIVEN a database with 50 papers
- WHEN calling len(db)
- THEN 50 is returned (including duplicates)

- GIVEN a database
- WHEN iterating: for paper in db:
- THEN all papers in self.papers are yielded

#### Scenario: Check paper membership

- GIVEN a database with paper A
- WHEN calling (A in db)
- THEN True is returned

- GIVEN paper B not in database
- WHEN calling (B in db)
- THEN False is returned

#### Scenario: Index and slice database

- GIVEN a database with 5 papers
- WHEN calling db[0]
- THEN the first paper is returned

- WHEN calling db[1:3]
- THEN papers at indices 1 and 2 are returned as a list

---

### Requirement: Duplicate Detection and Management

The system MUST support marking papers as duplicates and querying duplicate groups.

#### Scenario: Mark paper as duplicate

- GIVEN two papers A and B in database
- WHEN calling db.mark_duplicate(paper_id=B.id, duplicate_of_id=A.id)
- THEN B.duplicate_of is set to A
- AND B is indexed under A's DOI if applicable

#### Scenario: Retrieve all duplicates of a paper

- GIVEN a primary paper A with duplicates B and C
- WHEN calling db.get_duplicates_of(A.id)
- THEN [B, C] are returned (papers where duplicate_of == A)

#### Scenario: Get duplicate groups

- GIVEN papers with DOI groups: [A1, A2, A3] (doi="10.1/a") and [B1, B2] (doi="10.1/b")
- WHEN calling db.get_duplicate_groups()
- THEN a dict is returned with two groups only (groups with > 1 paper)

#### Scenario: Remove duplicate marking

- GIVEN a paper marked as duplicate
- WHEN calling db.remove_duplicate_marking(paper.id)
- THEN paper.duplicate_of is set to None
- AND paper becomes a primary paper

---

### Requirement: Normalization Rules

The system MUST normalize bibliographic fields according to standardized rules via the Normalizer class.

#### Scenario: Normalize title

- GIVEN title="the GREAT study of machine learning"
- WHEN calling Normalizer.normalize_title(title)
- THEN "The Great Study of Machine Learning" is returned
- AND "the", "of" are titlecased correctly per APA style

- GIVEN title="title with  multiple   spaces"
- WHEN calling Normalizer.normalize_title(title)
- THEN "Title With Multiple Spaces" is returned (spaces collapsed)

- GIVEN title="Title {with} <b>braces</b> and markup"
- WHEN calling Normalizer.normalize_title(title)
- THEN "Title With Braces and Markup" is returned (markup removed)

#### Scenario: Normalize abstract

- GIVEN abstract="  Some abstract text\n\nwith multiple\nlinebreaks  "
- WHEN calling Normalizer.normalize_abstract(abstract)
- THEN "Some Abstract Text With Multiple Linebreaks" is returned (whitespace collapsed)

#### Scenario: Normalize authors

- GIVEN authors="smith, john and doe, jane"
- WHEN calling Normalizer.normalize_authors(authors)
- THEN ["John Smith", "Jane Doe"] is returned

- GIVEN authors=[{"given_name": "john", "family_name": "smith"}]
- WHEN calling Normalizer.normalize_authors(authors)
- THEN ["John Smith"] is returned

- GIVEN authors with particles: "van der smith, john"
- WHEN calling Normalizer.normalize_authors(authors)
- THEN ["John Van Der Smith"] is returned (particles preserved)

#### Scenario: Normalize keywords

- GIVEN keywords="ML; Deep Learning; ml"
- WHEN calling Normalizer.normalize_keywords(keywords)
- THEN ["ml", "deep learning"] is returned (lowercase, deduplicated)

- GIVEN keywords="keyword1, keyword2, keyword1"
- WHEN calling Normalizer.normalize_keywords(keywords)
- THEN ["keyword1", "keyword2"] is returned (order preserved, duplicates removed)

- GIVEN keywords="ML and Deep Learning and ML"
- WHEN calling Normalizer.normalize_keywords(keywords)
- THEN ["ml", "deep learning"] is returned (priority: ; > , > and)

#### Scenario: Normalize journal name

- GIVEN journal="the JOURNAL of machine & learning"
- WHEN calling Normalizer.normalize_journal(journal)
- THEN "The Journal of Machine & Learning" is returned

#### Scenario: Normalize year

- GIVEN year="2024-01-15"
- WHEN calling Normalizer.normalize_year(year)
- THEN 2024 is returned (4-digit year extracted)

- GIVEN year="2024"
- WHEN calling Normalizer.normalize_year(year)
- THEN 2024 is returned

- GIVEN year="202a"
- WHEN calling Normalizer.normalize_year(year)
- THEN None is returned (invalid format)

- GIVEN year=3000
- WHEN calling Normalizer.normalize_year(year)
- THEN None is returned (out of range 1000-2100)

#### Scenario: Normalize DOI

- GIVEN doi="https://doi.org/10.1234/example"
- WHEN calling Normalizer.normalize_doi(doi)
- THEN "10.1234/example" is returned (URL stripped)

- GIVEN doi="doi:10.1234/example"
- WHEN calling Normalizer.normalize_doi(doi)
- THEN "10.1234/example" is returned (prefix removed)

- GIVEN doi="invalid/doi"
- WHEN calling Normalizer.normalize_doi(doi)
- THEN None is returned (doesn't start with "10.")

#### Scenario: Normalize paper type

- GIVEN paper_type="journal_article"
- WHEN calling Normalizer.normalize_paper_type(paper_type)
- THEN "journal_article" is returned (valid PaperType value)

- GIVEN paper_type="invalid_type"
- WHEN calling Normalizer.normalize_paper_type(paper_type)
- THEN None is returned (not in PaperType enum)

#### Scenario: Smart titlecase with acronyms and particles

- GIVEN text="ludwig von beethoven"
- WHEN calling Normalizer._smart_titlecase(text)
- THEN "Ludwig von Beethoven" is returned (particle preserved)

- GIVEN text="smith & co. gmbh"
- WHEN calling Normalizer._smart_titlecase(text)
- THEN "Smith & Co. GmbH" is returned (acronyms preserved)

- GIVEN text="jean-claude van damme"
- WHEN calling Normalizer._smart_titlecase(text)
- THEN "Jean-Claude van Damme" is returned (hyphenated parts handled)

---

### Requirement: Cite Key Generation

The system MUST generate deterministic citation keys in "LastnameYear" format with automatic collision handling.

#### Scenario: Generate basic cite key

- GIVEN a Paper with authors=[Author(family_name="Smith")], year=2020
- WHEN calling generate_cite_key(paper)
- THEN "Smith2020" is returned

#### Scenario: Generate cite key with multi-part family name

- GIVEN a Paper with authors=[Author(family_name="Van Der Smith")], year=2020
- WHEN calling generate_cite_key(paper)
- THEN "VanDerSmith2020" is returned (spaces removed)

#### Scenario: Resolve collision with single-letter suffix

- GIVEN base_key="Smith2020" already exists in database
- WHEN calling resolve_collision("Smith2020", existing_keys={"Smith2020": True})
- THEN "Smith2020a" is returned

#### Scenario: Resolve collision with progression

- GIVEN base_key="Smith2020" and collisions with suffixes a-z already exist
- WHEN calling resolve_collision("Smith2020", existing_keys={...26 existing keys...})
- THEN "Smith2020aa" is returned (after z comes aa)

#### Scenario: Collision suffix pattern

- GIVEN collision indices 0-25
- WHEN calling make_collision_suffix(i) for i in range(26)
- THEN ['a', 'b', ..., 'z'] are returned

- GIVEN collision index 26
- WHEN calling make_collision_suffix(26)
- THEN "aa" is returned

- GIVEN collision index 27
- WHEN calling make_collision_suffix(27)
- THEN "ab" is returned

#### Scenario: Fix cite key collisions in paper list

- GIVEN papers=[Paper(cite_key="Smith2020"), Paper(cite_key="Smith2020")] and existing_db.papers=[]
- WHEN calling fix_cite_key_collisions(papers, existing_db)
- THEN papers[0].cite_key stays "Smith2020" and papers[1].cite_key becomes "Smith2020a"
- AND 1 is returned (number of fixed collisions)

#### Scenario: Generate DOI-based cite key

- GIVEN a Paper with doi="10.1234/example"
- WHEN calling generate_doi_based_cite_key("10.1234/example")
- THEN a deterministic key like "doi_a1b2c3d4" is returned
- AND the same DOI always produces the same key

---

### Requirement: DOI Validation and Normalization

The system MUST validate DOI format and provide multiple representations.

#### Scenario: Validate DOI structure

- GIVEN doi="10.1234/example"
- WHEN creating DOI(doi)
- THEN DOI.stem returns "10.1234/example" (normalized)

- GIVEN doi="https://doi.org/10.1234/example"
- WHEN creating DOI(doi)
- THEN DOI.stem returns "10.1234/example" (URL stripped)

- GIVEN doi="doi:10.1234/example"
- WHEN creating DOI(doi)
- THEN DOI.stem returns "10.1234/example" (prefix removed)

#### Scenario: Validate DOI prefix requirement

- GIVEN doi="9.1234/example" (invalid prefix)
- WHEN creating DOI(doi)
- THEN ValueError is raised: "Invalid DOI prefix"

- GIVEN doi="10./example" (empty suffix)
- WHEN creating DOI(doi)
- THEN ValueError is raised: "Invalid DOI format"

- GIVEN doi="" (empty string)
- WHEN creating DOI(doi)
- THEN ValueError is raised: "DOI cannot be empty"

#### Scenario: DOI representations

- GIVEN doi="10.1234/example"
- WHEN calling DOI(doi).url
- THEN "https://doi.org/10.1234/example" is returned

- WHEN calling DOI(doi).safe
- THEN "10_1234_example" is returned (filename-safe: / : . replaced)

- WHEN calling DOI(doi).md5
- THEN a 32-character hex string is returned (MD5 hash of stem)

- WHEN calling str(DOI(doi))
- THEN "10.1234/example" is returned

#### Scenario: DOI case normalization

- GIVEN doi="HTTPS://DOI.ORG/10.1234/EXAMPLE"
- WHEN creating DOI(doi)
- THEN DOI.stem returns "10.1234/example" (lowercased)

---

### Requirement: Enumeration Types

The system MUST provide enumeration types for paper classification, discovery, and screening.

#### Scenario: PaperType enumeration

- GIVEN the PaperType enum
- WHEN accessing PaperType values
- THEN the following are valid: JOURNAL_ARTICLE, CONFERENCE_PAPER, BOOK, BOOK_CHAPTER, THESIS, TECHNICAL_REPORT, WORKING_PAPER, PREPRINT, PATENT, REPORT, DATASET, OTHER

#### Scenario: StudyType enumeration

- GIVEN the StudyType enum
- WHEN accessing StudyType values
- THEN the following are valid: EMPIRICAL_QUALITATIVE, EMPIRICAL_QUANTITATIVE, EMPIRICAL_MIXED, LITERATURE_REVIEW, META_ANALYSIS, CONCEPTUAL, EDITORIAL, THEORETICAL, BOOK_REVIEW, CASE_STUDY, UNKNOWN

#### Scenario: QualityTier enumeration

- GIVEN the QualityTier enum
- WHEN accessing QualityTier values
- THEN the following are valid: PEER_REVIEWED_JOURNAL, NON_PEER_REVIEWED_ARTICLE, PEER_REVIEWED_CONFERENCE, BOOK_CHAPTER, WORKING_PAPER, PREPRINT, GREY_LITERATURE, UNKNOWN

#### Scenario: DiscoveryMethod enumeration

- GIVEN the DiscoveryMethod enum
- WHEN accessing DiscoveryMethod values
- THEN the following are valid: FILE_PATH, KEYWORD_SEARCH, BACKWARD_CITATION, FORWARD_CITATION, LITERATURE_REVIEW_MINING, RECOMMENDATION, MANUAL, API

#### Scenario: ScreeningDecision enumeration

- GIVEN the ScreeningDecision enum
- WHEN accessing ScreeningDecision values
- THEN the following are valid: INCLUDED, INCLUDED_MANUAL, EXCLUDED, EXCLUDED_DUPLICATE, EXCLUDED_INCOMPLETE, EXCLUDED_MANUAL, PENDING, MANUAL_REVIEW, UNCERTAIN

#### Scenario: CitationDirection enumeration

- GIVEN the CitationDirection enum
- WHEN accessing CitationDirection values
- THEN the following are valid: FORWARD, BACKWARD

---

### Requirement: Database Statistics

The system MUST provide statistics about database content.

#### Scenario: Get database statistics

- GIVEN a database with 10 papers total, 3 duplicates, 5 with DOIs
- WHEN calling db.get_stats()
- THEN the result is a dict containing:
  - "total_papers": 10
  - "primary_papers": 7
  - "duplicate_papers": 3
  - "papers_with_doi": 5
  - "unique_dois": (count of unique DOI stems)
  - "duplicate_groups": (count of DOI groups with > 1 paper)
  - "max_duplicates_per_doi": (highest duplicate count)

#### Scenario: Count papers

- GIVEN a database with 10 papers (7 primary, 3 duplicates)
- WHEN calling db.count()
- THEN 10 is returned (total including duplicates)

- WHEN calling db.count(primary_only=True)
- THEN 7 is returned (only primary papers)

#### Scenario: Count specific DOI duplicates

- GIVEN a database with 3 papers sharing doi="10.1234/example"
- WHEN calling db.count_duplicates("10.1234/example")
- THEN 3 is returned

---

### Requirement: Database Shorthand Methods

The system MUST provide shorthand methods for common query patterns without requiring explicit query() builder calls.

#### Scenario: Shorthand filter by topic

- GIVEN db.by_topic("AI")
- WHEN executed
- THEN papers with "AI" in keywords are returned
- AND the result is a PapersQuery for further chaining

#### Scenario: Shorthand filter by author

- GIVEN db.by_author("Smith")
- WHEN executed
- THEN papers with "Smith" in any author name are returned

#### Scenario: Shorthand filter by year

- GIVEN db.by_year(2020)
- WHEN executed
- THEN papers from 2020 are returned

- GIVEN db.by_year(2020, 2023)
- WHEN executed
- THEN papers from 2020-2023 (inclusive) are returned

#### Scenario: Shorthand full-text search

- GIVEN db.search("transformer")
- WHEN executed
- THEN papers matching "transformer" in title or abstract are returned

---

## Metadata

### Implementation Files

- [src/paper_scanner/core/models.py](../../../src/paper_scanner/core/models.py) - Paper, Author, Citation, Embedding, TextChunk, Screening, and related models
- [src/paper_scanner/core/database.py](../../../src/paper_scanner/core/database.py) - PapersDatabase with indexing and CRUD operations
- [src/paper_scanner/core/query.py](../../../src/paper_scanner/core/query.py) - Fluent query builder (PapersQuery)
- [src/paper_scanner/core/enum.py](../../../src/paper_scanner/core/enum.py) - Enumeration types (PaperType, StudyType, etc.)
- [src/paper_scanner/core/normalization.py](../../../src/paper_scanner/core/normalization.py) - Centralised field normalisation (Normalizer)
- [src/paper_scanner/core/cite_key.py](../../../src/paper_scanner/core/cite_key.py) - Cite key generation and collision handling
- [src/paper_scanner/core/doi.py](../../../src/paper_scanner/core/doi.py) - DOI validation and normalisation

### Test Coverage

- Tests located in `tests/unit/` directory
- Test file for advanced parser: `test_advanced_section_parser.py`
- Additional model and database tests to be extended

### Related Specifications

- [002-pipeline-engine](../002-pipeline-engine/spec.md) - Pipeline execution and step orchestration
- [003-screening-workflow](../003-screening-workflow/spec.md) - Screening logic and decision rules
- [004-metadata-fetching](../004-metadata-fetching/spec.md) - Import/export and external data acquisition
- [005-embedding-system](../005-embedding-system/spec.md) - Embedding generation and indexing
- [006-web-interface](../006-web-interface/spec.md) - User interface and API endpoints

### Architectural Decision Records

- [ADR-0004: Source Structure & Test Organization](../../../docs/adr/0004-source-setup.md) — Module layout and three-tier test strategy

---

## References

- **RFC 2119**: https://datatracker.ietf.org/doc/html/rfc2119
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Digital Object Identifier**: https://en.wikipedia.org/wiki/Digital_object_identifier
- **DOI Handbook**: https://doi.org/10.1000/182
- **APA Style Capitalization**: https://apastyle.apa.org/style-grammar-guidelines/capitalization/title-case

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
