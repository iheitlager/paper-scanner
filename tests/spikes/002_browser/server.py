"""
PDF Browser Server - Web application for browsing and viewing PDFs with PostgreSQL backend.

Supports both local (port 8080) and Docker (port 8000) deployment.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from psycopg2 import OperationalError, connect
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extras import RealDictCursor

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
)
PDF_BASE_DIR = os.getenv("PDF_BASE_DIR", "/Users/iheitlager/wc/papers")
PORT = int(os.getenv("PORT", 8080))
ENV = os.getenv("ENV", "local")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app with static folder configuration
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)


# Custom Exceptions
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


class DatabaseManager:
    """Manages PostgreSQL connections and operations."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def get_connection(self, retries: int = 3, delay: int = 2) -> PsycopgConnection:
        """Get a database connection with retry logic.
        
        Args:
            retries: Number of retry attempts
            delay: Delay in seconds between retries
            
        Returns:
            PostgreSQL connection object
            
        Raises:
            DatabaseException: If connection fails after all retries
        """
        for attempt in range(retries):
            try:
                return connect(self.db_url)
            except (OperationalError, Exception) as e:
                if attempt < retries - 1:
                    logger.warning(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    error_msg = f"Database connection failed after {retries} attempts: {e}"
                    logger.error(error_msg)
                    raise DatabaseException(error_msg)

    def init_database(self) -> None:
        """Verify database schema is initialized (done by init-db.sql in Docker)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'papers'"
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                logger.info("Database schema verified successfully")
            else:
                logger.warning("PDF files table not found - will be created on first initialization")
        except Exception as e:
            logger.error(f"Failed to verify database schema: {e}")
            raise DatabaseException(f"Database initialization failed: {e}")

    def insert_pdf_record(self, record: Dict[str, Any]) -> bool:
        """Insert a PDF record into the database.
        
        Args:
            record: Dictionary containing PDF metadata
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            InvalidDataException: If required fields are missing
        """
        required_fields = ["file_path", "file_name", "directory"]
        if not all(field in record for field in required_fields):
            raise InvalidDataException(f"Missing required fields: {required_fields}")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO papers 
                (file_path, file_name, directory, size_bytes, 
                 created_time, modified_time, accessed_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    modified_time = EXCLUDED.modified_time,
                    accessed_time = EXCLUDED.accessed_time
                """,
                (
                    record["file_path"],
                    record["file_name"],
                    record["directory"],
                    record.get("size_bytes"),
                    record.get("created_time"),
                    record.get("modified_time"),
                    record.get("accessed_time"),
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to insert record: {e}")
            raise DatabaseException(f"Failed to insert PDF record: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_all_pdfs(self, directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all PDF records from database.
        
        Args:
            directory: Optional directory filter
            
        Returns:
            List of PDF records
            
        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            if directory:
                cursor.execute(
                    "SELECT * FROM papers WHERE directory = %s ORDER BY file_name",
                    (directory,),
                )
            else:
                cursor.execute("SELECT * FROM papers ORDER BY file_name")

            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch PDFs: {e}")
            raise DatabaseException(f"Failed to fetch PDF records: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_pdf_by_file_name(self, file_name: str) -> Optional[Dict[str, Any]]:
        """Get PDF record by file name.
        
        Args:
            file_name: Name of the PDF file
            
        Returns:
            PDF record dictionary or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("SELECT * FROM papers WHERE file_name = %s", (file_name,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to fetch PDF by file name: {e}")
            raise DatabaseException(f"Failed to fetch PDF record: {e}")
        finally:
            cursor.close()
            conn.close()


# Initialize database manager
db_manager = DatabaseManager(DATABASE_URL)


# Centralized Error Handler
@app.errorhandler(PDFBrowserException)
def handle_pdf_browser_exception(error: PDFBrowserException) -> Tuple[Dict[str, Any], int]:
    """Handle custom PDF Browser exceptions.
    
    Args:
        error: PDFBrowserException instance
        
    Returns:
        JSON response with error details and status code
    """
    logger.error(f"{error.__class__.__name__}: {error.message}")
    return jsonify({"success": False, "error": error.message}), error.status_code


@app.errorhandler(400)
def handle_bad_request(error: Any) -> Tuple[Dict[str, Any], int]:
    """Handle 400 Bad Request errors."""
    return jsonify({"success": False, "error": "Invalid request"}), 400


@app.errorhandler(404)
def handle_not_found(error: Any) -> Tuple[Dict[str, Any], int]:
    """Handle 404 Not Found errors."""
    return jsonify({"success": False, "error": "Resource not found"}), 404


@app.errorhandler(500)
def handle_internal_error(error: Any) -> Tuple[Dict[str, Any], int]:
    """Handle 500 Internal Server errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health() -> Tuple[Dict[str, Any], int]:
    """Health check endpoint.
    
    Returns:
        JSON response with health status and environment
    """
    try:
        db_manager.get_connection()
        return jsonify({"status": "ok", "environment": ENV}), 200
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
                    "accessed_time": str
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

        for idx, record in enumerate(records):
            try:
                db_manager.insert_pdf_record(record)
                loaded_count += 1
            except (InvalidDataException, DatabaseException) as e:
                logger.warning(f"Failed to insert record {idx}: {e}")
                failed_count += 1

        return jsonify({
            "success": True,
            "loaded": loaded_count,
            "failed": failed_count,
            "total": loaded_count + failed_count,
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
        if ENV == "docker":
            if file_path.startswith("/Users/iheitlager/wc/papers"):
                file_path = file_path.replace("/Users/iheitlager/wc/papers", "/papers", 1)
            elif file_path.startswith(PDF_BASE_DIR):
                file_path = file_path.replace(PDF_BASE_DIR, "/papers", 1)

        logger.info(f"Looking for PDF at path: {file_path} (ENV: {ENV})")

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
    return render_template("index.html", pdf_base_dir=PDF_BASE_DIR)


if __name__ == "__main__":
    # Initialize database on startup
    try:
        db_manager.init_database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Run Flask app
    debug = ENV == "local"
    app.run(host="0.0.0.0", port=PORT, debug=debug)
