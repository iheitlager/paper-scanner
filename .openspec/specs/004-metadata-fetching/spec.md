# Metadata Fetching Specification

**Domain:** Enrichment
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

---

## Overview

The Metadata Fetching domain enables acquisition of bibliographic data from multiple external sources with unified caching, handler fallback logic, and format tolerance. The system orchestrates metadata and citation retrieval through pluggable handlers (Crossref, OpenAlex, Semantic Scholar, manual cache), translates API responses to standardized Paper models, supports both BibTeX and RIS import formats, and manages HTTP caching and PDF downloads with open access detection.

### Philosophy

1. **Handler Fallback**: Fetch from primary source first; if unavailable or incomplete, cascade through configured handlers until quality threshold (0.9) is met.
2. **Unified Caching**: All HTTP responses cached at handler level; 404 markers prevent repeated API calls for non-existent entries.
3. **Format Tolerance**: BibTeX and RIS import support source-specific type mappings (Scopus, Web of Science, IEEE); manual handler serves as local cache fallback for pre-curated papers.

### Key Capabilities

- **Multi-source metadata acquisition** via Crossref, OpenAlex, Semantic Scholar APIs with automatic handler registration
- **DOI-based orchestration** with normalized DOI handling and handler quality scoring
- **Backward and forward citation fetching** with citation graph building and resolution
- **BibTeX and RIS import** with source-specific type mapping (Scopus, WoS, IEEE) and collision detection
- **PDF download and caching** with Unpaywall integration and open access detection
- **JSON response caching** with cache-busting for 404s and MD5-based key normalization
- **API rate limiting** via Semantic Scholar configuration (100 req/5min free; 5,000 req/5min with key)

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: Fetcher Orchestration

The Fetcher class MUST orchestrate metadata and citation retrieval from registered handler implementations with fallback logic and unified caching.

#### Scenario: Handler Registration and Initialization

- GIVEN a Fetcher initialized with `methods=["crossref", "openalex", "manual"]` and `cache_dir=~/.cache/paper-scanner`
- WHEN the Fetcher is constructed
- THEN it SHALL register handler instances for each method via `_register_handlers()`
  - CrossrefHandler at `cache_dir/crossref/`
  - OpenAlexHandler at `cache_dir/openalex/`
  - ManualHandler at `cache_dir/manual/`
- AND it SHALL initialize a PDFCache at `cache_dir/pdfs/`
- AND it SHALL raise `ValueError` if no valid handlers can be registered

#### Scenario: Metadata Fetching with Handler Fallback

- GIVEN a Fetcher with handlers `["manual", "crossref", "openalex"]` ordered by priority
- WHEN `fetch_paper(doi="10.1234/example")` is called
- THEN it SHALL try handlers in order
- AND it SHALL merge papers from multiple handlers if partial data is returned
- AND it SHALL stop attempting further handlers when paper quality >= 0.9 (via `paper.calculated_quality_score`)
- AND it SHALL return tuple of (Paper model or None, cache_hit: bool, handler_name: str)

#### Scenario: Citation Fetching Fallback

- GIVEN a Fetcher with methods `["crossref", "openalex"]`
- WHEN `fetch_citations(doi)` is called
- THEN it SHALL try handlers in order until first succeeds
- AND it SHALL return tuple of (citations list, cache_hit: bool)
- AND citations list MAY be empty if no handler returns results

#### Scenario: Forward Citations Fallback

- GIVEN a Fetcher with methods `["openalex", "semantic_scholar"]`
- WHEN `fetch_cited_by(doi, limit=100)` is called
- THEN it SHALL try handlers in order until first succeeds
- AND it SHALL return tuple of (citations list, cache_hit: bool)
- AND it SHALL limit results to specified limit

---

### Requirement: Base Handler Interface

All fetcher handlers MUST implement BaseFetcherHandler abstract interface with consistent metadata extraction and Paper model translation.

#### Scenario: Handler Initialization

- GIVEN a handler subclass (e.g., CrossrefHandler)
- WHEN initialized with `cache_dir=Path("~/.cache/ps"), debug=True`
- THEN it SHALL create cache directory at `cache_dir/[handler_name]/`
- AND it SHALL initialize JSONFileCache for storing API responses
- AND it SHALL store debug and verbose flags

#### Scenario: Metadata Translation

- GIVEN raw API response dict from external source (e.g., Crossref `works` object)
- WHEN `fetch_paper(doi)` is called
- THEN it SHALL extract all bibliographic fields via `_extract_*()` methods:
  - title (with HTML tag removal and newline normalization)
  - abstract (via AbstractParser.clean() for markup removal)
  - authors (as Author objects with given/family names)
  - keywords (from subject/concepts)
  - topics (from high-scoring concepts or fields of study)
  - paper_type (mapped via handler-specific enum)
  - year (from published-print, published-online, issued, or created)
  - journal (from container-title or source.display_name)
  - isbn, issn, pmid, url (optional fields)
  - oa_status (handler-specific OA detection)
