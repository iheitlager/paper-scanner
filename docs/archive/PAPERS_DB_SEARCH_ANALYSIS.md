# Papers Database Search Analysis

## Overview

This document analyzes how the `papers_db` (List[Paper]) is currently searched and accessed in the categorization, deduplication, and keyword_screening steps to identify optimization opportunities.

---

## Executive Summary

### Current Search Patterns

**All three critical steps use linear O(n) searches:**

1. **Deduplication**: Searches existing papers sequentially for matches (3 methods)
2. **Keyword Screening**: Iterates through papers once with field-based text matching
3. **Categorization**: Iterates through papers once with keyword extraction from titles/abstracts

### Performance Issues

- **Deduplication** is the most problematic:
  - For each paper, compares against ALL previously processed papers
  - Runs 3 different matching algorithms per paper
  - For 1000 papers: ~500,000 comparisons (n²/2)
  - For 10,000 papers: ~50 million comparisons
  - Each comparison includes text normalization, regex matching, or sequence matching

- **Keyword Screening**: 
  - Single-pass iteration (acceptable)
  - Text extraction and regex matching is O(n * k) where k = keyword count
  - No indexing of papers by content

- **Categorization**:
  - Single-pass iteration (acceptable)
  - Text extraction and keyword scanning
  - No indexing of papers by type/quality tier

---

## Detailed Analysis by Step

### 1. DEDUPLICATION STEP

**File**: `src/paper_scanner/steps/deduplication.py`

#### Current Algorithm
```python
unique_papers = []

for i, paper in enumerate(papers_db):
    if paper.duplicate_of is not None:
        continue
    
    duplicate_found = False
    
    for method_config in methods:  # 3 methods: doi_exact, title_author_fuzzy, title_fuzzy
        if method == "doi_exact":
            match_result = _doi_exact_match(paper, unique_papers)  # O(n) search
        elif method == "title_author_fuzzy":
            match_result = _title_author_fuzzy_match(paper, unique_papers, threshold)  # O(n) search
        elif method == "title_fuzzy":
            match_result = _title_fuzzy_match(paper, unique_papers, threshold)  # O(n) search
        
        if match_result:
            # Mark as duplicate and break
            break
    
    if not duplicate_found:
        unique_papers.append(paper)
```

#### Search Methods Used

##### Method 1: DOI Exact Match
```python
def _doi_exact_match(paper: Paper, existing_papers: List[Paper]) -> Optional[Tuple[str, float]]:
    if not paper.doi:
        return None
    
    for existing in existing_papers:  # LINEAR SEARCH: O(n)
        if existing.doi and existing.doi.lower() == paper.doi.lower():
            return (existing.id, 1.0)
    
    return None
```

**Complexity**: O(n) per paper → O(n²) total

**Optimization**: Use dict keyed by DOI
```python
doi_index = {p.doi.lower(): p for p in papers if p.doi}
# Lookup: O(1)
```

---

##### Method 2: Title + First Author Fuzzy Match
```python
def _title_author_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.90
) -> Optional[Tuple[str, float]]:
    if not paper.title or not paper.authors:
        return None
    
    norm_title = _normalize_title(paper.title)
    first_author = paper.authors[0].family_name.lower()
    
    for existing in existing_papers:  # LINEAR SEARCH: O(n)
        if not existing.title or not existing.authors:
            continue
        
        existing_norm_title = _normalize_title(existing.title)
        existing_first_author = existing.authors[0].family_name.lower()
        
        if first_author != existing_first_author:  # Early exit optimization
            continue
        
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()
        if similarity >= threshold:
            return (existing.id, similarity)
    
    return None
```

**Complexity**: O(n * m) per paper, where m = string comparison cost → O(n² * m) total

**Optimizations**:
1. Group papers by first author family name
2. Use BK-tree or similar fuzzy matching structure
3. Use tokenization + set operations for title comparison

---

##### Method 3: Title-Only Fuzzy Match
```python
def _title_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.95
) -> Optional[Tuple[str, float]]:
    if not paper.title:
        return None
    
    norm_title = _normalize_title(paper.title)
    
    for existing in existing_papers:  # LINEAR SEARCH: O(n)
        if not existing.title:
            continue
        
        existing_norm_title = _normalize_title(existing.title)
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()
        
        if similarity >= threshold:
            return (existing.id, similarity)
    
    return None
```

