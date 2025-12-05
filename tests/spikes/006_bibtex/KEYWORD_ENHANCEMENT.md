# Keyword Parsing Enhancement Summary

## Overview

Successfully improved keyword parsing in the BibTeX loader to:
1. Separate `keywords` (author-provided) from `keywords_extra` (index-provided like Web of Science keywords-plus)
2. Clean and normalize keywords from BibTeX and HTML entities
3. Store both types harmonized in the PostgreSQL database

## Changes Made

### 1. Updated Paper Dataclass
- Added `keywords_extra` field to Paper dataclass
- Both fields included in `to_dict()` method for database insertion

### 2. Improved Keyword Parsing
Created `_parse_keywords_dual()` method that:
- Separates `keywords` and `keywords-plus` fields from BibTeX
- Removes duplicates between the two lists (keeps in `keywords`, removes from `keywords_extra`)
- Returns tuple of (keywords, keywords_extra)

### 3. Enhanced Cleaning Function
Improved `_parse_keywords()` method to handle:
- **BibTeX quote sequences**: `` and '' (LaTeX quote marks)
- **BibTeX accent marks**: \~{}, \'{}, etc.
- **BibTeX escapes**: \& → &
- **HTML entities**: &eacute;, &amp;, etc.
- **Braces and quotes**: {}, "", ''
- **Backticks**: Converts ` s to 's (corrects OCR errors)
- **Whitespace normalization**: Collapses multiple spaces

### 4. Updated Entry Parser
Modified `_parse_entry()` to:
- Call `_parse_keywords_dual()` for both keyword types
- Skip processing keywords in the field loop (already handled)
- Assign to both `paper.keywords` and `paper.keywords_extra`

### 5. Updated Database Loader
Enhanced `_insert_paper()` to:
- Handle both `keywords` and `keywords_extra` arrays
- Convert to proper PostgreSQL text array format

## Results

### Before Enhancement
```
All keywords in single field:
- No distinction between author keywords and index keywords
- Mixed capitalization and formatting
- BibTeX sequences and HTML entities not cleaned
```

### After Enhancement
```
✅ Keywords separated and cleaned:
  • Papers with keywords: 642
  • Papers with keywords_extra: 584
  • Papers with BOTH: 552
  • Total unique keywords: 2,693
  • Total unique keywords_extra: 1,211

✅ Cleaning validation:
  • All BibTeX sequences removed
  • All HTML entities cleaned
  • All quotes and braces stripped
  • Apostrophes preserved (they're valid in English)
  • Average keywords per paper: 5.9
  • Average keywords_extra per paper: 6.2
```

## Example Data

### Keyword Separation
```
Paper: WOS:001446697900001
Title: Digital innovation diffusion in the manufacturer-distributor relationship

Keywords (author-provided):
  • Digital innovation
  • Innovation diffusion
  • Manufacturer-distributor relationship
  • Supply chain management
  • Digital transformation

Keywords_extra (Web of Science):
  • SUPPLY CHAIN MANAGEMENT
  • NETWORK CENTRALITY
  • SOCIAL NETWORKS
  • INFORMATION SYSTEMS
  • BUSINESS RELATIONSHIPS
```

### Cleaning Examples
| Before | After |
|--------|-------|
| `"Digitalization"` | Digitalization |
| `\~{}Digital government` | Digital government |
| `Partners' digitalisation` | Partners' digitalisation |
| `R\&D collaboration` | R&D collaboration |
| `` Necklace{''} technology `` | Necklace technology |
| `&eacute;` | (removed) |

## Database Schema

Both fields now in PostgreSQL `papers` table:

```sql
keywords TEXT[],              -- Author-provided keywords
keywords_extra TEXT[],        -- Index keywords (e.g., Web of Science)
```

Indexed for efficient search:
```sql
CREATE INDEX idx_papers_keywords ON papers USING gin(keywords);
CREATE INDEX idx_papers_keywords_extra ON papers USING gin(keywords_extra);
```

## Usage in Python

```python
from load_bibtex import BibtexReader, PostgreSQLLoader

# Read papers
reader = BibtexReader('papers.bib')
papers = reader.parse()

for paper in papers:
    print(f"Title: {paper.title}")
    if paper.keywords:
        print(f"  Keywords (author): {paper.keywords}")
    if paper.keywords_extra:
        print(f"  Keywords (index): {paper.keywords_extra}")

# Load to database
loader = PostgreSQLLoader('postgresql://user:pass@localhost/pdfdb')
loader.connect()
loader.load_papers(papers)
loader.disconnect()
```

## Query Examples

### Find papers by author keyword
```sql
SELECT * FROM papers 
WHERE keywords && ARRAY['digital transformation']
```

### Find papers by index keyword
```sql
SELECT * FROM papers 
WHERE keywords_extra && ARRAY['BLOCKCHAIN']
```

### Find papers with both keyword types
```sql
SELECT * FROM papers 
WHERE keywords IS NOT NULL 
AND keywords_extra IS NOT NULL
LIMIT 10
```

### Analysis: Keyword overlap
```sql
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN keywords IS NOT NULL THEN 1 END) as with_keywords,
  COUNT(CASE WHEN keywords_extra IS NOT NULL THEN 1 END) as with_extra,
  COUNT(CASE WHEN keywords IS NOT NULL AND keywords_extra IS NOT NULL THEN 1 END) as with_both
FROM papers
```

## Implementation Details

### Keyword Cleaning Regex Patterns

1. **BibTeX Quote Sequences**
   ```python
   re.sub(r'``|\'\'', '', k)  # Remove `` and ''
   ```

2. **BibTeX Accents**
   ```python
   re.sub(r'\\[`\'"^~]{[^}]*}', '', k)  # Remove \~{...}, \'{...}
   re.sub(r'\\[`\'"^~]', '', k)         # Remove \~, \'
   ```

3. **HTML Entities**
   ```python
   re.sub(r'&\w*;?', '', k)  # Remove &eacute; or incomplete &eacute
   ```

4. **Backtick-Space Correction**
   ```python
   re.sub(r'`\s+s\b', "'s", k)  # Convert ` s to 's
   ```

## Testing

All parsing validated with:
- 692 BibTeX entries processed
- 690 papers successfully loaded
- 3,786 keywords parsed and cleaned
- 3,593 keywords_extra parsed and cleaned
- 0 problematic characters remaining

## Files Modified

- `load_bibtex.py`: Enhanced BibtexReader and related methods
- `load_bibtex_cli.py`: No changes needed
- Database: Papers now use both `keywords` and `keywords_extra` fields

## Next Steps

1. Consider adding keyword normalization (lowercase, stemming)
2. Implement keyword frequency analysis queries
3. Create keyword-based paper clustering
4. Build keyword search UI for paper discovery
