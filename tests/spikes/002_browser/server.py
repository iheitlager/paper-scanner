"""
PDF Browser Server - Web application for browsing and viewing PDFs with PostgreSQL backend.

Supports both local (port 8080) and Docker (port 8000) deployment.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from psycopg2 import connect, sql, OperationalError
from psycopg2.extras import RealDictCursor
import logging

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


class DatabaseManager:
    """Manages PostgreSQL connections and operations."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def get_connection(self, retries: int = 3, delay: int = 2):
        """Get a database connection with retry logic."""
        for attempt in range(retries):
            try:
                return connect(self.db_url)
            except (OperationalError, Exception) as e:
                if attempt < retries - 1:
                    logger.warning(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Database connection failed after {retries} attempts: {e}")
                    raise

    def init_database(self):
        """Verify database schema is initialized (done by init-db.sql in Docker)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Just verify the table exists
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'pdf_files'"
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

    def insert_pdf_record(self, record: dict) -> bool:
        """Insert a PDF record into the database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO pdf_files 
                (file_path, file_name, directory, relative_path, size_bytes, 
                 created_time, modified_time, accessed_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    modified_time = EXCLUDED.modified_time,
                    accessed_time = EXCLUDED.accessed_time
                """,
                (
                    record["file_path"],
                    record["file_name"],
                    record["directory"],
                    record["relative_path"],
                    record.get("size_bytes"),
                    record.get("created_time"),
                    record.get("modified_time"),
                    record.get("accessed_time"),
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to insert record: {e}")
            cursor.close()
            conn.close()
            return False

    def get_all_pdfs(self, directory: Optional[str] = None) -> list:
        """Get all PDF records from database."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if directory:
            cursor.execute(
                "SELECT * FROM pdf_files WHERE directory = %s ORDER BY file_name",
                (directory,),
            )
        else:
            cursor.execute("SELECT * FROM pdf_files ORDER BY file_name")

        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(row) for row in results]

    def get_pdf_by_file_name(self, file_name: str) -> Optional[dict]:
        """Get PDF record by file name."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM pdf_files WHERE file_name = %s", (file_name,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return dict(result) if result else None


# Initialize database manager
db_manager = DatabaseManager(DATABASE_URL)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    try:
        db_manager.get_connection()
        return jsonify({"status": "ok", "environment": ENV}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/files", methods=["GET"])
def get_files():
    """Get list of all PDF files from database."""
    try:
        directory = request.args.get("directory")
        files = db_manager.get_all_pdfs(directory)
        return jsonify({"success": True, "files": files}), 200
    except Exception as e:
        logger.error(f"Error fetching files: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/load-jsonlines", methods=["POST"])
def load_jsonlines():
    """Load PDF records from the request body into the database."""
    try:
        data = request.get_json()
        records = data.get("records", [])

        if not records:
            return jsonify({"success": False, "error": "No records provided"}), 400

        loaded_count = 0
        failed_count = 0

        for record in records:
            try:
                if db_manager.insert_pdf_record(record):
                    loaded_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error inserting record: {e}")
                failed_count += 1

        return (
            jsonify(
                {
                    "success": True,
                    "loaded": loaded_count,
                    "failed": failed_count,
                    "total": loaded_count + failed_count,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error loading records: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/file_details/<file_name>", methods=["GET"])
def get_file_details(file_name: str):
    """Get file details by name."""
    try:
        pdf_record = db_manager.get_pdf_by_file_name(file_name)

        if not pdf_record:
            logger.error(f"PDF not found in database for file_name: {file_name}")
            return jsonify({"success": False, "error": "PDF not found in database"}), 404

        return jsonify({"success": True, "details": pdf_record}), 200
    except Exception as e:
        logger.error(f"Error retrieving file details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pdf/<file_name>", methods=["GET"])
def get_pdf(file_name: str):
    """Serve a PDF file by name."""
    try:
        pdf_record = db_manager.get_pdf_by_file_name(file_name)

        if not pdf_record:
            logger.error(f"PDF not found in database for file_name: {file_name}")
            return jsonify({"success": False, "error": "PDF not found in database"}), 404

        file_path = pdf_record["file_path"]
        
        # In Docker, translate paths from host machine to container paths
        if ENV == "docker":
            # Replace the host path prefix with the container path prefix
            if file_path.startswith("/Users/iheitlager/wc/papers"):
                file_path = file_path.replace("/Users/iheitlager/wc/papers", "/papers", 1)
            elif file_path.startswith(PDF_BASE_DIR):
                # Replace PDF_BASE_DIR with /papers in Docker
                file_path = file_path.replace(PDF_BASE_DIR, "/papers", 1)
        
        logger.info(f"Looking for PDF at path: {file_path} (ENV: {ENV})")

        if not os.path.exists(file_path):
            logger.error(f"PDF file not found on disk at: {file_path}")
            logger.error(f"PDF record: {pdf_record}")
            # List available files in the papers directory for debugging
            if os.path.exists("/papers"):
                available = os.listdir("/papers")[:5]
                logger.error(f"Sample files in /papers: {available}")
            return (
                jsonify({"success": False, "error": f"PDF file not found on disk at {file_path}"}),
                404,
            )

        return send_file(file_path, mimetype="application/pdf"), 200
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    """Render the main HTML interface."""
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