**Complexity**: O(n * m) per paper, where m = string length → O(n² * m) total

**Optimization**: Locality-sensitive hashing (LSH) for approximate title matching

---

#### Deduplication Performance Estimates

For different database sizes:

| Papers | Comparisons | Method 1 (exact) | Method 2 (fuzzy) | Method 3 (fuzzy) | Total Operations |
|--------|-------------|------------------|------------------|------------------|------------------|
| 100    | 5,000       | Fast             | Slow             | Slow             | ~10K             |
| 1,000  | 500,000     | Fast             | Very Slow        | Very Slow        | ~1M              |
| 10,000 | 50M         | Medium           | Extremely Slow   | Extremely Slow   | ~100M            |
| 100K   | 5B          | Slow             | Impractical      | Impractical      | ~10B             |

---

### 2. KEYWORD SCREENING STEP

**File**: `src/paper_scanner/steps/keyword_screening.py`

#### Current Algorithm
```python
for i, paper in enumerate(papers_db):  # O(n)
    screening, passed, exclusion_reason = _screen_paper(
        paper,
        hard_exclusions,
        inclusion_keywords,
        inclusion_threshold=threshold,
        use_word_boundaries=use_word_boundaries,
        verbose=verbose
    )
    # ... record results
```

#### Screening Operations Per Paper

```python
def _screen_paper(
    paper: Paper,
    hard_exclusions: List[str],
    inclusion_keywords: List[str],
    inclusion_threshold: int = 1,
    use_word_boundaries: bool = True,
    verbose: bool = False
) -> Tuple[KeywordScreening, bool, Optional[str]]:
    
    # Combine text once
    combined_text = _normalize_text(f"{paper.title or ''} {paper.abstract or ''}")
    
    # Check hard exclusions
    excluded_kw, excluded_count = _check_keyword_match(
        combined_text, hard_exclusions, use_word_boundaries
    )  # O(k * len(combined_text)) where k = exclusion keywords
    
    if excluded_count > 0:
        return (...)
    
    # Check inclusion keywords  
    title_matches, abstract_matches, keywords_matches, all_matched = _get_field_matches(
        paper, inclusion_keywords, use_word_boundaries
    )  # O(3 * k * field_length) where k = inclusion keywords
```

#### Keyword Matching Implementation

```python
def _check_keyword_match(
    text: str,
    keywords: List[str],
    use_word_boundaries: bool = True
) -> Tuple[List[str], int]:
    
    matched = []
    
    for keyword in keywords:  # O(k) iterations
        keyword_lower = keyword.lower()
        
        if use_word_boundaries:
            # Regex compilation + search: O(len(text)) per keyword
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(pattern, text):
                matched.append(keyword)
        else:
            # Simple substring: O(len(text)) per keyword
            if keyword_lower in text:
                matched.append(keyword)
    
    return matched, len(matched)
```

**Complexity**: O(n * k * m) where:
- n = number of papers
- k = number of keywords
- m = average text length

**Performance**: With 1000 papers, 50 inclusion keywords, ~500 chars combined text:
- ~25M character comparisons per pass
- Acceptable for single pass

#### Keyword Screening Optimizations Needed

**Minor optimization opportunity**: 
- Pre-compile regex patterns instead of compiling per paper
- Use single pass for both exclusion and inclusion keywords

**Current**: Regex compiled fresh for each paper per keyword
**Better**: Pre-compile all patterns once

---

### 3. CATEGORIZATION STEP

**File**: `src/paper_scanner/steps/categorization.py`

#### Current Algorithm
```python
for i, paper in enumerate(papers_db):  # O(n)
    categorization, should_include, exclusion_reason = _categorize_paper(
        paper,
        verbose=verbose
    )
    # ... record results
```

#### Categorization Operations Per Paper

```python
def _categorize_paper(paper: Paper, verbose: bool = False) -> Tuple[Categorization, bool, Optional[str]]:
    
    # 1. Check paper type
    paper_type, is_peer_reviewed, type_rejection = _check_paper_type(
        getattr(paper, 'paper_type', None)
    )  # O(1) - simple lookup
    
    # 2. Check if review paper
    is_review = _is_review_paper(paper.title, paper.abstract)  # O(k * m) where k = review keywords
    
    # 3. Check if conceptual paper
    is_conceptual = _is_conceptual_paper(paper.title, paper.abstract)  # O(2k * m)
```

