#!/usr/bin/env python3

"""Unit tests for exceptions module."""

import pytest

from paper_scanner.web.exceptions import (
    DatabaseException,
    FileNotFoundException,
    InvalidDataException,
    PDFBrowserException,
    PDFNotFoundException,
)


class TestPDFBrowserException:
    """Tests for PDFBrowserException base class."""

    def test_initialization_with_message(self):
        """Test initializing exception with message."""
        message = "Test error message"
        exception = PDFBrowserException(message)
        assert exception.message == message
        assert str(exception) == message

    def test_initialization_with_status_code(self):
        """Test initializing exception with custom status code."""
        message = "Test error"
        status_code = 503
        exception = PDFBrowserException(message, status_code=status_code)
        assert exception.message == message
        assert exception.status_code == status_code

    def test_default_status_code(self):
        """Test that default status code is 500."""
        exception = PDFBrowserException("Test error")
        assert exception.status_code == 500

    def test_exception_is_base_exception(self):
        """Test that PDFBrowserException extends Exception."""
        exception = PDFBrowserException("Test")
        assert isinstance(exception, Exception)

    def test_message_preserved_in_args(self):
        """Test that message is preserved in exception args."""
        message = "Error message"
        exception = PDFBrowserException(message)
        assert message in str(exception)


class TestDatabaseException:
    """Tests for DatabaseException."""

    def test_is_pdf_browser_exception(self):
        """Test that DatabaseException is a PDFBrowserException."""
        exception = DatabaseException("Database error")
        assert isinstance(exception, PDFBrowserException)

    def test_initialization(self):
        """Test initializing DatabaseException."""
        message = "Connection failed"
        exception = DatabaseException(message)
        assert exception.message == message
        assert exception.status_code == 500

    def test_custom_status_code(self):
        """Test custom status code for DatabaseException."""
        exception = DatabaseException("Error", status_code=503)
        assert exception.status_code == 503

    def test_string_representation(self):
        """Test string representation of DatabaseException."""
        message = "Database error"
        exception = DatabaseException(message)
        assert str(exception) == message


class TestInvalidDataException:
    """Tests for InvalidDataException."""

    def test_is_pdf_browser_exception(self):
        """Test that InvalidDataException is a PDFBrowserException."""
        exception = InvalidDataException("Invalid data")
        assert isinstance(exception, PDFBrowserException)

    def test_initialization(self):
        """Test initializing InvalidDataException."""
        message = "Missing required fields"
        exception = InvalidDataException(message)
        assert exception.message == message
        assert exception.status_code == 400

    def test_status_code_is_bad_request(self):
        """Test that status code is 400 (Bad Request)."""
        exception = InvalidDataException("Invalid data")
        assert exception.status_code == 400

    def test_status_code_always_400(self):
        """Test that InvalidDataException always has status code 400."""
        exception = InvalidDataException("Invalid data")
        assert exception.status_code == 400


class TestFileNotFoundException:
    """Tests for FileNotFoundException."""

    def test_is_pdf_browser_exception(self):
        """Test that FileNotFoundException is a PDFBrowserException."""
        exception = FileNotFoundException("/path/to/file")
        assert isinstance(exception, PDFBrowserException)

    def test_initialization(self):
        """Test initializing FileNotFoundException."""
        file_path = "/path/to/missing/file.pdf"
        exception = FileNotFoundException(file_path)
        assert file_path in exception.message
        assert "File not found on disk" in exception.message
        assert exception.status_code == 404

    def test_status_code_is_not_found(self):
        """Test that status code is 404 (Not Found)."""
        exception = FileNotFoundException("/some/path")
        assert exception.status_code == 404

    def test_message_contains_path(self):
        """Test that exception message contains file path."""
        file_path = "/Users/test/document.pdf"
        exception = FileNotFoundException(file_path)
        assert file_path in str(exception)


class TestPDFNotFoundException:
    """Tests for PDFNotFoundException."""

    def test_is_pdf_browser_exception(self):
        """Test that PDFNotFoundException is a PDFBrowserException."""
        exception = PDFNotFoundException("document.pdf")
        assert isinstance(exception, PDFBrowserException)

    def test_initialization(self):
        """Test initializing PDFNotFoundException."""
        file_name = "document.pdf"
        exception = PDFNotFoundException(file_name)
        assert file_name in exception.message
        assert "PDF not found" in exception.message
        assert exception.status_code == 404

    def test_status_code_is_not_found(self):
        """Test that status code is 404 (Not Found)."""
        exception = PDFNotFoundException("missing.pdf")
        assert exception.status_code == 404

    def test_message_contains_filename(self):
        """Test that exception message contains file name."""
        file_name = "research_paper.pdf"
        exception = PDFNotFoundException(file_name)
        assert file_name in str(exception)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and inheritance."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all exceptions inherit from PDFBrowserException."""
        exceptions = [
            DatabaseException("test"),
            InvalidDataException("test"),
            FileNotFoundException("test"),
            PDFNotFoundException("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, PDFBrowserException)

    def test_exception_catching_by_base_class(self):
        """Test that exceptions can be caught by base class."""
        with pytest.raises(PDFBrowserException):
            raise DatabaseException("Database error")

        with pytest.raises(PDFBrowserException):
            raise InvalidDataException("Invalid data")

        with pytest.raises(PDFBrowserException):
            raise FileNotFoundException("File not found")

        with pytest.raises(PDFBrowserException):
            raise PDFNotFoundException("PDF not found")

    def test_exception_specific_catching(self):
        """Test that exceptions can be caught by specific class."""
        with pytest.raises(DatabaseException):
            raise DatabaseException("Database error")

        with pytest.raises(InvalidDataException):
            raise InvalidDataException("Invalid data")

        with pytest.raises(FileNotFoundException):
            raise FileNotFoundException("File path")

        with pytest.raises(PDFNotFoundException):
            raise PDFNotFoundException("File name")

    def test_status_codes_by_exception_type(self):
        """Test that each exception type has correct status code."""
        assert DatabaseException("test").status_code == 500
        assert InvalidDataException("test").status_code == 400
        assert FileNotFoundException("test").status_code == 404
        assert PDFNotFoundException("test").status_code == 404


class TestExceptionMessages:
    """Tests for exception message handling."""

    def test_message_with_special_characters(self):
        """Test handling of special characters in messages."""
        message = "Error: 'quoted' \"string\" with\\special chars"
        exception = PDFBrowserException(message)
        assert exception.message == message

    def test_message_with_unicode(self):
        """Test handling of unicode characters in messages."""
        message = "Error: файл не найден 文件未找到"
        exception = PDFBrowserException(message)
        assert exception.message == message

    def test_long_message(self):
        """Test handling of long messages."""
        message = "A" * 1000
        exception = PDFBrowserException(message)
        assert exception.message == message
        assert len(exception.message) == 1000

    def test_empty_message(self):
        """Test handling of empty message."""
        exception = PDFBrowserException("")
        assert exception.message == ""
        assert str(exception) == ""
