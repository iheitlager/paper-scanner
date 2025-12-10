# Quick Reference: BibTeX Type Mapping

## What's New

The BibTeX importer now automatically evaluates and populates the `paper_type` field for all imported papers.

## Quick Start

### Default Behavior (No Changes Needed!)

```python
papers = bibtex_file_to_papers("data/scopus.bib", source_type="scopus")
# paper.paper_type is now populated! ✓
```

### With Custom Configuration

```python
papers = bibtex_file_to_papers(
    "data/file.bib",
    type_mapping_config=load_type_mapping_config("custom_config.yaml")
)
```

## Configuration File

Located at: `etc/bibtex_type_mapping.yaml`

Contains mappings for 23+ BibTeX entry types to standardized paper types.

## Supported Paper Types

```
article              - Journal articles
conference_paper     - Conference proceedings
book                 - Full books
book_chapter         - Book chapters
thesis               - PhD/Master theses
technical_report     - Technical reports/standards
working_paper        - Working papers
preprint             - Preprints (arXiv)
patent               - Patents
other                - Miscellaneous
```

## Test Coverage

Run tests to verify:

```bash
pytest tests/unit/test_bibtex_paper_type.py -v
# 18 tests, all passing ✓
```

## Real Data Results

- **Scopus**: 18 articles + 1 conference
- **IEEE**: 18 conference + 1 article + 1 book chapter  
- **WoS**: 20 articles

All papers successfully typed! ✓

## Key Functions

| Function | Purpose |
|----------|---------|
| `load_type_mapping_config()` | Load YAML config with caching |
| `evaluate_paper_type()` | Evaluate type from BibTeX entry |
| `bibtex_file_to_papers()` | Import file with type evaluation |
| `bibtex_to_papers()` | Parse string with type evaluation |

## Configuration Format

```yaml
type_mappings:
  article:
    paper_type: "article"
    description: "Journal article"
    confidence: 0.95

source_overrides:
  scopus:
    article_type_field: "type"
    type_value_mappings:
      "Article": "article"

custom_mappings:
  my_type:
    paper_type: "article"
    confidence: 0.8
```

## Source-Specific Intelligence

- **Scopus**: Uses `type` field + Scopus-specific mappings
- **IEEE**: Uses `type` field + IEEE-specific mappings
- **Web of Science**: Uses `document_type` field

## Confidence Scores

- 0.95: Standard BibTeX types
- 0.90: Source-specific mappings
- 0.85: Custom mappings
- 0.75-0.80: Lower confidence types
- 0.5-0.60: Fallback heuristics

## Files

| File | Purpose |
|------|---------|
| `etc/bibtex_type_mapping.yaml` | Type mapping configuration |
| `docs/BIBTEX_TYPE_MAPPING.md` | Full documentation |
| `tests/unit/test_bibtex_paper_type.py` | Test suite (18 tests) |
| `BIBTEX_IMPLEMENTATION_SUMMARY.md` | Implementation details |

## Common Issues

**Papers not getting paper_type?**
- Check BibTeX has valid ENTRYTYPE
- Verify config is loaded (check logs)
- Try adding custom mapping

**Wrong type assigned?**
- Check source database type
- Look for `type` field in BibTeX entry
- Add custom mapping if needed

**Need custom mapping?**
- Create `custom_mapping.yaml`
- Add to `custom_mappings` section
- Pass to import function

## Documentation

- **Full Guide**: `docs/BIBTEX_TYPE_MAPPING.md`
- **Implementation**: `BIBTEX_IMPLEMENTATION_SUMMARY.md`
- **Examples**: See `tests/unit/test_bibtex_paper_type.py`

## Summary

✓ Automatic paper type evaluation
✓ Configurable via YAML
✓ Source-specific intelligence  
✓ 23+ BibTeX types supported
✓ 18 comprehensive tests
✓ Backward compatible
✓ Zero performance impact
