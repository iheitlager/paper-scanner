"""Custom exceptions for PDF Browser application."""


class PDFBrowserException(Exception):
    """Base exception for PDF Browser application."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseException(PDFBrowserException):
    """Exception raised for database operations."""
    pass


class PDFNotFoundException(PDFBrowserException):
    """Exception raised when a PDF is not found."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"PDF not found: {identifier}", status_code=404)


class FileNotFoundException(PDFBrowserException):
    """Exception raised when a file is not found on disk."""

    def __init__(self, path: str) -> None:
        super().__init__(f"File not found on disk: {path}", status_code=404)


class InvalidDataException(PDFBrowserException):
    """Exception raised for invalid data."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
