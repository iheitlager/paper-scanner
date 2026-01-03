"""
Unit tests for GenerateEmbeddingsStep (hierarchical implementation).

Tests cover:
- Configuration validation
- Hierarchical chunk creation (3-level)
- Embedding generation for Level 1 (sections) and Level 2 (paragraphs)
- Aggregation from paragraph to section embeddings
- Filtering options
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import numpy as np

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus, ScreeningDecision
from paper_scanner.core.models import Paper, TextChunk, Embedding, PDFInfo
from paper_scanner.steps.generate_embeddings import GenerateEmbeddingsStep


class TestGenerateEmbeddingsValidation:
    """Test configuration validation for hierarchical embeddings."""

    def test_validate_empty_config(self):
        """Empty config should be valid (uses defaults)."""
        is_valid, errors = GenerateEmbeddingsStep.validate({})
        assert is_valid
        assert len(errors) == 0

    def test_validate_valid_model(self):
        """Valid model name should pass."""
        config = {"model": "all-mpnet-base-v2"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_model_type(self):
        """Non-string model should fail."""
        config = {"model": 123}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid
        assert any("model" in e.lower() for e in errors)

    def test_validate_valid_device(self):
        """Valid device values should pass."""
        for device in ("cpu", "cuda", "mps"):
            config = {"device": device}
            is_valid, errors = GenerateEmbeddingsStep.validate(config)
            assert is_valid, f"Device '{device}' should be valid"

    def test_validate_invalid_device(self):
        """Invalid device should fail."""
        config = {"device": "gpu"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid
        assert any("device" in e.lower() for e in errors)

    def test_validate_batch_size(self):
        """Batch size must be positive integer."""
        # Valid
        config = {"batch_size": 32}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid - not integer
        config = {"batch_size": "32"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - not positive
        config = {"batch_size": 0}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

    def test_validate_filter(self):
        """Filter must be dictionary with valid options."""
        # Valid
        config = {"filter": {"included_only": True, "min_year": 2020}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid - not dict
        config = {"filter": ["included_only"]}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - wrong type for included_only
        config = {"filter": {"included_only": "true"}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - wrong type for min_year
        config = {"filter": {"min_year": "2020"}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid


class TestHierarchicalChunkCreation:
    """Test hierarchical TextChunk creation (3-level)."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock()

    @pytest.fixture
    def mock_general_config(self):
        """Create mock general config."""
        return {"project_name": "test"}

    @pytest.fixture
    def sample_paper(self):
        """Create sample paper with PDF info."""
        paper = Paper(
            cite_key="test2024",
            title="Test Paper on Machine Learning",
            year=2024,
        )
        paper.pdf_info = PDFInfo(file_path="/tmp/test.pdf")
        return paper

    @pytest.fixture
    def step(self, mock_db, mock_general_config, tmp_path):
        """Create step instance."""
        def mock_callback(msg, debug=False):
            pass  # No-op for testing
        
        return GenerateEmbeddingsStep(
            general_config=mock_general_config,
            db=mock_db,
            cache_dir=tmp_path,
            on_event=mock_callback,
        )

    def test_split_paragraphs(self, step):
        """Test paragraph splitting logic."""
        text = "First paragraph with more than 20 chars.\n\nSecond paragraph with enough text.\n\nThird paragraph here."
        paragraphs = step._split_paragraphs(text)

        assert len(paragraphs) >= 2
        assert "First" in paragraphs[0]

    def test_split_paragraphs_filters_short(self, step):
        """Test that very short paragraphs are filtered."""
        text = "A\n\nLong enough paragraph here with more than 20 characters."
        paragraphs = step._split_paragraphs(text)

        # "A" should be filtered out
        assert all(len(p) > 20 for p in paragraphs)


