"""
Database management module for PDF Browser application.

Handles PostgreSQL connections and operations including:
- Connection management with retry logic
- PDF record CRUD operations
- Tag management
- Database schema initialization
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from psycopg2 import OperationalError, connect
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extras import RealDictCursor

from .exceptions import (
    DatabaseException,
    InvalidDataException,
)

# Logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connections and operations."""

    def __init__(self, db_url: str) -> None:
        """Initialize database manager with connection URL.
        
        Args:
            db_url: PostgreSQL connection URL
        """
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
            raise DatabaseException(f"Database initialization failed: {e}")

    def insert_pdf_record(self, record: Dict[str, Any]) -> bool:
        """Insert a PDF record into the database.
        
        Args:
            record: Dictionary containing PDF metadata
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            InvalidDataException: If required fields are missing
            DatabaseException: If insert fails
        """
        required_fields = ["file_path", "file_name", "directory", "relative_path"]
        if not all(field in record for field in required_fields):
            raise InvalidDataException(f"Missing required fields: {required_fields}")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            tags = record.get("tags")
            # If tags provided, sync them to tags table
            if tags:
                tag_list = [t.strip() for t in tags.split(":") if t.strip()]
                for tag in tag_list:
                    cursor.execute(
                        "INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING",
                        (tag,)
                    )

            # Extract title and citekey from title-details if present
            title = None
            citekey = None
            year = None
            title_details = None

            if "title-details" in record:
                title_details = record["title-details"]
                title = title_details.get("title")
                citekey = title_details.get("citekey")
                year = title_details.get("year")
                # Convert year to int if it's a string
                if year is not None:
                    try:
                        year = int(year)
                    except (ValueError, TypeError):
                        year = None

            # Extract analysis if present
            analysis = record.get("analysis")

            cursor.execute(
                """
                INSERT INTO pdf_files 
                (file_path, file_name, directory, relative_path, size_bytes, 
                 created_time, modified_time, accessed_time, tags, title, citekey, year, title_details, analysis)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    modified_time = EXCLUDED.modified_time,
                    accessed_time = EXCLUDED.accessed_time,
                    tags = EXCLUDED.tags,
                    title = EXCLUDED.title,
                    citekey = EXCLUDED.citekey,
                    year = EXCLUDED.year,
                    title_details = EXCLUDED.title_details,
                    analysis = EXCLUDED.analysis
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
                    tags,
                    title,
                    citekey,
                    year,
                    json.dumps(title_details) if title_details else None,
                    json.dumps(analysis) if analysis else None,
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
                    "SELECT * FROM pdf_files WHERE directory = %s ORDER BY file_name",
                    (directory,),
                )
            else:
                cursor.execute("SELECT * FROM pdf_files ORDER BY file_name")

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
            cursor.execute("SELECT * FROM pdf_files WHERE file_name = %s", (file_name,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to fetch PDF by file name: {e}")
            raise DatabaseException(f"Failed to fetch PDF record: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_all_tags(self) -> List[str]:
        """Get all unique tags from the database.
        
        Returns:
            List of tag names
            
        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT tag_name FROM tags ORDER BY tag_name")
            results = cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch tags: {e}")
            raise DatabaseException(f"Failed to fetch tags: {e}")
        finally:
            cursor.close()
            conn.close()

    def update_pdf_tags(self, file_name: str, tags: str) -> bool:
        """Update tags for a PDF record.
        
        Args:
            file_name: Name of the PDF file
            tags: Colon-separated string of tags
            
        Returns:
            True if successful
            
        Raises:
            DatabaseException: If update fails
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Sync tags to tags table
            if tags:
                tag_list = [t.strip() for t in tags.split(":") if t.strip()]
                for tag in tag_list:
                    cursor.execute(
                        "INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING",
                        (tag,)
                    )

            cursor.execute(
                "UPDATE pdf_files SET tags = %s WHERE file_name = %s",
                (tags, file_name)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update tags: {e}")
            raise DatabaseException(f"Failed to update tags: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_year_overview(self) -> List[Dict[str, Any]]:
        """Get overview of papers by publication year.
        
        Returns:
            List of dicts with year, count, and paper names
            
        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("""
                SELECT 
                    year,
                    COUNT(*) as count,
                    json_agg(json_build_object('file_name', file_name, 'title', title, 'citekey', citekey)) as papers
                FROM pdf_files
                WHERE year IS NOT NULL
                GROUP BY year
                ORDER BY year DESC
            """)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch year overview: {e}")
            raise DatabaseException(f"Failed to fetch year overview: {e}")
        finally:
            cursor.close()
            conn.close()
