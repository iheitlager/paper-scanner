# Spike 008: Fetcher Architecture & External Metadata Integration

## Design Overview

A flexible, composable fetcher system for retrieving paper metadata, citations, and PDFs from multiple external sources (Crossref, OpenAlex, CORE, Semantic Scholar, Unpaywall, etc.) with:

- **Separate handlers per API** - Each service has its own implementation
- **Flexible prioritization** - Configure which APIs to use and in what order
- **Field translators** - Normalize different API field formats/positions into Paper model
- **Intelligent caching** - Cache by API: `$CACHE_DIR/crossref/`, `$CACHE_DIR/openalex/`, etc.
- **Maximum traceability** - Use OpenAccessStatus, Discovery, PDFInfo for audit trails
- **Keywords & topics** - Extract and propagate keywords from best sources
- **Key propagation** - Ensure cite_key generation works correctly through the pipeline

## Architecture Principles

### 1. Separation of Concerns
Each operation is independent:
- **MetadataFetcher**: Load paper metadata by DOI → `Paper` model
- **CitationFetcher**: Load references (backward) → `Citation` + `Paper` models
- **CitedByFetcher**: Load citing papers (forward) → basic `Paper` models
- **PDFFetcher**: Download PDFs + detect OA status → `PDFInfo` + `OpenAccessStatus`

Database concerns are separate from fetcher concerns.

### 2. API Handler Pattern
Each API gets its own implementation class:
```
CrossrefMetadataFetcher
CrossrefCitationFetcher
UnpaywallPDFFetcher
OpenAlexMetadataFetcher
OpenAlexCitedByFetcher
COREMetadataFetcher
SemanticScholarCitationFetcher
... etc
```

No inheritance chains, each implements its interface cleanly.

### 3. Priority-Based Fallback
`FetcherConfig` allows registering multiple handlers with priorities:
```python
config = FetcherConfig()
config.add_metadata_fetcher(CrossrefMetadataFetcher(), priority=100)  # Try first
config.add_metadata_fetcher(OpenAlexMetadataFetcher(), priority=90)   # Fallback
config.add_metadata_fetcher(SemanticScholarFetcher(), priority=80)    # Last resort
```

Best sources for each task:
| Task | 1st Priority | 2nd | 3rd |
|------|-------------|-----|-----|
| **Metadata** | Crossref (fast, reliable) | OpenAlex (keywords) | CORE |
| **Keywords** | OpenAlex ⭐ (scoring) | Semantic Scholar | Crossref (subjects) |
| **Citations** | Crossref (50-100%) | Semantic Scholar | arXiv (preprints) |
| **Cited-by** | OpenAlex ⭐ (real-time) | Crossref (delayed) | Semantic Scholar |
| **PDFs** | Unpaywall (OA detection) | arXiv (preprints) | CORE (repos) |

### 4. Field Translators (Normalizers)
Each API returns different field names/formats. Translators normalize to Paper model:

**Example: Author normalization**
```python
# Crossref format
{"given": "John", "family": "Smith", "affiliation": [...]}

# OpenAlex format  
{"display_name": "John Smith", "orcid": "..."}

# Semantic Scholar format
{"name": "John Smith", "paperCount": 5}

# → All translate to Paper.authors: List[Author]
```

**Example: Date normalization**
```python
# Crossref: {"issued": {"date-parts": [[2020, 3, 15]]}}
# OpenAlex: "publication_date": "2020-03-15"
# CORE: "datePublished": "2020-03-15"

# → All translate to Paper.publication_date: datetime
```

**Translator responsibilities:**
- Extract field from API response (different paths per API)
- Convert to correct type (string → int, array → datetime, etc.)
- Handle null/missing values gracefully
- Preserve raw data in `raw_json` for audit

### 5. Caching Strategy
Cache responses per API in separate directories to:
- Respect rate limits
- Speed up re-runs
- Enable offline debugging
- Track API changes over time

```
~/.cache/paper-scanner/
├── crossref/
│   ├── a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.json
│   └── b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7.json
├── openalex/
│   ├── c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8.json
│   └── ...
├── core/
│   └── ...
├── unpaywall/
│   └── ...
└── semantic_scholar/
    └── ...
```

