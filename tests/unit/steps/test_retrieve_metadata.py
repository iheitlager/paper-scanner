"""
Tests for the retrieve_metadata step

Tests metadata retrieval, API fetching, and cache handling
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone

from paper_scanner.steps.retrieve_metadata import RetrieveMetadataStep, _merge_paper_metadata
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper, Author, OpenAccessStatus
from paper_scanner.core.enum import PaperType


class TestValidate:
    """Test RetrieveMetadataStep.validate() static method"""

    def test_validate_valid_config(self):
        """Test validation of valid configuration"""
        config = {
            "methods": ["crossref"]
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_multiple_methods(self):
        """Test validation with multiple fetcher methods"""
        config = {
            "methods": ["crossref", "openalex"]
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_continue_on_not_found(self):
        """Test validation with optional continue_on_not_found parameter"""
        config = {
            "methods": ["crossref"],
            "continue_on_not_found": False
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_methods(self):
        """Test validation fails when methods is missing"""
        config = {}
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is False
        assert any("'methods' is required" in err for err in errors)

    def test_validate_methods_not_list(self):
        """Test validation fails when methods is not a list"""
        config = {
            "methods": "crossref"
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is False
        assert any("'methods' must be a non-empty list" in err for err in errors)

    def test_validate_methods_empty_list(self):
        """Test validation fails when methods is an empty list"""
        config = {
            "methods": []
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is False
        assert any("'methods' must be a non-empty list" in err for err in errors)

    def test_validate_methods_none(self):
        """Test validation fails when methods is None"""
        config = {
            "methods": None
        }
        
        is_valid, errors = RetrieveMetadataStep.validate(config)
        
        assert is_valid is False
        assert any("'methods' must be a non-empty list" in err for err in errors)


class TestExecute:
    """Test RetrieveMetadataStep.execute() method"""

    def test_execute_empty_database(self, tmp_path):
        """Test execute with empty database"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher'):
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["total_papers"] == 0
        assert result["updated_papers"] == 0
        assert result["skipped_no_doi"] == 0

    def test_execute_papers_without_doi(self, tmp_path):
        """Test execute skips papers without DOI"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        # Add paper without DOI
        paper = Paper(cite_key="test2024a", title="Test Paper")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher'):
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["total_papers"] == 1
        assert result["skipped_no_doi"] == 1
        assert result["updated_papers"] == 0

    def test_execute_with_valid_doi(self, tmp_path):
        """Test execute fetches metadata for paper with DOI"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        # Add paper with DOI
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/test")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        # Mock Fetcher
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            # Mock successful fetch with cache hit
            enriched_paper = Paper(
                cite_key="test2024a",
                title="Test Paper",
                doi="10.1234/test",
                abstract="Test abstract",
                year=2023,
                journal="Test Journal"
            )
            mock_fetcher.fetch_paper.return_value = (enriched_paper, True)
            
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["total_papers"] == 1
        assert result["updated_papers"] == 1
        assert result["cache_hits"] == 1
        assert result["cache_misses"] == 0

    def test_execute_cache_miss(self, tmp_path):
        """Test execute handles cache misses"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/test")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            enriched_paper = Paper(
                cite_key="test2024a",
                title="Test Paper",
                doi="10.1234/test",
                abstract="Fetched abstract"
            )
            mock_fetcher.fetch_paper.return_value = (enriched_paper, False)
            
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["cache_hits"] == 0
        assert result["cache_misses"] == 1

    def test_execute_metadata_not_found(self, tmp_path):
        """Test execute handles metadata not found"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/notfound")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"],
            "continue_on_not_found": True
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            # Fetch returns None for metadata not found
            mock_fetcher.fetch_paper.return_value = (None, False)
            
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["not_found"] == 1
        assert result["updated_papers"] == 0
        assert len(result["errors"]) == 0  # continue_on_not_found=True

    def test_execute_not_found_stops_on_error(self, tmp_path):
        """Test execute stops on not found when continue_on_not_found is False"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/notfound")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"],
            "continue_on_not_found": False
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            mock_fetcher.fetch_paper.return_value = (None, False)
            
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["not_found"] == 1
        assert len(result["errors"]) == 1
        assert "Not found" in result["errors"][0]

    def test_execute_dry_run_doesnt_update_db(self, tmp_path):
        """Test execute with dry_run doesn't write to database"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/test", abstract=None)
        db.add(paper)
        initial_count = len(db.all(primary_only=False))
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            enriched_paper = Paper(
                cite_key="test2024a",
                title="Test Paper",
                doi="10.1234/test",
                abstract="New abstract"
            )
            mock_fetcher.fetch_paper.return_value = (enriched_paper, False)
            
            result = step.execute(config, verbose=False, dry_run=True)
        
        # Database shouldn't be modified in dry_run mode
        # The update method should not be called
        assert result["updated_papers"] == 1
        # Check that db.update was not called by verifying record count unchanged
        final_count = len(db.all(primary_only=False))
        assert initial_count == final_count

    def test_execute_multiple_papers(self, tmp_path):
        """Test execute processes multiple papers"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        # Add multiple papers
        for i in range(3):
            paper = Paper(cite_key=f"paper{i}2024", title=f"Paper {i}", doi=f"10.1234/test{i}")
            db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            def fetch_side_effect(doi):
                return (Paper(
                    cite_key=f"updated{doi[-4:]}",
                    title=f"Updated {doi}",
                    doi=doi,
                    abstract=f"Abstract for {doi}"
                ), False)
            
            mock_fetcher.fetch_paper.side_effect = fetch_side_effect
            
            result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["total_papers"] == 3
        assert result["updated_papers"] == 3

    def test_execute_with_custom_methods(self, tmp_path):
        """Test execute uses specified fetcher methods"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        db = PapersDatabase()
        
        paper = Paper(cite_key="test2024a", title="Test Paper", doi="10.1234/test")
        db.add(paper)
        
        step = RetrieveMetadataStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )
        
        config = {
            "methods": ["openalex", "crossref"]
        }
        
        with patch('paper_scanner.steps.retrieve_metadata.Fetcher') as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            
            enriched_paper = Paper(
                cite_key="test2024a",
                doi="10.1234/test",
                abstract="Test abstract"
            )
            mock_fetcher.fetch_paper.return_value = (enriched_paper, False)
            
            result = step.execute(config, verbose=False, dry_run=False)
            
            # Verify Fetcher was instantiated with correct methods
            mock_fetcher_class.assert_called_once()
            call_kwargs = mock_fetcher_class.call_args[1]
            assert call_kwargs["methods"] == ["openalex", "crossref"]


