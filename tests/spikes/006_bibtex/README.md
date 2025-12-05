# Paper Screening Pipeline

A multi-stage system for loading BibTeX papers and filtering them through keyword and semantic analysis.

## Overview

```
📚 LOAD BIBTEX → STAGE 1 FILTER → STAGE 2 FILTER → 📊 DASHBOARD
```

## 1. Load BibTeX

Load academic papers from BibTeX files (Web of Science, Scopus, or IEEE Xplore) into PostgreSQL.

**File**: `load_bibtex.py`

**Triple-Source Support** ✨:
- **Web of Science (WOS)**: Auto-detected by `WOS:` prefix or `web-of-science-*` fields
- **Scopus**: Auto-detected by `source=Scopus` or `author_keywords` field
- **IEEE Xplore**: Auto-detected by fully numeric citekeys or `booktitle + (issn|month)` fields
- **Automatic field mapping**: 
  - WOS: `keywords` → keywords, `keywords-plus` → keywords_extra
  - Scopus: `author_keywords` → keywords, `keywords` → keywords_extra
  - IEEE: `keywords` → keywords (semicolon-separated)

**Architecture**:
- `BibtexTranslator`: Base class with common parsing
- `WOSTranslator`: Web of Science specific field mapping
- `ScopusTranslator`: Scopus specific field mapping
- `IEEETranslator`: IEEE Xplore specific field mapping
- `BibtexReader`: Auto-detects source and uses appropriate translator
- `PostgreSQLLoader`: Inserts papers with proper JSON serialization

**Usage**:
```bash
# Load and upload to database
python load_bibtex.py papers.bib

# Dry-run validation (no database upload)
python load_bibtex.py papers.bib --try --sample 50

# List papers without uploading
python load_bibtex.py papers.bib --list --sample 10

# Custom database
python load_bibtex.py papers.bib --db postgresql://user:pass@localhost/db

# Verbose output
python load_bibtex.py papers.bib -v
```

**Supported BibTeX sources**:
- ✅ Web of Science exports
- ✅ Scopus exports
- ✅ IEEE Xplore exports
- ✅ Mixed BibTeX files with any combination of sources

## 2. Stage 1: Keyword Screening

Coarse filter using keyword rules to remove obviously irrelevant papers.

**File**: `stage1_keyword_screening.py`

**Characteristics**:
- Precision: ~70% | Recall: ~95%
- Hard exclusions: papers matching disease/education/military keywords
- Required inclusions: papers with innovation/digital/supplier keywords
- Fast, deterministic results

**Output**: Papers marked `stage1_pass` or `stage1_fail`

## 3. Stage 2: Semantic Filtering

Semi-automated semantic analysis using embeddings to find papers similar to research question.

**File**: `stage2_semantic_screening.py`

**Characteristics**:
- Precision: ~85% | Recall: ~90%
- Embeddings-based similarity to research question
- Three-tier classification:
  - **INCLUDE**: similarity ≥ 0.65
  - **MANUAL REVIEW**: 0.55–0.65
  - **EXCLUDE**: < 0.55

**Output**: Papers marked `stage2_pass`, `stage2_review`, or `stage2_fail` with similarity scores

## 4. Multiple Review Passes

Review processes for filtering results across stages.

**Available Scripts**:
- `show_top_papers.py`: Display high-similarity papers for manual review
- `semantic_screening_utils.py`: Utilities for similarity analysis
- Manual review interface via dashboard

## 5. Dashboard

Visual monitoring of the entire screening pipeline.

**File**: `screening_dashboard.py`

**Features**:
- Real-time statistics for Stage 1 and Stage 2 results
- Similarity distribution analysis
- Processing timeline and metrics
- Recommendations for next actions
- Color-coded status indicators

**Usage**:
```bash
python screening_dashboard.py --db-url postgresql://user:pass@localhost/pdfdb
```

---

## Quick Start

```bash
# 1. Load papers
python load_bibtex.py --bibtex papers.bib

# 2. Run Stage 1
python stage1_keyword_screening.py

# 3. Run Stage 2
python stage2_semantic_screening.py

# 4. View results
python screening_dashboard.py

# 5. Show output
python show_top_papers.py -v
```

## Database Schema

Papers stored in `papers` table with:
- **Identifiers**: citekey, paper_type
- **Metadata**: title, authors, year, journal, volume, issue, pages, doi, publisher
- **Content**: abstract, keywords
- **Screening**: stage1_processed_at, screening_stage, semantic_similarity, final_decision

## Implementation Files

- `load_bibtex.py` - Core loading logic
- `stage1_keyword_screening.py` - Stage 1 implementation
- `stage2_semantic_screening.py` - Stage 2 implementation
- `screening_dashboard.py` - Dashboard interface
- `test_*.py` - Comprehensive test suite
