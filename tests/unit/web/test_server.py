"""
Comprehensive tests for Flask server module.

Tests cover:
- Flask app creation and configuration
- Route handlers (GET, POST, PUT)
- Error handling and status codes
- JSON response formatting
- File serving and path translation
- Database integration
"""

from unittest.mock import Mock, patch

import pytest
from flask import Flask

from paper_scanner.web.config import Config
from paper_scanner.web.exceptions import (DatabaseException,
                                          InvalidDataException)
from paper_scanner.web.server import create_app, parse_args


class TestCreateApp:
    """Test Flask application factory."""

    def test_create_app_returns_tuple(self):
        """Test that create_app returns (Flask, DatabaseManager, Config) tuple."""
        with patch("paper_scanner.web.server.get_config") as mock_get_config:
            mock_config = Mock(spec=Config)
            mock_config.log_level = "INFO"
            mock_config.debug = False
            mock_config.database_url = "postgresql://localhost/test"
            mock_config.pdf_base_dir = "/path/to/pdfs"
            mock_config.env = "local"
            mock_get_config.return_value = mock_config

            result = create_app()

            assert isinstance(result, tuple)
            assert len(result) == 3
            app, db_manager, config = result
            assert isinstance(app, Flask)
            assert config == mock_config

    def test_create_app_with_provided_config(self):
        """Test that create_app uses provided config."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "DEBUG"
        mock_config.debug = True
        mock_config.database_url = "postgresql://custom/db"
        mock_config.pdf_base_dir = "/custom/path"
        mock_config.env = "docker"

        with patch("paper_scanner.web.server.get_config") as mock_get_config:
            app, db_manager, config = create_app(mock_config)

            # get_config should NOT be called when config is provided
            mock_get_config.assert_not_called()
            assert config == mock_config

    def test_create_app_configures_flask(self):
        """Test that create_app properly configures Flask app."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        assert app.config["DATABASE_URL"] == "postgresql://localhost/test"
        assert app.config["PDF_BASE_DIR"] == "/path/to/pdfs"
        assert app.config["ENV_MODE"] == "local"
        assert app.config["DEBUG"] is False

    def test_create_app_registers_error_handlers(self):
        """Test that error handlers are registered."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        with patch("paper_scanner.web.server.register_error_handlers") as mock_register:
            create_app(mock_config)
            mock_register.assert_called_once()

    def test_create_app_initializes_database_manager(self):
        """Test that DatabaseManager is initialized."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        assert db_manager is not None
        assert db_manager.db_url == "postgresql://localhost/test"

    def test_create_app_routes_registered(self):
        """Test that all routes are registered."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        # Check that routes exist
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/health" in routes
        assert "/api/files" in routes
        assert "/api/load-jsonlines" in routes
        assert "/api/file_details/<file_name>" in routes
        assert "/api/tags" in routes
        assert "/api/file_tags/<file_name>" in routes
        assert "/api/pdf/<file_name>" in routes
        assert "/" in routes


class TestHealthRoute:
    """Test /health route."""

    def test_health_check_success(self):
        """Test health check with successful database connection."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_connection"):
            client = app.test_client()
            response = client.get("/health")

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ok"
            assert data["environment"] == "local"

    def test_health_check_database_error(self):
        """Test health check with database error."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "docker"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_connection", side_effect=DatabaseException("Connection failed")):
            client = app.test_client()
            response = client.get("/health")

            assert response.status_code == 500
            data = response.get_json()
            assert data["status"] == "error"
            assert "Connection failed" in data["message"]


class TestFilesRoute:
    """Test /api/files route."""

    def test_get_files_no_filter(self):
        """Test retrieving all files without directory filter."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_files = [
            {"file_name": "file1.pdf", "file_path": "/path/file1.pdf"},
            {"file_name": "file2.pdf", "file_path": "/path/file2.pdf"},
        ]
        with patch.object(db_manager, "get_all_pdfs", return_value=mock_files):
            client = app.test_client()
            response = client.get("/api/files")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["files"] == mock_files

    def test_get_files_with_directory_filter(self):
        """Test retrieving files with directory filter."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_files = [
            {"file_name": "file1.pdf", "file_path": "/docs/file1.pdf", "directory": "/docs"},
        ]
        with patch.object(db_manager, "get_all_pdfs", return_value=mock_files) as mock_get:
            client = app.test_client()
            response = client.get("/api/files?directory=/docs")

            assert response.status_code == 200
            mock_get.assert_called_once_with("/docs")

    def test_get_files_empty(self):
        """Test retrieving files when database is empty."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_all_pdfs", return_value=[]):
            client = app.test_client()
            response = client.get("/api/files")

            assert response.status_code == 200
            data = response.get_json()
            assert data["files"] == []

    def test_get_files_database_error(self):
        """Test error handling when database fails."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_all_pdfs", side_effect=DatabaseException("Query failed")):
            client = app.test_client()
            response = client.get("/api/files")

            assert response.status_code == 500


class TestLoadJsonLinesRoute:
    """Test /api/load-jsonlines POST route."""

    def test_load_jsonlines_success(self):
        """Test successfully loading PDF records."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "insert_pdf_record"):
            client = app.test_client()
            payload = {
                "records": [
                    {
                        "file_path": "/path/file1.pdf",
                        "file_name": "file1.pdf",
                        "directory": "/path",
                    },
                    {
                        "file_path": "/path/file2.pdf",
                        "file_name": "file2.pdf",
                        "directory": "/path",
                    },
                ]
            }
            response = client.post("/api/load-jsonlines", json=payload)

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["loaded"] == 2
            assert data["failed"] == 0
            assert data["total"] == 2

    def test_load_jsonlines_partial_failure(self):
        """Test loading records with some failures."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        def insert_side_effect(record):
            if record["file_name"] == "bad.pdf":
                raise InvalidDataException("Invalid record")

        with patch.object(db_manager, "insert_pdf_record", side_effect=insert_side_effect):
            client = app.test_client()
            payload = {
                "records": [
                    {
                        "file_path": "/path/file1.pdf",
                        "file_name": "file1.pdf",
                        "directory": "/path",
                    },
                    {
                        "file_path": "/path/bad.pdf",
                        "file_name": "bad.pdf",
                        "directory": "/path",
                    },
                ]
            }
            response = client.post("/api/load-jsonlines", json=payload)

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["loaded"] == 1
            assert data["failed"] == 1
            assert data["total"] == 2

    def test_load_jsonlines_no_request_body(self):
        """Test error when no request body provided."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        client = app.test_client()
        response = client.post("/api/load-jsonlines")

        # Flask returns 415 for missing Content-Type
        assert response.status_code in (400, 415)

    def test_load_jsonlines_empty_records(self):
        """Test error when no records provided."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        client = app.test_client()
        response = client.post("/api/load-jsonlines", json={"records": []})

        assert response.status_code == 400


class TestFileDetailsRoute:
    """Test /api/file_details/<file_name> route."""

    def test_get_file_details_success(self):
        """Test retrieving file details successfully."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_details = {
            "file_name": "paper.pdf",
            "file_path": "/path/paper.pdf",
            "title": "Sample Paper",
        }
        with patch.object(db_manager, "get_pdf_by_file_name", return_value=mock_details):
            client = app.test_client()
            response = client.get("/api/file_details/paper.pdf")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["details"] == mock_details

    def test_get_file_details_not_found(self):
        """Test error when file details not found."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_pdf_by_file_name", return_value=None):
            client = app.test_client()
            response = client.get("/api/file_details/nonexistent.pdf")

            assert response.status_code == 404


class TestTagsRoute:
    """Test /api/tags route."""

    def test_get_tags_success(self):
        """Test retrieving all tags successfully."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_tags = ["machine learning", "python", "ai"]
        with patch.object(db_manager, "get_all_tags", return_value=mock_tags):
            client = app.test_client()
            response = client.get("/api/tags")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["tags"] == mock_tags

    def test_get_tags_empty(self):
        """Test retrieving tags when none exist."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_all_tags", return_value=[]):
            client = app.test_client()
            response = client.get("/api/tags")

            assert response.status_code == 200
            data = response.get_json()
            assert data["tags"] == []


class TestYearOverviewRoute:
    """Test /api/year-overview route."""

    def test_get_year_overview_success(self):
        """Test retrieving year overview successfully."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_year_data = [
            {
                "year": 2025,
                "count": 3,
                "papers": [
                    {"file_name": "paper1.pdf", "title": "Paper 1", "citekey": "P1"},
                    {"file_name": "paper2.pdf", "title": "Paper 2", "citekey": "P2"},
                    {"file_name": "paper3.pdf", "title": "Paper 3", "citekey": "P3"},
                ],
            },
            {
                "year": 2024,
                "count": 2,
                "papers": [
                    {"file_name": "paper4.pdf", "title": "Paper 4", "citekey": "P4"},
                    {"file_name": "paper5.pdf", "title": "Paper 5", "citekey": "P5"},
                ],
            },
        ]
        with patch.object(db_manager, "get_year_overview", return_value=mock_year_data):
            client = app.test_client()
            response = client.get("/api/year-overview")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["years"]) == 2
            assert data["years"][0]["year"] == 2025
            assert data["years"][0]["count"] == 3

    def test_get_year_overview_empty(self):
        """Test retrieving year overview when no years present."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_year_overview", return_value=[]):
            client = app.test_client()
            response = client.get("/api/year-overview")

            assert response.status_code == 200
            data = response.get_json()
            assert data["years"] == []


class TestUpdateFileTagsRoute:
    """Test /api/file_tags/<file_name> PUT route."""

    def test_update_file_tags_success(self):
        """Test successfully updating file tags."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_record = {"file_name": "paper.pdf", "file_path": "/path/paper.pdf"}

        with patch.object(db_manager, "get_pdf_by_file_name", return_value=mock_record):
            with patch.object(db_manager, "update_pdf_tags"):
                client = app.test_client()
                response = client.put("/api/file_tags/paper.pdf", json={"tags": "tag1:tag2"})

                assert response.status_code == 200
                data = response.get_json()
                assert data["success"] is True

    def test_update_file_tags_not_found(self):
        """Test error when file not found."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_pdf_by_file_name", return_value=None):
            client = app.test_client()
            response = client.put("/api/file_tags/nonexistent.pdf", json={"tags": "tag1"})

            assert response.status_code == 404

    def test_update_file_tags_no_body(self):
        """Test error when request body missing."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        client = app.test_client()
        response = client.put("/api/file_tags/paper.pdf")

        # Flask returns 415 for missing Content-Type
        assert response.status_code in (400, 415)


