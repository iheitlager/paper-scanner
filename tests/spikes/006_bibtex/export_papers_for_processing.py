#!/usr/bin/env python3
"""
Export Papers for Processing

Extracts all records from papers table where:
- screening_stage is 'stage2_pass', 'stage2_review', or other _pass/_review stages
- file_path is set (not NULL)

Exports as JSONL (one JSON object per line) to stdout

Usage:
    python export_papers_for_processing.py [--db-url <url>] > papers_for_processing.jsonl

The output can be piped to:
    chunk_embed_pipeline.py (for chunking/embedding)
    load_database.py (for loading into PostgreSQL)

Examples:
    # Export to file
    python export_papers_for_processing.py > papers_for_processing.jsonl

    # Export to file with custom database
    python export_papers_for_processing.py --db-url "postgresql://user:pass@host/db" > papers.jsonl

    # Pipe directly to chunking pipeline
    python export_papers_for_processing.py | python ../004_embedding/chunk_embed_pipeline.py
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()


class PapersExporter:
    """Export papers from database as JSONL."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None

    def connect(self) -> bool:
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            return True
        except psycopg2.Error as e:
            print(f"❌ Connection failed: {e}", file=sys.stderr)
            return False

    def disconnect(self) -> None:
        """Close connection."""
        if self.conn:
            self.conn.close()

    def get_papers_for_processing(self) -> List[Dict]:
        """
        Get all papers with:
        - screening_stage in ('stage2_pass', 'stage2_review', 'stage3_review', etc.)
        - file_path is not NULL
        
        Returns list of paper records as dictionaries
        """
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT 
            p.*
        FROM papers p
        JOIN paper_screening ps ON p.id = ps.paper_id
        WHERE 
            ps.screening_stage IN (
                'stage2_pass',
                'stage2_review',
                'stage3_review',
                'stage4_validated',
                'included'
            )
            AND p.file_path IS NOT NULL
        ORDER BY p.id ASC
        """

        try:
            cursor.execute(query)
            papers = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in papers] if papers else []
        except psycopg2.Error as e:
            print(f"❌ Query failed: {e}", file=sys.stderr)
            cursor.close()
            return []

    def serialize_paper(self, paper: Dict) -> str:
        """
        Serialize paper record to JSON string.
        
        Handles special types (datetime, etc.) for JSON serialization.
        """
        # Create a copy to avoid modifying original
        paper_data = dict(paper)

        # Convert datetime objects to ISO format strings
        for key, value in paper_data.items():
            if isinstance(value, datetime):
                paper_data[key] = value.isoformat()

        return json.dumps(paper_data, default=str)

    def export_jsonl(self) -> int:
        """
        Export papers as JSONL to stdout.
        
        Returns: number of papers exported
        """
        papers = self.get_papers_for_processing()

        if not papers:
            print("⚠️  No papers found matching criteria", file=sys.stderr)
            return 0

        # Print statistics to stderr
        print(f"Exporting {len(papers)} papers as JSONL", file=sys.stderr)
        print("=" * 80, file=sys.stderr)

        # Export each paper as a JSON line to stdout
        for i, paper in enumerate(papers, 1):
            try:
                json_line = self.serialize_paper(paper)
                print(json_line)

                # Progress indicator to stderr
                if i % 10 == 0:
                    print(f"  Exported {i}/{len(papers)} papers", file=sys.stderr)

            except Exception as e:
                print(
                    f"❌ Error serializing paper {paper.get('id')}: {e}",
                    file=sys.stderr,
                )
                return -1

        print("=" * 80, file=sys.stderr)
        print(f"✓ Successfully exported {len(papers)} papers", file=sys.stderr)

        return len(papers)


def main():
    parser = argparse.ArgumentParser(
        description="Export papers for processing (chunking/embedding)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export to file
  python export_papers_for_processing.py > papers_for_processing.jsonl

  # Export with custom database
  python export_papers_for_processing.py --db-url "postgresql://user:pass@host/db" > papers.jsonl

  # Pipe to chunking pipeline
  python export_papers_for_processing.py | python ../004_embedding/chunk_embed_pipeline.py

Selection criteria:
  • screening_stage: 'stage2_pass', 'stage2_review', 'stage3_review', 'stage4_validated', 'included'
  • file_path: Must be set (not NULL)

Output format:
  • JSONL (one JSON object per line)
  • All fields from papers table included
  • Timestamps in ISO 8601 format
        """,
    )

    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"),
        help="PostgreSQL connection URL (default: env DATABASE_URL or localhost)",
    )

    args = parser.parse_args()

    # Create exporter
    exporter = PapersExporter(args.db_url)

    try:
        if not exporter.connect():
            sys.exit(1)

        count = exporter.export_jsonl()

        sys.exit(0 if count >= 0 else 1)

    except KeyboardInterrupt:
        print("\n⏸️  Export interrupted (CTRL-C)", file=sys.stderr)
        sys.exit(0)

    finally:
        exporter.disconnect()


if __name__ == "__main__":
    main()
