"""
Unit tests for the expansion step - backward snowballing

Tests cover:
- CitationsDatabase operations
- Citation extraction from papers
- Paper fetching and addition
- Backward snowballing iteration logic
- Statistics tracking
- Saturation detection
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from paper_scanner.core.models import Paper, Citation, Author, Discovery
from paper_scanner.core.database import PapersDatabase, CitationsDatabase
from paper_scanner.core.enum import DiscoveryMethod
from paper_scanner.steps.expansion import (
    ExpansionStatistics,
    validate,
    _extract_citations_from_paper,
    _fetch_and_add_paper,
    _extract_year,
    execute_backward_snowballing,
    execute,
)


# ============================================================================
# CITATIONS DATABASE TESTS
# ============================================================================

class TestCitationsDatabase:
    """Test CitationsDatabase class"""
    
    def test_init(self):
        """Test database initialization"""
        db = CitationsDatabase()
        assert db.count() == 0
        assert len(db.all()) == 0
        assert db.get_stats()["total_citations"] == 0
    
    def test_add_citation(self):
        """Test adding a single citation"""
        db = CitationsDatabase()
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        
        db.add(citation)
        
        assert db.count() == 1
        assert db.get_by_id(citation.id) is citation
    
    def test_add_duplicate_id_raises_error(self):
        """Test that adding citation with duplicate ID raises error"""
        db = CitationsDatabase()
        citation = Citation(
            id="same_id",
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        
        db.add(citation)
        
        # Try to add another citation with same ID
        citation2 = Citation(
            id="same_id",
            doi="10.1234/test2",
            title="Test Paper 2",
            extraction_method="crossref",
        )
        
        with pytest.raises(ValueError, match="already exists"):
            db.add(citation2)
    
    def test_get_by_doi(self):
        """Test getting citations by DOI"""
        db = CitationsDatabase()
        citation1 = Citation(
            doi="10.1234/test",
            title="Test Paper 1",
            extraction_method="crossref",
        )
        citation2 = Citation(
            doi="10.1234/test",
            title="Test Paper 1 Duplicate",
            extraction_method="crossref",
        )
        citation3 = Citation(
            doi="10.5678/other",
            title="Other Paper",
            extraction_method="crossref",
        )
        
        db.add_many([citation1, citation2, citation3])
        
        # Get by DOI (normalized)
        results = db.get_by_doi("10.1234/TEST")
        assert len(results) == 2
        assert citation1 in results
        assert citation2 in results
    
    def test_update_citation(self):
        """Test updating a citation"""
        db = CitationsDatabase()
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        db.add(citation)
        
        # Update citation
        citation.title = "Updated Title"
        db.update(citation)
        
        updated = db.get_by_id(citation.id)
        assert updated.title == "Updated Title"
    
    def test_delete_citation(self):
        """Test deleting a citation"""
        db = CitationsDatabase()
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        db.add(citation)
        
        deleted = db.delete_by_id(citation.id)
        assert deleted is True
        assert db.count() == 0
        assert db.get_by_id(citation.id) is None
    
    def test_exists_by_doi(self):
        """Test checking if DOI exists"""
        db = CitationsDatabase()
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        db.add(citation)
        
        assert db.exists_by_doi("10.1234/test") is True
        assert db.exists_by_doi("10.1234/test") is True  # Normalized
        assert db.exists_by_doi("10.9999/none") is False
    
    def test_clear(self):
        """Test clearing database"""
        db = CitationsDatabase()
        citations = [
            Citation(doi=f"10.{i}/test", title=f"Paper {i}", extraction_method="crossref")
            for i in range(3)
        ]
        db.add_many(citations)
        
        assert db.count() == 3
        
        db.clear()
        
        assert db.count() == 0
        assert len(db.all()) == 0
    
    def test_get_stats(self):
        """Test statistics generation"""
        db = CitationsDatabase()
        
        # Add citations
        citations = [
            Citation(doi="10.1/test", title="Paper 1", extraction_method="crossref"),
            Citation(doi="10.2/test", title="Paper 2", extraction_method="crossref"),
            Citation(doi=None, title="Paper 3", extraction_method="manual"),  # No DOI
        ]
        db.add_many(citations)
        
        # Resolve one
        citations[0].resolved_paper = Mock(spec=Paper)
        db.update(citations[0])
        
        stats = db.get_stats()
        
        assert stats["total_citations"] == 3
        assert stats["citations_with_doi"] == 2
        assert stats["resolved_citations"] == 1
        assert stats["unresolved_citations"] == 2


# ============================================================================
# EXPANSION STATISTICS TESTS
# ============================================================================

class TestExpansionStatistics:
    """Test ExpansionStatistics class"""
    
    def test_init(self):
        """Test statistics initialization"""
        stats = ExpansionStatistics()
        
        assert stats.papers_expanded == 0
        assert stats.citations_found == 0
        assert stats.new_papers_added == 0
    
    def test_duration_seconds(self):
        """Test duration calculation"""
        import time
        stats = ExpansionStatistics()
        time.sleep(0.1)
        
        duration = stats.duration_seconds()
        assert duration >= 0.1
    
    def test_to_dict(self):
        """Test converting statistics to dictionary"""
        stats = ExpansionStatistics()
        stats.papers_expanded = 5
        stats.citations_found = 50
        stats.new_papers_added = 10
        
        result = stats.to_dict()
        
        assert result["papers_expanded"] == 5
        assert result["citations_found"] == 50
        assert result["new_papers_added"] == 10
        assert "duration_seconds" in result


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidation:
    """Test configuration validation"""
    
    def test_valid_config(self):
        """Test validation of valid configuration"""
        config = {
            "expansion": {
                "backward": {
                    "extraction_methods": ["crossref"],
                }
            }
        }
        
        is_valid, errors = validate(config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_invalid_extraction_methods_type(self):
        """Test validation with invalid extraction_methods type"""
        config = {
            "expansion": {
                "backward": {
                    "extraction_methods": "crossref",  # Should be list
                }
            }
        }
        
        is_valid, errors = validate(config)
        
        assert is_valid is False
        assert any("extraction_methods" in e for e in errors)
    
    def test_missing_crossref_method(self):
        """Test validation when crossref not in methods"""
        config = {
            "expansion": {
                "backward": {
                    "extraction_methods": ["grobid", "llm_fallback"],
                }
            }
        }
        
        is_valid, errors = validate(config)
        
        assert is_valid is False
        assert any("crossref" in e for e in errors)


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

class TestExtractYear:
    """Test year extraction from Crossref metadata"""
    
    def test_extract_year_from_published_print(self):
        """Test extracting year from published-print field"""
        message = {
            "published-print": {
                "date-parts": [[2023, 5, 15]]
            }
        }
        
        year = _extract_year(message)
        
        assert year == 2023
    
    def test_extract_year_from_published_online(self):
        """Test extracting year from published-online field"""
        message = {
            "published-online": {
                "date-parts": [[2023, 6, 1]]
            }
        }
        
        year = _extract_year(message)
        
        assert year == 2023
    
    def test_extract_year_invalid_data(self):
        """Test extracting year with invalid data"""
        message = {
            "published-print": {
                "date-parts": [[]]
            }
        }
        
        year = _extract_year(message)
        
        assert year is None


# ============================================================================
# CITATION EXTRACTION TESTS
# ============================================================================

class TestExtractCitationsFromPaper:
    """Test citation extraction from papers"""
    
    def test_extract_citations_with_doi(self):
        """Test extracting citations when paper has DOI"""
        paper = Paper(
            cite_key="test_paper",
            title="Test Paper",
            doi="10.1234/test",
        )
        
        mock_fetcher = Mock()
        mock_fetcher.fetch_references_for_doi.return_value = {
            "references": [
                {
                    "DOI": "10.5678/ref1",
                    "article-title": "Reference 1",
                    "author": "Smith, J.",
                    "year": 2020,
                    "journal-title": "Journal 1",
                },
                {
                    "DOI": "10.9999/ref2",
                    "article-title": "Reference 2",
                    "year": 2021,
                },
            ]
        }
        
        citations = _extract_citations_from_paper(paper, mock_fetcher)
        
        assert len(citations) == 2
        assert citations[0].doi == "10.5678/ref1"
        assert citations[0].title == "Reference 1"
        assert citations[0].year == 2020
        assert citations[1].doi == "10.9999/ref2"
    
    def test_extract_citations_without_doi(self):
        """Test extracting citations when paper has no DOI"""
        paper = Paper(
            cite_key="test_paper",
            title="Test Paper",
            doi=None,
        )
        
        mock_fetcher = Mock()
        
        citations = _extract_citations_from_paper(paper, mock_fetcher)
        
        assert len(citations) == 0
        mock_fetcher.fetch_references_for_doi.assert_not_called()
    
    def test_extract_citations_fetch_fails(self):
        """Test when fetching references fails"""
        paper = Paper(
            cite_key="test_paper",
            title="Test Paper",
            doi="10.1234/test",
        )
        
        mock_fetcher = Mock()
        mock_fetcher.fetch_references_for_doi.return_value = None
        
        citations = _extract_citations_from_paper(paper, mock_fetcher)
        
        assert len(citations) == 0


# ============================================================================
# PAPER FETCHING AND ADDITION TESTS
# ============================================================================

class TestFetchAndAddPaper:
    """Test fetching and adding papers from citations"""
    
    def test_fetch_and_add_new_paper(self):
        """Test fetching and adding a new paper from citation"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        citations_db.add(citation)
        
        mock_fetcher = Mock()
        mock_fetcher.polite_client.get_work.return_value = {
            "message": {
                "title": ["New Test Paper"],
                "published-print": {
                    "date-parts": [[2023, 5, 15]]
                },
                "container-title": ["Test Journal"],
                "author": [
                    {"given": "John", "family": "Doe"},
                ],
            }
        }
        
        stats = ExpansionStatistics()
        
        result = _fetch_and_add_paper(
            citation,
            papers_db,
            citations_db,
            mock_fetcher,
            stats=stats,
        )
        
        assert result is not None
        assert result.doi == "10.1234/test"
        assert result.title == "New Test Paper"
        assert result.year == 2023
        assert len(result.authors) == 1
        assert result.authors[0].family_name == "Doe"
        assert result.discovery.iteration == 0  # Default iteration value
        assert result.discovery.method == DiscoveryMethod.BACKWARD_SNOWBALLING
        
        # Check statistics
        assert stats.new_papers_added == 1
        assert stats.citations_resolved == 1
        
        # Check database
        assert papers_db.count() == 1
        assert papers_db.get_by_doi("10.1234/test") is not None
    
    def test_fetch_paper_already_exists(self):
        """Test fetching when paper already exists in database"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        # Add existing paper
        existing_paper = Paper(
            cite_key="existing",
            title="Existing Paper",
            doi="10.1234/test",
        )
        papers_db.add(existing_paper)
        
        citation = Citation(
            doi="10.1234/test",
            title="Test Paper",
            extraction_method="crossref",
        )
        citations_db.add(citation)
        
        mock_fetcher = Mock()
        stats = ExpansionStatistics()
        
        result = _fetch_and_add_paper(
            citation,
            papers_db,
            citations_db,
            mock_fetcher,
            stats=stats,
        )
        
        assert result is None
        assert stats.new_papers_added == 0
        assert stats.citations_resolved == 1
        assert papers_db.count() == 1  # No new paper added
    
    def test_fetch_paper_no_doi(self):
        """Test fetching when citation has no DOI"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        citation = Citation(
            doi=None,
            title="Test Paper",
            extraction_method="manual",
        )
        citations_db.add(citation)
        
        mock_fetcher = Mock()
        stats = ExpansionStatistics()
        
        result = _fetch_and_add_paper(
            citation,
            papers_db,
            citations_db,
            mock_fetcher,
            stats=stats,
        )
        
        assert result is None
    
    def test_fetch_paper_crossref_fails(self):
        """Test when Crossref fetch fails"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        citation = Citation(
            doi="10.1234/invalid",
            title="Invalid Paper",
            extraction_method="crossref",
        )
        citations_db.add(citation)
        
        mock_fetcher = Mock()
        mock_fetcher.polite_client.get_work.return_value = None
        
        stats = ExpansionStatistics()
        
        result = _fetch_and_add_paper(
            citation,
            papers_db,
            citations_db,
            mock_fetcher,
            stats=stats,
        )
        
        assert result is None
        assert stats.new_papers_failed == 1


# ============================================================================
# BACKWARD SNOWBALLING TESTS
# ============================================================================

class TestBackwardSnowballing:
    """Test backward snowballing execution"""
    
    def test_single_iteration(self):
        """Test backward snowballing with single pass"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        # Add initial paper with DOI
        initial_paper = Paper(
            cite_key="initial",
            title="Initial Paper",
            doi="10.1111/initial",
        )
        papers_db.add(initial_paper)
        
        config = {
            "backward": {
                "extraction_methods": ["crossref"],
            }
        }
        
        with patch("paper_scanner.steps.expansion.CrossrefReferenceFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value
            
            # Mock citation extraction
            mock_fetcher.fetch_references_for_doi.return_value = {
                "references": [
                    {
                        "DOI": "10.2222/ref1",
                        "article-title": "Reference 1",
                        "year": 2020,
                    }
                ]
            }
            
            # Mock paper fetching
            mock_fetcher.polite_client.get_work.return_value = {
                "message": {
                    "title": ["Reference 1"],
                    "year": 2020,
                    "author": [{"given": "Jane", "family": "Doe"}],
                }
            }
            
            result = execute_backward_snowballing(papers_db, citations_db, config)
        
        assert result["success"] is True
        assert result["statistics"]["papers_expanded"] >= 1
        assert result["statistics"]["citations_found"] >= 1
        assert result["statistics"]["new_papers_added"] >= 1
    
    def test_no_papers_to_expand(self):
        """Test when there are no papers to expand"""
        papers_db = PapersDatabase()
        citations_db = CitationsDatabase()
        
        # Add paper without DOI
        paper = Paper(
            cite_key="no_doi",
            title="Paper without DOI",
            doi=None,
        )
        papers_db.add(paper)
        
        config = {
            "backward": {
                "extraction_methods": ["crossref"],
            }
        }
        
        with patch("paper_scanner.steps.expansion.CrossrefReferenceFetcher") as MockFetcher:
            result = execute_backward_snowballing(papers_db, citations_db, config)
        
        assert result["success"] is True
        assert result["statistics"]["papers_expanded"] == 0


# ============================================================================
# EXECUTE FUNCTION TESTS
# ============================================================================

class TestExecute:
    """Test main execute function"""
    
    def test_execute_valid_config(self):
        """Test execute with valid configuration"""
        papers_db = PapersDatabase()
        
        config = {
            "expansion": {
                "backward": {
                    "extraction_methods": ["crossref"],
                }
            }
        }
        
        # Add a paper to avoid empty database
        paper = Paper(
            cite_key="test",
            title="Test",
            doi="10.1234/test",
        )
        papers_db.add(paper)
        
        with patch("paper_scanner.steps.expansion.CrossrefReferenceFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value
            mock_fetcher.fetch_references_for_doi.return_value = {"references": []}
            
            result = execute(config, papers_db)
        
        assert result["success"] is True
        assert "statistics" in result
    
    def test_execute_invalid_config(self):
        """Test execute with invalid configuration"""
        papers_db = PapersDatabase()
        
        config = {
            "expansion": {
                "backward": {
                    "extraction_methods": "not_a_list",  # Invalid
                }
            }
        }
        
        result = execute(config, papers_db)
        
        assert result["success"] is False
        assert "Invalid configuration" in result["error"]
    
    def test_execute_no_backward_config(self):
        """Test execute without backward snowballing config"""
        papers_db = PapersDatabase()
        
        config = {
            "expansion": {}
        }
        
        result = execute(config, papers_db)
        
        assert result["success"] is False
        assert "No backward snowballing configuration" in result["error"]
