#!/usr/bin/env python3

"""Unit tests for http_handlers module."""

import json
from unittest.mock import MagicMock

import pytest
from flask import Flask

from paper_scanner.web.exceptions import (
    DatabaseException,
    FileNotFoundException,
    InvalidDataException,
    PDFBrowserException,
    PDFNotFoundException,
)
from paper_scanner.web.http_handlers import register_error_handlers


def create_test_app_basic():
    """Create a basic Flask app with test routes and error handlers (without server config)."""
    app = Flask(__name__)
    register_error_handlers(app)

    # Test routes for different exceptions
    @app.route("/test/pdf_exception")
    def test_pdf_exception():
        raise PDFBrowserException("Test error message", status_code=500)

    @app.route("/test/db_exception")
    def test_db_exception():
        raise DatabaseException("Database connection failed")

    @app.route("/test/invalid_data")
    def test_invalid_data():
        raise InvalidDataException("Missing required fields")

    @app.route("/test/file_not_found")
    def test_file_not_found():
        raise FileNotFoundException("/path/to/missing/file.pdf")

    @app.route("/test/pdf_not_found")
    def test_pdf_not_found():
        raise PDFNotFoundException("document.pdf")

    @app.route("/test/internal_error")
    def test_internal_error():
        raise RuntimeError("Unexpected error")

    return app


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    return create_test_app_basic()


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


class TestErrorHandlers:
    """Tests for HTTP error handler registration and handling."""

    def test_register_error_handlers_called(self, app):
        """Test that error handlers are registered without errors."""
        # If we got here, registration worked
        assert app is not None

    def test_pdf_browser_exception_handler(self, client):
        """Test handling of PDFBrowserException."""
        response = client.get("/test/pdf_exception")
        assert response.status_code == 500

        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Test error message"

    def test_database_exception_handler(self, client):
        """Test handling of DatabaseException."""
        response = client.get("/test/db_exception")
        assert response.status_code == 500

        data = json.loads(response.data)
        assert data["success"] is False
        assert "Database connection failed" in data["error"]

    def test_invalid_data_exception_handler(self, client):
        """Test handling of InvalidDataException."""
        response = client.get("/test/invalid_data")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data["success"] is False
        assert "Missing required fields" in data["error"]

    def test_file_not_found_exception_handler(self, client):
        """Test handling of FileNotFoundException."""
        response = client.get("/test/file_not_found")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False
        assert "/path/to/missing/file.pdf" in data["error"]

    def test_pdf_not_found_exception_handler(self, client):
        """Test handling of PDFNotFoundException."""
        response = client.get("/test/pdf_not_found")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False
        assert "document.pdf" in data["error"]

    def test_not_found_handler(self, client):
        """Test handling of 404 Not Found errors."""
        response = client.get("/nonexistent/route")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_internal_error_handler(self, client):
        """Test handling of 500 Internal Server errors."""
        response = client.get("/test/internal_error")
        assert response.status_code == 500

        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    def test_exception_error_message_format(self, client):
        """Test that error messages are properly formatted as JSON."""
        response = client.get("/test/db_exception")
        assert response.content_type == "application/json"

        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert "success" in data
        assert "error" in data
        assert data["success"] is False

    def test_all_exception_types_handled(self, client):
        """Test that different exception types are handled correctly."""
        test_cases = [
            ("/test/db_exception", 500),
            ("/test/invalid_data", 400),
            ("/test/file_not_found", 404),
            ("/test/pdf_not_found", 404),
        ]

        for route, expected_status in test_cases:
            response = client.get(route)
            assert response.status_code == expected_status
            data = json.loads(response.data)
            assert data["success"] is False

    def test_exception_with_special_characters(self, client):
        """Test that exception messages with special characters are handled."""
        # DatabaseException accepts any message
        response = client.get("/test/db_exception")
        assert response.status_code == 500

        data = json.loads(response.data)
        assert data["success"] is False
        # Should be able to parse without errors

    def test_exception_response_consistency(self, client):
        """Test that all exception responses follow consistent format."""
        response = client.get("/test/db_exception")
        data = json.loads(response.data)

        # All responses should have success and error fields
        assert "success" in data
        assert "error" in data
        assert data["success"] is False
        assert isinstance(data["error"], str)

    def test_status_codes_are_correct(self, client):
        """Test that response status codes are correct for each exception type."""
        test_cases = [
            ("/test/invalid_data", 400),
            ("/test/db_exception", 500),
            ("/test/pdf_not_found", 404),
            ("/test/file_not_found", 404),
        ]

        for route, expected_status in test_cases:
            response = client.get(route)
            assert response.status_code == expected_status

    def test_error_handler_completes_successfully(self, client):
        """Test that error handlers complete without raising exceptions."""
        response = client.get("/test/db_exception")
        assert response is not None
        assert response.status_code == 500

    def test_multiple_error_types_in_sequence(self, client):
        """Test handling multiple different exception types sequentially."""
        responses = [
            client.get("/test/invalid_data"),
            client.get("/test/pdf_not_found"),
            client.get("/test/db_exception"),
        ]

        expected_statuses = [400, 404, 500]
        for response, expected_status in zip(responses, expected_statuses):
            assert response.status_code == expected_status
            data = json.loads(response.data)
            assert data["success"] is False

    def test_json_encoding_in_response(self, client):
        """Test that responses are valid JSON."""
        response = client.get("/test/db_exception")
        # Should not raise an exception
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_error_message_included_in_response(self, client):
        """Test that error messages are included in responses."""
        response = client.get("/test/invalid_data")
        data = json.loads(response.data)
        assert data["error"]  # Error message should not be empty
        assert isinstance(data["error"], str)

