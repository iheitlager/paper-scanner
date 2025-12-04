"""
PDF Browser Server - Web application for browsing and viewing PDFs with PostgreSQL backend.

Supports both local (port 8080) and Docker (port 8000) deployment.
"""

import argparse
import logging
import os
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS

from .config import Config, get_config
from .database import DatabaseManager
from .exceptions import (
    DatabaseException,
    FileNotFoundException,
    InvalidDataException,
    PDFNotFoundException,
)
from .http_handlers import register_error_handlers

# Logging
logger = logging.getLogger(__name__)


def create_app(config: Optional[Config] = None) -> Tuple[Flask, DatabaseManager, Config]:
    """Create and configure the Flask application.
    
    Args:
        config: Config instance (default: loaded from environment)
    
    Returns:
        Tuple of (Flask app, DatabaseManager instance, Config instance)
    """
    # Load config if not provided
    if config is None:
        config = get_config()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.debug(f"Loaded configuration: {config}")

    # Initialize Flask app with static folder configuration
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    CORS(app)

    # Store config in app context for route access
    app.config['DATABASE_URL'] = config.database_url
    app.config['PDF_BASE_DIR'] = config.pdf_base_dir
    app.config['ENV_MODE'] = config.env
    app.config['DEBUG'] = config.debug

    # Initialize database manager
    db_manager = DatabaseManager(config.database_url)

    # Register HTTP error handlers
    register_error_handlers(app)

    # Register routes
    @app.route("/health", methods=["GET"])
    def health() -> Tuple[Dict[str, Any], int]:
        """Health check endpoint.
        
        Returns:
            JSON response with health status and environment
        """
        try:
            db_manager.get_connection()
            return jsonify({"status": "ok", "environment": app.config['ENV_MODE']}), 200
        except DatabaseException as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/files", methods=["GET"])
    def get_files() -> Tuple[Dict[str, Any], int]:
        """Get list of all PDF files from database.
        
        Query parameters:
            directory: Optional directory filter
            
        Returns:
            JSON response with list of PDF files
        """
        try:
            directory = request.args.get("directory")
            files = db_manager.get_all_pdfs(directory)
            return jsonify({"success": True, "files": files}), 200
        except DatabaseException:
            raise

    @app.route("/api/load-jsonlines", methods=["POST"])
    def load_jsonlines() -> Tuple[Dict[str, Any], int]:
        """Load PDF records from the request body into the database.
        
        Expected JSON:
            {
                "records": [
                    {
                        "file_path": str,
                        "file_name": str,
                        "directory": str,
                        "size_bytes": int,
                        "created_time": str,
                        "modified_time": str,
                        "accessed_time": str,
                        "title-details": dict (optional),
                        "analysis": dict (optional),
                        "references": dict (optional, with extraction results)
                    }
                ]
            }
        
        Returns:
            JSON response with loaded/failed counts
        """
        try:
            data = request.get_json()
            if not data:
                raise InvalidDataException("Request body must be JSON")

            records = data.get("records", [])
            if not records:
                raise InvalidDataException("No records provided in request")

            loaded_count = 0
            failed_count = 0
            references_count = 0

            for idx, record in enumerate(records):
                try:
                    db_manager.insert_pdf_record(record)
                    loaded_count += 1
                    
                    # If references are present, insert them into the database
                    if "references" in record and record["references"]:
                        try:
                            # Get the inserted paper's ID by file_name
                            pdf_record = db_manager.get_pdf_by_file_name(record["file_name"])
                            if pdf_record:
                                db_manager.insert_references(pdf_record["id"], record["references"])
                                references_count += len(record.get("references", {}).get("references", []))
                        except DatabaseException as e:
                            logger.warning(f"Failed to insert references for record {idx}: {e}")
                            # Continue without references; don't fail the paper insertion

                except (InvalidDataException, DatabaseException) as e:
                    logger.warning(f"Failed to insert record {idx}: {e}")
                    failed_count += 1

            return jsonify({
                "success": True,
                "loaded": loaded_count,
                "failed": failed_count,
                "total": loaded_count + failed_count,
                "references_loaded": references_count,
            }), 200
        except InvalidDataException:
            raise

    @app.route("/api/file_details/<file_name>", methods=["GET"])
    def get_file_details(file_name: str) -> Tuple[Dict[str, Any], int]:
        """Get file details by name.
        
        Args:
            file_name: Name of the PDF file
            
        Returns:
            JSON response with file details
        """
        try:
            pdf_record = db_manager.get_pdf_by_file_name(file_name)
            if not pdf_record:
                raise PDFNotFoundException(file_name)

            return jsonify({"success": True, "details": pdf_record}), 200
        except DatabaseException:
            raise

    @app.route("/api/tags", methods=["GET"])
    def get_tags() -> Tuple[Dict[str, Any], int]:
        """Get all unique tags from database.
        
        Returns:
            JSON response with list of tags
        """
        try:
            tags = db_manager.get_all_tags()
            return jsonify({"success": True, "tags": tags}), 200
        except DatabaseException:
            raise

    @app.route("/api/year-overview", methods=["GET"])
    def get_year_overview() -> Tuple[Dict[str, Any], int]:
        """Get overview of papers grouped by publication year.
        
        Returns:
            JSON response with year statistics
        """
        try:
            year_data = db_manager.get_year_overview()
            return jsonify({"success": True, "years": year_data}), 200
        except DatabaseException:
            raise

    @app.route("/api/file_tags/<file_name>", methods=["PUT"])
    def update_file_tags(file_name: str) -> Tuple[Dict[str, Any], int]:
        """Update tags for a PDF file.
        
        Args:
            file_name: Name of the PDF file
            
        Expected JSON:
            {
                "tags": "tag1:tag2:tag3"
            }
        
        Returns:
            JSON response with success status
        """
        try:
            data = request.get_json()
            if not data:
                raise InvalidDataException("Request body must be JSON")

            tags = data.get("tags", "")

            # Verify file exists
            pdf_record = db_manager.get_pdf_by_file_name(file_name)
            if not pdf_record:
                raise PDFNotFoundException(file_name)

            db_manager.update_pdf_tags(file_name, tags)
            return jsonify({"success": True, "message": "Tags updated successfully"}), 200
        except (DatabaseException, InvalidDataException, PDFNotFoundException):
            raise

    @app.route("/api/references/<file_name>", methods=["GET"])
    def get_references(file_name: str) -> Tuple[Dict[str, Any], int]:
        """Get all references for a specific paper.
        
        Args:
            file_name: Name of the PDF file
            
        Returns:
            JSON response with list of references
        """
        try:
            pdf_record = db_manager.get_pdf_by_file_name(file_name)
            if not pdf_record:
                raise PDFNotFoundException(file_name)

            references = db_manager.get_references_for_paper(pdf_record["id"])
            
            # Parse JSONB fields back to objects for JSON response
            for ref in references:
                if ref.get("authors") and isinstance(ref["authors"], str):
                    try:
                        ref["authors"] = json.loads(ref["authors"])
                    except json.JSONDecodeError:
                        pass
            
            return jsonify({"success": True, "references": references}), 200
        except (DatabaseException, PDFNotFoundException):
            raise

    @app.route("/api/pdf/<file_name>", methods=["GET"])
    def get_pdf(file_name: str) -> Tuple[Any, int]:
        """Serve a PDF file by name.
        
        Args:
            file_name: Name of the PDF file
            
        Returns:
            PDF file or JSON error response
        """
        try:
            pdf_record = db_manager.get_pdf_by_file_name(file_name)
            if not pdf_record:
                raise PDFNotFoundException(file_name)

            file_path: str = pdf_record["file_path"]

            # In Docker, translate paths from host machine to container paths
            if app.config['ENV_MODE'] == "docker":
                if file_path.startswith("/Users/iheitlager/wc/papers"):
                    file_path = file_path.replace("/Users/iheitlager/wc/papers", "/papers", 1)
                elif file_path.startswith(app.config['PDF_BASE_DIR']):
                    file_path = file_path.replace(app.config['PDF_BASE_DIR'], "/papers", 1)

            logger.info(f"Looking for PDF at path: {file_path} (ENV: {app.config['ENV_MODE']})")

            if not os.path.exists(file_path):
                logger.error(f"PDF file not found on disk at: {file_path}")
                raise FileNotFoundException(file_path)

            return send_file(file_path, mimetype="application/pdf"), 200
        except (DatabaseException, PDFNotFoundException, FileNotFoundException):
            raise

    @app.route("/", methods=["GET"])
    def index() -> str:
        """Render the main HTML interface.
        
        Returns:
            Rendered HTML template
        """
        return render_template("index.html", pdf_base_dir=app.config['PDF_BASE_DIR'])

    return app, db_manager, config