#### Keyword Searching in Categorization

```python
def _is_review_paper(title: Optional[str], abstract: Optional[str]) -> bool:
    combined_text = _normalize_text(f"{title or ''} {abstract or ''}")
    
    for keyword in REVIEW_KEYWORDS:  # 11 keywords
        if keyword.lower() in combined_text:  # Substring search: O(m)
            return True
    
    return False

def _is_conceptual_paper(title: Optional[str], abstract: Optional[str]) -> bool:
    combined_text = _normalize_text(f"{title or ''} {abstract or ''}")
    
    # Count conceptual keywords
    conceptual_count = 0
    for keyword in CONCEPTUAL_KEYWORDS:  # 11 keywords
        if keyword.lower() in combined_text:  # O(m) per keyword
            conceptual_count += 1
    
    # Count empirical keywords
    empirical_count = 0
    for keyword in EMPIRICAL_KEYWORDS:  # 16 keywords
        if keyword.lower() in combined_text:  # O(m) per keyword
            empirical_count += 1
    
    return conceptual_count > empirical_count
```

**Complexity**: O(n * (11 + 11 + 16) * m) = O(n * 38 * m)
- n = 1000 papers
- m = ~600 chars average
- ~22.8M character comparisons (still acceptable)

#### Categorization Optimization Opportunities

**Minor**: Pre-split text into tokens, use set intersection instead of substring search
- Current: 38 substring searches per paper
- Better: 1-2 token set operations per paper

---

## Summary Table: Search Complexity Analysis

| Step | Algorithm | Search Type | Complexity | Papers | Ops |
|------|-----------|-------------|-----------|---------|-----|
| **Deduplication - DOI** | Exact match | Linear search | O(n²) | 1K | 500K |
| **Deduplication - Title+Author** | Fuzzy match | Linear search + regex | O(n² * m) | 1K | 1M+ |
| **Deduplication - Title** | Fuzzy match | Linear search + regex | O(n² * m) | 1K | 1M+ |
| **Keyword Screening** | Keyword matching | Linear scan with regex | O(n * k * m) | 1K | 25M |
| **Categorization** | Keyword matching | Linear scan | O(n * 38 * m) | 1K | 23M |

---

## Recommended Optimizations

### Priority 1: Deduplication (Biggest Impact)

#### For DOI exact matching:
```python
# BUILD PHASE: O(n)
doi_map = {}
for paper in papers_db:
    if paper.doi:
        doi_map[paper.doi.lower()] = paper

# LOOKUP PHASE: O(1)
def find_doi_duplicate(paper, doi_map):
    if paper.doi:
        return doi_map.get(paper.doi.lower())
    return None
```

#### For Title+Author fuzzy matching:
```python
# BUILD PHASE: O(n log n)
from collections import defaultdict
author_groups = defaultdict(list)
for paper in papers_db:
    if paper.authors:
        author_groups[paper.authors[0].family_name.lower()].append(paper)

# LOOKUP PHASE: O(k * m) where k = papers by same author
def find_author_fuzzy_duplicate(paper, author_groups, threshold):
    if paper.authors:
        author = paper.authors[0].family_name.lower()
        candidates = author_groups[author]  # Pre-filtered
        # Only compare against candidates
        for existing in candidates:
            ...
```

#### For Title fuzzy matching:
```python
# Option 1: LSH (Locality-Sensitive Hashing)
# Pre-build Bloom filter or MinHash signatures
# Query: O(log n) approximate lookups

# Option 2: Simple token-based deduplication
def title_tokens(title):
    return set(title.lower().split()) - stop_words

# BUILD PHASE: O(n)
token_map = defaultdict(list)
for paper in papers_db:
    tokens = title_tokens(paper.title)
    for token in tokens:
        token_map[token].append(paper)

# LOOKUP: O(k) where k = avg papers per token
def find_title_fuzzy_candidates(paper, token_map):
    tokens = title_tokens(paper.title)
    candidate_papers = set()
    for token in tokens:
        candidate_papers.update(token_map[token])
    return list(candidate_papers)
```

### Priority 2: Keyword Screening (Medium Impact)

