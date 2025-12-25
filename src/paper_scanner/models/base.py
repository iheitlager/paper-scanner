"""Base handler for LLM processing with handler registry."""

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple

from pypdf import PdfReader


class LLMHandler(ABC):
    """Abstract base class for LLM handlers (Claude, Ollama, etc.)."""

    # Each handler must define its supported models
    # Format: {"model_name": max_output_tokens}
    MODELS: Dict[str, int] = {}

    # Each handler should define its group name (e.g., "Claude", "Ollama")
    GROUP: str = "Unknown"

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        """
        Initialize handler with optional logger function.

        Args:
            logger: Optional function that takes a string message for logging.
                   If None, logging is disabled.
        """
        self.logger = logger

    def log(self, message: str) -> None:
        """Log a message if logger is available."""
        if self.logger:
            self.logger(message)

    @abstractmethod
    def call(
        self,
        text: str,
        system_prompt: str,
        max_tokens: int,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, int]]:
        """
        Process text with the LLM handler.

        Args:
            text: Input text or file path to process
            system_prompt: System prompt to guide the LLM
            max_tokens: Maximum tokens for output

        Returns:
            Tuple of (parsed_json_response, token_usage)
            - parsed_json_response: Parsed JSON dict or None on error
            - token_usage: Dict with "input_tokens" and "output_tokens" keys
        """
        pass

    @classmethod
    def get_models(cls) -> Dict[str, int]:
        """Get supported models for this handler."""
        return cls.MODELS.copy()

    @classmethod
    def get_group(cls) -> str:
        """Get the group name for this handler."""
        return cls.GROUP

    def extract_pdf_text(self, file_path: str, max_chars: Optional[int] = None) -> Optional[str]:
        """
        Extract text from PDF using pypdf.

        Args:
            file_path: Path to PDF file
            max_chars: Optional limit on characters to extract

        Returns:
            Extracted text or None on error
        """
        try:
            reader = PdfReader(file_path)
            text = ""

            # Extract text from all pages
            for _, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text
                    # If we've already reached max_chars, stop reading
                    if max_chars and len(text) >= max_chars:
                        break

            # Truncate to max_chars if specified
            if max_chars:
                text = text[:max_chars]

            if not text.strip():
                self.log(f"Warning: No text extracted from {file_path}")
                return None

            return text
        except Exception as e:
            self.log(f"Warning: Could not extract PDF text from {file_path}: {e}")
            return None


# Handler registry
_HANDLER_REGISTRY: Dict[str, LLMHandler] = {}


def register_handler(handler: LLMHandler) -> None:
    """
    Register a handler for its supported models.

    Args:
        handler: Handler instance to register
    """
    for model_name in handler.MODELS.keys():
        _HANDLER_REGISTRY[model_name] = handler


def get_handler(model_name: str) -> Optional[LLMHandler]:
    """
    Get handler for a given model name.

    Args:
        model_name: Name of the model

    Returns:
        Handler instance or None if not registered
    """
    return _HANDLER_REGISTRY.get(model_name)


def get_all_models() -> Dict[str, int]:
    """
    Get all available models across all registered handlers.

    Returns:
        Dict mapping model names to max output tokens
    """
    all_models = {}
    for handler in set(_HANDLER_REGISTRY.values()):  # Use set to avoid duplicates
        all_models.update(handler.get_models())
    return all_models


def get_models_by_group() -> Dict[str, Dict[str, int]]:
    """
    Get all available models grouped by handler.

    Returns:
        Dict mapping group names to {model_name: max_output_tokens}
    """
    models_by_group = {}
    for handler in set(_HANDLER_REGISTRY.values()):  # Use set to avoid duplicates
        group = handler.get_group()
        if group not in models_by_group:
            models_by_group[group] = {}
        models_by_group[group].update(handler.get_models())
    return models_by_group


def get_registered_handlers() -> Dict[str, LLMHandler]:
    """Get all registered handlers."""
    return _HANDLER_REGISTRY.copy()


def parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from response with robust cleanup.

    Handles:
    - Preamble before JSON
    - Markdown code blocks
    - Trailing content after JSON
    - Various whitespace

    Args:
        response_text: Raw response from LLM

    Returns:
        Parsed JSON dict or None on error
    """
    try:
        # Remove preamble before JSON
        json_start = response_text.find("{")
        if json_start != -1:
            response_text = response_text[json_start:]

        # Remove markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n", 1)
            if len(lines) > 1:
                response_text = lines[1]
            if response_text.endswith("```"):
                response_text = response_text[:-3].rstrip()

        # Remove anything after closing brace
        json_end = response_text.rfind("}")
        if json_end != -1:
            response_text = response_text[: json_end + 1]

        # Parse JSON
        return json.loads(response_text)
    except json.JSONDecodeError:
        return None


# ============================================================================
# Handler Registration (Deferred to avoid circular imports)
# ============================================================================


def initialize_handlers(api_key: Optional[str] = None, logger: Optional[Callable[[str], None]] = None) -> None:
    """
    Initialize and register all available handlers.

    Should be called once at application startup.

    Args:
        api_key: Anthropic API key for Claude handler (optional for listing models)
        logger: Optional logging function for handlers
    """
    # Import here to avoid circular imports
    from .anthropic import ClaudeHandler
    from .ollama import OllamaHandler

    # Always register Claude handler (models are available regardless of API key)
    # The API key will be checked when actually calling the handler
    try:
        claude_handler = ClaudeHandler(api_key=api_key or "", logger=logger)
        register_handler(claude_handler)
    except Exception:
        # If Claude handler fails to initialize, it's OK - Ollama will still work
        pass

    # Register Ollama handler (always available if Ollama is installed)
    ollama_handler = OllamaHandler(logger=logger)
    register_handler(ollama_handler)
