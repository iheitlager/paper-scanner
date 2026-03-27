#!/usr/bin/env python
"""
Simple standalone test of sql.py upload methods.
Tests all four upload operations with fake data.

Usage:
    python tests/spikes/try_07_sql.py

Requires:
    - DATABASE_URL in .env or environment
    - PostgreSQL database initialized with schema
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from paper_scanner.core.models import Author, Citation, CitationDirection, Embedding, Paper, TextChunk
from paper_scanner.io.sql import DatabaseConnectionPool, PaperUploader


def create_fake_embedding(text_source: str) -> Embedding:
    """Create fake 768-dim embedding"""
    # Fake but realistic vector (all 0.1)
    vector = [0.1] * 768
    return Embedding(
        vector=vector,
        model="all-mpnet-base-v2",
        text_source=text_source,
    )


def create_fake_paper_with_chunks() -> Paper:
    """Create a fake paper with text chunks and embeddings"""

    # Create chunks with hierarchy
    chunk_intro = TextChunk(
        chunk_index=0,
        text="This is the introduction section of the paper. It provides context and background.",
        section="introduction",
        hierarchy_level=1,  # Section level
        embedding=create_fake_embedding("introduction"),
        word_count=12,
    )

    chunk_para1 = TextChunk(
        chunk_index=1,
        text="This is the first paragraph of the introduction.",
        hierarchy_level=2,  # Paragraph level
        parent_chunk=chunk_intro,
        embedding=create_fake_embedding("introduction_para1"),
        word_count=10,
    )

    chunk_para2 = TextChunk(
        chunk_index=2,
        text="This is the second paragraph with more details.",
        hierarchy_level=2,  # Paragraph level
        parent_chunk=chunk_intro,
        embedding=create_fake_embedding("introduction_para2"),
        word_count=9,
    )

    chunk_intro.children_chunks = [chunk_para1, chunk_para2]

    chunk_methods = TextChunk(
        chunk_index=3,
        text="The methods section describes our experimental approach.",
        section="methods",
        hierarchy_level=1,  # Section level
        embedding=create_fake_embedding("methods"),
        word_count=10,
    )

    chunk_results = TextChunk(
        chunk_index=4,
        text="The results demonstrate significant findings.",
        section="results",
        hierarchy_level=1,  # Section level
        embedding=create_fake_embedding("results"),
        word_count=7,
    )

    # Create paper with chunks
    paper = Paper(
        cite_key="TestPaper2024",
        title="Test Paper: SQL Upload Testing",
        abstract="This is a test paper for validating SQL upload with chunks and embeddings.",
        authors=[
            Author(given_name="John", family_name="Smith", full_name="John Smith"),
            Author(given_name="Jane", family_name="Doe", full_name="Jane Doe"),
        ],
        year=2024,
        journal="Test Journal",
        volume="10",
        issue="5",
        pages="123-145",
        doi="10.1234/test.2024.00001",
        url="https://example.com/paper",
        keywords=["testing", "database", "embeddings"],
        text_chunks=[chunk_intro, chunk_methods, chunk_results],
    )

    return paper


def create_fake_paper_with_citations() -> Paper:
    """Create a fake paper with citations"""
    paper = Paper(
        cite_key="CitedPaper2023",
        title="Related Work Paper",
        abstract="This paper discusses related work.",
        authors=[Author(given_name="Bob", family_name="Johnson", full_name="Bob Johnson")],
        year=2023,
        journal="Other Journal",
        doi="10.1234/other.2023.00001",
        keywords=["related", "work"],
        citations=[
            Citation(
                direction=CitationDirection.FORWARD,
                title="Referenced Paper",
                authors=["Smith, A.", "Jones, B."],
                year=2022,
                journal="Reference Journal",
                doi="10.1234/ref.2022.00001",
                extraction_method="manual",
                confidence=0.95,
            )
        ]
    )

    return paper


def main():
    """Run SQL upload test"""

    # Get database URL
    database_url = os.getenv("DATABASE_URL")

    # If not set, try to build from components
    if not database_url:
        db_user = os.getenv("DB_USER", "pdfuser")
        db_password = os.getenv("DB_PASSWORD", "pdfpass")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "paper_scanner")

        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    if not database_url:
        print("❌ DATABASE_URL or DB_* components not found in environment or .env file")
        sys.exit(1)

    print("=" * 70)
    print("SQL Upload Test - All Four Operations")
    print("=" * 70)

    try:
        # Initialize connection pool
        print("\n1️⃣  Initializing connection pool...")
        pool = DatabaseConnectionPool(database_url)
        pool.initialize()
        print("   ✅ Connection pool initialized")

        # Create uploader
        uploader = PaperUploader(pool)

        # Create test data
        print("\n2️⃣  Creating test data...")
        paper1 = create_fake_paper_with_chunks()
        paper2 = create_fake_paper_with_citations()
        papers = [paper1, paper2]
        print(f"   ✅ Created {len(papers)} papers with chunks")
        print(f"      - Paper 1: {paper1.cite_key} ({len(paper1.text_chunks)} chunks)")
        print(f"      - Paper 2: {paper2.cite_key} ({len(paper2.citations)} citations)")

        # STEP 1: Insert papers
        print("\n3️⃣  STEP 1/4: Inserting papers...")
        papers_stats = uploader.insert_papers(papers, conflict_strategy="update")
        print(f"   ✅ Papers: {papers_stats['inserted']} inserted, {papers_stats['error_count']} errors")
        if papers_stats["error_count"] > 0:
            for err in papers_stats["errors"]:
                print(f"      ⚠️  {err}")
        print(f"   ✅ Citation edges: {papers_stats['citation_edges']['edges_inserted']} inserted")

        # STEP 2: Insert chunks
        print("\n4️⃣  STEP 2/4: Inserting text chunks...")
        chunks_stats = uploader.insert_chunks(papers)
        print(f"   ✅ Chunks: {chunks_stats['chunks_inserted']} inserted, {chunks_stats['error_count']} errors")
        if chunks_stats["error_count"] > 0:
            for err in chunks_stats["errors"]:
                print(f"      ⚠️  {err}")

        # STEP 3: Insert chunk embeddings
        print("\n5️⃣  STEP 3/4: Inserting chunk embeddings...")
        chunk_emb_stats = uploader.insert_chunk_embeddings(papers)
        print(f"   ✅ Embeddings: {chunk_emb_stats['embeddings_upserted']} upserted, {chunk_emb_stats['error_count']} errors")
        if chunk_emb_stats["error_count"] > 0:
            for err in chunk_emb_stats["errors"]:
                print(f"      ⚠️  {err}")

        # STEP 4: Insert paper embeddings
        print("\n6️⃣  STEP 4/4: Inserting paper embeddings...")
        paper_emb_stats = uploader.insert_embeddings(papers)
        print(f"   ✅ Embeddings: {paper_emb_stats['upserted']} upserted, {paper_emb_stats['error_count']} errors")
        if paper_emb_stats["error_count"] > 0:
            for err in paper_emb_stats["errors"]:
                print(f"      ⚠️  {err}")

        # Verify in database
        print("\n7️⃣  Verifying data in database...")

        # Check papers
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Count papers
            cursor.execute("SELECT COUNT(*) FROM papers")
            paper_count = cursor.fetchone()[0]
            print(f"   ✅ Papers table: {paper_count} total papers")

            # Count chunks
            cursor.execute("SELECT COUNT(*) FROM paper_chunks")
            chunk_count = cursor.fetchone()[0]
            print(f"   ✅ Paper chunks table: {chunk_count} total chunks")

            # Count chunk embeddings
            cursor.execute("SELECT COUNT(*) FROM chunk_embeddings")
            chunk_emb_count = cursor.fetchone()[0]
            print(f"   ✅ Chunk embeddings table: {chunk_emb_count} total embeddings")

            # Count paper embeddings
            cursor.execute("SELECT COUNT(*) FROM paper_embeddings")
            paper_emb_count = cursor.fetchone()[0]
            print(f"   ✅ Paper embeddings table: {paper_emb_count} total embeddings")

            # Show hierarchy
            print("\n   📊 Chunk hierarchy breakdown:")
            cursor.execute("""
                SELECT hierarchy_level, COUNT(*) as count
                FROM paper_chunks
                GROUP BY hierarchy_level
                ORDER BY hierarchy_level
            """)
            for level, count in cursor.fetchall():
                level_name = {0: "Root (paper)", 1: "Section", 2: "Paragraph"}.get(level, f"Level {level}")
                print(f"      - {level_name}: {count} chunks")

            # Show sample data
            print("\n   📝 Sample chunk with embedding:")
            cursor.execute("""
                SELECT c.id, c.chunk_index, c.section, c.hierarchy_level,
                       e.model_name, e.model_dimension
                FROM paper_chunks c
                LEFT JOIN chunk_embeddings e ON c.id = e.chunk_id
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                chunk_id, idx, section, level, model, dim = row
                print(f"      - Chunk ID: {chunk_id}")
                print(f"      - Index: {idx}, Section: {section}, Level: {level}")
                print(f"      - Embedding: {model} ({dim}d)")

            cursor.close()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)

        # Cleanup
        pool.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
