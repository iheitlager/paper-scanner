#!/usr/bin/env python3

"""Unit tests for Ollama handler functionality."""

from unittest.mock import Mock, patch

import pytest

from paper_scanner.models.ollama import OllamaHandler


class TestOllamaHandler:
    """Tests for Ollama-specific handler functionality."""

    def test_ollama_handler_initialization(self):
        """Test OllamaHandler initialization."""
        handler = OllamaHandler()
        assert handler is not None
        assert handler.GROUP == "Ollama"

    def test_ollama_handler_has_models(self):
        """Test that OllamaHandler has supported models."""
        assert len(OllamaHandler.MODELS) > 0
        assert "phi" in OllamaHandler.MODELS
        assert "tinyllama" in OllamaHandler.MODELS
        assert "llama3.2:1b" in OllamaHandler.MODELS

    def test_ollama_handler_token_estimation(self):
        """Test token estimation in Ollama handler."""
        text = "This is a test string with approximately 8 words total"
        tokens = OllamaHandler._estimate_tokens(text)

        # 4 chars ≈ 1 token, so ~56 chars / 4 = ~14 tokens
        assert tokens > 0
        assert tokens == len(text) // 4

    def test_ollama_handler_get_model_name(self):
        """Test that OllamaHandler returns model name."""
        handler = OllamaHandler()
        model_name = handler._get_model_name()

        assert model_name is not None
        assert isinstance(model_name, str)
        assert model_name == "phi"  # Default

    @patch("subprocess.run")
    def test_ollama_handler_call_success(self, mock_run):
        """Test successful Ollama handler call."""
        # Mock successful subprocess output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": "parsed JSON"}'
        mock_run.return_value = mock_result

        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="test text",
            system_prompt="test prompt",
            max_tokens=100
        )

        assert result is not None
        assert result["result"] == "parsed JSON"
        assert token_usage["input_tokens"] > 0
        assert token_usage["output_tokens"] > 0

    @patch("subprocess.run")
    def test_ollama_handler_call_subprocess_error(self, mock_run):
        """Test Ollama handler call with subprocess error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"
        mock_run.return_value = mock_result

        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="test text",
            system_prompt="test prompt",
            max_tokens=100
        )

        assert result is None
        assert token_usage["input_tokens"] == 0

    @patch("subprocess.run")
    def test_ollama_handler_call_json_parse_failure(self, mock_run):
        """Test Ollama handler call with JSON parsing failure."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Not valid JSON at all"
        mock_run.return_value = mock_result

        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="test text",
            system_prompt="test prompt",
            max_tokens=100
        )

        assert result is None

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_ollama_handler_call_ollama_not_found(self, mock_run):
        """Test Ollama handler when ollama command is not found."""
        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="test text",
            system_prompt="test prompt",
            max_tokens=100
        )

        assert result is None

    @patch("subprocess.run", side_effect=TimeoutError)
    def test_ollama_handler_call_timeout(self, mock_run):
        """Test Ollama handler timeout."""
        mock_run.side_effect = Exception("timeout")
        
        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="test text",
            system_prompt="test prompt",
            max_tokens=100
        )

        assert result is None

    def test_ollama_handler_group_identifier(self):
        """Test that Ollama handler has correct group identifier."""
        assert OllamaHandler.GROUP == "Ollama"
        handler = OllamaHandler()
        assert handler.get_group() == "Ollama"

    def test_ollama_handler_extract_pdf_text(self):
        """Test that Ollama handler inherits PDF extraction."""
        handler = OllamaHandler()
        
        assert hasattr(handler, "extract_pdf_text")
        assert callable(handler.extract_pdf_text)

    @patch("pypdf.PdfReader")
    def test_ollama_handler_pdf_extraction(self, mock_pdf_reader):
        """Test Ollama handler PDF extraction."""
        handler = OllamaHandler()
        
        # Mock the PDF reading
        mock_page = Mock()
        mock_page.extract_text.return_value = "Ollama extracted PDF content"
        mock_pdf_reader.return_value.pages = [mock_page]

        result = handler.extract_pdf_text("/path/to/document.pdf")
        assert result == "Ollama extracted PDF content"

    def test_ollama_models_have_token_limits(self):
        """Test that Ollama models have reasonable token limits."""
        for model, tokens in OllamaHandler.MODELS.items():
            assert isinstance(tokens, int)
            assert tokens > 0
            # Ollama models should have reasonable limits
            assert 1024 <= tokens <= 8192

    def test_ollama_handler_logging(self):
        """Test Ollama handler logging functionality."""
        logged_messages = []

        def mock_logger(msg: str):
            logged_messages.append(msg)

        handler = OllamaHandler(logger=mock_logger)
        handler.log("test message")
        
        assert len(logged_messages) == 1
        assert logged_messages[0] == "test message"

    def test_ollama_handler_get_models(self):
        """Test getting all Ollama models."""
        models = OllamaHandler.get_models()
        
        assert isinstance(models, dict)
        assert len(models) > 0
        assert "phi" in models
        assert "tinyllama" in models
        assert "llama3.2:1b" in models

    @patch("subprocess.run")
    def test_ollama_handler_call_with_valid_json_output(self, mock_run):
        """Test Ollama handler call with various JSON formats."""
        handler = OllamaHandler()
        
        test_cases = [
            '{"status": "success"}',
            '{"data": [1, 2, 3]}',
            '{"nested": {"key": "value"}}',
        ]
        
        for json_output in test_cases:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json_output
            mock_run.return_value = mock_result
            
            result, token_usage = handler.call(
                text="test",
                system_prompt="prompt",
                max_tokens=100
            )
            
            assert result is not None
            assert isinstance(result, dict)

    @patch("subprocess.run")
    def test_ollama_handler_token_usage_calculation(self, mock_run):
        """Test that token usage is properly calculated."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"output": "test response"}'
        mock_run.return_value = mock_result

        handler = OllamaHandler()
        result, token_usage = handler.call(
            text="input text here",
            system_prompt="system prompt here",
            max_tokens=100
        )

        # Token usage should be estimated based on character count
        assert token_usage["input_tokens"] > 0
        assert token_usage["output_tokens"] > 0
        # Input should be more than output for this test
        assert token_usage["input_tokens"] > token_usage["output_tokens"]
