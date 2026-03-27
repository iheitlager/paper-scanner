"""
Unit tests for embedding SQL persistence (pgvector integration).

Tests:
- EmbeddingToRowConverter: Convert Embedding models to SQL rows
- PaperUploader.insert_embeddings: Insert/upsert embeddings into paper_embeddings table
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

from paper_scanner.core.models import Embedding, Paper, TextChunk
from paper_scanner.io.sql import (
    DatabaseConnectionPool,
    EmbeddingToRowConverter,
    PaperUploader,
)


class TestEmbeddingToRowConverter(unittest.TestCase):
    """Test embedding to SQL row conversion"""

    def test_embedding_to_row_valid(self):
        """Test converting valid embedding to SQL row"""
        embedding = Embedding(
            vector=[0.1] * 768,  # Valid 768-dim vector
            model="all-mpnet-base-v2",
            text_source="title",
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        row = EmbeddingToRowConverter.embedding_to_row(
            embedding,
            paper_db_id=1,
            embedding_method="title",
            embedding_version=1,
        )

        # Verify row structure
        assert row["paper_id"] == 1
        assert row["model_name"] == "all-mpnet-base-v2"
        assert row["embedding_method"] == "title"
        assert row["embedding_version"] == 1
        assert row["created_at"] == embedding.created_at
        assert len(row["embedding"]) == 768
        assert all(v == 0.1 for v in row["embedding"])

    def test_embedding_to_row_invalid_dimensions(self):
        """Test that invalid dimension vectors raise error during Embedding creation"""
        from pydantic_core import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            Embedding(
                vector=[0.1] * 512,  # Wrong dimensions
                model="all-mpnet-base-v2",
                text_source="title",
            )

        assert "768 dimensions" in str(ctx.exception)

    def test_embedding_to_row_different_methods(self):
        """Test converting embeddings with different methods"""
        vector = [0.1] * 768
        embedding = Embedding(
            vector=vector,
            model="all-mpnet-base-v2",
            text_source="abstract",
        )

        for method in ["title", "abstract", "keywords", "full_text"]:
            row = EmbeddingToRowConverter.embedding_to_row(
                embedding,
                paper_db_id=1,
                embedding_method=method,
            )
            assert row["embedding_method"] == method


class TestPaperUploaderEmbeddings(unittest.TestCase):
    """Test PaperUploader.insert_embeddings method"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_pool = Mock(spec=DatabaseConnectionPool)
        self.uploader = PaperUploader(self.mock_pool)

    def test_insert_embeddings_empty_list(self):
        """Test inserting empty paper list"""
        stats = self.uploader.insert_embeddings([], dry_run=False)

        assert stats["upserted"] == 0
        assert stats["skipped"] == 0
        assert stats["error_count"] == 0

    def test_insert_embeddings_no_embeddings(self):
        """Test inserting papers without embeddings"""
        # Create paper with text chunks but no embeddings
        chunk = TextChunk(
            chunk_index=0,
            text="Some text without embedding",
            embedding=None,  # No embedding
        )
        paper = Paper(
            id="paper-1",
            cite_key="key1",
            title="Test Paper",
            text_chunks=[chunk],
        )

        # Mock connection with context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = None
        self.mock_pool.get_connection.return_value = mock_cm

        stats = self.uploader.insert_embeddings([paper], dry_run=False)

        # Chunk without embedding should be skipped
        assert stats["skipped"] >= 1

    def test_insert_embeddings_dry_run(self):
        """Test dry-run mode"""
        embedding = Embedding(
            vector=[0.1] * 768,
            model="all-mpnet-base-v2",
            text_source="title",
        )
        chunk = TextChunk(
            chunk_index=0,
            text="Test chunk text",
            embedding=embedding,
        )
        paper = Paper(
            id="paper-1",
            cite_key="key1",
            title="Test Paper",
            text_chunks=[chunk],
        )

        stats = self.uploader.insert_embeddings([paper], dry_run=True)

        # In dry-run, should report upserted without actually inserting
        assert stats["upserted"] == 1
        assert stats["skipped"] == 0
        assert self.mock_pool.get_connection.call_count == 0

    @patch("paper_scanner.io.sql.logger")
    def test_insert_embeddings_with_mock_connection(self, mock_logger):
        """Test actual embedding insertion with mocked database"""
        embedding = Embedding(
            vector=[0.1] * 768,
            model="all-mpnet-base-v2",
            text_source="title",
        )
        chunk = TextChunk(
            chunk_index=0,
            text="Test chunk text",
            embedding=embedding,
        )
        paper = Paper(
            id="paper-1",
            cite_key="key1",
            title="Test Paper",
            text_chunks=[chunk],
        )

        # Set up mock connection with context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Return paper_db_id = 1
        mock_conn.cursor.return_value = mock_cursor

        # Create context manager mock
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = None
        self.mock_pool.get_connection.return_value = mock_cm

        # Execute
        stats = self.uploader.insert_embeddings([paper], dry_run=False)

        # Verify database calls were made
        assert stats["upserted"] == 1
        assert mock_cursor.execute.called
        assert mock_conn.commit.called

    def test_insert_embeddings_filter_valid_papers(self):
        """Test that papers/chunks without embeddings are correctly filtered"""
        embedding = Embedding(
            vector=[0.1] * 768,
            model="all-mpnet-base-v2",
            text_source="title",
        )
        no_embedding = TextChunk(
            chunk_index=0,
            text="No embedding text",
            embedding=None,
        )

        papers = [
            Paper(
                id="paper-1",
                cite_key="key1",
                title="Has Embedding",
                text_chunks=[
                    TextChunk(
                        chunk_index=0,
                        text="Has embedding text",
                        embedding=embedding,
                    )
                ],
            ),
            Paper(
                id="paper-2",
                cite_key="key2",
                title="No Embedding",
                text_chunks=[no_embedding],
            ),
            Paper(
                id="paper-3",
                cite_key="key3",
                title="Has Embedding 2",
                text_chunks=[
                    TextChunk(
                        chunk_index=0,
                        text="Has embedding text 2",
                        embedding=embedding,
                    )
                ],
            ),
        ]

        # Mock connection with context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Return paper_db_id = 1
        mock_conn.cursor.return_value = mock_cursor

        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = None
        self.mock_pool.get_connection.return_value = mock_cm

        stats = self.uploader.insert_embeddings(papers, dry_run=False)

        # Should insert 2 chunks with embeddings, skip 1 without
        assert stats["upserted"] == 2
        assert stats["skipped"] == 1
        assert stats["error_count"] == 0


class TestEmbeddingRowConversion(unittest.TestCase):
    """Integration tests for embedding conversion"""

    def test_embedding_round_trip(self):
        """Test that embedding can be converted and restored"""
        original_vector = [0.1 * i for i in range(768)]
        embedding = Embedding(
            vector=original_vector,
            model="all-mpnet-base-v2",
            text_source="title",
        )

        # Convert to row
        row = EmbeddingToRowConverter.embedding_to_row(
            embedding,
            paper_db_id=1,
            embedding_method="title",
            embedding_version=1,
        )

        # Verify all fields present
        assert "paper_id" in row
        assert "embedding" in row
        assert "model_name" in row
        assert "embedding_method" in row
        assert "embedding_version" in row
        assert "created_at" in row

        # Verify data integrity
        assert row["model_name"] == embedding.model
        assert row["embedding_method"] == "title"
        assert row["created_at"] == embedding.created_at


if __name__ == "__main__":
    unittest.main()
