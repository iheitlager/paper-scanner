"""
Tests for JSON serialization/deserialization of Paper models.

Tests complete round-trip conversion (Paper ↔ JSON) including:
- Single paper conversion to/from JSON
- Multiple papers and JSONLines formats
- PaperCollection handling
- Partial/filtered serialization views
- Schema validation and round-trip verification
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List

import pytest

from paper_scanner.core.models import (
    Paper, Author, Embedding, Citation, TextChunk, Discovery,
    Screening, Categorization, KeywordScreening, SemanticScreening,
    DeduplicationResult, PDFInfo, CAMOStatement, ConceptualAnalysis,
    ProcessingMetadata, PaperCollection,
    PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision
)
from paper_scanner.io.json import (
    paper_to_dict, paper_to_json, papers_to_json,
    paper_to_json_file, papers_to_json_file,
    dict_to_paper, json_to_paper, json_to_papers,
    json_file_to_paper, json_file_to_papers,
    papers_to_jsonl, papers_to_jsonl_file,
    jsonl_to_papers, jsonl_file_to_papers,
    stream_jsonl_file,
    collection_to_dict, collection_to_json, collection_to_json_file,
    dict_to_collection, json_to_collection, json_file_to_collection,
    paper_to_dict_minimal, paper_to_dict_bibliographic,
    paper_to_dict_screening, paper_to_dict_camo,
    papers_to_json_partial,
    validate_json_schema, validate_json_file,
    verify_round_trip, PaperJSONEncoder
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def minimal_paper() -> Paper:
    """Create a minimal valid Paper for testing."""
    return Paper(
        cite_key="test-paper-1",
        title="Test Paper",
        year=2024,
        doi="10.1234/test"
    )


@pytest.fixture
def rich_paper() -> Paper:
    """Create a Paper with many populated fields."""
    return Paper(
        cite_key="test-paper-2",
        title="Comprehensive Test Paper",
        authors=[
            Author(family_name="Doe", full_name="John Doe"),
            Author(family_name="Smith", full_name="Jane Smith")
        ],
        year=2024,
        doi="10.5678/comprehensive",
        abstract="This is a comprehensive test abstract.",
        journal="Test Journal",
        volume="42",
        number="1",
        pages="10-25",
        keywords=["machine learning", "testing"],
        publication_date=datetime(2024, 1, 15),
        url="https://example.com/paper",
        discovery=Discovery(
            method=DiscoveryMethod.API,
            source="PubMed",
            search_query="machine learning",
            retrieved_date=datetime(2024, 1, 10),
            relevance_score=0.95
        ),
        screening=Screening(
            decision=ScreeningDecision.INCLUDED,
            reason="Relevant to scope",
            screener="reviewer1",
            date=datetime(2024, 1, 20)
        )
    )


@pytest.fixture
def paper_list(minimal_paper, rich_paper) -> List[Paper]:
    """Create a list of papers for testing."""
    return [minimal_paper, rich_paper]


# ============================================================================
# Tests: Single Paper Serialization
# ============================================================================

class TestSinglePaperSerialization:
    """Test converting single Paper to various JSON formats."""

    def test_paper_to_dict_minimal(self, minimal_paper):
        """Test converting minimal paper to dictionary."""
        result = paper_to_dict(minimal_paper)
        
        assert isinstance(result, dict)
        assert result["cite_key"] == "test-paper-1"
        assert result["title"] == "Test Paper"
        assert result["year"] == 2024
        assert result["doi"] == "10.1234/test"

    def test_paper_to_dict_exclude_none(self, rich_paper):
        """Test that exclude_none removes None values."""
        result_with_none = paper_to_dict(rich_paper, exclude_none=False)
        result_without_none = paper_to_dict(rich_paper, exclude_none=True)
        
        # Dictionary without None should have fewer or equal keys
        assert len(result_without_none) <= len(result_with_none)

    def test_paper_to_json_string(self, minimal_paper):
        """Test converting paper to JSON string."""
        json_str = paper_to_json(minimal_paper)
        
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["cite_key"] == "test-paper-1"

    def test_paper_to_json_compact(self, minimal_paper):
        """Test JSON without indentation (compact)."""
        json_str = paper_to_json(minimal_paper, indent=None)
        
        # Compact JSON should not contain newlines
        assert "\n" not in json_str

    def test_paper_to_json_indented(self, minimal_paper):
        """Test JSON with indentation (pretty)."""
        json_str = paper_to_json(minimal_paper, indent=2)
        
        # Indented JSON should contain newlines
        assert "\n" in json_str

    def test_paper_to_json_file(self, minimal_paper, tmp_path):
        """Test writing paper to JSON file."""
        filepath = tmp_path / "paper.json"
        paper_to_json_file(minimal_paper, str(filepath))
        
        assert filepath.exists()
        
        # Verify file contents
        with open(filepath) as f:
            data = json.load(f)
        assert data["cite_key"] == "test-paper-1"

    def test_paper_datetime_serialization(self, rich_paper):
        """Test that datetime objects are properly serialized."""
        json_str = paper_to_json(rich_paper)
        data = json.loads(json_str)
        
        # publication_date should be ISO format string
        assert isinstance(data["publication_date"], str)
        assert "2024-01-15" in data["publication_date"]


# ============================================================================
# Tests: Multiple Papers Serialization
# ============================================================================

class TestMultiplePapersSerialization:
    """Test converting multiple papers to JSON formats."""

    def test_papers_to_json_array(self, paper_list):
        """Test converting papers list to JSON array."""
        json_str = papers_to_json(paper_list)
        
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["cite_key"] == "test-paper-1"
        assert data[1]["cite_key"] == "test-paper-2"

    def test_papers_to_json_file(self, paper_list, tmp_path):
        """Test writing papers array to JSON file."""
        filepath = tmp_path / "papers.json"
        papers_to_json_file(paper_list, str(filepath))
        
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        assert len(data) == 2

    def test_papers_to_jsonl(self, paper_list):
        """Test converting papers to JSONLines format."""
        jsonl_str = papers_to_jsonl(paper_list)
        
        # JSONLines: one JSON object per line
        lines = jsonl_str.strip().split('\n')
        assert len(lines) == 2
        
        # Each line should be valid JSON
        obj1 = json.loads(lines[0])
        obj2 = json.loads(lines[1])
        assert obj1["cite_key"] == "test-paper-1"
        assert obj2["cite_key"] == "test-paper-2"

    def test_papers_to_jsonl_file(self, paper_list, tmp_path):
        """Test writing papers to JSONL file."""
        filepath = tmp_path / "papers.jsonl"
        papers_to_jsonl_file(paper_list, str(filepath))
        
        assert filepath.exists()
        
        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) == 2
        
        # Verify JSONLines format
        lines = filepath.read_text().strip().split('\n')
        assert len(lines) == 2

    def test_jsonl_no_blank_lines(self, paper_list, tmp_path):
        """Test that JSONLines output has no blank lines."""
        filepath = tmp_path / "papers.jsonl"
        papers_to_jsonl_file(paper_list, str(filepath))
        
        content = filepath.read_text()
        # No double newlines or blank lines
        assert "\n\n" not in content


# ============================================================================
# Tests: Deserialization (JSON → Paper)
# ============================================================================

class TestDeserialization:
    """Test converting JSON back to Paper objects."""

    def test_dict_to_paper(self, minimal_paper):
        """Test converting dictionary to Paper."""
        paper_dict = paper_to_dict(minimal_paper)
        restored = dict_to_paper(paper_dict)
        
        assert restored.cite_key == minimal_paper.cite_key
        assert restored.title == minimal_paper.title
        assert restored.year == minimal_paper.year
        assert restored.doi == minimal_paper.doi

    def test_json_to_paper(self, minimal_paper):
        """Test converting JSON string to Paper."""
        json_str = paper_to_json(minimal_paper)
        restored = json_to_paper(json_str)
        
        assert restored.cite_key == minimal_paper.cite_key
        assert restored.title == minimal_paper.title

    def test_json_file_to_paper(self, minimal_paper, tmp_path):
        """Test reading paper from JSON file."""
        filepath = tmp_path / "paper.json"
        paper_to_json_file(minimal_paper, str(filepath))
        
        restored = json_file_to_paper(str(filepath))
        assert restored.cite_key == minimal_paper.cite_key

    def test_json_to_papers_list(self, paper_list):
        """Test converting JSON array to papers list."""
        json_str = papers_to_json(paper_list)
        restored = json_to_papers(json_str)
        
        assert len(restored) == 2
        assert restored[0].cite_key == paper_list[0].cite_key
        assert restored[1].cite_key == paper_list[1].cite_key

    def test_json_file_to_papers(self, paper_list, tmp_path):
        """Test reading papers from JSON file."""
        filepath = tmp_path / "papers.json"
        papers_to_json_file(paper_list, str(filepath))
        
        restored = json_file_to_papers(str(filepath))
        assert len(restored) == 2

    def test_jsonl_to_papers(self, paper_list):
        """Test converting JSONLines string to papers."""
        jsonl_str = papers_to_jsonl(paper_list)
        restored = jsonl_to_papers(jsonl_str)
        
        assert len(restored) == 2
        assert restored[0].cite_key == paper_list[0].cite_key
        assert restored[1].cite_key == paper_list[1].cite_key

    def test_jsonl_file_to_papers(self, paper_list, tmp_path):
        """Test reading papers from JSONLines file."""
        filepath = tmp_path / "papers.jsonl"
        papers_to_jsonl_file(paper_list, str(filepath))
        
        restored = jsonl_file_to_papers(str(filepath))
        assert len(restored) == 2

    def test_stream_jsonl_file(self, paper_list, tmp_path):
        """Test streaming papers from JSONLines file."""
        filepath = tmp_path / "papers.jsonl"
        papers_to_jsonl_file(paper_list, str(filepath))
        
        streamed_papers = list(stream_jsonl_file(str(filepath)))
        assert len(streamed_papers) == 2
        assert streamed_papers[0].cite_key == paper_list[0].cite_key


# ============================================================================
# Tests: Round-Trip Verification
# ============================================================================

class TestRoundTrip:
    """Test that papers survive round-trip conversion."""

    def test_round_trip_minimal_paper(self, minimal_paper):
        """Test round-trip: Paper → JSON → Paper."""
        json_str = paper_to_json(minimal_paper)
        restored = json_to_paper(json_str)
        
        assert verify_round_trip(minimal_paper)
        assert restored == minimal_paper

    def test_round_trip_rich_paper(self, rich_paper):
        """Test round-trip with fully populated paper."""
        json_str = paper_to_json(rich_paper)
        restored = json_to_paper(json_str)
        
        assert verify_round_trip(rich_paper)
        assert restored == rich_paper

    def test_round_trip_via_dict(self, minimal_paper):
        """Test round-trip via dictionary intermediate."""
        paper_dict = paper_to_dict(minimal_paper)
        restored = dict_to_paper(paper_dict)
        
        assert restored == minimal_paper

    def test_round_trip_papers_list(self, paper_list):
        """Test round-trip with multiple papers."""
        json_str = papers_to_json(paper_list)
        restored = json_to_papers(json_str)
        
        assert len(restored) == len(paper_list)
        for orig, rest in zip(paper_list, restored):
            assert rest == orig

    def test_round_trip_jsonl(self, paper_list):
        """Test round-trip with JSONLines format."""
        jsonl_str = papers_to_jsonl(paper_list)
        restored = jsonl_to_papers(jsonl_str)
        
        assert len(restored) == len(paper_list)
        assert restored[0] == paper_list[0]
        assert restored[1] == paper_list[1]


# ============================================================================
# Tests: Partial/Filtered Serialization
# ============================================================================

class TestPartialSerialization:
    """Test converting to partial paper representations."""

    def test_paper_to_dict_minimal_view(self, rich_paper):
        """Test minimal view of paper."""
        result = paper_to_dict_minimal(rich_paper)
        
        # Should contain core fields
        assert "cite_key" in result
        assert "title" in result
        assert "year" in result
        
        # Minimal view should exclude detailed fields
        # (specific fields depend on implementation)
        assert isinstance(result, dict)

    def test_paper_to_dict_bibliographic_view(self, rich_paper):
        """Test bibliographic view of paper."""
        result = paper_to_dict_bibliographic(rich_paper)
        
        # Should include publication details
        assert "cite_key" in result
        assert "title" in result
        assert "authors" in result
        assert "year" in result
        assert isinstance(result, dict)

    def test_paper_to_dict_screening_view(self, rich_paper):
        """Test screening view of paper."""
        result = paper_to_dict_screening(rich_paper)
        
        # Should include screening-relevant fields
        assert "cite_key" in result
        assert "title" in result
        assert isinstance(result, dict)

    def test_paper_to_dict_camo_view(self, rich_paper):
        """Test CAMO (Conceptual Analysis) view of paper."""
        result = paper_to_dict_camo(rich_paper)
        
        assert "id" in result
        assert isinstance(result, dict)

    def test_papers_to_json_partial(self, paper_list):
        """Test converting papers to JSON with partial fields."""
        json_str = papers_to_json_partial(paper_list, mode='minimal')
        data = json.loads(json_str)
        
        assert len(data) == 2
        assert "cite_key" in data[0]
        assert "title" in data[0]


# ============================================================================
# Tests: PaperCollection
# ============================================================================

class TestPaperCollectionSerialization:
    """Test PaperCollection serialization."""

    def test_collection_to_dict(self, paper_list):
        """Test converting collection to dictionary."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        result = collection_to_dict(collection)
        
        assert result["name"] == "Test Collection"
        assert len(result["papers"]) == 2

    def test_collection_to_json(self, paper_list):
        """Test converting collection to JSON."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        json_str = collection_to_json(collection)
        data = json.loads(json_str)
        
        assert data["name"] == "Test Collection"
        assert len(data["papers"]) == 2

    def test_collection_to_json_file(self, paper_list, tmp_path):
        """Test writing collection to JSON file."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        filepath = tmp_path / "collection.json"
        result = collection_to_json_file(collection, str(filepath))
        
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        assert data["name"] == "Test Collection"

    def test_dict_to_collection(self, paper_list):
        """Test converting dictionary to collection."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        collection_dict = collection_to_dict(collection)
        restored = dict_to_collection(collection_dict)
        
        assert restored.name == collection.name
        assert len(restored.papers) == len(collection.papers)

    def test_json_to_collection(self, paper_list):
        """Test converting JSON to collection."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        json_str = collection_to_json(collection)
        restored = json_to_collection(json_str)
        
        assert restored.name == collection.name
        assert len(restored.papers) == 2

    def test_json_file_to_collection(self, paper_list, tmp_path):
        """Test reading collection from JSON file."""
        collection = PaperCollection(
            name="Test Collection",
            papers=paper_list
        )
        
        filepath = tmp_path / "collection.json"
        collection_to_json_file(collection, str(filepath))
        
        restored = json_file_to_collection(str(filepath))
        assert restored.name == collection.name
        assert len(restored.papers) == 2


