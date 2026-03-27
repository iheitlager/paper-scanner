#!/usr/bin/env python3

"""Unit tests for Claude handler functionality."""

import tempfile
from pathlib import Path
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

    @patch("paper_scanner.models.anthropic.parse_json_response")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_text_input(self, mock_anthropic_class, mock_parse_json):
        """Test calling Claude with plain text input."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="{'result': 'success'}")]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        # Mock the JSON parser
        expected_result = {"result": "success"}
        mock_parse_json.return_value = expected_result

        # Execute
        handler = ClaudeHandler(api_key="test_key", model="claude-3-opus-20240229")
        result, token_usage = handler.call(
            text="Hello Claude",
            system_prompt="You are helpful",
            max_tokens=1000
        )

        # Verify
        assert result == expected_result
        assert token_usage["input_tokens"] == 100
        assert token_usage["output_tokens"] == 50
        mock_client.messages.create.assert_called_once()

    @patch("paper_scanner.models.anthropic.parse_json_response")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_pdf_file(self, mock_anthropic_class, mock_parse_json):
        """Test calling Claude with PDF file input."""
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            f.write(b"PDF content")
            pdf_path = f.name

        try:
            # Setup mock
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [Mock(text='{"pdf": "analyzed"}')]
            mock_response.usage = Mock(input_tokens=150, output_tokens=75)
            mock_client.messages.create.return_value = mock_response

            # Mock JSON parser
            expected_result = {"pdf": "analyzed"}
            mock_parse_json.return_value = expected_result

            # Execute
            handler = ClaudeHandler(api_key="test_key")
            result, token_usage = handler.call(
                text=pdf_path,
                system_prompt="Analyze this PDF",
                max_tokens=2000
            )

            # Verify
            assert result == expected_result
            assert token_usage["input_tokens"] == 150
            assert token_usage["output_tokens"] == 75

            # Verify that messages.create was called with document content
            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 1
            assert len(messages[0]["content"]) == 1
            assert messages[0]["content"][0]["type"] == "document"
        finally:
            Path(pdf_path).unlink()

    @patch("paper_scanner.models.anthropic.parse_json_response")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_pdf_that_fails_to_open(self, mock_anthropic_class, mock_parse_json):
        """Test calling Claude with PDF that can't be opened - falls back to text."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text='{"fallback": "text"}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        # Mock JSON parser
        expected_result = {"fallback": "text"}
        mock_parse_json.return_value = expected_result

        logged = []
        def log_fn(msg):
            logged.append(msg)

        # Execute with non-existent PDF path
        handler = ClaudeHandler(api_key="test_key", logger=log_fn)
        result, token_usage = handler.call(
            text="/nonexistent/file.pdf",
            system_prompt="Test",
            max_tokens=1000
        )

        # Verify - should treat as text since file doesn't exist
        assert result == expected_result
        assert token_usage["input_tokens"] == 100

        # Verify the text content was used
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["content"][0]["type"] == "text"

    @patch("paper_scanner.models.anthropic.parse_json_response")
    @patch("paper_scanner.models.anthropic.time.sleep")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_rate_limit_error_and_retry(self, mock_anthropic_class, mock_sleep, mock_parse_json):
        """Test that rate limit errors trigger retry logic."""
        from anthropic import RateLimitError

        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First call raises RateLimitError, second succeeds
        mock_response = Mock()
        mock_response.content = [Mock(text='{"retry": "success"}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)

        # Create instances that will trigger isinstance checks
        mock_client.messages.create.side_effect = [
            RateLimitError(message="Rate limited", response=Mock(status_code=429), body={}),
            mock_response
        ]

        # Mock JSON parser
        expected_result = {"retry": "success"}
        mock_parse_json.return_value = expected_result

        logged = []
        def log_fn(msg):
            logged.append(msg)

        # Execute
        handler = ClaudeHandler(api_key="test_key", logger=log_fn)
        result, token_usage = handler.call(
            text="Test",
            system_prompt="Test",
            max_tokens=1000
        )

        # Verify
        assert result == expected_result
        mock_sleep.assert_called_once_with(61)  # RATE_LIMIT_WAIT
        assert any("Rate limit" in msg for msg in logged)

    @patch("paper_scanner.models.anthropic.time.sleep")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_max_retries_exceeded(self, mock_anthropic_class, mock_sleep):
        """Test that max retries are respected."""
        from anthropic import RateLimitError

        # Setup mock to always raise RateLimitError
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Create real RateLimitError instances
        rate_limit_error = RateLimitError(message="Rate limited", response=Mock(status_code=429), body={})

        mock_client.messages.create.side_effect = rate_limit_error

        logged = []
        def log_fn(msg):
            logged.append(msg)

        # Execute
        handler = ClaudeHandler(api_key="test_key", logger=log_fn)
        result, token_usage = handler.call(
            text="Test",
            system_prompt="Test",
            max_tokens=1000
        )

        # Verify
        assert result is None
        assert token_usage["input_tokens"] == 0
        assert token_usage["output_tokens"] == 0
        assert mock_sleep.call_count == 5  # MAX_RETRIES
        assert any("Max retries" in msg for msg in logged)

    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_generic_error(self, mock_anthropic_class):
        """Test that generic errors are caught."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = ValueError("Some error")

        logged = []
        def log_fn(msg):
            logged.append(msg)

        # Execute
        handler = ClaudeHandler(api_key="test_key", logger=log_fn)
        result, token_usage = handler.call(
            text="Test",
            system_prompt="Test",
            max_tokens=1000
        )

        # Verify
        assert result is None
        assert token_usage["input_tokens"] == 0
        assert any("Error calling Claude API" in msg for msg in logged)

    @patch("paper_scanner.models.anthropic.parse_json_response")
    @patch("paper_scanner.models.anthropic.Anthropic")
    def test_call_with_pdf_file_read_error(self, mock_anthropic_class, mock_parse_json):
        """Test calling Claude with PDF file that fails to read."""
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            f.write(b"PDF content")
            pdf_path = f.name

        try:
            # Setup mock
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [Mock(text='{"fallback": "text_mode"}')]
            mock_response.usage = Mock(input_tokens=100, output_tokens=50)
            mock_client.messages.create.return_value = mock_response

            # Mock JSON parser
            expected_result = {"fallback": "text_mode"}
            mock_parse_json.return_value = expected_result

            logged = []
            def log_fn(msg):
                logged.append(msg)

            # Patch open to raise an exception
            with patch("builtins.open", side_effect=PermissionError("Cannot read file")):
                # Execute
                handler = ClaudeHandler(api_key="test_key", logger=log_fn)
                result, token_usage = handler.call(
                    text=pdf_path,
                    system_prompt="Test",
                    max_tokens=1000
                )

            # Verify - should fall back to text mode
            assert result == expected_result
            assert token_usage["input_tokens"] == 100

            # Verify warning was logged
            assert any("Could not encode PDF" in msg for msg in logged)

            # Verify text content was used
            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"][0]["type"] == "text"
        finally:
            Path(pdf_path).unlink()
