"""Claude API handler for Anthropic models."""

import base64
import os
from typing import Callable, Optional, Dict, Any, Tuple

from anthropic import Anthropic, RateLimitError

from .base import LLMHandler, parse_json_response


class ClaudeHandler(LLMHandler):
    """Handler for Anthropic Claude models via API."""

    # Group identifier for Claude models
    GROUP = "Claude"

    # Supported Claude models with max output tokens
    MODELS = {
        # Claude 4 models (current generation)
        "claude-opus-4-20250514": 16384,          # Most capable
        "claude-sonnet-4-5-20250929": 16384,      # Best balance of speed & capability
        "claude-haiku-4-5-20251001": 16384,       # Fastest, most economical
        # Claude 3.5 models (previous generation)
        "claude-3-5-sonnet-20241022": 8192,
        "claude-3-5-haiku-20241022": 8192,
        # Claude 3 models (legacy)
        "claude-3-opus-20240229": 4096,
    }

    MAX_RETRIES = 5
    RATE_LIMIT_WAIT = 61

    def __init__(self, api_key: str, model: Optional[str] = None, logger: Optional[Callable] = None):
        """
        Initialize Claude handler.

        Args:
            api_key: Anthropic API key
            model: Model to use (defaults to first available or claude-opus-4-20250514)
            logger: Optional logging function
        """
        super().__init__(logger=logger)
        self.client = Anthropic(api_key=api_key)
        self.api_key = api_key
        self.model = model or "claude-opus-4-20250514"  # Default to Opus if not specified

    def call(
        self,
        text: str,
        system_prompt: str,
        max_tokens: int,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, int]]:
        """
        Call Claude API with the given text and prompt.

        Supports both:
        - Direct text input
        - PDF file paths (encoded as base64 documents)

        Args:
            text: Input text or path to PDF file
            system_prompt: System prompt to guide Claude
            max_tokens: Maximum output tokens

        Returns:
            Tuple of (parsed_json_response, token_usage)
        """
        token_usage = {"input_tokens": 0, "output_tokens": 0}
        retries = 0

        while retries <= self.MAX_RETRIES:
            try:
                # Prepare message content
                content = []

                # If text is a file path to a PDF, encode and send as document
                if text.lower().endswith('.pdf') and os.path.exists(text):
                    try:
                        with open(text, 'rb') as f:
                            pdf_bytes = f.read()
                            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

                        content.append({
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64
                            }
                        })
                    except Exception as e:
                        self.log(f"Warning: Could not encode PDF {text}: {e}. Using as text instead.")
                        content.append({"type": "text", "text": text})
                else:
                    # Regular text content
                    content.append({"type": "text", "text": text})

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": content}],
                )

                # Capture token usage from API response
                if hasattr(response, 'usage'):
                    token_usage["input_tokens"] = response.usage.input_tokens
                    token_usage["output_tokens"] = response.usage.output_tokens

                response_text = response.content[0].text.strip()
                parsed_response = parse_json_response(response_text)
                return (parsed_response, token_usage)

            except RateLimitError:
                retries += 1
                if retries <= self.MAX_RETRIES:
                    self.log(
                        f"Rate limit (429). Waiting {self.RATE_LIMIT_WAIT}s before retry {retries}/{self.MAX_RETRIES}..."
                    )
                    time.sleep(self.RATE_LIMIT_WAIT)
                    continue
                else:
                    self.log(f"Max retries ({self.MAX_RETRIES}) exceeded.")
                    return (None, token_usage)

            except Exception as e:
                self.log(f"Error calling Claude API: {e}")
                return (None, token_usage)

        return (None, token_usage)