- AND it SHALL apply Normalizer.normalize_*() to clean extracted values
- AND it SHALL translate to Paper model with discovery metadata

#### Scenario: Caching with 404 Markers

- GIVEN a handler with JSONFileCache
- WHEN `fetch_metadata(doi)` is called for first time
- THEN it SHALL check JSONFileCache with key = DOI (MD5-normalized)
- AND if not in cache, SHALL call `_fetch_from_api(doi)`
- AND if API returns None, SHALL cache 404 marker (special dict) to prevent repeated calls
- AND on subsequent calls, SHALL detect 404 marker and return (None, True) immediately

#### Scenario: Paper Merging

- GIVEN target_paper from manual handler and source_paper from Crossref
- WHEN `merge_papers(target, source, overwrite=False)` is called
- THEN for each field (abstract, title, keywords, etc.):
  - IF overwrite=True, OVERWRITE target field with source field
  - ELSE IF target field empty, UPDATE target with source field
  - ELSE KEEP target field unchanged
- AND it SHALL update `target.updated_at` to current datetime

---

### Requirement: Crossref Handler

The CrossrefHandler MUST fetch publication metadata and backward citations from Crossref API with polite pool compliance.

#### Scenario: Crossref Metadata Fetching

- GIVEN DOI "10.1038/nature12373"
- WHEN `fetch_paper(doi)` is called
- THEN it SHALL:
  - Normalize DOI to stem via DOI(doi).stem
  - Call Crossref API at `https://api.crossref.org/works/{stem}`
  - Use User-Agent: `paper-scanner/1.0 (mailto:i.heitlager@tue.nl)` (polite pool)
  - Extract response from `data["message"]` field
- AND it SHALL extract fields:
  - title: from `title[0]` (list) or string
  - abstract: from `abstract` field via AbstractParser.clean()
  - authors: from `author` array with given/family fields
  - keywords: from `subject` array
  - paper_type: map `type` field (journal-article, proceedings-article, book, etc.)
  - year: from `published-print.date-parts[0][0]`, fallback to published-online, issued, created
  - journal: from `container-title[0]` or `short-container-title[0]`
  - volume, issue: from `volume`, `issue` fields
  - isbn: from `isbn[0]` (array)
  - issn: from `issn[0]` (array)
  - url: from `resource.primary.URL` or top-level `URL` field
  - publisher: from `publisher` field
