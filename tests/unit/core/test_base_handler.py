#!/usr/bin/env python3

"""Unit tests for base LLM handler functionality and registry."""

from unittest.mock import Mock, patch

from paper_scanner.models.anthropic import ClaudeHandler
from paper_scanner.models.base import (_HANDLER_REGISTRY, get_all_models,
                                       get_handler, get_models_by_group,
                                       get_registered_handlers,
                                       initialize_handlers,
                                       parse_json_response, register_handler)
from paper_scanner.models.ollama import OllamaHandler


class TestHandlerBase:
    """Tests for base LLM handler functionality."""

    def test_handler_has_group_identifier(self):
        """Test that handlers have a GROUP identifier."""
        assert hasattr(ClaudeHandler, "GROUP")
        assert hasattr(OllamaHandler, "GROUP")
        assert ClaudeHandler.GROUP == "Claude"
        assert OllamaHandler.GROUP == "Ollama"

    def test_handler_get_group_method(self):
        """Test that handlers can retrieve their group."""
        assert ClaudeHandler.get_group() == "Claude"
        assert OllamaHandler.get_group() == "Ollama"

    def test_handler_has_models_defined(self):
        """Test that handlers have models defined."""
        assert len(ClaudeHandler.MODELS) > 0
        assert len(OllamaHandler.MODELS) > 0

    def test_handler_get_models_method(self):
        """Test that handlers can retrieve their models."""
        claude_models = ClaudeHandler.get_models()
        ollama_models = OllamaHandler.get_models()

        assert isinstance(claude_models, dict)
        assert isinstance(ollama_models, dict)
        assert len(claude_models) > 0
        assert len(ollama_models) > 0

    def test_handler_logging_disabled_by_default(self):
        """Test that handler logging is optional."""
        handler = OllamaHandler()
        assert handler.logger is None
        # Should not raise an error when logging with no logger
        handler.log("test message")

    def test_handler_logging_with_logger(self):
        """Test that handler logging works with a logger function."""
        logged_messages = []

        def mock_logger(msg: str):
            logged_messages.append(msg)

        handler = OllamaHandler(logger=mock_logger)
        handler.log("test message")
        assert len(logged_messages) == 1
        assert logged_messages[0] == "test message"

    def test_extract_pdf_text_available(self):
        """Test that extract_pdf_text method is available on handlers."""
        claude_handler = ClaudeHandler(api_key="test_key")
        ollama_handler = OllamaHandler()

        assert hasattr(claude_handler, "extract_pdf_text")
        assert hasattr(ollama_handler, "extract_pdf_text")
        assert callable(claude_handler.extract_pdf_text)
        assert callable(ollama_handler.extract_pdf_text)

    def test_extract_pdf_text_with_pypdf_installed(self):
        """Test PDF extraction when pypdf is available."""
        handler = OllamaHandler()

        with patch("pypdf.PdfReader") as mock_pdf_reader:
            # Mock the PDF reading
            mock_page = Mock()
            mock_page.extract_text.return_value = "Sample PDF text content"
            mock_pdf_reader.return_value.pages = [mock_page]

            result = handler.extract_pdf_text("/path/to/test.pdf")
            assert result == "Sample PDF text content"

    def test_extract_pdf_text_without_pypdf(self):
        """Test PDF extraction when pypdf is not available."""
        handler = OllamaHandler()
        logged_messages = []

        def mock_logger(msg: str):
            logged_messages.append(msg)

        handler.logger = mock_logger

        with patch.dict("sys.modules", {"pypdf": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                result = handler.extract_pdf_text("/path/to/test.pdf")
                assert result is None
                assert any("pypdf not installed" in msg for msg in logged_messages)


class TestHandlerRegistry:
    """Tests for handler registration and retrieval."""

    def setup_method(self):
        """Initialize handlers before each test."""
        # Initialize handlers fresh for each test
        _HANDLER_REGISTRY.clear()
        initialize_handlers(api_key="test_key")

    def test_initialize_handlers(self):
        """Test that handlers are initialized and registered."""
        initialize_handlers(api_key="test_key")

        # Should have registered handlers
        handlers = get_registered_handlers()
        assert len(handlers) > 0

        # All Claude models should be registered
        for model in ClaudeHandler.MODELS.keys():
            assert model in handlers

        # All Ollama models should be registered
        for model in OllamaHandler.MODELS.keys():
            assert model in handlers

    def test_get_handler_for_model(self):
        """Test retrieving a handler for a specific model."""
        claude_handler = get_handler("claude-3-opus-20240229")
        assert claude_handler is not None
        assert isinstance(claude_handler, ClaudeHandler)

        ollama_handler = get_handler("phi")
        assert ollama_handler is not None
        assert isinstance(ollama_handler, OllamaHandler)

    def test_get_handler_for_nonexistent_model(self):
        """Test that getting a handler for non-existent model returns None."""
        handler = get_handler("nonexistent-model")
        assert handler is None

    def test_get_all_models(self):
        """Test retrieving all models across all handlers."""
        all_models = get_all_models()

        # Should include Claude models
        assert "claude-3-opus-20240229" in all_models

        # Should include Ollama models
        assert "phi" in all_models
        assert "tinyllama" in all_models

        # All models should have token limits
        for model, tokens in all_models.items():
            assert isinstance(tokens, int)
            assert tokens > 0

    def test_get_models_by_group(self):
        """Test retrieving models organized by group."""
        models_by_group = get_models_by_group()

        # Should have both Claude and Ollama groups
        assert "Claude" in models_by_group
        assert "Ollama" in models_by_group

        # Claude group should have Claude models
        claude_models = models_by_group["Claude"]
        assert "claude-3-opus-20240229" in claude_models
        assert "claude-sonnet-4-5-20250929" in claude_models

        # Ollama group should have Ollama models
        ollama_models = models_by_group["Ollama"]
        assert "phi" in ollama_models
        assert "tinyllama" in ollama_models
        assert "llama3.2:1b" in ollama_models

    def test_models_by_group_structure(self):
        """Test the structure of models_by_group output."""
        models_by_group = get_models_by_group()

        # Each group should be a dict
        for group_name, models_dict in models_by_group.items():
            assert isinstance(group_name, str)
            assert isinstance(models_dict, dict)

            # Each model should map to an integer token count
            for model_name, token_count in models_dict.items():
                assert isinstance(model_name, str)
                assert isinstance(token_count, int)
                assert token_count > 0

    def test_register_handler_multiple_models(self):
        """Test that registering a handler registers all its models."""
        _HANDLER_REGISTRY.clear()

        handler = OllamaHandler()
        register_handler(handler)

        # All Ollama models should be accessible
        for model_name in OllamaHandler.MODELS.keys():
            retrieved_handler = get_handler(model_name)
            assert retrieved_handler is handler

    def test_get_registered_handlers(self):
        """Test retrieving all registered handlers."""
        handlers = get_registered_handlers()

        # Should have at least Claude and Ollama handlers
        handler_instances = set(handlers.values())
        assert len(handler_instances) >= 2


class TestJsonParsing:
    """Tests for JSON parsing functionality."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        response = '{"key": "value", "number": 42}'
        result = parse_json_response(response)

        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_parse_json_with_preamble(self):
        """Test parsing JSON with preamble text before it."""
        response = 'Here is the JSON:\n{"key": "value"}'
        result = parse_json_response(response)

        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_with_markdown_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        response = '```json\n{"key": "value"}\n```'
        result = parse_json_response(response)

        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_with_markdown_block_no_language(self):
        """Test parsing JSON in markdown code block without language."""
        response = '```\n{"key": "value"}\n```'
        result = parse_json_response(response)

        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_with_trailing_content(self):
        """Test parsing JSON with content after closing brace."""
        response = '{"key": "value"} and some trailing text'
        result = parse_json_response(response)

        assert result is not None
        assert result["key"] == "value"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        response = "This is not JSON at all"
        result = parse_json_response(response)

        assert result is None

    def test_parse_malformed_json(self):
        """Test parsing malformed JSON returns None."""
        response = '{"key": "value"'  # Missing closing brace
        result = parse_json_response(response)

        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_json_response("")
        assert result is None


class TestHandlerGrouping:
    """Tests for handler grouping functionality."""

    def test_models_grouped_by_handler(self):
        """Test that models are correctly grouped by handler."""
        models_by_group = get_models_by_group()

        # Verify grouping
        assert "Claude" in models_by_group
        assert "Ollama" in models_by_group

        # All Claude models should be in Claude group
        for model in ClaudeHandler.MODELS.keys():
            assert model in models_by_group["Claude"]

        # All Ollama models should be in Ollama group
        for model in OllamaHandler.MODELS.keys():
            assert model in models_by_group["Ollama"]

    def test_no_model_in_multiple_groups(self):
        """Test that no model appears in multiple groups."""
        models_by_group = get_models_by_group()

        all_models_seen = set()
        for group_name, models_dict in models_by_group.items():
            for model_name in models_dict.keys():
                assert model_name not in all_models_seen, f"Model {model_name} appears in multiple groups"
                all_models_seen.add(model_name)

    def test_get_all_models_equals_flattened_groups(self):
        """Test that get_all_models matches flattened get_models_by_group."""
        all_models = get_all_models()
        models_by_group = get_models_by_group()

        # Flatten groups
        flattened = {}
        for group_models in models_by_group.values():
            flattened.update(group_models)

        assert all_models == flattened