class TestPdfRoute:
    """Test /api/pdf/<file_name> route."""

    def test_get_pdf_success(self):
        """Test successfully serving a PDF file."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        # Create a temporary test file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        mock_record = {"file_name": "paper.pdf", "file_path": tmp_path}

        try:
            with patch.object(db_manager, "get_pdf_by_file_name", return_value=mock_record):
                client = app.test_client()
                response = client.get("/api/pdf/paper.pdf")

                assert response.status_code == 200
                assert response.content_type == "application/pdf"
        finally:
            import os

            os.unlink(tmp_path)

    def test_get_pdf_not_found_in_db(self):
        """Test error when PDF not found in database."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        with patch.object(db_manager, "get_pdf_by_file_name", return_value=None):
            client = app.test_client()
            response = client.get("/api/pdf/nonexistent.pdf")

            assert response.status_code == 404

    def test_get_pdf_not_found_on_disk(self):
        """Test error when PDF file not found on disk."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, db_manager, _ = create_app(mock_config)

        mock_record = {"file_name": "paper.pdf", "file_path": "/nonexistent/path/paper.pdf"}

        with patch.object(db_manager, "get_pdf_by_file_name", return_value=mock_record):
            client = app.test_client()
            response = client.get("/api/pdf/paper.pdf")

            assert response.status_code == 404

    def test_get_pdf_docker_path_translation(self):
        """Test PDF path translation in Docker environment."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/papers"
        mock_config.env = "docker"

        app, db_manager, _ = create_app(mock_config)

        # Create a temporary test file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        # Mock record with host path
        mock_record = {"file_name": "paper.pdf", "file_path": "/Users/iheitlager/wc/papers/paper.pdf"}

        try:
            with patch.object(db_manager, "get_pdf_by_file_name", return_value=mock_record):
                with patch("os.path.exists", return_value=True):
                    with patch("paper_scanner.web.server.send_file") as mock_send:
                        mock_send.return_value = ("", 200)
                        client = app.test_client()
                        response = client.get("/api/pdf/paper.pdf")

                        # Verify path translation occurred
                        call_args = mock_send.call_args[0]
                        assert "/papers/paper.pdf" in call_args[0]
        finally:
            import os

            os.unlink(tmp_path)


