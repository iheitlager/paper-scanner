"""
Fetchers for retrieving bibliographic metadata from various sources.
"""

from paper_scanner.tools.fetchers.crossref_fetcher import (
    CrossrefReferenceFetcher,
    PoliteCrossrefClient,
    CROSSREF_EMAIL,
    CROSSREF_API_BASE,
)

__all__ = [
    'CrossrefReferenceFetcher',
    'PoliteCrossrefClient',
    'CROSSREF_EMAIL',
    'CROSSREF_API_BASE',
]