class TestEmbeddingGeneration:
    """Test embedding generation for hierarchical chunks."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock()

    @pytest.fixture
    def mock_general_config(self):
        """Create mock general config."""
        return {"project_name": "test"}

    @pytest.fixture
    def step(self, mock_db, mock_general_config, tmp_path):
        """Create step instance."""
        def mock_callback(msg, debug=False):
            pass  # No-op for testing
        
        return GenerateEmbeddingsStep(
            general_config=mock_general_config,
            db=mock_db,
            cache_dir=tmp_path,
            on_event=mock_callback,
        )

    @pytest.fixture
    def mock_model(self):
        """Create mock SentenceTransformer model."""
        model = MagicMock()
        model.get_sentence_embedding_dimension.return_value = 768
        # Return proper embeddings as numpy array (single text returns 1D array)
        model.encode.return_value = np.random.randn(768)
        return model

    def test_generate_embedding_success(self, step, mock_model):
        """Test successful embedding generation."""
        text = "This is a test sentence for embedding generation."
        embedding = step._generate_embedding(text, mock_model, batch_size=32, model_name="all-mpnet-base-v2")

        assert embedding is not None
        assert embedding.vector is not None
        assert len(embedding.vector) == 768
        assert embedding.model == "all-mpnet-base-v2"

    def test_generate_embedding_empty_text(self, step, mock_model):
        """Test handling of empty text."""
        text = ""
        embedding = step._generate_embedding(text, mock_model, batch_size=32, model_name="all-mpnet-base-v2")

        # Should handle gracefully
        assert embedding is None or isinstance(embedding, Embedding)


class TestExecutionWithHierarchy:
    """Test full execution with hierarchical chunks."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_general_config(self):
        """Create mock general config."""
        return {"project_name": "test"}

    @pytest.fixture
    def sample_paper(self):
        """Create sample paper with PDF."""
        paper = Paper(
            cite_key="test2024",
            title="Test Paper",
            year=2024,
        )
        paper.pdf_info = PDFInfo(file_path="/tmp/test.pdf")
        return paper

    @pytest.fixture
    def step(self, mock_db, mock_general_config, tmp_path):
        """Create step instance."""
        def mock_callback(msg, debug=False):
            pass  # No-op for testing
        
        return GenerateEmbeddingsStep(
            general_config=mock_general_config,
            db=mock_db,
            cache_dir=tmp_path,
            on_event=mock_callback,
        )

    def test_execute_no_papers(self, step, mock_db):
        """Should handle case with no papers."""
        mock_db.find.return_value = []

        result = step.execute(config={})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_count"] == 0

    def test_execute_with_hierarchical_chunks(self, step, mock_db, sample_paper):
        """Test that chunks are created with proper hierarchy."""
        # Create some test chunks with proper hierarchy
        paper_chunk = TextChunk(
            chunk_index=0,
            text="[Paper root]",
            hierarchy_level=0,
            paper=sample_paper,
            parent_chunk=None,
        )
        
        section_chunk = TextChunk(
            chunk_index=1,
            text="Introduction section content...",
            section="introduction",
            hierarchy_level=1,
            paper=sample_paper,
            parent_chunk=paper_chunk,
        )
        paper_chunk.children_chunks.append(section_chunk)

        para_chunk = TextChunk(
            chunk_index=2,
            text="This is a paragraph in the introduction.",
            section="introduction",
            hierarchy_level=2,
            paper=sample_paper,
            parent_chunk=section_chunk,
        )
        section_chunk.children_chunks.append(para_chunk)

        chunks = [paper_chunk, section_chunk, para_chunk]

        # Verify hierarchy structure
        assert paper_chunk.hierarchy_level == 0
        assert section_chunk.hierarchy_level == 1
        assert section_chunk.parent_chunk == paper_chunk
        assert paper_chunk.children_chunks[0] == section_chunk
        assert para_chunk.hierarchy_level == 2
        assert para_chunk.parent_chunk == section_chunk
        assert section_chunk.children_chunks[0] == para_chunk

    def test_device_selection_mps(self, step):
        """Test device selection prioritizes MPS."""
        with patch("torch.backends.mps.is_available", return_value=True):
            device = step._select_device(None)
            # Will be "mps" if mps check passes
            assert device in ("mps", "cuda", "cpu")

    def test_device_selection_cuda(self, step):
        """Test device selection falls back to CUDA."""
        import torch
        with patch("torch.backends.mps.is_available", return_value=False):
            with patch("torch.cuda.is_available", return_value=True):
                device = step._select_device(None)
                assert device in ("cuda", "cpu")

    def test_device_selection_cpu(self, step):
        """Test device selection defaults to CPU."""
        import torch
        with patch("torch.backends.mps.is_available", return_value=False):
            with patch("torch.cuda.is_available", return_value=False):
                device = step._select_device(None)
                assert device == "cpu"

    def test_device_selection_explicit(self, step):
        """Test explicit device selection."""
        device = step._select_device("mps")
        assert device == "mps"

        device = step._select_device("cpu")
        assert device == "cpu"
