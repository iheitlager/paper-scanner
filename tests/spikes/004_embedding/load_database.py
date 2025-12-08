#!/usr/bin/env python3
"""
Database Import Script for Chunked & Embedded Papers

Reads enhanced JSONL file (output from chunk_embed_pipeline.py)
Inserts into PostgreSQL tables:
- papers (main metadata + file info)
- paper_chunks (text chunks)
- chunk_embeddings (chunk vectors)
- paper_embeddings (paper-level vectors)
- processing_logs (tracking)

Usage:
    python import_to_database.py papers_with_chunks_embeddings.jsonl
"""

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import psycopg2
from psycopg2.extensions import register_adapter
from psycopg2.extras import Json, execute_values


# Register numpy array adapter for PostgreSQL
def addapt_numpy_array(numpy_array):
    """Adapt numpy array to PostgreSQL array format"""
    return psycopg2.extensions.AsIs(str(numpy_array.tolist()))


register_adapter(np.ndarray, addapt_numpy_array)


class DatabaseImporter:
    """
    Import enriched paper data into PostgreSQL
    """

    def __init__(self, connection_string: str):
        """
        Initialize database connection

        connection_string format:
        postgresql://user:password@host:port/database
        """
        self.conn = psycopg2.connect(connection_string)
        self.conn.autocommit = False  # Use transactions
        print("✓ Connected to database", file=sys.stderr)

    def __del__(self):
        """Close connection on cleanup"""
        if hasattr(self, "conn"):
            self.conn.close()

    def insert_paper(self, record: Dict, cursor) -> Optional[int]:
        """
        Insert or update paper record

        Returns paper_id
        """

        file_details = record.get("file-details", {})
        metadata = record.get("_metadata", {})
        chunk_metadata = record.get("_chunk_embed_metadata", {})

        # Extract authors array
        authors_list = file_details.get("authors", [])
        authors_json = None
        if authors_list:
            # Convert to structured format
            authors_json = [{"name": author, "order": i + 1} for i, author in enumerate(authors_list)]

        # Extract keywords if present
        keywords = file_details.get("keywords", None)
        if keywords and isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]

        # Determine processing status
        processing_status = "pending"
        if chunk_metadata.get("status") == "success":
            processing_status = "embedded"
        elif chunk_metadata.get("status") == "error":
            processing_status = "error"

        query = """
        INSERT INTO papers (
            file_path, file_name, directory, size_bytes,
            created_time, modified_time, accessed_time,
            citekey, title, authors, year,
            journal, volume, issue, pages, doi, publisher,
            keywords, paper_type,
            processing_status,
            abstract,
            embedding_completed_at,
            last_error,
            title_details,
            indexed_at, updated_at
        ) VALUES (
            %(file_path)s, %(file_name)s, %(directory)s, %(size_bytes)s,
            %(created_time)s, %(modified_time)s, %(accessed_time)s,
            %(citekey)s, %(title)s, %(authors)s, %(year)s,
            %(journal)s, %(volume)s, %(issue)s, %(pages)s, %(doi)s, %(publisher)s,
            %(keywords)s, %(paper_type)s,
            %(processing_status)s,
            %(abstract)s,
            %(embedding_completed_at)s,
            %(last_error)s,
            %(title_details)s,
            %(indexed_at)s, %(updated_at)s
        )
        ON CONFLICT (file_path) DO UPDATE SET
            citekey = EXCLUDED.citekey,
            title = EXCLUDED.title,
            authors = EXCLUDED.authors,
            year = EXCLUDED.year,
            journal = EXCLUDED.journal,
            volume = EXCLUDED.volume,
            issue = EXCLUDED.issue,
            pages = EXCLUDED.pages,
            doi = EXCLUDED.doi,
            publisher = EXCLUDED.publisher,
            keywords = EXCLUDED.keywords,
            processing_status = EXCLUDED.processing_status,
            embedding_completed_at = EXCLUDED.embedding_completed_at,
            last_error = EXCLUDED.last_error,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """

        params = {
            "file_path": record.get("file_path"),
            "file_name": record.get("file_name"),
            "directory": record.get("directory"),
            "size_bytes": metadata.get("size_bytes"),
            "created_time": self._parse_timestamp(metadata.get("created_time")),
            "modified_time": self._parse_timestamp(metadata.get("modified_time")),
            "accessed_time": self._parse_timestamp(metadata.get("accessed_time")),
            "citekey": file_details.get("citekey"),
            "title": file_details.get("title"),
            "authors": Json(authors_json) if authors_json else None,
            "year": self._parse_int(file_details.get("year")),
            "journal": file_details.get("journal"),
            "volume": file_details.get("volume"),
            "issue": file_details.get("issue"),
            "pages": file_details.get("pages"),
            "doi": file_details.get("doi"),
            "publisher": file_details.get("publisher"),
            "keywords": keywords,
            "paper_type": "journal_article",  # Default, could be enhanced
            "processing_status": processing_status,
            # "title": record.get("title", None),
            "abstract": record.get("abstract", None),
            "embedding_completed_at": datetime.now(UTC) if processing_status == "embedded" else None,
            "last_error": chunk_metadata.get("error") if processing_status == "error" else None,
            "title_details": Json(file_details) if file_details else None,
            "indexed_at": self._parse_timestamp(record.get("indexed_at", datetime.now(UTC).isoformat())),
            "updated_at": datetime.now(UTC),
        }

        try:
            cursor.execute(query, params)
            paper_id = cursor.fetchone()[0]
            return paper_id
        except Exception as e:
            print(f"  ✗ Error inserting paper: {e}", file=sys.stderr)
            raise

    def insert_chunks(self, paper_id: int, chunks: List[Dict], cursor) -> List[int]:
        """
        Insert paper chunks

        Returns list of chunk_ids
        """

        if not chunks:
            return []

        query = """
        INSERT INTO paper_chunks (
            paper_id, chunk_index, chunk_type,
            content, content_length, token_count,
            section_title,
            chunking_strategy, chunk_size_target, overlap_size,
            metadata
        ) VALUES %s
        RETURNING id
        """

        values = []
        for chunk in chunks:
            values.append(
                (
                    paper_id,
                    chunk.get("chunk_index"),
                    chunk.get("chunk_type"),
                    chunk.get("content"),
                    chunk.get("content_length"),
                    chunk.get("token_count"),
                    chunk.get("section_title"),
                    chunk.get("chunking_strategy"),
                    chunk.get("chunk_size_target"),
                    chunk.get("overlap_size"),
                    Json(
                        {
                            "page_numbers": chunk.get("page_numbers", []),
                            "line_start": chunk.get("line_start"),
                            "line_end": chunk.get("line_end"),
                        }
                    ),
                )
            )

        try:
            # Use execute_values for bulk insert
            chunk_ids = []
            result = execute_values(
                cursor, query, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", fetch=True
            )
            chunk_ids = [row[0] for row in result]
            return chunk_ids
        except Exception as e:
            print(f"  ✗ Error inserting chunks: {e}", file=sys.stderr)
            raise

    def insert_chunk_embeddings(self, chunk_ids: List[int], chunks: List[Dict], cursor):
        """
        Insert chunk embeddings
        """

        if not chunk_ids or not chunks:
            return

        query = """
        INSERT INTO chunk_embeddings (
            chunk_id, embedding,
            model_name, model_dimension
        ) VALUES %s
        """

        values = []
        for chunk_id, chunk in zip(chunk_ids, chunks):
            embedding_data = chunk.get("embedding", {})
            vector = embedding_data.get("vector", [])

            if not vector:
                continue

            # Format vector for pgvector
            vector_str = "[" + ",".join(map(str, vector)) + "]"

            values.append((chunk_id, vector_str, embedding_data.get("model_name"), embedding_data.get("dimension")))

        try:
            execute_values(cursor, query, values, template="(%s, %s::vector, %s, %s)")
        except Exception as e:
            print(f"  ✗ Error inserting chunk embeddings: {e}", file=sys.stderr)
            raise

    def insert_paper_embedding(self, paper_id: int, paper_embedding: Dict, cursor):
        """
        Insert paper-level embedding
        """

        if not paper_embedding:
            return

        vector = paper_embedding.get("vector", [])
        if not vector:
            return

        # Format vector for pgvector
        vector_str = "[" + ",".join(map(str, vector)) + "]"

        query = """
        INSERT INTO paper_embeddings (
            paper_id, embedding,
            embedding_method,
            model_name, model_dimension
        ) VALUES (
            %s, %s::vector, %s, %s, %s
        )
        ON CONFLICT (paper_id, model_name, embedding_method, embedding_version)
        DO UPDATE SET
            embedding = EXCLUDED.embedding,
            created_at = CURRENT_TIMESTAMP
        """

        try:
            cursor.execute(
                query,
                (
                    paper_id,
                    vector_str,
                    paper_embedding.get("method", "aggregate_chunks"),
                    paper_embedding.get("model_name"),
                    paper_embedding.get("dimension"),
                ),
            )
        except Exception as e:
            print(f"  ✗ Error inserting paper embedding: {e}", file=sys.stderr)
            raise

    def insert_processing_log(self, paper_id: int, record: Dict, cursor):
        """
        Insert processing log entry
        """

        chunk_metadata = record.get("_chunk_embed_metadata", {})

        if not chunk_metadata:
            return

        query = """
        INSERT INTO processing_logs (
            paper_id, stage, status,
            message, error_details,
            duration_seconds, tokens_used,
            model_used
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        status_map = {"success": "completed", "error": "failed", "failed": "failed"}

        try:
            cursor.execute(
                query,
                (
                    paper_id,
                    "chunking_embedding",
                    status_map.get(chunk_metadata.get("status"), "completed"),
                    f"Generated {chunk_metadata.get('chunk_count', 0)} chunks",
                    chunk_metadata.get("error"),
                    chunk_metadata.get("elapsed_seconds"),
                    chunk_metadata.get("total_tokens"),
                    chunk_metadata.get("embedding_model"),
                ),
            )
        except Exception as e:
            print(f"  ✗ Error inserting processing log: {e}", file=sys.stderr)
            # Don't raise - this is not critical

    def process_record(self, record: Dict) -> bool:
        """
        Process a single record (in a transaction)

        Returns True on success, False on failure
        """

        file_name = Path(record.get("file_path", "")).name

        try:
            cursor = self.conn.cursor()

            # Step 1: Insert paper
            paper_id = self.insert_paper(record, cursor)
            print(f"  → Paper inserted (id={paper_id})", file=sys.stderr)

            # Step 2: Insert chunks
            chunks = record.get("chunks", [])
            chunk_ids = []

            if chunks:
                chunk_ids = self.insert_chunks(paper_id, chunks, cursor)
                print(f"  → {len(chunk_ids)} chunks inserted", file=sys.stderr)

                # Step 3: Insert chunk embeddings
                self.insert_chunk_embeddings(chunk_ids, chunks, cursor)
                print(f"  → {len(chunk_ids)} chunk embeddings inserted", file=sys.stderr)

            # Step 4: Insert paper embedding
            paper_embedding = record.get("paper_embedding")
            if paper_embedding:
                self.insert_paper_embedding(paper_id, paper_embedding, cursor)
                print("  → Paper embedding inserted", file=sys.stderr)

            # Step 5: Insert processing log
            self.insert_processing_log(paper_id, record, cursor)

            # Commit transaction
            self.conn.commit()
            cursor.close()

            print("  ✓ Complete", file=sys.stderr)
            return True

        except Exception as e:
            # Rollback on error
            self.conn.rollback()
            print(f"  ✗ Failed: {e}", file=sys.stderr)
            return False

    def import_jsonl(self, jsonl_path: str):
        """
        Import entire JSONL file
        """

        print(f"Importing from: {jsonl_path}", file=sys.stderr)
        print("", file=sys.stderr)

        records_processed = 0
        records_succeeded = 0
        records_failed = 0

        start_time = time.time()

        with open(jsonl_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)

                    file_name = Path(record.get("file_path", "")).name
                    print(f"[{line_num}] Processing: {file_name}", file=sys.stderr)

                    success = self.process_record(record)

                    records_processed += 1
                    if success:
                        records_succeeded += 1
                    else:
                        records_failed += 1

                    print("", file=sys.stderr)

                except json.JSONDecodeError as e:
                    print(f"[{line_num}] ✗ JSON parse error: {e}", file=sys.stderr)
                    records_failed += 1
                except Exception as e:
                    print(f"[{line_num}] ✗ Unexpected error: {e}", file=sys.stderr)
                    records_failed += 1

        elapsed = time.time() - start_time

        # Summary
        print("=" * 70, file=sys.stderr)
        print("IMPORT COMPLETE", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"Total records: {records_processed}", file=sys.stderr)
        print(f"Succeeded: {records_succeeded}", file=sys.stderr)
        print(f"Failed: {records_failed}", file=sys.stderr)
        print(f"Time: {elapsed:.1f}s ({elapsed / records_processed:.1f}s per record)", file=sys.stderr)
        print("", file=sys.stderr)

        # Show database stats
        self._print_database_stats()

    def _print_database_stats(self):
        """Print database statistics"""

        cursor = self.conn.cursor()

        try:
            # Papers count
            cursor.execute("SELECT COUNT(*), processing_status FROM papers GROUP BY processing_status")
            print("Papers by status:", file=sys.stderr)
            for count, status in cursor.fetchall():
                print(f"  {status}: {count}", file=sys.stderr)

            # Chunks count
            cursor.execute("SELECT COUNT(*) FROM paper_chunks")
            chunks_count = cursor.fetchone()[0]
            print(f"Total chunks: {chunks_count}", file=sys.stderr)

            # Embeddings count
            cursor.execute("SELECT COUNT(*) FROM chunk_embeddings")
            chunk_emb_count = cursor.fetchone()[0]
            print(f"Chunk embeddings: {chunk_emb_count}", file=sys.stderr)

            cursor.execute("SELECT COUNT(*) FROM paper_embeddings")
            paper_emb_count = cursor.fetchone()[0]
            print(f"Paper embeddings: {paper_emb_count}", file=sys.stderr)

        except Exception as e:
            print(f"Error getting stats: {e}", file=sys.stderr)
        finally:
            cursor.close()

    @staticmethod
    def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO timestamp string"""
        if not ts_str:
            return None
        try:
            # Handle with or without timezone
            if "+" in ts_str or ts_str.endswith("Z"):
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                return datetime.fromisoformat(ts_str)
        except:
            return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        """Safely parse integer"""
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None


def main():
    """Main entry point"""

    if len(sys.argv) < 2:
        print("Usage: python import_to_database.py input.jsonl [connection_string]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Connection string format:", file=sys.stderr)
        print("  postgresql://user:password@host:port/database", file=sys.stderr)
        print("", file=sys.stderr)
        print("Default connection string:", file=sys.stderr)
        print("  postgresql://pdfuser:pdfpass@localhost:5432/pdfdb", file=sys.stderr)
        sys.exit(1)

    jsonl_path = sys.argv[1]

    # Default connection string (matches your docker-compose)
    connection_string = "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"

    if len(sys.argv) >= 3:
        connection_string = sys.argv[2]

    # Validate input file
    if not Path(jsonl_path).exists():
        print(f"Error: File not found: {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    # Create importer and run
    try:
        importer = DatabaseImporter(connection_string)
        importer.import_jsonl(jsonl_path)
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Make sure PostgreSQL is running:", file=sys.stderr)
        print("  docker-compose up -d pdf-browser-db", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
