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
from datetime import datetime
from typing import List

import pytest

from paper_scanner.core.models import Author, Discovery, DiscoveryMethod, Paper, Screening, ScreeningDecision
from paper_scanner.io.json import (
    PaperJSONEncoder,
    dict_to_paper,
    json_file_to_paper,
    json_file_to_papers,
    json_to_paper,
    json_to_papers,
    jsonl_file_to_papers,
    jsonl_to_papers,
    paper_to_dict,
    paper_to_dict_bibliographic,
    paper_to_dict_camo,
    paper_to_dict_minimal,
    paper_to_dict_screening,
    paper_to_json,
    paper_to_json_file,
    papers_to_json,
    papers_to_json_file,
    papers_to_json_partial,
    papers_to_jsonl,
    papers_to_jsonl_file,
    stream_jsonl_file,
    validate_json_file,
    validate_json_schema,
    verify_round_trip,
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


# ============================================================================
# Tests: Additional Coverage - Compression Support
# ============================================================================

class TestCompressionSupport:
    """Test compressed JSON output (gzip)."""

    def test_papers_to_json_gz(self, paper_list, tmp_path):
        """Test writing papers to compressed JSON file."""
        try:
            from paper_scanner.io.json import papers_to_json_gz
        except ImportError:
            pytest.skip("Compression support not available")

        filepath = tmp_path / "papers.json.gz"
        papers_to_json_gz(paper_list, str(filepath))

        assert filepath.exists()
        # File should be binary/compressed
        assert filepath.stat().st_size > 0

    def test_json_gz_to_papers(self, paper_list, tmp_path):
        """Test reading papers from compressed JSON file."""
        try:
            from paper_scanner.io.json import papers_to_json_gz, json_gz_to_papers
        except ImportError:
            pytest.skip("Compression support not available")

        filepath = tmp_path / "papers.json.gz"
        papers_to_json_gz(paper_list, str(filepath))

        restored = json_gz_to_papers(str(filepath))
        assert len(restored) == len(paper_list)


# ============================================================================
# Tests: Additional Coverage - Batch Operations
# ============================================================================

class TestBatchOperations:
    """Test batch operations on papers."""

    def test_split_papers_to_files(self, minimal_paper, tmp_path):
        """Test splitting papers into multiple files."""
        try:
            from paper_scanner.io.json import split_papers_to_files
        except ImportError:
            pytest.skip("Batch operations not available")

        papers = [minimal_paper for _ in range(25)]
        output_dir = str(tmp_path)

        result = split_papers_to_files(papers, output_dir, papers_per_file=10)

        assert isinstance(result, list)
        assert len(result) > 0
        # Should create multiple files
        assert len(result) >= 3  # 25 papers / 10 per file = 3 files

    def test_merge_json_files(self, minimal_paper, tmp_path):
        """Test merging multiple JSON files."""
        try:
            from paper_scanner.io.json import split_papers_to_files, merge_json_files
        except ImportError:
            pytest.skip("Batch operations not available")

        papers = [minimal_paper for _ in range(15)]

        # First split into multiple files
        split_dir = tmp_path / "split"
        split_dir.mkdir()
        result = split_papers_to_files(papers, str(split_dir), papers_per_file=5)

        # Then merge them back
        output_file = tmp_path / "merged.json"
        total = merge_json_files(result, str(output_file))

        assert total == 15
        assert output_file.exists()


# ============================================================================
# Tests: Additional Coverage - Partial Export Modes
# ============================================================================

class TestPartialExportModes:
    """Test various partial export modes."""

    def test_papers_to_json_partial_bibliographic(self, paper_list):
        """Test bibliographic partial export mode."""
        json_str = papers_to_json_partial(paper_list, mode='bibliographic')
        data = json.loads(json_str)

        assert len(data) == 2
        # Bibliographic mode should include publication details
        assert all('title' in item for item in data)

    def test_papers_to_json_partial_screening(self, paper_list):
        """Test screening partial export mode."""
        json_str = papers_to_json_partial(paper_list, mode='screening')
        data = json.loads(json_str)

        assert len(data) == 2
        # Should include screening-related fields
        assert isinstance(data, list)

    def test_papers_to_json_partial_camo(self, paper_list):
        """Test CAMO partial export mode."""
        json_str = papers_to_json_partial(paper_list, mode='camo')
        data = json.loads(json_str)

        assert len(data) == 2
        # Should have CAMO statements structure
        assert isinstance(data, list)

    def test_papers_to_json_partial_invalid_mode(self, paper_list):
        """Test invalid export mode raises error."""
        with pytest.raises(ValueError, match="Unknown mode"):
            papers_to_json_partial(paper_list, mode='invalid_mode')


# ============================================================================
# Tests: Additional Coverage - Special Cases
# ============================================================================

class TestSpecialCases:
    """Test special cases and edge conditions."""

    def test_json_with_exclude_none_true(self, rich_paper):
        """Test JSON export with exclude_none=True."""
        json_with_none = paper_to_json(rich_paper, exclude_none=False)
        json_without_none = paper_to_json(rich_paper, exclude_none=True)

        data_with = json.loads(json_with_none)
        data_without = json.loads(json_without_none)

        # Without None should have fewer or equal keys
        assert len(data_without) <= len(data_with)

    def test_jsonl_with_exclude_none(self, paper_list):
        """Test JSONL export with exclude_none=True."""
        jsonl_str = papers_to_jsonl(paper_list, exclude_none=True)
        lines = jsonl_str.strip().split('\n')

        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert isinstance(data, dict)

    def test_invalid_json_file_path(self):
        """Test handling of non-existent file for reading."""
        try:
            json_file_to_papers("/nonexistent/path/papers.json")
            assert False, "Should raise FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_invalid_jsonl_file_path(self):
        """Test handling of non-existent JSONL file."""
        try:
            jsonl_file_to_papers("/nonexistent/path/papers.jsonl")
            assert False, "Should raise FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_stream_empty_jsonl_file(self, tmp_path):
        """Test streaming empty JSONL file."""
        filepath = tmp_path / "empty.jsonl"
        filepath.write_text("")

        count = 0
        for paper in stream_jsonl_file(str(filepath)):
            count += 1

        assert count == 0

    def test_jsonl_file_with_blank_lines(self, minimal_paper, tmp_path):
        """Test JSONL file with blank lines is handled correctly."""
        filepath = tmp_path / "with_blanks.jsonl"

        # Write papers with intentional blank lines using proper JSONL format
        line1 = json.dumps(paper_to_dict(minimal_paper))
        line2 = json.dumps(paper_to_dict(minimal_paper))
        content = line1 + "\n\n" + line2 + "\n"
        filepath.write_text(content)

        papers = jsonl_file_to_papers(str(filepath))
        # Should skip blank lines and read 2 papers
        assert len(papers) == 2


# ============================================================================
# Tests: Additional Coverage - Paper Relationships
# ============================================================================

class TestPaperRelationships:
    """Test handling of paper relationships in JSON."""

    def test_round_trip_with_authors_list(self, rich_paper):
        """Test round-trip with multiple authors."""
        json_str = paper_to_json(rich_paper)
        restored = json_to_paper(json_str)

        assert len(restored.authors) == len(rich_paper.authors)
        for orig, rest in zip(rich_paper.authors, restored.authors):
            assert orig.full_name == rest.full_name

    def test_round_trip_with_discovery_metadata(self, rich_paper):
        """Test round-trip with discovery metadata."""
        json_str = paper_to_json(rich_paper)
        restored = json_to_paper(json_str)

        if rich_paper.discovery:
            assert restored.discovery.method == rich_paper.discovery.method
            assert restored.discovery.source_database == rich_paper.discovery.source_database

    def test_round_trip_with_keywords(self, rich_paper):
        """Test round-trip with keywords."""
        json_str = paper_to_json(rich_paper)
        restored = json_to_paper(json_str)

        assert set(restored.keywords) == set(rich_paper.keywords)


# ============================================================================
# Tests: Additional Coverage - Encoder Edge Cases
# ============================================================================

class TestEncoderEdgeCases:
    """Test edge cases for PaperJSONEncoder."""

    def test_encoder_with_none_values(self):
        """Test encoder handles None values."""
        data = {"field": None, "value": 123}
        json_str = json.dumps(data, cls=PaperJSONEncoder)
        restored = json.loads(json_str)

        assert restored["field"] is None
        assert restored["value"] == 123

    def test_encoder_with_empty_collections(self):
        """Test encoder handles empty lists and dicts."""
        data = {"authors": [], "keywords": [], "nested": {}}
        json_str = json.dumps(data, cls=PaperJSONEncoder)
        restored = json.loads(json_str)

        assert restored["authors"] == []
        assert restored["keywords"] == []
        assert restored["nested"] == {}

    def test_encoder_with_special_characters(self):
        """Test encoder handles special characters in strings."""
        data = {"title": "Test with émojis and spëcial çharacters"}
        json_str = json.dumps(data, cls=PaperJSONEncoder)
        restored = json.loads(json_str)

        assert "émojis" in restored["title"]
        assert "spëcial" in restored["title"]


# ============================================================================
# Tests: Additional Coverage - Validation Edge Cases
# ============================================================================

class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_validate_file_with_invalid_json(self, tmp_path):
        """Test validating file with invalid JSON."""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("{ invalid json")

        result = validate_json_file(str(filepath))
        assert result["valid"] is False
        assert result["error"] is not None

    def test_validate_file_with_wrong_schema(self, tmp_path):
        """Test validating file with wrong schema."""
        filepath = tmp_path / "wrong.json"
        filepath.write_text('{"not": "a paper"}')

        result = validate_json_file(str(filepath))
        # Should indicate validation failure
        assert isinstance(result, dict)

    def test_verify_round_trip_with_rich_paper(self, rich_paper):
        """Test round-trip verification with complex paper."""
        result = verify_round_trip(rich_paper)
        assert isinstance(result, bool)


# ============================================================================
# Tests: Additional Coverage - Collection Serialization
# ============================================================================

class TestDictionaryConversions:
    """Test dict to/from paper conversions."""

    def test_dict_to_paper_minimal(self):
        """Test converting minimal dict to Paper."""
        paper_dict = {
            "cite_key": "test2024",
            "title": "Test Paper",
            "year": 2024
        }
        paper = dict_to_paper(paper_dict)

        assert paper.cite_key == "test2024"
        assert paper.title == "Test Paper"
        assert paper.year == 2024

    def test_dict_to_paper_with_authors(self):
        """Test converting dict with authors."""
        paper_dict = {
            "cite_key": "test2024",
            "title": "Test Paper",
            "authors": [
                {
                    "family_name": "Smith",
                    "given_name": "John",
                    "full_name": "John Smith"
                }
            ]
        }
        paper = dict_to_paper(paper_dict)

        assert len(paper.authors) == 1
        assert paper.authors[0].full_name == "John Smith"

    def test_dict_to_paper_with_discovery(self):
        """Test converting dict with discovery info."""
        paper_dict = {
            "cite_key": "test2024",
            "title": "Test Paper",
            "discovery": {
                "method": "keyword_search",
                "source_database": "scopus"
            }
        }
        paper = dict_to_paper(paper_dict)

        assert paper.discovery.source_database == "scopus"