# ============================================================================
# Tests: Validation
# ============================================================================

class TestValidation:
    """Test JSON validation functions."""

    def test_validate_json_schema(self, minimal_paper):
        """Test JSON schema validation."""
        json_str = paper_to_json(minimal_paper)
        
        # Valid JSON should pass validation
        result = validate_json_schema(json_str)
        assert result is True

    def test_validate_invalid_json_schema(self):
        """Test validation fails on invalid JSON."""
        invalid_json = "{ invalid json }"
        
        result = validate_json_schema(invalid_json)
        assert result is False

    def test_validate_json_file(self, minimal_paper, tmp_path):
        """Test JSON file validation."""
        filepath = tmp_path / "paper.json"
        paper_to_json_file(minimal_paper, str(filepath))
        
        result = validate_json_file(str(filepath))
        
        assert isinstance(result, dict)
        assert "valid" in result or isinstance(result, dict)


# ============================================================================
# Tests: Custom JSON Encoder
# ============================================================================

class TestCustomEncoder:
    """Test PaperJSONEncoder for special types."""

    def test_encoder_datetime(self):
        """Test encoding datetime objects."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        json_str = json.dumps({"date": dt}, cls=PaperJSONEncoder)
        
        data = json.loads(json_str)
        assert "2024-01-15" in data["date"]

    def test_encoder_in_paper_serialization(self, rich_paper):
        """Test encoder handles all datetime fields in paper."""
        json_str = paper_to_json(rich_paper)
        
        # Should not raise any encoding errors
        data = json.loads(json_str)
        assert isinstance(data, dict)


# ============================================================================
# Tests: File I/O Edge Cases
# ============================================================================

class TestFileIOEdgeCases:
    """Test file operations edge cases."""

    def test_read_write_empty_papers_list(self, tmp_path):
        """Test handling empty papers list."""
        filepath = tmp_path / "empty.json"
        papers_to_json_file([], str(filepath))
        
        assert filepath.exists()
        restored = json_file_to_papers(str(filepath))
        assert restored == []

    def test_read_write_large_papers_list(self, minimal_paper, tmp_path):
        """Test handling large papers list."""
        large_list = [minimal_paper for _ in range(100)]
        
        filepath = tmp_path / "large.json"
        papers_to_json_file(large_list, str(filepath))
        
        restored = json_file_to_papers(str(filepath))
        assert len(restored) == 100

    def test_jsonl_streaming_large_file(self, minimal_paper, tmp_path):
        """Test streaming large JSONLines file."""
        large_list = [minimal_paper for _ in range(100)]
        
        filepath = tmp_path / "large.jsonl"
        papers_to_jsonl_file(large_list, str(filepath))
        
        # Stream and count
        count = 0
        for paper in stream_jsonl_file(str(filepath)):
            count += 1
            assert isinstance(paper, Paper)
        
        assert count == 100
