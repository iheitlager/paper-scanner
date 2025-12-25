#!/usr/bin/env python3

"""Unit tests for Claude handler functionality."""

from unittest.mock import Mock, patch

from paper_scanner.models.anthropic import ClaudeHandler


class TestClaudeHandler:
    """Tests for Claude-specific handler functionality."""

    def test_claude_handler_initialization(self):
        """Test ClaudeHandler initialization."""
        handler = ClaudeHandler(api_key="test_key")
        assert handler is not None
        assert handler.GROUP == "Claude"

    def test_claude_handler_has_models(self):
        """Test that ClaudeHandler has supported models."""
        assert len(ClaudeHandler.MODELS) > 0
        assert "claude-3-opus-20240229" in ClaudeHandler.MODELS
        assert "claude-sonnet-4-5-20250929" in ClaudeHandler.MODELS

    def test_claude_handler_group_identifier(self):
        """Test that Claude handler has correct group identifier."""
        assert ClaudeHandler.GROUP == "Claude"
        handler = ClaudeHandler(api_key="test_key")
        assert handler.get_group() == "Claude"

    def test_claude_model_token_limits(self):
        """Test that Claude models have correct token limits."""
        for model, tokens in ClaudeHandler.MODELS.items():
            assert isinstance(tokens, int)
            assert tokens > 0
            assert tokens <= 16384  # Reasonable max for Claude models

    def test_claude_handler_has_supported_models(self):
        """Test specific Claude model availability."""
        models = ClaudeHandler.get_models()

        # Should have at least one Claude 3 model
        assert any("claude-3" in m or "claude-" in m for m in models.keys())

        # All should have token limits
        for model, tokens in models.items():
            assert isinstance(tokens, int)
            assert tokens > 0

    def test_claude_handler_default_model(self):
        """Test that Claude handler initializes with a default model."""
        handler = ClaudeHandler(api_key="test_key")
        assert hasattr(handler, "model")
        assert handler.model is not None
        assert isinstance(handler.model, str)
        assert handler.model in ClaudeHandler.MODELS

    def test_claude_handler_model_setting(self):
        """Test that Claude handler model can be set."""
        handler = ClaudeHandler(api_key="test_key", model="claude-3-opus-20240229")
        assert handler.model == "claude-3-opus-20240229"

    def test_claude_handler_logging(self):
        """Test Claude handler logging functionality."""
        logged_messages = []

        def mock_logger(msg: str):
            logged_messages.append(msg)

        handler = ClaudeHandler(api_key="test_key", logger=mock_logger)
        handler.log("test message")

        assert len(logged_messages) == 1
        assert logged_messages[0] == "test message"

    def test_claude_handler_extract_pdf_text(self):
        """Test that Claude handler inherits PDF extraction."""
        handler = ClaudeHandler(api_key="test_key")

        assert hasattr(handler, "extract_pdf_text")
        assert callable(handler.extract_pdf_text)

    @patch("paper_scanner.models.base.PdfReader")
    def test_claude_handler_pdf_extraction(self, mock_pdf_reader):
        """Test Claude handler PDF extraction."""
        handler = ClaudeHandler(api_key="test_key")

        # Mock the PDF reading
        mock_page = Mock()
        mock_page.extract_text.return_value = "Claude extracted PDF content"
        mock_pdf_reader.return_value.pages = [mock_page]

        result = handler.extract_pdf_text("/path/to/document.pdf")
        assert result == "Claude extracted PDF content"

    def test_claude_models_have_reasonable_token_limits(self):
        """Test that Claude model token limits are reasonable."""
        for model, tokens in ClaudeHandler.MODELS.items():
            # Claude models should have at least 1024 tokens max output
            assert tokens >= 1024, f"Model {model} has unexpectedly low token limit: {tokens}"

            # Claude models should not exceed 16384 tokens
            assert tokens <= 16384, f"Model {model} has unexpectedly high token limit: {tokens}"

    def test_claude_handler_api_key_storage(self):
        """Test that Claude handler stores API key."""
        api_key = "test_api_key_123"
        handler = ClaudeHandler(api_key=api_key)

        assert handler.api_key is not None
        assert handler.api_key == api_key

    def test_claude_handler_client_initialization(self):
        """Test that Claude handler initializes Anthropic client."""
        handler = ClaudeHandler(api_key="test_key")

        assert hasattr(handler, "client")
        assert handler.client is not None
