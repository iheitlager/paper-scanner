"""
Tests for Crossref handler cache reading and field extraction.

Validates that cached Crossref API responses can be properly read and
fields extracted into Paper models.
"""

import json
import pytest
from pathlib import Path
from typing import Optional, Dict, Any

from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefMetadataFetcher,
)
from paper_scanner.core.models import Paper


class TestCrossrefCacheReading:
    """Test Crossref cache reading and field extraction."""

    @pytest.fixture
    def crossref_fetcher(self, tmp_path) -> CrossrefMetadataFetcher:
        """Create a Crossref fetcher with temp cache directory."""
        return CrossrefMetadataFetcher(cache_dir=tmp_path)

    @pytest.fixture
    def crossref_api_data(self) -> Dict[str, Any]:
        """Load the Crossref API response from test data."""
        test_file = Path(__file__).parent.parent.parent / "data" / "06faa12bd3241050da0cc16ddda711af.json"
        with open(test_file, "r") as f:
            response = json.load(f)
        # Extract the "message" field (actual API response)
        return response["message"]

    def test_load_from_cache_valid_file(self, crossref_fetcher, crossref_api_data, tmp_path):
        """Test loading a valid cached API response from file."""
        doi = "10.1186/s13731-024-00404-5"
        # Save test data to cache using new API
        success = crossref_fetcher._cache.set(doi, crossref_api_data)
        assert success

        # Load from cache
        loaded_data = crossref_fetcher._cache.get(doi)

        # Verify it loaded correctly
        assert loaded_data is not None
        assert loaded_data["DOI"] == "10.1186/s13731-024-00404-5"
        assert "message-type" not in loaded_data  # Should be the inner message, not the wrapper

    def test_load_from_cache_missing_file(self, crossref_fetcher):
        """Test loading from a non-existent cache entry."""
        loaded_data = crossref_fetcher._cache.get("non.existent.doi")
        assert loaded_data is None

    def test_extract_abstract_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting abstract from cached API response."""
        abstract = crossref_fetcher._extract_abstract(crossref_api_data)

        assert abstract is not None
        assert "Digital transformation" in abstract
        assert len(abstract) > 100

    def test_extract_title_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting title from cached API response."""
        # Title is extracted in _translate_to_paper
        title = crossref_api_data.get("title", "")
        if isinstance(title, list):
            title = title[0] if title else ""

        assert title is not None
        assert "Digital transformation" in title

    def test_extract_authors_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting authors from cached API response."""
        authors = crossref_fetcher._extract_authors(crossref_api_data)

        assert len(authors) >= 2
        assert authors[0].family_name == "Hoessler"
        assert authors[1].family_name == "Carbon"
        # Check full names are constructed
        assert "Sabrina" in authors[0].full_name
        assert "Claus-Christian" in authors[1].full_name

    def test_extract_keywords_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting keywords (subjects) from cached API response."""
        keywords = crossref_fetcher._extract_keywords(crossref_api_data)

        # Crossref may not have keywords for this paper
        # Keywords are extracted from 'subject' field which might be empty
        assert isinstance(keywords, list)

    def test_extract_paper_type_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting paper type from cached API response."""
        paper_type = crossref_fetcher._extract_paper_type(crossref_api_data)

        # This is a journal article
        assert paper_type == "journal_article"

    def test_extract_doi_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting DOI from cached API response."""
        doi = crossref_api_data.get("DOI")
        assert doi == "10.1186/s13731-024-00404-5"

    def test_extract_publication_date_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting publication date from cached API response."""
        published = crossref_api_data.get("published-online")
        assert published is not None
        assert published["date-parts"][0] == [2024, 7, 29]

    def test_extract_year_from_cached_data(self, crossref_fetcher, crossref_api_data):
        """Test extracting year from cached API response."""
        # Year might be extracted from published-online or created
        published = crossref_api_data.get("published-online")
        year = published["date-parts"][0][0] if published else None
        assert year == 2024

    def test_translate_cached_data_to_paper(self, crossref_fetcher, crossref_api_data):
        """Test full translation of cached data to Paper model."""
        doi = "10.1186/s13731-024-00404-5"
        paper = crossref_fetcher._translate_to_paper(doi, crossref_api_data)

        # Verify critical fields
        assert paper.doi == doi
        assert paper.title is not None
        assert "Digital transformation" in paper.title
        assert paper.abstract is not None
        assert len(paper.authors) >= 2
        assert paper.authors[0].family_name == "Hoessler"

    def test_get_cache_file_path(self, crossref_fetcher):
        """Test cache file path generation from DOI."""
        doi = "10.1186/s13731-024-00404-5"
        cache_file = crossref_fetcher._cache._get_cache_path(doi)

        # Should be in cache_dir
        assert cache_file.parent == crossref_fetcher._cache.cache_dir
        # Should be an MD5 hash
        assert cache_file.name.endswith(".json")
        assert len(cache_file.name) == 37  # 32 chars MD5 + 5 chars ".json"

    def test_get_cache_file_path_consistency(self, crossref_fetcher):
        """Test that same DOI always produces same cache file path."""
        doi = "10.1186/s13731-024-00404-5"
        path1 = crossref_fetcher._cache._get_cache_path(doi)
        path2 = crossref_fetcher._cache._get_cache_path(doi)

        assert path1 == path2

    def test_get_cache_file_path_normalized_doi(self, crossref_fetcher):
        """Test that different DOI formats normalize to same cache file."""
        # Different formats of same DOI
        doi1 = "10.1186/s13731-024-00404-5"
        doi2 = "DOI:10.1186/s13731-024-00404-5"
        doi3 = "https://doi.org/10.1186/s13731-024-00404-5"
        doi4 = "10.1186/S13731-024-00404-5"  # uppercase

        path1 = crossref_fetcher._cache._get_cache_path(doi1)
        path2 = crossref_fetcher._cache._get_cache_path(doi2)
        path3 = crossref_fetcher._cache._get_cache_path(doi3)
        path4 = crossref_fetcher._cache._get_cache_path(doi4)

        assert path1 == path2
        assert path1 == path3
        assert path1 == path4

    def test_fetch_and_parse_with_cached_data(self, crossref_fetcher, crossref_api_data, tmp_path):
        """Test fetching with cached data (cache hit scenario)."""
        doi = "10.1186/s13731-024-00404-5"
        
        # Pre-populate cache
        success = crossref_fetcher._cache.set(doi, crossref_api_data)
        assert success

        # Now fetch (should hit cache)
        paper, cache_hit = crossref_fetcher.fetch_and_parse(doi)

        assert cache_hit is True
        assert paper is not None
        assert paper.doi == doi
        assert paper.title is not None

    def test_save_and_load_cache_roundtrip(self, crossref_fetcher, crossref_api_data, tmp_path):
        """Test saving and loading cache maintains data integrity."""
        doi = "roundtrip_test_doi"

        # Save
        success = crossref_fetcher._cache.set(doi, crossref_api_data)
        assert success

        # Load
        loaded_data = crossref_fetcher._cache.get(doi)

        # Verify key fields preserved
        assert loaded_data["DOI"] == crossref_api_data["DOI"]
        assert loaded_data["title"] == crossref_api_data["title"]
        assert len(loaded_data["author"]) == len(crossref_api_data["author"])

    def test_cache_handles_references(self, crossref_fetcher, crossref_api_data):
        """Test that cached data with references is handled correctly."""
        # The test data includes a large references array
        assert "reference" in crossref_api_data
        assert len(crossref_api_data["reference"]) > 0

        # Should not cause issues when extracting
        paper = crossref_fetcher._translate_to_paper("10.1186/s13731-024-00404-5", crossref_api_data)
        assert paper is not None

    def test_cache_handles_complex_nested_data(self, crossref_fetcher, crossref_api_data):
        """Test that cache handles complex nested structures."""
        # The test data has nested license info, funder, etc.
        assert "license" in crossref_api_data
        assert "funder" in crossref_api_data
        assert "content-domain" in crossref_api_data

        # Should translate without errors
        paper = crossref_fetcher._translate_to_paper("10.1186/s13731-024-00404-5", crossref_api_data)
        assert paper is not None
        assert paper.doi == "10.1186/s13731-024-00404-5"
        assert paper.title == "Digital transformation in incumbent companies: a qualitative study on exploration and exploitation activities in innovation"  # noqa    
        assert len(paper.authors) >= 2
        assert len(paper.keywords) >= 0
        assert len(paper.abstract) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