**Cache key format (MD5 hash of identifier):**
- Crossref: MD5(lowercase DOI) = MD5(`10.1287/isre.1100.0322`) = `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
- OpenAlex: MD5(OpenAlex ID) = `c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8`
- CORE: MD5(CORE ID) = `e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0`
- Others: MD5(best available identifier) = filename

**Benefits of MD5 hashing:**
- Fixed-length filenames (32 chars) regardless of identifier format
- Works with any identifier type (DOI, URL, ID number)
- Easy filesystem portability across systems
- Fast key lookup

**Cache hit tracking:**
- Store `last_cache_hit` in fetcher state
- Report in step results: "2/100 from cache, 98 from API"

### 6. Traceability in Paper Model

Every piece of metadata must be traceable to its source:

**Discovery** - How paper was found:
```python
class Discovery(BaseModel):
    method: DiscoveryMethod  # API, FILE, REFERENCE, SEARCH
    source_database: Optional[str]  # "crossref", "openalex", "file_scan"
    record_update: Optional[datetime]  # When source record was updated
    iteration: int  # 0=initial, 1+=snowballing
```

**OpenAccessStatus** - OA information with source:
```python
class OpenAccessStatus(BaseModel):
    is_oa: bool
    oa_status: Optional[str]  # "gold", "green", "bronze", "closed"
    oa_url: Optional[str]  # Direct PDF link
    version: Optional[str]  # "publishedVersion", "acceptedVersion", "submittedVersion"
    license: Optional[str]  # "CC-BY-4.0", etc.
    host_type: Optional[str]  # "publisher", "repository"
    source: Optional[str]  # "unpaywall", "openalex", "core"
    verified_at: Optional[datetime]  # When OA status was checked
```


**Raw data preservation:**
```python
class Paper(BaseModel):
    raw_json: Optional[Dict[str, Any]]  # Full original API response
    raw_bibtex: Optional[str]  # Original bibtex if applicable
```

### 7. Keywords & Topics Handling

**Best sources per quality:**

| Source | Keywords | Topics | Quality | Confidence |
|--------|----------|--------|---------|-----------|
| **OpenAlex** | ✅ `keywords[].display_name` | ✅ `topics[].display_name` | ⭐⭐⭐⭐⭐ | scores included |
| **Semantic Scholar** | ❌ `fieldsOfStudy: null` | ❌ blocked | ❌ Not provided | - |
| **CORE** | ❌ `fieldOfStudy: null` | ❌ blocked | ❌ Not provided | - |
| **Crossref** | ✅ `subject[]` | ❌ No | ⭐⭐ | No scoring |
| **Unpaywall** | ❌ No | ❌ No | ❌ Not provided | - |

**Strategy:**
1. Use OpenAlex keywords if available (with score > 0.5)
2. Fall back to Crossref subjects
3. Fall back to OpenAlex topics if no keywords
4. Store both `keywords` and `topics` in Paper model (separate fields)

**In Paper model:**
```python
class Paper(BaseModel):
    keywords: List[str] = []  # Extracted keywords defined in paper 
    topics: List[str] = []    # Broader topics/discipline categories
```



## Workflow Integration

### Step 1: load_files
```
PDF Files → Extract DOI → Create Paper with minimal metadata
Output: Paper(doi, title from PDF filename, cite_key from DOI/title)
```

### Step 2: retrieve_metadata
```
Paper(with DOI) → Fetch from APIs → Enrich all fields
Output: Paper(complete: abstract, keywords, authors, journal, etc.)
```

### Step 3: retrieve_citations
```
Paper(complete) → Fetch references → Create Citation + Paper records
Output: Backward Citation[](with DOI) → Paper[](new papers with screening)
```

### Step 4: retrieve_cited_by
```
Paper(complete) → Fetch forward citations → Create Citation + Paper records
Output: Forward Citation[](with DOI) → Paper[](new papers with screening)
```

### Step 5: retrieve_from_literature
```
Specialized version of retrieve_citations for lit review papers
Same as step 3 but with domain-specific screening rules
```

## Configuration Schema

```yaml
fetchers:
  metadata:
    - name: crossref
      priority: 100
      cache_dir: ~/.cache/paper-scanner/crossref
      rate_limit: 50  # per second
      
    - name: openalex
      priority: 90
      cache_dir: ~/.cache/paper-scanner/openalex
      rate_limit: 10
      
    - name: core
      priority: 80
      cache_dir: ~/.cache/paper-scanner/core
      api_key: ${CORE_API_KEY}
  
  citations:
    - name: crossref
      priority: 100
      max_references: 100
      
    - name: semantic_scholar
      priority: 90
      max_references: 500
  
  pdf:
    - name: unpaywall
      priority: 100
      email: i.heitlager@tue.nl
      
    - name: arxiv
      priority: 90
      for_preprints_only: true

keywords:
  primary_source: openalex  # Best source
  fallbacks:
    - crossref
    - core
  min_confidence: 0.5  # For OpenAlex scores
  max_count: 10  # Limit per paper

