### 8. Citation Key Propagation

**Generation strategy:**
1. Try: `{first_author_family_name}_{year}` (e.g., "smith_2020")
2. If no author: `{first_word_of_title}_{year}` (e.g., "innovation_2020")
3. If no year: Use DOI slug (e.g., "10-1287-isre")
4. If nothing: Use random UUID suffix

**When key needs re-generation:**
- Paper created from API with incomplete metadata
- Author list changes during metadata enrichment
- Year discovered/corrected
- → Always regenerate if author or year changes

**Key tracking in Discovery:**
```python
class Discovery(BaseModel):
    cite_key_generated_from: Optional[str]  # "author_year", "title_year", "doi", "uuid"
    cite_key_original: Optional[str]  # For merging/deduplication
```