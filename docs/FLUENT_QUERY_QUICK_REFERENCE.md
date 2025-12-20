"""
Quick Reference: Fluent Query API for PapersDatabase

The PapersQuery fluent builder pattern enables chainable queries with
lazy evaluation for complex paper filtering, sorting, and limiting.

INSTALLATION
============
This is built into PapersDatabase via the query() method.
No additional imports needed beyond:
    from paper_scanner.core.database import PapersDatabase


BASIC USAGE
===========
db = PapersDatabase()  # ... load papers ...

# Simple filter
papers = db.query().filter_by_topic("AI").execute()

# Chained filters
papers = db.query().filter_by_year(2020, 2023).filter_by_topic("ML").execute()

# With sorting
papers = (db.query()
    .filter_by_topic("AI")
    .order_by_year(descending=True)
    .execute())

# With limit
papers = db.query().filter_by_topic("AI").top(10).execute()

# Terminal operations
first_paper = db.query().filter_by_topic("AI").first()
count = db.query().filter_by_topic("AI").count()


FILTER METHODS
==============

filter_by_topic(topic: str) -> PapersQuery
  Matches papers by keyword
  >>> papers = db.query().filter_by_topic("AI").execute()

filter_by_year(min_year: int, max_year: int = None) -> PapersQuery
  Filters papers by publication year range
  >>> papers = db.query().filter_by_year(2020, 2023).execute()
  >>> papers = db.query().filter_by_year(2020).execute()  # Single year

filter_by_author(author_name: str) -> PapersQuery
  Partial match on author name
  >>> papers = db.query().filter_by_author("Smith").execute()

filter_by_doi(doi: str) -> PapersQuery
  Match exact DOI (normalized)
  >>> papers = db.query().filter_by_doi("10.1234/example").execute()

grep(text: str) -> PapersQuery
  Full-text search in title and abstract
  >>> papers = db.query().grep("machine learning").execute()

filter(predicate: Callable[[Paper], bool]) -> PapersQuery
  Custom filter function
  >>> papers = db.query().filter(lambda p: p.year and p.year > 2020).execute()

exclude_duplicates() -> PapersQuery
  Only include primary papers (exclude duplicate_of)
  >>> papers = db.query().exclude_duplicates().execute()


SORT METHODS
============

order_by_year(descending: bool = True) -> PapersQuery
  Sort by publication year
  >>> papers = db.query().order_by_year(descending=True).execute()  # Newest first
  >>> papers = db.query().order_by_year(descending=False).execute()  # Oldest first

order_by_title(descending: bool = False) -> PapersQuery
  Sort alphabetically by title
  >>> papers = db.query().order_by_title(descending=False).execute()  # A-Z
  >>> papers = db.query().order_by_title(descending=True).execute()   # Z-A

order_by(key_func: Callable[[Paper], Any], descending: bool = False) -> PapersQuery
  Custom sort function
  >>> papers = db.query().order_by(lambda p: len(p.abstract or "")).execute()


LIMIT METHODS
=============

top(count: int) -> PapersQuery
  Limit results to N papers
  >>> papers = db.query().filter_by_topic("AI").top(10).execute()

limit(count: int) -> PapersQuery
  Alias for top()
  >>> papers = db.query().limit(5).execute()


TERMINAL OPERATIONS
====================

execute() -> List[Paper]
  Execute query and return all results
  >>> papers = db.query().filter_by_topic("AI").execute()

list() -> List[Paper]
  Alias for execute()
  >>> papers = db.query().filter_by_topic("AI").list()

first() -> Optional[Paper]
  Get first result or None
  >>> paper = db.query().filter_by_topic("AI").first()

count() -> int
  Count matching papers
  >>> count = db.query().filter_by_topic("AI").count()


COMPLEX EXAMPLES
================

# Find top 10 papers on AI from 2020-2023, sorted newest first
papers = (db.query()
    .filter_by_topic("AI")
    .filter_by_year(2020, 2023)
    .order_by_year(descending=True)
    .top(10)
    .execute())

# Search for "neural networks" in papers by author "Bengio"
papers = (db.query()
    .grep("neural networks")
    .filter_by_author("Bengio")
    .execute())

# Find and count unique papers (exclude duplicates) on climate ML
count = (db.query()
    .filter_by_topic("Climate")
    .filter_by_topic("ML")
    .exclude_duplicates()
    .count())

# Get single most recent paper on AI
paper = (db.query()
    .filter_by_topic("AI")
    .order_by_year(descending=True)
    .first())

# Complex custom filter: papers with long abstracts on ML
papers = (db.query()
    .filter_by_topic("ML")
    .filter(lambda p: p.abstract and len(p.abstract) > 500)
    .execute())

# Multi-topic search with year range and limit
papers = (db.query()
    .filter(lambda p: "AI" in (p.keywords or []) or "ML" in (p.keywords or []))
    .filter_by_year(2019, 2023)
    .order_by_year(descending=True)
    .top(20)
    .execute())
"""
