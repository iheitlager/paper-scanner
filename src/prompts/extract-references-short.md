Extract bibliographic references from the paper's reference list. Format as JSON with references array.

For each reference, extract: citekey (FirstAuthorYear format), type (journal_article|book|conference_paper|report|thesis|website|other), authors array, year, title, journal/source, DOI, URL.

JSON structure:
```json
{
  "references": [
    {
      "citekey": "FirstAuthorYear",
      "type": "journal_article",
      "authors": [{"name": "Last, First"}],
      "year": "YYYY",
      "title": "string",
      "source": "Journal Name",
      "volume": "X",
      "issue": "X",
      "pages": "start-end",
      "doi": "10.xxxx/xxxxx",
      "url": "https://...",
      "publisher": "string"
    }
  ]
}
```

Rules: Include all fields for each reference. Use null for missing data. Process ALL references in order. For duplicate author-year pairs, add letter suffix (e.g., Smith2020a, Smith2020b).