```python
# Pre-compile regex patterns
compiled_patterns = {
    'exclusion': [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) 
                  for kw in hard_exclusions],
    'inclusion': [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) 
                  for kw in inclusion_keywords]
}

# Use compiled patterns in loop
for paper in papers_db:
    combined_text = _normalize_text(f"{paper.title or ''} {paper.abstract or ''}")
    
    # Use compiled patterns
    for pattern in compiled_patterns['exclusion']:
        if pattern.search(combined_text):
            # excluded
            break
    
    for pattern in compiled_patterns['inclusion']:
        if pattern.search(combined_text):
            # found match
```

### Priority 3: Categorization (Low Impact)

```python
# Convert keyword lists to frozensets for faster checking
REVIEW_KEYWORDS_SET = frozenset(k.lower() for k in REVIEW_KEYWORDS)
CONCEPTUAL_KEYWORDS_SET = frozenset(k.lower() for k in CONCEPTUAL_KEYWORDS)
EMPIRICAL_KEYWORDS_SET = frozenset(k.lower() for k in EMPIRICAL_KEYWORDS)

# Use token-based matching instead of substring
def tokenize(text):
    return set(w.lower() for w in re.findall(r'\b\w+\b', text))

def _is_review_paper_optimized(title, abstract):
    tokens = tokenize(f"{title or ''} {abstract or ''}")
    return bool(tokens & REVIEW_KEYWORDS_SET)  # Set intersection
```

---

## Data Structure Recommendations for papers_db

### Current Structure
```python
papers_db: List[Paper] = []
```

### Recommended Enhanced Structure
```python
class PapersDatabase:
    """Papers database with indexing for fast lookup"""
    
    def __init__(self):
        self.papers: List[Paper] = []
        
        # Deduplication indexes
        self.doi_index: Dict[str, Paper] = {}  # doi -> paper
        self.author_index: Dict[str, List[Paper]] = defaultdict(list)  # author_name -> [papers]
        self.title_tokens: Dict[str, List[Paper]] = defaultdict(list)  # token -> [papers]
        
        # Screening indexes
        self.paper_type_index: Dict[str, List[Paper]] = defaultdict(list)  # type -> [papers]
        self.quality_tier_index: Dict[str, List[Paper]] = defaultdict(list)  # tier -> [papers]
        self.inclusion_decision: Dict[str, List[Paper]] = defaultdict(list)  # decision -> [papers]
    
    def add_paper(self, paper: Paper):
        """Add paper and update all indexes"""
        self.papers.append(paper)
        self._index_paper(paper)
    
    def _index_paper(self, paper: Paper):
        """Update all indexes for a paper"""
        if paper.doi:
            self.doi_index[paper.doi.lower()] = paper
        
        if paper.authors:
            self.author_index[paper.authors[0].family_name.lower()].append(paper)
        
        # ... other indexes
    
    def find_doi_duplicate(self, paper: Paper) -> Optional[Paper]:
        """O(1) lookup"""
        if paper.doi:
            return self.doi_index.get(paper.doi.lower())
        return None
    
    def find_author_duplicates(self, paper: Paper) -> List[Paper]:
        """O(1) group retrieval"""
        if paper.authors:
            return self.author_index.get(paper.authors[0].family_name.lower(), [])
        return []
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (30 min)
1. Add DOI index to deduplication
2. Pre-compile regex patterns for keyword screening
3. Test performance improvement

### Phase 2: Moderate Refactor (2-3 hours)
1. Add author grouping index
2. Add title token index
3. Update deduplication to use indexes
4. Benchmark performance

### Phase 3: Data Structure Refactor (1-2 days)
1. Create `PapersDatabase` class
2. Migrate all steps to use new structure
3. Add comprehensive indexing strategy
4. Full performance testing

---

## Notes on Backward Compatibility

All optimizations can be implemented transparently:
- `PapersDatabase` can be a wrapper around `List[Paper]`
- Existing code using `papers_db` directly can be migrated incrementally
- No changes needed to step interfaces (execute functions)

---

## Expected Performance Improvements

| Operation | Current | Optimized | Speedup |
|-----------|---------|-----------|---------|
| DOI matching (1K papers) | 1000 ops | 1 op | 1000x |
| Author grouping (1K papers) | 500K+ ops | 1000 ops | 500x |
| Title candidates (1K papers) | 500K+ ops | 1K-5K ops | 100-500x |
| Keyword screening (1K papers) | 25M+ ops | 5M ops | 5x |
| **Overall deduplication time** | ~30 mins | ~2 mins | **15x** |