- AND it SHALL NOT extract OA status (Crossref doesn't provide)
- AND it SHALL use DOI as source_key (via alternative-id fallback)

#### Scenario: Crossref Citation Extraction

- GIVEN API response with `reference` array field
- WHEN `fetch_citations(doi)` is called
- THEN for each reference object, it SHALL extract:
  - doi: from `DOI` field (normalized)
  - title: from `article-title`, `title`, or fallback to `unstructured`
  - authors: first author from `author` string
  - year: from `year` field (int)
  - journal: from `journal-title` or `container-title`
  - volume, issue, pages: from corresponding fields
  - publisher: from `publisher` field
  - confidence: 1.0 if `doi-asserted-by=publisher`, else calculated from presence of doi, title, year
- AND it SHALL return Citation model with direction=BACKWARD
- AND it SHALL NOT implement forward citations (raises NotImplementedError)

#### Scenario: Crossref PDF Download URL

- GIVEN API response with `link` array
- WHEN `_find_download_url(api_data)` is called
- THEN it SHALL search links in order:
  - PREFER links with `content-type: application/pdf`
  - FALLBACK to any link starting with `http`
- AND it SHALL return URL string or None if no PDF available

---

### Requirement: OpenAlex Handler

The OpenAlexHandler MUST fetch publication metadata from OpenAlex API with rich abstract/keyword coverage and OA detection.

#### Scenario: OpenAlex Metadata Fetching

- GIVEN DOI "10.1038/nature12373"
- WHEN `fetch_paper(doi)` is called
- THEN it SHALL:
  - Normalize DOI via DOI(doi).uri (returns `doi:{doi}` format)
  - Call OpenAlex API at `https://api.openalex.org/works/{normalized}`
  - Return work object directly (no wrapper)
- AND it SHALL extract fields:
  - title: from `title` field
  - abstract: reconstruct from `abstract_inverted_index` (inverted word position format)
  - authors: from `authorships[].author.display_name` with affiliations from `institutions[]`
  - keywords: from `concepts` where score > 0.3
  - topics: from `topics[]` field, fallback to high-level concepts (level <= 1, score > 0.5)
  - paper_type: map `type` field, special case `type_crossref=proceedings-article`
  - year: from `publication_year`, fallback to `publication_date` string
  - journal: from `primary_location.source.display_name`
  - issn: from `primary_location.source.issn` (list or string)
  - volume, issue: from `volume`, `issue` or `biblio` object
  - url: from `primary_location.landing_page_url` or fallback to DOI URL
  - publisher: from `primary_location.source.host_organization_name` or `best_oa_location`
  - pmid: extract from `ids.pmid` URL (numeric part after last `/`)
  - oa_status: from `open_access.is_oa` and `open_access.oa_status` (gold, green, hybrid, bronze, closed)
  - source_key: OpenAlex work ID from URL (e.g., W2741809807)

#### Scenario: OpenAlex Citation Extraction

- GIVEN API response with `referenced_works` array of work IDs
- WHEN `fetch_citations(doi)` is called
- THEN since OpenAlex only provides IDs without metadata:
  - Create minimal Citation objects with just openalex_id and confidence=0.5
  - RETURN empty list if referenced_works is empty
  - NOTE: Full citation details would require additional API calls per reference

#### Scenario: OpenAlex Forward Citations

- GIVEN DOI with OpenAlex metadata
- WHEN `fetch_cited_by(doi, limit=100)` is called
- THEN it SHALL:
  - Extract OpenAlex work ID via `_extract_source_key()`
  - Query API at `https://api.openalex.org/works?filter=cites:{work_id}&per-page={limit}`
  - Parse results array into Citation objects with CitationDirection.FORWARD
  - Extract doi, title, year, authors, journal from each work

#### Scenario: OpenAlex OA Detection

- GIVEN API response with `open_access` object
- WHEN extracting OA status
- THEN it SHALL create OpenAccessStatus with:
  - is_oa: from `open_access.is_oa` boolean
  - oa_status: from `open_access.oa_status` string value
  - source: "openalex"

---

### Requirement: Semantic Scholar Handler

The SemanticScholarHandler MUST fetch paper metadata and forward citations from S2 API with rate limiting support.

#### Scenario: Semantic Scholar Metadata Fetching

- GIVEN DOI "10.1038/nature12373"
- WHEN `fetch_paper(doi)` is called
- THEN it SHALL:
  - Accept DOI with or without "DOI:" prefix
  - Call S2 API at `https://api.semanticscholar.org/graph/v1/paper/{doi}`
  - Request fields: paperId, corpusId, url, title, abstract, venue, year, publicationDate, publicationTypes, externalIds, authors, citationCount, influentialCitationCount, s2FieldsOfStudy, publicationVenue, tldr, openAccessPdf, journal, isOpenAccess
  - Use optional API key from environment or config (x-api-key header)
- AND it SHALL extract fields:
  - title: from `title` field
  - abstract: from `abstract` field
  - authors: from `authors[].name` strings
  - topics: from `s2FieldsOfStudy[].category` (or raw string)
  - paper_type: from `publicationTypes[0]` first type
  - year: from `year` field (int)
  - journal: from `venue`, `publicationVenue.name`, or `journal.name`
  - oa_status: from `isOpenAccess` boolean (simple: "open" or "closed")
  - source_key: `s2:{paperId}` or `s2:{corpusId}` format

#### Scenario: Semantic Scholar Forward Citations

- GIVEN DOI with S2 metadata
- WHEN `fetch_cited_by(doi, limit=100)` is called
- THEN it SHALL:
  - Call S2 API at `https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations`
  - Request fields: paperId, title, abstract, authors, year, venue, citationCount, externalIds, publicationTypes
  - Parse `data[]` array (each item contains citingPaper object)
  - Extract doi from `citingPaper.externalIds.DOI`
  - Build Citation with direction=FORWARD
- AND it SHALL NOT implement PDF downloads (raises NotImplementedError)

#### Scenario: Semantic Scholar Rate Limiting

- GIVEN handler with optional api_key
- WHEN API key NOT provided
- THEN rate limit: 100 requests per 5 minutes (free tier)
- WHEN API key provided
- THEN rate limit: 5,000 requests per 5 minutes (institutional tier)
- NOTE: Enforce via backoff strategy at caller level (CitationsStep, RetrieveMetadataStep)

---

### Requirement: Manual Handler

The ManualHandler MUST serve as local cache fallback for user-curated papers from BibTeX files with no API calls.

#### Scenario: Manual Handler Cache-Only Operation

- GIVEN manually cached paper data in JSONFileCache
- WHEN `fetch_paper(doi)` is called
- THEN it SHALL:
  - Return None from `_fetch_from_api()` (no API calls)
  - Rely on base class fetch_metadata() to check cache first
  - Return cached data if available in JSONFileCache
- AND it SHALL NOT attempt external API calls

#### Scenario: Manual Handler Field Extraction

- GIVEN cached BibTeX-derived paper dict
- WHEN extracting fields
- THEN it SHALL handle both:
  - Author objects: convert via Author(**dict)
  - Author strings: convert via `_string_to_author()` (handles "Last, First" and "First Last" formats)
- AND it SHALL extract citations from cached `citations` array (each as dict or Citation object)
- AND it SHALL preserve download_url if present in cache

#### Scenario: Manual Handler Author String Parsing

- GIVEN author string "Smith, John"
- WHEN converting to Author object
- THEN it SHALL parse as family_name="Smith", given_name="John", full_name="Smith, John"
- GIVEN author string "John Smith"
- WHEN converting to Author object
- THEN it SHALL parse as given_name="John", family_name="Smith", full_name="John Smith"
- GIVEN author string "Smith"
- WHEN converting to Author object
- THEN it SHALL parse as family_name="Smith", full_name="Smith"

---

### Requirement: BibTeX Import

The BibTeX import system MUST parse BibTeX files, apply source-specific type mappings, extract fields with author/keyword normalization, and manage cite_key collisions.

#### Scenario: BibTeX Entry Parsing with Type Mapping

- GIVEN BibTeX file from Scopus export
- WHEN parsing with `bibtex_file_to_papers(filepath, source_type="scopus")`
- THEN it SHALL:
  - Load type mapping config from `etc/bibtex_type_mapping.yaml`
  - Support source-specific overrides:
    - Scopus: check `document_type` field for "Article", "Conference Paper", etc.
    - Web of Science: check `document_type` field for "Journal", "Proceedings", etc.
    - IEEE: check `publication_type` field
  - Fall back to standard BibTeX entry type mappings: article→journal_article, inproceedings→conference_paper, book→book, etc.
  - Confidence scores: source-specific match=0.85, standard mapping=0.95

#### Scenario: BibTeX Field Extraction

- GIVEN BibTeX entry dictionary
- WHEN converting to Paper via `bibtex_entry_to_paper()`
- THEN it SHALL extract and normalize:
  - cite_key: required, from entry ID
  - title: required, normalize via Normalizer.normalize_title()
  - abstract: from `abstract` field
  - authors: from `author` field, split on "and", parse "Last, First" format, create Author objects
  - year: from `year` field (int)
  - keywords: from `keyword`, `keywords`, `author_keywords`, `keywords-plus` fields
  - journal: from `journal` field, normalize
  - booktitle: from `booktitle` field (for conference papers)
  - publisher: from `publisher` field
  - isbn, issn: from corresponding fields
  - volume, issue/number, pages: from corresponding fields
- AND it SHALL use source_key = cite_key (both set to same value at import time)
- AND it SHALL set discovery.method = DiscoveryMethod.KEYWORD_SEARCH (or as configured)

#### Scenario: BibTeX Import with Cite Key Collision Detection

- GIVEN BibTeX import with papers having duplicate cite_keys or keys already in database
- WHEN executing with `fix_cite_key=True`
- THEN it SHALL:
  - Call `fix_cite_key_collisions(papers, db)` from database step
  - For each duplicate key, append `_NN` suffix (NN = 01, 02, ...)
  - Check against both existing database entries and newly imported papers
  - Return count of fixed collisions
- AND it SHALL update paper.cite_key before database insertion

#### Scenario: BibTeX Import with Type Mapping Configuration

- GIVEN configuration at `etc/bibtex_type_mapping.yaml`:
  ```yaml
  type_mappings:
    article: {paper_type: journal_article, confidence: 0.95}
    inproceedings: {paper_type: conference_paper, confidence: 0.95}
    # ... etc
  source_overrides:
    scopus:
      article_type_field: document_type
      type_value_mappings:
        Article: journal_article
        Conference Paper: conference_paper
  ```
- WHEN `bibtex_file_to_papers()` is called
- THEN it SHALL use source_type to select overrides for type determination

---

### Requirement: BibTeX Export

The BibTeX export system MUST convert Paper models to BibTeX entries with field mapping and format compliance.

#### Scenario: Paper to BibTeX Entry Conversion

- GIVEN Paper model with metadata
- WHEN calling `paper_to_bibtex_entry(paper, use_source_key=False)`
- THEN it SHALL:
  - Use cite_key as entry ID (or source_key if use_source_key=True)
  - Infer BibTeX entry type from paper.paper_type:
    - JOURNAL_ARTICLE → article
    - CONFERENCE_PAPER → inproceedings
    - BOOK → book
    - BOOK_CHAPTER → incollection
    - THESIS → phdthesis
    - TECHNICAL_REPORT → techreport
    - WORKING_PAPER, PREPRINT → unpublished
    - OTHER → misc
  - Map fields to BibTeX:
    - title: escape ampersands (\&)
    - authors: format as "Last1, First1 and Last2, First2" via `format_authors_bibtex()`
    - keywords: join with ", " via `format_keywords_bibtex()`
    - year: convert to string
    - abstract: escape ampersands
    - journal, booktitle, publisher: escape ampersands
    - doi, url, isbn, issn: preserve as-is
    - volume, number, pages: preserve as-is

#### Scenario: Papers to BibTeX File Export

- GIVEN list of Paper models
- WHEN calling `papers_to_bibtex_file(papers, filepath, use_source_key=True)`
- THEN it SHALL:
  - Convert each paper via `paper_to_bibtex_entry()`
  - Create BibDatabase with entries
  - Write to file via BibTexWriter with:
    - indent = "  " (2 spaces)
    - order_entries_by = ('ID', 'ENTRYTYPE')
  - Write to specified filepath in UTF-8 encoding

#### Scenario: Papers Export by Source Database

- GIVEN mixed papers from Scopus, Web of Science, manual
- WHEN calling `export_papers_by_source(papers, output_dir="./exports")`
- THEN it SHALL:
  - Group papers by discovery.source_database
  - Create separate .bib files: scopus_export.bib, wos_export.bib, etc.
  - Write each group to output directory
  - Return dict: {source_type: filepath}

---

### Requirement: RIS Import

The RIS import system MUST parse RIS format files (ProQuest, Scopus, RefMan) with field mapping and source database detection.

#### Scenario: RIS File Parsing

- GIVEN RIS file with records in format `TAG - value`
- WHEN parsing via `ris_file_to_papers(filepath, source_database="ProQuest")`
- THEN it SHALL:
  - Parse each record delimited by TY (start) and ER (end) tags
  - Support multi-value fields (same tag multiple times → list)
  - Extract RIS fields to Paper model:
    - TY: publication type → paper_type via `infer_paper_type_ris()`
    - T1: title (required)
    - AU: authors (multiple) → Author objects
    - AB: abstract
    - JF: journal name
    - PY: publication year
    - VL: volume
    - IS: issue
    - SP: start page / EP: end page → pages range
    - KW: keywords (multiple)
    - DO: DOI (normalize)
    - UR: URL
    - PB: publisher
    - AN: accession number (database-specific ID)
    - DB: database name (override if not provided)
- AND it SHALL map publication types: jour→journal_article, conf→conference_paper, thes→thesis, etc.

#### Scenario: RIS Citation Key Strategy

- GIVEN RIS record with fields AN (accession number), DO (DOI), title, author
- WHEN creating cite_key and source_key
- THEN it SHALL use priority order:
  1. PRIMARY: accession_number → `ris_an_{AN}`
  2. SECONDARY: doi → `ris_doi_{DO}`
  3. TERTIARY: auto-generated from title+first_author hash → `ris_auto_{md5_hash[:8]}`
- AND cite_key = source_key at import time (can be transformed downstream)

#### Scenario: RIS Source Database Inference

- GIVEN RIS file named "proquest_results.ris"
- WHEN calling `import_ris_files([filepath])`
- THEN it SHALL infer source_database from filename:
  - "proquest" → "ProQuest"
  - "scopus" → "Scopus"
  - "wos" or "webofscience" → "Web of Science"
  - "mendeley" → "Mendeley"
  - "zotero" → "Zotero"
  - default → "RIS Import"

---

### Requirement: Citation Extraction

The citation extraction system MUST fetch backward (references) and forward (cited-by) citations, resolve them to existing papers or create new ones, and build citation graphs.

#### Scenario: Backward Citation Extraction

- GIVEN papers with DOIs in database
- WHEN executing CitationsStep with `backward.citations=["crossref"]`
- THEN PASS 1: Fetch citations
  - For each paper with DOI, call `fetcher.fetch_citations(doi)`
  - Store returned Citation list in paper.citations
  - Track cache hits/misses and citation count
- THEN PASS 2: Resolve citations
  - For each Citation in paper.citations:
    - TRY resolve by DOI via db.get_by_doi()
    - IF found in database, set Citation.resolved_paper = existing_paper
    - IF not found, CALL fetcher.fetch_paper(normalized_doi) for metadata
    - IF fetcher succeeds, create new Paper and call db.add()
    - IF continue_on_not_found=False and no resolution, raise error
  - Set Citation.resolved=True if resolved_paper exists
- THEN PASS 3: Link citations
  - Build bidirectional links: paper.cited_papers and resolved_paper.cited_by_papers
  - Add resolved_paper to paper.cited_papers if not already present
  - Add paper to resolved_paper.cited_by_papers if not already present
  - Track forward_links_created and reverse_links_created

#### Scenario: Forward Citation Extraction

- GIVEN papers with DOIs published >= year threshold
- WHEN executing CitationsStep with `forward.citations=["openalex", "semantic_scholar"]`
- THEN it SHALL:
  - For each paper, call `fetcher.fetch_cited_by(doi, limit=100)`
  - Store returned Citation list (CitationDirection.FORWARD) in paper.cited_by
  - In PASS 2, resolve each forward citation same as backward
  - In PASS 3, link citations bidirectionally:
    - paper.cited_by_papers = citing papers
    - citing_paper.cited_papers = paper

#### Scenario: Citation Confidence Scoring

- GIVEN Crossref reference with fields
- WHEN calculating confidence score (Crossref handler)
- THEN:
  - IF doi-asserted-by=publisher: confidence = 1.0
  - ELSE: confidence = 0.5 (base) + 0.35 (if doi present) + 0.1 (if title > 10 chars) + 0.05 (if year)
  - CAP at 1.0

#### Scenario: Citation Iteration and Screening

- GIVEN backward config with `iterations=2` and `screening="screening_template"`
- WHEN executing CitationsStep
- THEN it SHALL:
  - WHILE iteration < iterations:
    - Get papers where discovery.iteration == current_iteration
    - Run PASS 1-3 for those papers
    - If screening template provided, execute it (marks papers INCLUDE/EXCLUDE)
    - Increment iteration counter
    - NEXT iteration processes newly created papers from PASS 2

#### Scenario: Citation Error Handling

- GIVEN backward config with `output_errors="/tmp/citation_errors.jsonl"`
- WHEN citations cannot be resolved
- THEN it SHALL:
  - Write unresolved citations to JSONL file: `{"doi": paper_doi, "citation": [...]}`
  - Continue processing other papers (unless continue_on_not_found=False)
  - Report error count and unresolved citations in StepResult

---

### Requirement: PDF Download and Caching

The PDF download system MUST fetch PDFs from multiple sources with caching, detect open access status, and support multiple download handlers.

#### Scenario: PDF Caching Architecture

- GIVEN Fetcher with PDFCache at `cache_dir/pdfs/`
- WHEN calling `fetch_pdf(doi, timeout=30)`
- THEN it SHALL:
  - CHECK PDFCache.get(doi) first (returns cached file path if exists)
  - IF cached_path exists and file exists on disk, RETURN PDFInfo with download_source="cache"
  - IF not cached, TRY handlers in order:
    - Call handler.fetch_pdf(doi) (returns PDFInfo with file_path and download_source)
    - If handler returns PDFInfo with file_path, CACHE it via PDFCache.set(doi, pdf_path)
    - RETURN PDFInfo with updated file_path (now in cache) and preserved download_source
- AND PDFCache SHALL use DOI as key for deterministic paths

#### Scenario: Handler PDF Download

- GIVEN handler with API metadata (e.g., Crossref link array)
- WHEN calling handler.fetch_pdf(doi, timeout=30)
- THEN it SHALL:
  - Call `fetch_metadata(doi)` to get API data
  - Call `_find_download_url(api_data)` (handler-specific implementation)
  - IF URL found, download via requests.get(url, timeout=timeout)
  - CHECK content-type header: IF 'text/html', reject (paywalled page)
  - CREATE temporary file with response.content
  - RETURN PDFInfo(file_path, file_size_bytes, download_source=handler.name, download_url)

#### Scenario: Open Access PDF Detection

- GIVEN OpenAlex metadata with open_access object
- WHEN downloading PDF
- THEN it SHALL:
  - Check OpenAccessStatus.is_oa from handler.fetch_paper()
  - IF is_oa=True, prioritize PDF download
  - Support oa_status values: gold, green, hybrid, bronze, closed
  - Prioritize gold/green over hybrid/bronze

#### Scenario: PDF Download Error Handling

- GIVEN network timeout or HTTP error during download
- WHEN handler.fetch_pdf() called
- THEN it SHALL:
  - Catch requests.exceptions.RequestException
  - Log error (if debug=True)
  - RETURN None (no PDF info)
  - Caller MAY retry with different handler or skip

#### Scenario: Downloaded PDF Storage

- GIVEN successfully downloaded PDF and DownloadPDFsStep config with `store_path=./papers/`
- WHEN executing step
- THEN it SHALL:
  - Create store directory if not exists
  - Copy PDF from temporary location via shutil.copy2()
  - Rename to `{DOI.safe}.pdf` (safe = DOI with special chars replaced)
  - Update Paper.pdf_info with new file path and file_size_bytes
  - Preserve download_source (handler name) for attribution

---

### Requirement: HTTP Response Caching

The HTTP caching system MUST cache JSON API responses with MD5-keyed storage, cache 404s to prevent repeated lookups, and support key normalization.

#### Scenario: JSONFileCache Operation

- GIVEN handler with JSONFileCache at `cache_dir/[handler_name]/`
- WHEN calling `_jsoncache.get(key)` first time
- THEN it SHALL:
  - Normalize key via MD5 hash: `hashlib.md5(key.encode()).hexdigest()`
  - Check if cache file exists at `cache_dir/[md5_hex].json`
  - IF not exists, return None
  - IF exists, deserialize JSON and return dict

#### Scenario: JSON Cache Storage

- GIVEN API response dict from Crossref
- WHEN calling `_jsoncache.set(doi, api_data)`
- THEN it SHALL:
  - Normalize key via MD5 hash
  - Serialize api_data as JSON
  - Write to cache file with atomic write (temp file + rename)
  - Set file permissions for security (if applicable)

#### Scenario: 404 Marker Caching

- GIVEN DOI not found in external API
- WHEN `fetch_metadata(doi)` called and `_fetch_from_api()` returns None
- THEN it SHALL:
  - Create 404 marker dict via `create_404_marker(key=doi, url=f"https://doi.org/{doi}")`
  - Cache marker: `_jsoncache.set(doi, marker_dict)`
- WHEN `fetch_metadata(doi)` called again
- THEN it SHALL:
  - Retrieve cached data
  - Check `is_404_marker(api_data)` → True
  - RETURN (None, True) immediately without API call
- AND cache_hit=True for 404s (prevents repeated external API lookups)

#### Scenario: Empty List Caching

- GIVEN API call for forward citations returns empty list
- WHEN caching via `_jsoncache.set(f"{doi}_fwd", [])`
- THEN on next call with same key:
  - Retrieve cached empty list
  - RETURN ([], True) for cache_hit

---

### Requirement: Metadata Merging

The metadata merging system MUST combine data from multiple handlers with field priority rules and timestamp tracking.

#### Scenario: Paper Merging in Fetcher

- GIVEN first handler returns partial Paper, second handler returns full Paper
- WHEN `fetch_paper(doi)` processes handlers sequentially
- THEN for each handler after first:
  - IF new_paper exists, call `handler.merge_papers(paper, new_paper)`
  - MERGE fields non-destructively
  - Continue to next handler unless quality >= 0.9

#### Scenario: Field Merge Priority

- GIVEN target Paper (from first handler) and source Paper (from second handler)
- WHEN calling `merge_papers(target, source, overwrite=False)`
- THEN for each field in order:
  - abstract, title, keywords, topics, authors, year, journal, url, isbn, issn, pmid, publisher, volume, number, pages, publication_date, paper_type, oa_status, raw_json:
    - IF overwrite=True: set target.field = source.field
    - ELSE IF target.field is empty/None: set target.field = source.field
    - ELSE: keep target.field unchanged
- AND update target.updated_at = datetime.now()

#### Scenario: Quality-Based Stopping

- GIVEN paper.calculated_quality_score = 0.92 (calculated from field coverage)
- WHEN fetching with handlers ordered [manual, crossref, openalex]
- THEN:
  - manual returns paper with quality=0.5 (incomplete)
  - crossref merges and achieves quality=0.92
  - STOP at crossref (quality >= 0.9 threshold)
  - DO NOT call openalex handler

---

## Metadata

### Implementation Files

- [src/paper_scanner/tools/fetchers/fetcher.py](../../../src/paper_scanner/tools/fetchers/fetcher.py) - Orchestrator for metadata fetching
- [src/paper_scanner/tools/fetchers/fetcher_handlers/base.py](../../../src/paper_scanner/tools/fetchers/fetcher_handlers/base.py) - Base handler abstract class
- [src/paper_scanner/tools/fetchers/fetcher_handlers/crossref_handler.py](../../../src/paper_scanner/tools/fetchers/fetcher_handlers/crossref_handler.py) - Crossref API handler
- [src/paper_scanner/tools/fetchers/fetcher_handlers/openalex_handler.py](../../../src/paper_scanner/tools/fetchers/fetcher_handlers/openalex_handler.py) - OpenAlex API handler
- [src/paper_scanner/tools/fetchers/fetcher_handlers/semantic_scholar_handler.py](../../../src/paper_scanner/tools/fetchers/fetcher_handlers/semantic_scholar_handler.py) - Semantic Scholar handler
- [src/paper_scanner/tools/fetchers/fetcher_handlers/manual_handler.py](../../../src/paper_scanner/tools/fetchers/fetcher_handlers/manual_handler.py) - Manual metadata entry handler
- [src/paper_scanner/io/bibtex.py](../../../src/paper_scanner/io/bibtex.py) - BibTeX import/export
- [src/paper_scanner/io/ris.py](../../../src/paper_scanner/io/ris.py) - RIS import
- [src/paper_scanner/steps/bibtex_import.py](../../../src/paper_scanner/steps/bibtex_import.py) - BibTeX import step
- [src/paper_scanner/steps/ris_import.py](../../../src/paper_scanner/steps/ris_import.py) - RIS import step
- [src/paper_scanner/steps/retrieve_metadata.py](../../../src/paper_scanner/steps/retrieve_metadata.py) - Metadata retrieval step
- [src/paper_scanner/steps/citations.py](../../../src/paper_scanner/steps/citations.py) - Citation extraction step
- [src/paper_scanner/steps/download_pdfs.py](../../../src/paper_scanner/steps/download_pdfs.py) - PDF download step

### Test Coverage

The following test files verify the requirements in this specification:

**Metadata Handlers:**
- [tests/unit/tools/test_crossref_handler.py](../../../tests/unit/tools/test_crossref_handler.py) - Crossref API integration
- [tests/unit/tools/test_crossref_metadata.py](../../../tests/unit/tools/test_crossref_metadata.py) - Crossref metadata extraction
- [tests/unit/tools/test_crossref_citations.py](../../../tests/unit/tools/test_crossref_citations.py) - Crossref citation data
- [tests/unit/tools/test_openalex_handler.py](../../../tests/unit/tools/test_openalex_handler.py) - OpenAlex API integration
- [tests/unit/tools/test_publisher_handler.py](../../../tests/unit/tools/test_publisher_handler.py) - Publisher API integration
- [tests/unit/tools/test_manual_handler.py](../../../tests/unit/tools/test_manual_handler.py) - Manual metadata entry
- [tests/unit/tools/test_manual_handler_authors.py](../../../tests/unit/tools/test_manual_handler_authors.py) - Manual author handling

**Fetcher and Caching:**
- [tests/unit/tools/test_fetcher.py](../../../tests/unit/tools/test_fetcher.py) - Core fetcher logic
- [tests/unit/tools/test_fetcher_jsoncache_reading.py](../../../tests/unit/tools/test_fetcher_jsoncache_reading.py) - JSON cache reading
- [tests/unit/tools/test_fetcher_metadata.py](../../../tests/unit/tools/test_fetcher_metadata.py) - Metadata fetching
- [tests/unit/tools/test_fetcher_pdf.py](../../../tests/unit/tools/test_fetcher_pdf.py) - PDF downloading

**Import/Export:**
- [tests/unit/io/test_bibtex_parser.py](../../../tests/unit/io/test_bibtex_parser.py) - BibTeX parsing
- [tests/unit/io/test_bibtex_with_normalizer.py](../../../tests/unit/io/test_bibtex_with_normalizer.py) - BibTeX with normalization
- [tests/unit/io/test_ris.py](../../../tests/unit/io/test_ris.py) - RIS format parsing
- [tests/unit/io/test_ris_with_normalizer.py](../../../tests/unit/io/test_ris_with_normalizer.py) - RIS with normalization
- [tests/unit/io/test_json.py](../../../tests/unit/io/test_json.py) - JSON serialization
- [tests/unit/io/test_serialization_validation.py](../../../tests/unit/io/test_serialization_validation.py) - Validation logic
- [tests/unit/io/test_sql.py](../../../tests/unit/io/test_sql.py) - SQL database operations

**Pipeline Steps:**
- [tests/unit/steps/test_bibtex_import.py](../../../tests/unit/steps/test_bibtex_import.py) - BibTeX import step
- [tests/unit/steps/test_ris_import.py](../../../tests/unit/steps/test_ris_import.py) - RIS import step
- [tests/unit/steps/test_retrieve_metadata.py](../../../tests/unit/steps/test_retrieve_metadata.py) - Metadata retrieval step
- [tests/unit/steps/test_download_pdfs.py](../../../tests/unit/steps/test_download_pdfs.py) - PDF download step
- [tests/unit/steps/test_load_files.py](../../../tests/unit/steps/test_load_files.py) - File loading step

**Citations:**
- [tests/unit/steps/test_citations.py](../../../tests/unit/steps/test_citations.py) - Citation extraction
- [tests/unit/steps/test_citations_backward.py](../../../tests/unit/steps/test_citations_backward.py) - Backward citations
- [tests/unit/steps/test_citations_forward.py](../../../tests/unit/steps/test_citations_forward.py) - Forward citations
- [tests/unit/tools/test_citations_integration.py](../../../tests/unit/tools/test_citations_integration.py) - Citation integration
- [tests/unit/io/test_citation_edges_db.py](../../../tests/unit/io/test_citation_edges_db.py) - Citation graph database

### Related Specifications

- [001-data-models](../001-data-models/spec.md) - Paper, Citation, Author, PDFInfo models
- [002-pipeline-engine](../002-pipeline-engine/spec.md) - StepResult, pipeline execution
- [003-screening-workflow](../003-screening-workflow/spec.md) - Paper filtering and decision logic
- [005-embedding-system](../005-embedding-system/spec.md) - Semantic search and embeddings (uses Paper models from metadata)
- [006-web-interface](../006-web-interface/spec.md) - API endpoints for metadata retrieval (consumes this spec)

### Architectural Decision Records

- [ADR-0004: Source Structure & Test Organization](../../../docs/adr/0004-source-setup.md) — Module layout and three-tier test strategy

---

## References

- **RFC 2119**: https://datatracker.ietf.org/doc/html/rfc2119
- **Crossref API**: https://github.com/CrossRef/rest-api-doc
- **OpenAlex API**: https://docs.openalex.org/
- **Semantic Scholar API**: https://api.semanticscholar.org/api-docs/graph
- **BibTeX Format**: https://www.ctan.org/pkg/bibtex
- **RIS Format**: https://en.wikipedia.org/wiki/RIS_(file_format)
- **JSON File Cache**: Paper Scanner core.cache module
- **Unpaywall API**: https://unpaywall.org/products/api

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
