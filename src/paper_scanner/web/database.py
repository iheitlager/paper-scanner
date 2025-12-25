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
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2 import OperationalError, connect
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extras import RealDictCursor

from .exceptions import DatabaseException, InvalidDataException

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

    @staticmethod
    def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a database row dict to JSON-serializable format.

        Handles:
        - JSONB columns (keep as dicts)
        - datetime objects (convert to ISO strings)
        - Lists/arrays (keep as-is)

        Args:
            row: Database row as dict

        Returns:
            JSON-serializable dict
        """
        if not row:
            return row

        serialized = {}
        for key, value in row.items():
            if value is None:
                serialized[key] = None
            elif isinstance(value, datetime):
                # Convert datetime to ISO format string
                serialized[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool)):
                # Primitive types are already JSON-safe
                serialized[key] = value
            elif isinstance(value, (list, tuple)):
                # Lists/tuples (from PostgreSQL arrays)
                serialized[key] = list(value)
            elif isinstance(value, dict):
                # Already a dict (from JSONB), keep as-is
                serialized[key] = value
            else:
                # Fallback: convert to string
                serialized[key] = str(value)

        return serialized

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
            cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'papers'")
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
        required_fields = ["file_path", "file_name", "directory"]
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
                    cursor.execute("INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING", (tag,))

            # Extract title and cite_key from title-details if present
            title = None
            cite_key = None
            year = None
            title_details = None

            if "title-details" in record:
                title_details = record["title-details"]
                title = title_details.get("title")
                cite_key = title_details.get("cite_key")
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
                INSERT INTO papers 
                (file_path, file_name, directory, size_bytes, 
                 created_time, modified_time, accessed_time, tags, title, cite_key, year, title_details, analysis)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    modified_time = EXCLUDED.modified_time,
                    accessed_time = EXCLUDED.accessed_time,
                    tags = EXCLUDED.tags,
                    title = EXCLUDED.title,
                    cite_key = EXCLUDED.cite_key,
                    year = EXCLUDED.year,
                    title_details = EXCLUDED.title_details,
                    analysis = EXCLUDED.analysis
                """,
                (
                    record["file_path"],
                    record["file_name"],
                    record["directory"],
                    record.get("size_bytes"),
                    record.get("created_time"),
                    record.get("modified_time"),
                    record.get("accessed_time"),
                    tags,
                    title,
                    cite_key,
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

    def get_all_pdfs(self) -> List[Dict[str, Any]]:
        """Get all PDF records from database.

        Returns:
            List of PDF records with JSON-serializable fields, excluding large JSONB fields

        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Select only essential columns, excluding large JSONB fields (raw_json, discovery, screening)
            # to improve API response performance
            # Include citation counts for UI display
            cursor.execute("""
                SELECT 
                    p.db_id, p.id, p.cite_key, p.source_key, p.doi, p.arxiv_id, p.pmid, p.isbn, p.issn, p.url,
                    p.title, p.abstract, p.authors, p.keywords, p.topics, p.year, p.journal, p.journal_acronym, p.journal_iso4,
                    p.booktitle, p.publisher, p.volume, p.issue, p.pages, p.paper_type, p.language,
                    p.publication_date, p.pdf_info, p.file_path, p.file_name,
                    p.size_bytes, p.conceptual_analysis, p.manually_validated,
                    p.validation_notes, p.validated_by, p.validated_at, p.raw_bibtex, p.tags,
                    p.created_at, p.updated_at,
                    COALESCE(inbound.count, 0) as inbound_count,
                    COALESCE(outbound.count, 0) as outbound_count
                FROM papers p
                LEFT JOIN (
                    SELECT cited_paper_id, COUNT(*) as count
                    FROM citation_edges
                    WHERE cited_paper_id IS NOT NULL
                    GROUP BY cited_paper_id
                ) inbound ON p.db_id = inbound.cited_paper_id
                LEFT JOIN (
                    SELECT citing_paper_id, COUNT(*) as count
                    FROM citation_edges
                    GROUP BY citing_paper_id
                ) outbound ON p.db_id = outbound.citing_paper_id
                ORDER BY p.title
            """)

            results = cursor.fetchall()
            # Serialize each row to handle JSONB and datetime columns
            return [self._serialize_row(dict(row)) for row in results]
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
            PDF record dictionary or None if not found (JSON-serializable)

        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("SELECT * FROM papers WHERE file_name = %s", (file_name,))
            result = cursor.fetchone()
            if result:
                return self._serialize_row(dict(result))
            return None
        except Exception as e:
            logger.error(f"Failed to fetch PDF by file name: {e}")
            raise DatabaseException(f"Failed to fetch PDF record: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_pdf_by_cite_key(self, cite_key: str) -> Optional[Dict[str, Any]]:
        """Get PDF record by cite_key.

        Args:
            cite_key: Citation key of the paper

        Returns:
            PDF record dictionary or None if not found (JSON-serializable)

        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("SELECT * FROM papers WHERE cite_key = %s", (cite_key,))
            result = cursor.fetchone()
            if result:
                return self._serialize_row(dict(result))
            return None
        except Exception as e:
            logger.error(f"Failed to fetch PDF by cite_key: {e}")
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
                    cursor.execute("INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING", (tag,))

            cursor.execute("UPDATE papers SET tags = %s WHERE file_name = %s", (tags, file_name))
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
            List of dicts with year, count, and papers array

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
                    json_agg(json_build_object('id', id, 'file_name', file_name, 'title', title, 'cite_key', cite_key, 'authors', authors)) as papers
                FROM papers
                WHERE year IS NOT NULL
                GROUP BY year
                ORDER BY year DESC
            """)
            results = cursor.fetchall()
            return [self._serialize_row(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch year overview: {e}")
            raise DatabaseException(f"Failed to fetch year overview: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_citations_for_paper(self, paper_db_id: int) -> List[Dict[str, Any]]:
        """Get papers cited by a specific paper (via citation_edges table).

        Args:
            paper_db_id: Database ID of the paper

        Returns:
            List of cited papers with JSON-serializable fields

        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute(
                """
                SELECT p.*
                FROM papers p
                INNER JOIN citation_edges ce ON p.db_id = ce.cited_paper_id
                WHERE ce.citing_paper_id = %s
                ORDER BY p.title
                """,
                (paper_db_id,),
            )
            results = cursor.fetchall()
            return [self._serialize_row(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch citations for paper {paper_db_id}: {e}")
            raise DatabaseException(f"Failed to fetch citations: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_full_citation_network(self) -> Dict[str, Any]:
        """Get full citation network with all papers and citation edges.

        Returns:
            Dictionary with nodes (all papers) and links (citation edges)

        Raises:
            DatabaseException: If query fails
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Get all papers with citation counts, excluding large JSONB fields
            cursor.execute(
                """
                SELECT 
                    db_id, id, cite_key, title, authors, year, journal, doi, url,
                    COALESCE(inbound.count, 0) as inbound_count,
                    COALESCE(outbound.count, 0) as outbound_count
                FROM papers p
                LEFT JOIN (
                    SELECT cited_paper_id, COUNT(*) as count
                    FROM citation_edges
                    WHERE cited_paper_id IS NOT NULL
                    GROUP BY cited_paper_id
                ) inbound ON p.db_id = inbound.cited_paper_id
                LEFT JOIN (
                    SELECT citing_paper_id, COUNT(*) as count
                    FROM citation_edges
                    GROUP BY citing_paper_id
                ) outbound ON p.db_id = outbound.citing_paper_id
                ORDER BY p.title
                """
            )
            paper_rows = cursor.fetchall()
            nodes = [self._serialize_row(dict(row)) for row in paper_rows]

            # Get all citation edges, mapping db_ids to UUIDs
            cursor.execute(
                """
                SELECT 
                    cp.id as source_id,
                    cip.id as target_id
                FROM citation_edges ce
                JOIN papers cp ON ce.citing_paper_id = cp.db_id
                JOIN papers cip ON ce.cited_paper_id = cip.db_id
                WHERE ce.cited_paper_id IS NOT NULL
                ORDER BY ce.citing_paper_id, ce.cited_paper_id
                """
            )
            link_rows = cursor.fetchall()
            links = [
                {"source": dict(row)["source_id"], "target": dict(row)["target_id"]}
                for row in link_rows
            ]

            return {
                "nodes": nodes,
                "links": links
            }
        except Exception as e:
            logger.error(f"Failed to fetch citation network: {e}")
            raise DatabaseException(f"Failed to fetch citation network: {e}")
        finally:
            cursor.close()
            conn.close()
