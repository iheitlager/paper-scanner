"""
Comprehensive citation handler tests.

Tests the complete citation workflow:
1. Manual handler caching citations from bibtex
2. Citation direction (forward/backward)
3. Citation validation and confidence
4. Handler chain integration
"""

import tempfile
from pathlib import Path

import pytest

from paper_scanner.core.models import Citation, CitationDirection, Paper
from paper_scanner.tools.fetchers.fetcher_handlers.bibtex_parser import BibtexParser
from paper_scanner.tools.fetchers.fetcher_handlers.manual_handler import ManualHandler


class TestCitationHandling:
    """Test citation handling in manual handler."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, temp_cache_dir):
        """Create manual handler with temp cache."""
        return ManualHandler(cache_dir=temp_cache_dir)

    @pytest.fixture
    def bibtex_with_citations(self, temp_cache_dir):
        """Create a bibtex file with citation data."""
        bibtex_content = """
@article{Smith2023,
  author = {Smith, John and Doe, Jane},
  title = {Example Paper with Citations},
  year = {2023},
  doi = {10.1109/example.2023.1234567},
  abstract = {This paper demonstrates citation handling},
  keywords = {citation, metadata, snowballing},
  
  cites = {10.1234/ref1, 10.1234/ref2, 10.1234/ref3},
  citedby = {10.1234/citing1, 10.1234/citing2},
  citedbycount = {2},
  lastchecked = {2025-12-24},
  studytype = {empirical_case_study},
  journal = {IEEE Transactions}
}
"""
        bibtex_file = temp_cache_dir / "citations_test.bib"
        bibtex_file.write_text(bibtex_content)
        return bibtex_file

    def test_bibtex_parsing_creates_backward_citations(self, bibtex_with_citations):
        """Test that bibtex cites field creates backward citations."""
        entries, skipped = BibtexParser.parse_file(bibtex_with_citations)
        
        assert len(entries) == 1
        assert len(skipped) == 0
        
        entry = entries[0]
        assert "citations" in entry
        citations = entry["citations"]
        
        # Should have 5 citations total: 3 backward + 2 forward
        assert len(citations) == 5
        
        # Find backward citations
        backward = [c for c in citations if isinstance(c, dict) and c.get("direction") == CitationDirection.BACKWARD]
        assert len(backward) == 3
        assert all(c["doi"] in ["10.1234/ref1", "10.1234/ref2", "10.1234/ref3"] for c in backward)

    def test_bibtex_parsing_creates_forward_citations(self, bibtex_with_citations):
        """Test that bibtex citedby field creates forward citations."""
        entries, skipped = BibtexParser.parse_file(bibtex_with_citations)
        
        entry = entries[0]
        citations = entry["citations"]
        
        # Find forward citations
        forward = [c for c in citations if isinstance(c, dict) and c.get("direction") == CitationDirection.FORWARD]
        assert len(forward) == 2
        assert all(c["doi"] in ["10.1234/citing1", "10.1234/citing2"] for c in forward)

    def test_citation_metadata_set_correctly(self, bibtex_with_citations):
        """Test that citations have correct metadata (manual, confidence=1.0)."""
        entries, _ = BibtexParser.parse_file(bibtex_with_citations)
        entry = entries[0]
        citations = entry["citations"]
        
        # All should be manual with max confidence
        for citation in citations:
            assert citation["extraction_method"] == "manual"
            assert citation["confidence"] == 1.0

    def test_manual_handler_caches_citations(self, handler, bibtex_with_citations):
        """Test that manual handler can cache parsed citations."""
        entries, _ = BibtexParser.parse_file(bibtex_with_citations)
        entry = entries[0]
        
        # Cache the entry
        doi = entry["doi"]
        handler._jsoncache.set(doi, entry)
        
        # Retrieve and verify
        api_data, from_api = handler.fetch_metadata(doi)
        
        assert api_data is not None
        assert "citations" in api_data
        assert len(api_data["citations"]) == 5

    def test_citations_preserved_in_paper_model(self, handler, bibtex_with_citations):
        """Test that citations are properly preserved when creating Paper model."""
        entries, _ = BibtexParser.parse_file(bibtex_with_citations)
        entry = entries[0]
        doi = entry["doi"]
        
        # Cache and fetch via handler
        handler._jsoncache.set(doi, entry)
        paper, _ = handler.fetch_paper(doi)
        
        assert paper is not None
        assert len(paper.citations) == 5
        
        # Verify citation types
        backward_cits = [c for c in paper.citations if c.direction == CitationDirection.BACKWARD]
        forward_cits = [c for c in paper.citations if c.direction == CitationDirection.FORWARD]
        
        assert len(backward_cits) == 3
        assert len(forward_cits) == 2

    def test_citation_direction_values(self, bibtex_with_citations):
        """Test that citation directions are valid enum values."""
        entries, _ = BibtexParser.parse_file(bibtex_with_citations)
        entry = entries[0]
        citations = entry["citations"]
        
        valid_directions = {CitationDirection.BACKWARD, CitationDirection.FORWARD}
        
        for citation in citations:
            assert citation["direction"] in valid_directions

    def test_citedbycount_calculated_correctly(self, bibtex_with_citations):
        """Test that citedbycount is set correctly."""
        entries, _ = BibtexParser.parse_file(bibtex_with_citations)
        entry = entries[0]
        
        # Should be 2 (from citedby field length)
        assert entry["citedbycount"] == 2

    def test_multiple_papers_with_cross_references(self, handler, temp_cache_dir):
        """Test that multiple papers can reference each other."""
        # Create two papers that cite each other
        paper1 = {
            "doi": "10.1234/paper1",
            "title": "Paper 1",
            "abstract": "First paper",
            "authors": ["Author One"],
            "year": 2023,
            "keywords": ["test"],
            "cites": ["10.1234/paper2"],
            "citedby": ["10.1234/paper2"],
            "citations": [
                {
                    "doi": "10.1234/paper2",
                    "direction": CitationDirection.BACKWARD,
                    "extraction_method": "manual",
                    "confidence": 1.0,
                }
            ],
        }
        
        paper2 = {
            "doi": "10.1234/paper2",
            "title": "Paper 2",
            "abstract": "Second paper",
            "authors": ["Author Two"],
            "year": 2023,
            "keywords": ["test"],
            "cites": ["10.1234/paper1"],
            "citedby": ["10.1234/paper1"],
            "citations": [
                {
                    "doi": "10.1234/paper1",
                    "direction": CitationDirection.BACKWARD,
                    "extraction_method": "manual",
                    "confidence": 1.0,
                }
            ],
        }
        
        # Cache both
        handler._jsoncache.set(paper1["doi"], paper1)
        handler._jsoncache.set(paper2["doi"], paper2)
        
        # Fetch both and verify cross-references
        p1, _ = handler.fetch_paper("10.1234/paper1")
        p2, _ = handler.fetch_paper("10.1234/paper2")
        
        assert p1 is not None
        assert p2 is not None
        
        # Paper1 cites Paper2 (backward citation)
        p1_backward = [c for c in p1.citations if c.direction == CitationDirection.BACKWARD]
        assert len(p1_backward) == 1
        assert p1_backward[0].doi == "10.1234/paper2"
        
        # Paper2 cites Paper1 (backward citation)
        p2_backward = [c for c in p2.citations if c.direction == CitationDirection.BACKWARD]
        assert len(p2_backward) == 1
        assert p2_backward[0].doi == "10.1234/paper1"

    def test_snowballing_scenario(self, handler):
        """Test realistic snowballing scenario with seed paper and forward citations."""
        # Seed paper
        seed = {
            "doi": "10.1234/seed",
            "title": "Seed Paper",
            "abstract": "The seed",
            "authors": ["Seed Author"],
            "year": 2020,
            "keywords": ["seed"],
            "citedby": ["10.1234/citing1", "10.1234/citing2", "10.1234/citing3"],
            "citations": [
                {
                    "doi": f"10.1234/citing{i}",
                    "direction": CitationDirection.FORWARD,
                    "extraction_method": "manual",
                    "confidence": 1.0,
                }
                for i in range(1, 4)
            ],
        }
        
        handler._jsoncache.set(seed["doi"], seed)
        paper, _ = handler.fetch_paper(seed["doi"])
        
        assert paper is not None
        # 3 forward citations (papers that cite this one)
        forward_cits = [c for c in paper.citations if c.direction == CitationDirection.FORWARD]
        assert len(forward_cits) == 3
        
        # Can extract DOIs for snowballing
        snowball_dois = [c.doi for c in forward_cits]
        assert len(snowball_dois) == 3


class TestCitationEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, temp_cache_dir):
        """Create manual handler with temp cache."""
        return ManualHandler(cache_dir=temp_cache_dir)

    def test_empty_citations_field(self, handler):
        """Test handling of empty citations field."""
        data = {
            "doi": "10.1234/test",
            "title": "Test",
            "abstract": "Test",
            "authors": ["Test Author"],
            "year": 2023,
            "keywords": [],
            "citations": [],
        }
        
        citations = handler._extract_citations(data)
        assert citations == []

    def test_missing_citations_field(self, handler):
        """Test handling of missing citations field."""
        data = {
            "doi": "10.1234/test",
            "title": "Test",
            "abstract": "Test",
            "authors": ["Test Author"],
            "year": 2023,
            "keywords": [],
        }
        
        citations = handler._extract_citations(data)
        assert citations == []

    def test_malformed_citations_not_list(self, handler):
        """Test handling of malformed citations (not a list)."""
        data = {
            "doi": "10.1234/test",
            "title": "Test",
            "citations": "not a list",
        }
        
        citations = handler._extract_citations(data)
        assert citations == []

    def test_citation_without_doi(self, handler):
        """Test handling of citation without DOI."""
        data = {
            "doi": "10.1234/test",
            "title": "Test",
            "citations": [
                {
                    "title": "Citation without DOI",
                    "direction": CitationDirection.BACKWARD,
                    "extraction_method": "manual",
                }
            ],
        }
        
        citations = handler._extract_citations(data)
        assert len(citations) == 1
        assert citations[0].doi is None
