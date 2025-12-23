"""
Tests for StepResult dataclass.

Validates:
- Basic initialization
- Dict-like __getitem__ access
- KeyError handling for invalid fields
- to_dict() serialization
- Status enum handling
- Flexible stats and metadata dicts
"""

import pytest

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.step_result import StepResult


class TestStepResultInitialization:
    """Test StepResult initialization and default values"""

    def test_minimal_initialization(self):
        """Test creating StepResult with only required fields"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
        )

        assert result.status == StepStatus.SUCCESS
        assert result.step == "test_step"
        assert result.message == ""
        assert result.description is None
        assert result.stats == {}
        assert result.details is None
        assert result.error is None
        assert result.error_detail is None
        assert result.metadata == {}

    def test_full_initialization(self):
        """Test creating StepResult with all fields"""
        result = StepResult(
            status=StepStatus.WARNING,
            step="bibtex_import",
            message="Imported 40/50 papers",
            description="Import BibTeX files",
            stats={"processed": 50, "created": 40, "errors": 10},
            details="Failed on 10 papers with invalid DOI",
            error=None,
            error_detail=None,
            metadata={"duration_seconds": 2.5},
        )

        assert result.status == StepStatus.WARNING
        assert result.step == "bibtex_import"
        assert result.message == "Imported 40/50 papers"
        assert result.description == "Import BibTeX files"
        assert result.stats == {"processed": 50, "created": 40, "errors": 10}
        assert result.details == "Failed on 10 papers with invalid DOI"
        assert result.metadata == {"duration_seconds": 2.5}

    def test_error_status_with_error_fields(self):
        """Test creating StepResult with ERROR status and error details"""
        result = StepResult(
            status=StepStatus.ERROR,
            step="export",
            message="Failed to write output",
            error="Permission denied",
            error_detail="[Errno 13] Permission denied: /output.jsonl",
            stats={"processed": 0, "errors": 1},
        )

        assert result.status == StepStatus.ERROR
        assert result.error == "Permission denied"
        assert result.error_detail == "[Errno 13] Permission denied: /output.jsonl"


class TestStepResultGetItem:
    """Test dict-like __getitem__ access for backward compatibility"""

    def test_getitem_valid_fields(self):
        """Test __getitem__ with valid field names"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            message="Test message",
        )

        # Test accessing all fields via __getitem__
        assert result["status"] == StepStatus.SUCCESS
        assert result.get("status") == StepStatus.SUCCESS
        assert result["step"] == "test_step"
        assert result["message"] == "Test message"
        assert result["description"] is None
        assert result["stats"] == {}
        assert result["details"] is None
        assert result["error"] is None
        assert result["error_detail"] is None
        assert result["metadata"] == {}

    def test_getitem_raises_keyerror_for_invalid_field(self):
        """Test __getitem__ raises KeyError for non-existent fields"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
        )

        with pytest.raises(KeyError) as exc_info:
            _ = result["invalid_field"]

        assert "invalid_field" in str(exc_info.value)

    def test_getitem_with_stats_dict(self):
        """Test __getitem__ with flexible stats dict"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            stats={"processed": 100, "created": 95, "skipped": 5},
        )

        stats = result["stats"]
        assert isinstance(stats, dict)
        assert stats["processed"] == 100
        assert stats["created"] == 95
        assert stats["skipped"] == 5

    def test_getitem_with_metadata_dict(self):
        """Test __getitem__ with flexible metadata dict"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            metadata={"duration_seconds": 2.3, "started_at": "2025-12-23T10:30:00"},
        )

        metadata = result["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["duration_seconds"] == 2.3
        assert metadata["started_at"] == "2025-12-23T10:30:00"

    def test_getitem_preserves_none_values(self):
        """Test __getitem__ correctly returns None values"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            error=None,
            error_detail=None,
            description=None,
        )

        assert result["error"] is None
        assert result["error_detail"] is None
        assert result["description"] is None

    def test_getitem_mixed_valid_and_invalid(self):
        """Test __getitem__ with mix of valid and invalid fields"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            message="Message",
        )

        # Valid field works
        assert result["message"] == "Message"

        # Invalid field raises KeyError
        with pytest.raises(KeyError):
            _ = result["nonexistent"]

        # Can still access valid fields after error
        assert result["step"] == "test_step"


class TestStepResultToDict:
    """Test to_dict() serialization"""

    def test_to_dict_basic(self):
        """Test to_dict() with basic StepResult"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            message="Test message",
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["status"] == StepStatus.SUCCESS.value
        assert result_dict["step"] == "test_step"
        assert result_dict["message"] == "Test message"
        assert result_dict["description"] is None
        assert result_dict["stats"] == {}
        assert result_dict["details"] is None
        assert result_dict["error"] is None
        assert result_dict["error_detail"] is None
        assert result_dict["metadata"] == {}

    def test_to_dict_with_all_fields(self):
        """Test to_dict() with all fields populated"""
        result = StepResult(
            status=StepStatus.WARNING,
            step="retrieve_metadata",
            message="Retrieved 85/100 papers",
            description="Fetch DOI metadata",
            stats={"processed": 100, "created": 85, "errors": 15},
            details="Failed citations: Smith2020, Johnson2019",
            error=None,
            error_detail=None,
            metadata={"duration_seconds": 45.2, "api_calls": 100},
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "warning"
        assert result_dict["step"] == "retrieve_metadata"
        assert result_dict["message"] == "Retrieved 85/100 papers"
        assert result_dict["description"] == "Fetch DOI metadata"
        assert result_dict["stats"] == {"processed": 100, "created": 85, "errors": 15}
        assert result_dict["details"] == "Failed citations: Smith2020, Johnson2019"
        assert result_dict["metadata"] == {"duration_seconds": 45.2, "api_calls": 100}

    def test_to_dict_status_enum_conversion(self):
        """Test that status enum is converted to string value in to_dict()"""
        for status in [
            StepStatus.SUCCESS,
            StepStatus.WARNING,
            StepStatus.ERROR,
            StepStatus.HALTED,
        ]:
            result = StepResult(status=status, step="test")
            result_dict = result.to_dict()

            assert isinstance(result_dict["status"], str)
            assert result_dict["status"] == status.value

    def test_to_dict_with_error_fields(self):
        """Test to_dict() with error status and error fields"""
        result = StepResult(
            status=StepStatus.ERROR,
            step="export",
            message="Export failed",
            error="Permission denied",
            error_detail="Traceback: ...",
            stats={"processed": 0, "errors": 1},
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "error"
        assert result_dict["error"] == "Permission denied"
        assert result_dict["error_detail"] == "Traceback: ..."
        assert result_dict["stats"]["errors"] == 1

    def test_to_dict_returns_dict_not_dataclass(self):
        """Test that to_dict() returns a dict, not a dataclass instance"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test",
            message="Original",
            stats={"count": 5},
            metadata={"key": "value"},
        )

        result_dict = result.to_dict()

        # Result dict is a plain dict, not StepResult
        assert isinstance(result_dict, dict)
        assert not isinstance(result_dict, StepResult)

        # Can modify the returned dict independently
        result_dict["message"] = "Modified"
        assert result_dict["message"] == "Modified"
        assert result.message == "Original"  # Original unchanged

    def test_to_dict_preserves_status_value(self):
        """Test that to_dict() converts enum status to string value"""
        result = StepResult(
            status=StepStatus.WARNING,
            step="test",
        )

        result_dict = result.to_dict()

        # Status should be string value, not enum
        assert result_dict["status"] == "warning"
        assert isinstance(result_dict["status"], str)

        # But original should still be enum
        assert isinstance(result.status, StepStatus)


class TestStepResultStatuses:
    """Test different StepStatus values"""

    def test_all_step_statuses(self):
        """Test creating StepResult with each status"""
        statuses = [
            StepStatus.SUCCESS,
            StepStatus.WARNING,
            StepStatus.ERROR,
            StepStatus.HALTED,
        ]

        for status in statuses:
            result = StepResult(status=status, step="test")
            assert result.status == status
            assert result["status"] == status

    def test_success_status(self):
        """Test SUCCESS status semantics"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="bibtex_import",
            message="Imported 42 papers",
            stats={"processed": 42, "created": 42, "errors": 0},
        )

        assert result.status == StepStatus.SUCCESS
        assert result.stats["errors"] == 0

    def test_warning_status(self):
        """Test WARNING status semantics"""
        result = StepResult(
            status=StepStatus.WARNING,
            step="retrieve_metadata",
            message="Retrieved 85/100 papers",
            stats={"processed": 100, "created": 85, "errors": 15},
            details="15 papers failed DOI lookup",
        )

        assert result.status == StepStatus.WARNING
        assert result.stats["errors"] > 0
        assert result.details is not None

    def test_error_status(self):
        """Test ERROR status semantics"""
        result = StepResult(
            status=StepStatus.ERROR,
            step="export",
            message="Failed to write file",
            error="Permission denied",
            stats={"processed": 0, "errors": 1},
        )

        assert result.status == StepStatus.ERROR
        assert result.error is not None


class TestStepResultFlexibleDicts:
    """Test flexible stats and metadata dicts"""

    def test_custom_stats_keys(self):
        """Test adding custom keys to stats dict"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="custom_step",
            stats={
                "processed": 100,
                "created": 90,
                "skipped": 5,
                "warnings": 5,
                "custom_metric": 42,
            },
        )

        assert result.stats["processed"] == 100
        assert result.stats["custom_metric"] == 42

    def test_custom_metadata_keys(self):
        """Test adding custom keys to metadata dict"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="custom_step",
            metadata={
                "duration_seconds": 2.5,
                "duration_ms": 2500,
                "api_calls": 10,
                "cache_hits": 5,
                "custom_field": "value",
            },
        )

        assert result.metadata["duration_seconds"] == 2.5
        assert result.metadata["custom_field"] == "value"

    def test_empty_stats_and_metadata(self):
        """Test that empty stats and metadata default to empty dicts"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test",
        )

        assert result.stats == {}
        assert result.metadata == {}
        assert isinstance(result.stats, dict)
        assert isinstance(result.metadata, dict)

    def test_stats_and_metadata_isolation(self):
        """Test that stats and metadata are independent"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test",
            stats={"processed": 10},
            metadata={"duration": 5.0},
        )

        # Modify stats doesn't affect metadata
        result.stats["new_key"] = "value"
        assert "new_key" not in result.metadata

        # Modify metadata doesn't affect stats
        result.metadata["another_key"] = "value"
        assert "another_key" not in result.stats


class TestStepResultAttributeVsDict:
    """Test attribute access vs dict-like access"""

    def test_attribute_and_dict_access_same_value(self):
        """Test that attribute and dict access return same value"""
        result = StepResult(
            status=StepStatus.SUCCESS,
            step="test_step",
            message="Test message",
            stats={"count": 5},
        )

        # Attribute access
        assert result.status == StepStatus.SUCCESS
        assert result.message == "Test message"
        assert result.stats["count"] == 5

        # Dict-like access
        assert result["status"] == StepStatus.SUCCESS
        assert result["message"] == "Test message"
        assert result["stats"]["count"] == 5

    def test_prefer_attribute_access(self):
        """Demonstrate that attribute access is preferred"""
        result = StepResult(
            status=StepStatus.WARNING,
            step="test",
            message="Warning message",
        )

        # Both work, but attribute access is more Pythonic
        # Attribute access (preferred)
        status = result.status
        message = result.message

        # Dict-like access (backward compatible, but not preferred)
        status_dict = result["status"]
        message_dict = result["message"]

        assert status == status_dict
        assert message == message_dict