class TestMergePaperMetadata:
    """Test _merge_paper_metadata helper function"""

    def test_merge_abstract(self):
        """Test merging abstract from source to target"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        source = Paper(cite_key="src2024a", title="Source", doi="10.1234/test", abstract="Source abstract")
        
        _merge_paper_metadata(target, source)
        
        assert target.abstract == "Source abstract"

    def test_merge_abstract_doesnt_overwrite(self):
        """Test merge doesn't overwrite existing abstract"""
        target = Paper(
            cite_key="test2024a",
            title="Test",
            doi="10.1234/test",
            abstract="Target abstract"
        )
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            abstract="Source abstract"
        )
        
        _merge_paper_metadata(target, source)
        
        assert target.abstract == "Target abstract"

    def test_merge_keywords(self):
        """Test merging keywords"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            keywords=["keyword1", "keyword2"]
        )
        
        _merge_paper_metadata(target, source)
        
        assert target.keywords == ["keyword1", "keyword2"]

    def test_merge_multiple_fields(self):
        """Test merging multiple fields"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            abstract="Test abstract",
            year=2023,
            journal="Test Journal",
            authors=[Author(family_name="Author", given_name="Test", full_name="Test Author")]
        )
        
        _merge_paper_metadata(target, source)
        
        assert target.abstract == "Test abstract"
        assert target.year == 2023
        assert target.journal == "Test Journal"
        assert target.authors == [Author(family_name="Author", given_name="Test", full_name="Test Author")]

    def test_merge_updates_timestamp(self):
        """Test merge updates the updated_at timestamp"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        old_timestamp = target.updated_at
        
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            abstract="Test abstract"
        )
        
        _merge_paper_metadata(target, source)
        
        # If both are aware or both are naive, compare directly
        if old_timestamp.tzinfo is None and target.updated_at.tzinfo is None:
            assert target.updated_at > old_timestamp
        elif old_timestamp.tzinfo is not None and target.updated_at.tzinfo is not None:
            assert target.updated_at > old_timestamp
        else:
            # Just verify timestamp was updated (different from original)
            assert target.updated_at != old_timestamp

    def test_merge_all_fields(self):
        """Test merging all supported fields"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            abstract="Abstract",
            keywords=["kw"],
            topics=["topic"],
            authors=[Author(family_name="Author", given_name="Test", full_name="Test Author")],
            year=2023,
            journal="Journal",
            publisher="Publisher",
            volume="10",
            number="5",
            pages="1-10",
            publication_date=datetime(2023, 1, 1),
            paper_type=PaperType.JOURNAL_ARTICLE,
            language="en",
            oa_status=OpenAccessStatus(is_oa=True, oa_status="gold"),
            raw_json={"test": "data"}
        )
        
        _merge_paper_metadata(target, source, overwrite=True)
        
        assert target.abstract == "Abstract"
        assert target.title == "Source"
        assert target.keywords == ["kw"]
        assert target.topics == ["topic"]
        assert target.authors == [Author(family_name="Author", given_name="Test", full_name="Test Author")]
        assert target.year == 2023
        assert target.journal == "Journal"
        assert target.publisher == "Publisher"
        assert target.volume == "10"
        assert target.number == "5"
        assert target.pages == "1-10"
        assert target.publication_date == datetime(2023, 1, 1)
        assert target.paper_type == PaperType.JOURNAL_ARTICLE
        assert target.language == "en"
        assert target.oa_status == OpenAccessStatus(is_oa=True, oa_status="gold")
        assert target.raw_json == {"test": "data"}

    def test_merge_all_fields_overwrite_false(self):
        """Test merging all supported fields"""
        target = Paper(
            cite_key="test2024a", 
            doi="10.1234/test",
            title="Test", 
            abstract="Target Abstract",
        )
        source = Paper(
            doi="10.1234/test",
            cite_key="src2024a",
            title="Source Title",
            abstract="Abstract",
            keywords=["kw"],
            topics=["topic"],
            authors=[Author(family_name="Author", given_name="Test", full_name="Test Author")],
            year=2023,
            journal="Journal",
            publisher="Publisher",
            volume="10",
            number="5",
            pages="1-10",
            publication_date=datetime(2023, 1, 1),
            paper_type=PaperType.JOURNAL_ARTICLE,
            language="en",
            oa_status=OpenAccessStatus(is_oa=True, oa_status="gold"),
            raw_json={"test": "data"}
        )
        
        _merge_paper_metadata(target, source, overwrite=False)
        
        assert target.abstract == "Target Abstract"
        assert target.title == "Test" # Stays the same
        assert target.keywords == ["kw"]
        assert target.topics == ["topic"]
        assert target.authors == [Author(family_name="Author", given_name="Test", full_name="Test Author")]
        assert target.year == 2023
        assert target.journal == "Journal"
        assert target.publisher == "Publisher"
        assert target.volume == "10"
        assert target.number == "5"
        assert target.pages == "1-10"
        assert target.publication_date == datetime(2023, 1, 1)
        assert target.paper_type == PaperType.JOURNAL_ARTICLE
        assert target.language == "en"
        assert target.oa_status == OpenAccessStatus(is_oa=True, oa_status="gold")
        assert target.raw_json == {"test": "data"}

    def test_merge_skips_empty_source_fields(self):
        """Test merge skips None/empty fields in source"""
        target = Paper(cite_key="test2024a", title="Test", doi="10.1234/test")
        source = Paper(
            cite_key="src2024a",
            title="Source",
            doi="10.1234/test",
            abstract=None,
            keywords=[]
        )
        
        _merge_paper_metadata(target, source)
        
        # Empty/None fields from source should not be merged
        assert target.abstract is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