traceability:
  store_raw_json: true      # Full API response
  store_source: true        # Which API fetched it
  store_fetch_timestamp: true
```

## Implementation Checklist

### Phase 1: Base Interfaces & Crossref
- [ ] `base.py` - MetadataFetcher, CitationFetcher, CitedByFetcher, PDFFetcher interfaces
- [ ] `crossref_handler.py` - CrossrefMetadataFetcher, CrossrefCitationFetcher
- [ ] Field translators for Crossref format
- [ ] Caching system (JSONFileCache in $CACHE_DIR/crossref/)
- [ ] Unit tests for Crossref fetcher

### Phase 2: Additional Handlers
- [ ] `openalex_handler.py` - OpenAlexMetadataFetcher, OpenAlexCitedByFetcher
- [ ] `unpaywall_handler.py` - UnpaywallPDFFetcher with OA detection
- [ ] `core_handler.py` - COREMetadataFetcher
- [ ] `semantic_scholar_handler.py` - SemanticScholarCitationFetcher
- [ ] Field translators for each API

### Phase 3: Keywords & Topics
- [ ] Keywords extractor strategy (prioritize OpenAlex)
- [ ] Topics field in Paper model
- [ ] Keywords filtering by confidence
- [ ] Test keywords propagation

### Phase 4: Steps & Integration
- [ ] `retrieve_metadata_step.py` - Load metadata step
- [ ] `retrieve_citations_step.py` - Load citations step
- [ ] `retrieve_pdfs_step.py` - Load PDFs step
- [ ] Cite key re-generation logic
- [ ] Integration tests

### Phase 5: Configuration & CLI
- [ ] FetcherConfig YAML parser
- [ ] CLI for testing fetchers
- [ ] Performance monitoring (cache hits, API calls)

## Testing Strategy

**Unit tests per fetcher:**
```python
def test_crossref_fetcher_metadata():
    fetcher = CrossrefMetadataFetcher()
    paper = fetcher.fetch_metadata("10.1287/isre.1100.0322")
    assert paper.doi == "10.1287/isre.1100.0322"
    assert paper.title is not None
    assert len(paper.authors) > 0
```

**Integration tests:**
```python
def test_metadata_retrieval_with_fallback():
    config = FetcherConfig()
    config.add_metadata_fetcher(BrokenFetcher(), priority=100)  # Will fail
    config.add_metadata_fetcher(CrossrefFetcher(), priority=90)  # Will succeed
    
    paper, source = FallbackFetcher.fetch_metadata_with_fallback(...)
    assert source == "crossref"  # Fallback worked
```

**Cache validation tests:**
```python
def test_cache_hit_tracking():
    fetcher = CrossrefMetadataFetcher(cache_dir=tmpdir)
    
    # First call - cache miss
    paper1 = fetcher.fetch_metadata("10.1287/isre.1100.0322")
    assert not fetcher.last_cache_hit
    
    # Second call - cache hit
    paper2 = fetcher.fetch_metadata("10.1287/isre.1100.0322")
    assert fetcher.last_cache_hit
    assert paper1 == paper2
```

## Traceability Validation

Example of complete traceability chain:

```python
# Paper loaded with all traceability
paper = Paper(
    cite_key="smith_2020",
    title="Innovation in Digital Transformation",
    authors=[Author(family_name="Smith", ...)],
    keywords=["innovation", "digital", "transformation"],
    keywords_source="openalex",  # Best source
    
    doi="10.1287/isre.1100.0322",
    discovery=Discovery(
        method=DiscoveryMethod.API,
        source_database="crossref",
        record_update=datetime(2025, 1, 15),
        iteration=0
    ),
    
    oa_status=OpenAccessStatus(
        is_oa=True,
        oa_status="green",
        source="unpaywall",
        verified_at=datetime(2025, 1, 20)
    ),
    
    pdf_info=PDFInfo(
        file_path="/data/pdfs/smith_2020.pdf",
        download_source="unpaywall",
        downloaded_at=datetime(2025, 1, 20)
    ),
    
    raw_json={...}  # Full Crossref response for audit
)
```

You can trace:
- Where paper came from (Discovery.source_database)
- When metadata was last updated (Discovery.record_update)
- Where keywords came from (keywords_source)
- Whether PDF is open access (OpenAccessStatus)
- Where PDF was downloaded from (PDFInfo.download_source)
- Full original API response (raw_json)

## Next Steps

1. Review this design
2. Create base.py with interfaces
3. Implement Crossref handlers first (simplest, most used)
4. Build cache layer
5. Add remaining API handlers incrementally
6. Integrate with existing steps
