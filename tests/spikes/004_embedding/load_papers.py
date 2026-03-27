#!/usr/bin/env python3
"""
Load papers from JSONL into PostgreSQL database.

This script loads out2.jsonl (sample papers) into the papers table.
Only considers existing fields from the original papers schema.

Usage:
    python load_papers.py <path_to_jsonl> [--db-url postgresql://...]

Example:
    python load_papers.py out2.jsonl
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from psycopg2 import OperationalError, connect
from psycopg2.extensions import connection as PsycopgConnection

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PaperLoader:
    """Load papers from JSONL into PostgreSQL database."""

    # Original fields from papers table schema
    ORIGINAL_FIELDS = {
        "file_path": str,
        "file_name": str,
        "directory": str,
        "size_bytes": int,
        "created_time": str,
        "modified_time": str,
        "accessed_time": str,
        "tags": str,
        "title": str,
        "citekey": str,
        "year": int,
        "title_details": dict,
        "analysis": dict,
    }

    def __init__(self, db_url: str) -> None:
        """Initialize loader with database URL.

        Args:
            db_url: PostgreSQL connection URL
        """
        self.db_url = db_url
        self.conn: Optional[PsycopgConnection] = None
        self.stats = {
            "total_records": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

    def connect(self, retries: int = 3, delay: int = 2) -> None:
        """Connect to database with retry logic.

        Args:
            retries: Number of retry attempts
            delay: Delay between retries

        Raises:
            RuntimeError: If connection fails
        """
        for attempt in range(retries):
            try:
                self.conn = connect(self.db_url)
                logger.info(f"Connected to database: {self.db_url}")
                return
            except OperationalError as e:
                if attempt < retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying...")
                else:
                    raise RuntimeError(f"Failed to connect after {retries} attempts: {e}")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def extract_fields_from_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only original fields from record.

        Maps nested structure from out2.jsonl to flat fields for papers table:
        - file_path, file_name, directory, _metadata.* from top level
        - title, citekey, year from file-details

        Args:
            record: Raw record from JSONL

        Returns:
            Dictionary with only original fields
        """
        extracted = {}

        # Top-level fields
        for field in ("file_path", "file_name", "directory"):
            if field in record:
                extracted[field] = record[field]

        # Metadata fields
        if "_metadata" in record:
            meta = record["_metadata"]
            extracted["size_bytes"] = meta.get("size_bytes")
            extracted["created_time"] = meta.get("created_time")
            extracted["modified_time"] = meta.get("modified_time")
            extracted["accessed_time"] = meta.get("accessed_time")

        # File details
        if "file-details" in record:
            details = record["file-details"]
            extracted["title"] = details.get("title")
            extracted["citekey"] = details.get("citekey")
            extracted["year"] = details.get("year")
            extracted["title_details"] = details

            # Extract metadata from file-details if present
            if "_metadata" in details:
                extracted["analysis"] = {"processing_metadata": details["_metadata"]}

        return extracted

    def load_paper(self, record: Dict[str, Any]) -> bool:
        """Load a single paper into database.

        Args:
            record: Paper record from JSONL

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            fields = self.extract_fields_from_record(record)

            # Validate required fields
            if not fields.get("file_path") or not fields.get("file_name"):
                logger.warning("Skipping record: missing required fields")
                self.stats["skipped"] += 1
                return False

            # Prepare values
            file_path = fields["file_path"]
            file_name = fields["file_name"]
            directory = fields.get("directory", "")
            size_bytes = fields.get("size_bytes")
            created_time = fields.get("created_time")
            modified_time = fields.get("modified_time")
            accessed_time = fields.get("accessed_time")
            tags = fields.get("tags")
            title = fields.get("title")
            citekey = fields.get("citekey")
            year = fields.get("year")
            title_details = fields.get("title_details")
            analysis = fields.get("analysis")

            # Convert year to int if possible
            if year is not None:
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    year = None

            # Insert or update
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO papers
                (file_path, file_name, directory, size_bytes,
                 created_time, modified_time, accessed_time, tags,
                 title, citekey, year, title_details, analysis)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    modified_time = EXCLUDED.modified_time,
                    accessed_time = EXCLUDED.accessed_time,
                    tags = EXCLUDED.tags,
                    title = EXCLUDED.title,
                    citekey = EXCLUDED.citekey,
                    year = EXCLUDED.year,
                    title_details = EXCLUDED.title_details,
                    analysis = EXCLUDED.analysis
                RETURNING (xmax = 0) AS inserted
                """,
                (
                    file_path,
                    file_name,
                    directory,
                    size_bytes,
                    created_time,
                    modified_time,
                    accessed_time,
                    tags,
                    title,
                    citekey,
                    year,
                    json.dumps(title_details) if title_details else None,
                    json.dumps(analysis) if analysis else None,
                ),
            )

            result = cursor.fetchone()
            self.conn.commit()
            cursor.close()

            if result and result[0]:
                self.stats["inserted"] += 1
                logger.debug(f"Inserted: {file_path}")
            else:
                self.stats["updated"] += 1
                logger.debug(f"Updated: {file_path}")

            return True

        except Exception as e:
            logger.error(f"Error loading paper: {e}")
            self.stats["errors"] += 1
            self.conn.rollback()
            return False

    def load_from_jsonl(self, jsonl_path: str) -> None:
        """Load papers from JSONL file.

        Args:
            jsonl_path: Path to JSONL file
        """
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {jsonl_path}")

        logger.info(f"Loading papers from: {jsonl_path}")

        with open(path, "r") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    self.stats["total_records"] += 1
                    self.load_paper(record)
                except json.JSONDecodeError as e:
                    logger.error(f"Line {line_num}: Invalid JSON - {e}")
                    self.stats["errors"] += 1

    def print_stats(self) -> None:
        """Print loading statistics."""
        print("\n" + "=" * 50)
        print("Loading Statistics")
        print("=" * 50)
        print(f"Total records processed: {self.stats['total_records']}")
        print(f"Successfully inserted: {self.stats['inserted']}")
        print(f"Successfully updated:  {self.stats['updated']}")
        print(f"Skipped:               {self.stats['skipped']}")
        print(f"Errors:                {self.stats['errors']}")
        print("=" * 50 + "\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load papers from JSONL into PostgreSQL database")
    parser.add_argument("jsonl_file", help="Path to JSONL file to load")
    parser.add_argument("--db-url", help="PostgreSQL connection URL", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get database URL
    load_dotenv()
    db_url = args.db_url or os.getenv("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")

    # Load papers
    loader = PaperLoader(db_url)
    try:
        loader.connect()
        loader.load_from_jsonl(args.jsonl_file)
        loader.print_stats()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
