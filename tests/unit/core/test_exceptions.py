"""
Tests for paper-scanner exception hierarchy.

This test suite documents and validates the exception interface:
- Inheritance hierarchy
- Exception raising and catching
- Message handling
- Backwards compatibility with external exceptions
"""

import pytest

from paper_scanner.core.exceptions import (
    CheckpointError,
    ConfigurationError,
    PaperScannerError,
    PipelineExecutionError,
    StepError,
)
from paper_scanner.steps.halt import HaltException
from paper_scanner.core.cache import CacheError


class TestPaperScannerError:
    """Tests for base PaperScannerError class."""

    def test_is_exception(self):
        """PaperScannerError should be an Exception."""
        assert issubclass(PaperScannerError, Exception)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch PaperScannerError."""
        with pytest.raises(PaperScannerError):
            raise PaperScannerError("Test error")

    def test_message_preserved(self):
        """Error message should be preserved."""
        message = "Custom error message"
        with pytest.raises(PaperScannerError) as exc_info:
            raise PaperScannerError(message)
        assert str(exc_info.value) == message

    def test_with_context(self):
        """Should support exception chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise PaperScannerError("Wrapped error") from e
        except PaperScannerError as e:
            assert e.__cause__.__class__ == ValueError


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_is_paper_scanner_error(self):
        """ConfigurationError should inherit from PaperScannerError."""
        assert issubclass(ConfigurationError, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch ConfigurationError."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Invalid config")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise ConfigurationError("Invalid config")

    def test_specific_catch_only(self):
        """Should not catch unrelated exceptions."""
        with pytest.raises(ValueError):
            try:
                raise ValueError("Different error")
            except ConfigurationError:
                pass


class TestStepError:
    """Tests for StepError."""

    def test_is_paper_scanner_error(self):
        """StepError should inherit from PaperScannerError."""
        assert issubclass(StepError, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch StepError."""
        with pytest.raises(StepError):
            raise StepError("Unknown step")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise StepError("Unknown step")


class TestCheckpointError:
    """Tests for CheckpointError."""

    def test_is_paper_scanner_error(self):
        """CheckpointError should inherit from PaperScannerError."""
        assert issubclass(CheckpointError, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch CheckpointError."""
        with pytest.raises(CheckpointError):
            raise CheckpointError("Checkpoint failed")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise CheckpointError("Checkpoint failed")


class TestPipelineExecutionError:
    """Tests for PipelineExecutionError."""

    def test_is_paper_scanner_error(self):
        """PipelineExecutionError should inherit from PaperScannerError."""
        assert issubclass(PipelineExecutionError, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch PipelineExecutionError."""
        with pytest.raises(PipelineExecutionError):
            raise PipelineExecutionError("Step failed")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise PipelineExecutionError("Step failed")


class TestHaltException:
    """Tests for HaltException (from steps.halt module)."""

    def test_is_paper_scanner_error(self):
        """HaltException should inherit from PaperScannerError."""
        assert issubclass(HaltException, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch HaltException."""
        with pytest.raises(HaltException):
            raise HaltException("Pipeline halted")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise HaltException("Pipeline halted")

    def test_backwards_compatibility(self):
        """HaltException should still be importable from halt module."""
        from paper_scanner.steps.halt import HaltException as OriginalHalt
        assert OriginalHalt is HaltException


class TestCacheError:
    """Tests for CacheError (from tools.cache module)."""

    def test_is_paper_scanner_error(self):
        """CacheError should inherit from PaperScannerError."""
        assert issubclass(CacheError, PaperScannerError)

    def test_can_raise_and_catch(self):
        """Should be able to raise and catch CacheError."""
        with pytest.raises(CacheError):
            raise CacheError("Cache operation failed")

    def test_caught_by_parent(self):
        """Should be caught by PaperScannerError handler."""
        with pytest.raises(PaperScannerError):
            raise CacheError("Cache operation failed")

    def test_backwards_compatibility(self):
        """CacheError should still be importable from cache module."""
        from paper_scanner.core.cache import CacheError as OriginalCache
        assert OriginalCache is CacheError


class TestExceptionHierarchy:
    """Tests for the overall exception hierarchy."""

    def test_all_custom_exceptions_inherit_from_base(self):
        """All custom exceptions should inherit from PaperScannerError."""
        exceptions = [
            ConfigurationError,
            StepError,
            CheckpointError,
            PipelineExecutionError,
            HaltException,
            CacheError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, PaperScannerError), (
                f"{exc_class.__name__} should inherit from PaperScannerError"
            )

    def test_catch_all_paper_scanner_errors(self):
        """Should be able to catch all paper-scanner errors with single handler."""
        exceptions = [
            ConfigurationError("config"),
            StepError("step"),
            CheckpointError("checkpoint"),
            PipelineExecutionError("pipeline"),
            HaltException("halt"),
            CacheError("cache"),
        ]

        for exc in exceptions:
            with pytest.raises(PaperScannerError):
                raise exc

    def test_catch_specific_error_type(self):
        """Should be able to catch specific error types without catching others."""
        with pytest.raises(StepError):
            try:
                raise StepError("step")
            except ConfigurationError:
                pass  # Should not catch StepError
            except StepError:
                raise

    def test_error_messages_preserved(self):
        """Error messages should be preserved through hierarchy."""
        test_cases = [
            (ConfigurationError, "Invalid step config"),
            (StepError, "Unknown step: foo"),
            (CheckpointError, "Corrupt checkpoint"),
            (PipelineExecutionError, "Step execution failed"),
            (HaltException, "Pipeline halted by user"),
            (CacheError, "Cache write failed"),
        ]

        for exc_class, message in test_cases:
            with pytest.raises(exc_class) as exc_info:
                raise exc_class(message)
            assert str(exc_info.value) == message


class TestExceptionChaining:
    """Tests for exception chaining with context."""

    def test_configuration_error_chaining(self):
        """ConfigurationError should support chaining."""
        try:
            try:
                raise ValueError("Malformed YAML")
            except ValueError as e:
                raise ConfigurationError("Failed to parse config") from e
        except ConfigurationError as e:
            assert isinstance(e.__cause__, ValueError)

    def test_step_error_chaining(self):
        """StepError should support chaining."""
        try:
            try:
                raise ImportError("Cannot import step module")
            except ImportError as e:
                raise StepError("Failed to instantiate step") from e
        except StepError as e:
            assert isinstance(e.__cause__, ImportError)

    def test_checkpoint_error_chaining(self):
        """CheckpointError should support chaining."""
        try:
            try:
                raise IOError("Cannot write to disk")
            except IOError as e:
                raise CheckpointError("Failed to save checkpoint") from e
        except CheckpointError as e:
            assert isinstance(e.__cause__, IOError)