# Application instance for WSGI servers (gunicorn, etc.)
# Lazy initialization to avoid database connection at import time
_app = None
_db_manager = None
_config = None


def get_app():
    """Get or create the Flask app instance (lazy initialization)."""
    global _app, _db_manager, _config
    if _app is None:
        _app, _db_manager, _config = create_app()
    return _app


# For gunicorn WSGI compatibility, create a callable app object
class AppProxy:
    """Lazy proxy for Flask app to defer initialization until first request."""
    
    def __init__(self):
        self._app = None
    
    def __call__(self, environ, start_response):
        """WSGI interface - initialize app on first call."""
        if self._app is None:
            self._app, _, _ = create_app()
        return self._app(environ, start_response)
    
    def __getattr__(self, name):
        """Delegate attribute access to the actual app."""
        if self._app is None:
            self._app, _, _ = create_app()
        return getattr(self._app, name)


app = AppProxy()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="PDF Browser Server - Browse and view PDFs with metadata"
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection URL (default: env var DATABASE_URL)",
    )
    parser.add_argument(
        "--pdf-dir",
        help="Base directory for PDF files (default: env var PDF_BASE_DIR)",
    )
    parser.add_argument(
        "--env",
        choices=["local", "docker", "production"],
        help="Environment mode (default: env var ENV)",
    )
    parser.add_argument(
        "--host",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to bind to (default: 8080)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_args()

    # Load .env file if specified
    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file)
        logger.info(f"Loaded environment from {args.env_file}")

    # Build config from args, env vars, and defaults
    app_config = get_config(
        database_url=args.database_url,
        pdf_base_dir=args.pdf_dir,
        env=args.env,
        host=args.host,
        port=args.port,
        debug=args.debug,
        log_level=args.log_level,
    )

    # Recreate app with CLI config
    app, db_manager, config = create_app(app_config)

    # Initialize database on startup
    try:
        db_manager.init_database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Run Flask app
    logger.info(f"Starting PDF Browser on {config.host}:{config.port} (ENV: {config.env})")
    app.run(host=config.host, port=config.port, debug=config.debug)
