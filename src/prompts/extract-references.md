You MUST output ONLY valid JSON with no preamble, explanation, or follow-up questions. Output nothing else.

Extract ALL bibliographic references as JSON array.

For each reference extract:
- citekey: FirstAuthorYear format (add a,b,c for duplicates)
- type: journal_article|book|book_chapter|conference_paper|working_paper|report|website|other
- authors: [{last_name, first_name, initials}]
- year: "YYYY"
- title: "string"
- source: {name, volume, issue, pages, publisher, location, editors}
- identifiers: {doi, url}

JSON structure:
{
  "total": 0,
  "references": [{
    "id": 1,
    "citekey": "Author_2020",
    "type": "journal_article",
    "authors": [{"last_name": "Smith", "first_name": "John", "initials": "J."}],
    "year": "2020",
    "title": "Title here",
    "source": {
      "name": "Journal Name",
      "volume": "10",
      "issue": "2",
      "pages": "100-120"
    },
    "identifiers": {
      "doi": "10.xxxx/xxxxx",
      "url": null
    }
  }]
}

Rules: Process in order. Extract ALL authors. Clean DOIs (remove https://doi.org/). Use null for missing data. Include all references. Do not add explanations or ask questions. Output only the JSON object.
