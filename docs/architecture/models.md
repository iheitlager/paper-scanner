# Data Models

## Core Entities

### Paper

Represents a single academic publication with comprehensive metadata.

**Fields:**
- `id` (UUID) - Unique identifier
- `cite_key` (str) - BibTeX cite key
- `title` (str) - Paper title
- `authors` (List[Author]) - List of authors
- `year` (int) - Publication year
- `journal` (str) - Journal or venue name
- `volume` (str) - Journal volume
- `number` (str) - Journal issue number
- `pages` (str) - Page range
- `doi` (str) - Digital Object Identifier
- `url` (str) - Paper URL
- `abstract` (str) - Paper abstract
- `keywords` (List[str]) - Keywords
- `paper_type` (PaperType) - Type of publication
- `cited_papers` (List[Paper]) - Papers this cites
- `cited_by_papers` (List[Paper]) - Papers that cite this
- `citations` (List[Citation]) - Backward citations
- `cited_by` (List[Citation]) - Forward citations
- `tags` (List[str]) - User-defined tags
- `screening_results` (Dict) - ML screening results
- `created_at` (datetime) - Creation timestamp
- `updated_at` (datetime) - Last update timestamp

**Example:**
```python
paper = Paper(
    cite_key="Smith2023",
    title="A Survey of Machine Learning",
    authors=[Author(first_name="John", last_name="Smith")],
    year=2023,
    journal="Nature Machine Intelligence",
    doi="10.1234/example.doi",
    abstract="This survey covers...",
    keywords=["machine learning", "deep learning"],
    paper_type=PaperType.JOURNAL_ARTICLE
)
```

### Citation

Represents a citation relationship between papers.

**Fields:**
- `id` (UUID) - Unique identifier
- `doi` (str) - DOI of cited paper
- `title` (str) - Title of cited paper
- `authors` (List[Author]) - Authors of cited paper
- `year` (int) - Publication year
- `direction` (CitationDirection) - BACKWARD or FORWARD
- `extraction_method` (str) - How citation was extracted
- `confidence` (float) - Confidence score (0-1)
- `resolved` (bool) - Whether resolved to a Paper
- `resolved_paper` (Paper) - Referenced Paper object
- `raw_text` (str) - Citation as it appeared
- `raw_json` (Dict) - Raw structured data

**Directions:**
- `BACKWARD`: Paper cites this (reference)
- `FORWARD`: Paper is cited by this (cited_by)

**Example:**
```python
citation = Citation(
    doi="10.1234/cited.doi",
    title="Foundation Paper",
    direction=CitationDirection.BACKWARD,
    extraction_method="crossref",
    confidence=0.95
)
```

### Author

Represents a paper author or researcher.

**Fields:**
- `id` (UUID) - Unique identifier
- `first_name` (str) - Given name
- `last_name` (str) - Family name
- `email` (str, optional) - Email address
- `affiliation` (str, optional) - Organization/institution
- `orcid` (str, optional) - ORCID identifier

**Example:**
```python
author = Author(
    first_name="Jane",
    last_name="Doe",
    affiliation="MIT",
    orcid="0000-0001-2345-6789"
)
```

### Keyword

Represents a subject keyword for papers.

**Fields:**
- `value` (str) - Keyword text
- `papers` (List[Paper]) - Papers with this keyword

## Enumerations

### PaperType
Type of academic publication:
- `journal_article` - Journal article
- `conference_paper` - Conference proceedings
- `book_chapter` - Book chapter
- `book` - Standalone book
- `preprint` - Preprint (arXiv, etc.)
- `thesis` - Thesis/dissertation
- `technical_report` - Technical report
- `other` - Other type

### CitationDirection
Direction of citation relationship:
- `backward` - References (this paper cites other)
- `forward` - Cited by (other papers cite this)

### ScreeningStatus
Results of ML-based screening:
- `included` - Meets criteria
- `excluded` - Doesn't meet criteria
- `unclear` - Insufficient information
- `not_screened` - Not yet evaluated

## Relationships

### Paper ↔ Paper (via Citation)
```
Paper "cites"    → Citation → Paper "cited_papers"
Paper "cited_by" ← Citation ← Paper "cited_by_papers"
```

### Paper ↔ Author (Many-to-Many)
```
Paper "authors" → Author (multiple)
```

### Paper ↔ Keyword (Many-to-Many)
```
Paper "keywords" → Keyword
```

## Serialization

### JSON Format
Papers serialize to JSON for export and API responses:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "cite_key": "Smith2023",
  "title": "A Survey of Machine Learning",
  "authors": [
    {
      "first_name": "John",
      "last_name": "Smith",
      "affiliation": "MIT"
    }
  ],
  "year": 2023,
  "doi": "10.1234/example.doi",
  "abstract": "...",
  "keywords": ["machine learning", "deep learning"],
  "paper_type": "journal_article",
  "created_at": "2023-01-01T12:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z"
}
```

### BibTeX Format
Papers convert to BibTeX for citation management:

```bibtex
@article{Smith2023,
  title={A Survey of Machine Learning},
  author={Smith, John},
  journal={Nature Machine Intelligence},
  year={2023},
  doi={10.1234/example.doi}
}
```

## Database Schema

### papers table
```sql
CREATE TABLE papers (
  id UUID PRIMARY KEY,
  cite_key VARCHAR(255) UNIQUE,
  title TEXT NOT NULL,
  year INTEGER,
  journal VARCHAR(255),
  doi VARCHAR(255) UNIQUE,
  url TEXT,
  abstract TEXT,
  paper_type VARCHAR(50),
  batch_id UUID,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### authors table
```sql
CREATE TABLE authors (
  id UUID PRIMARY KEY,
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  email VARCHAR(255),
  affiliation VARCHAR(255),
  orcid VARCHAR(50)
);
```

### paper_authors (join table)
```sql
CREATE TABLE paper_authors (
  paper_id UUID REFERENCES papers(id),
  author_id UUID REFERENCES authors(id),
  position INTEGER,
  PRIMARY KEY (paper_id, author_id)
);
```

### citations table
```sql
CREATE TABLE citations (
  id UUID PRIMARY KEY,
  paper_id UUID REFERENCES papers(id),
  cited_doi VARCHAR(255),
  cited_title TEXT,
  direction VARCHAR(50),
  extraction_method VARCHAR(255),
  resolved BOOLEAN,
  resolved_paper_id UUID REFERENCES papers(id),
  created_at TIMESTAMP
);
```

## Query Patterns

### Find paper by DOI
```python
papers = db.get_by_doi("10.1234/example.doi")
```

### Find papers by author
```python
papers = db.find(
    lambda p: any(author.last_name == "Smith" for author in p.authors)
)
```

### Get citation graph
```python
paper = db.get(paper_id)
cited_papers = paper.cited_papers  # Papers this cites
citing_papers = paper.cited_by_papers  # Papers citing this
```

### Find papers by keyword
```python
papers = db.find(lambda p: "machine learning" in p.keywords)
```

## See Also

- [Architecture Overview](overview.md)
- [Database Operations](../api/core.md)