class TestIndexRoute:
    """Test / GET route."""

    def test_index_renders_template(self):
        """Test that index route renders HTML template."""
        mock_config = Mock(spec=Config)
        mock_config.log_level = "INFO"
        mock_config.debug = False
        mock_config.database_url = "postgresql://localhost/test"
        mock_config.pdf_base_dir = "/path/to/pdfs"
        mock_config.env = "local"

        app, _, _ = create_app(mock_config)

        with patch("paper_scanner.web.server.render_template", return_value="<html></html>") as mock_render:
            client = app.test_client()
            response = client.get("/")

            assert response.status_code == 200
            mock_render.assert_called_once()
            # Verify pdf_base_dir is passed to template
            call_kwargs = mock_render.call_args[1]
            assert call_kwargs["pdf_base_dir"] == "/path/to/pdfs"


class TestParseArgs:
    """Test command-line argument parsing."""

    def test_parse_args_defaults(self):
        """Test parse_args with no arguments."""
        with patch("sys.argv", ["server.py"]):
            args = parse_args()

            assert args.database_url is None
            assert args.pdf_dir is None
            assert args.env is None
            assert args.host is None
            assert args.port is None
            assert args.debug is False
            assert args.log_level is None
            assert args.env_file == ".env"

    def test_parse_args_with_values(self):
        """Test parse_args with all arguments."""
        with patch(
            "sys.argv",
            [
                "server.py",
                "--database-url",
                "postgresql://localhost/test",
                "--pdf-dir",
                "/path/to/pdfs",
                "--env",
                "docker",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--debug",
                "--log-level",
                "DEBUG",
                "--env-file",
                "/etc/.env",
            ],
        ):
            args = parse_args()

            assert args.database_url == "postgresql://localhost/test"
            assert args.pdf_dir == "/path/to/pdfs"
            assert args.env == "docker"
            assert args.host == "0.0.0.0"
            assert args.port == 8000
            assert args.debug is True
            assert args.log_level == "DEBUG"
            assert args.env_file == "/etc/.env"

    def test_parse_args_port_as_int(self):
        """Test that port argument is parsed as integer."""
        with patch("sys.argv", ["server.py", "--port", "5000"]):
            args = parse_args()

            assert args.port == 5000
            assert isinstance(args.port, int)

    def test_parse_args_env_choices(self):
        """Test that env argument accepts specific choices."""
        valid_envs = ["local", "docker", "production"]
        for env in valid_envs:
            with patch("sys.argv", ["server.py", "--env", env]):
                args = parse_args()
                assert args.env == env

    def test_parse_args_invalid_env(self):
        """Test that invalid env choice raises error."""
        with patch("sys.argv", ["server.py", "--env", "invalid"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_log_level_choices(self):
        """Test that log-level argument accepts specific choices."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            with patch("sys.argv", ["server.py", "--log-level", level]):
                args = parse_args()
                assert args.log_level == level
