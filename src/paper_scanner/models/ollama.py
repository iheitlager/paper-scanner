"""Ollama handler for local Small Language Models (SLM)."""

import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

from .base import LLMHandler, parse_json_response


class OllamaHandler(LLMHandler):
    """Handler for local SLM models via Ollama."""

    # Group identifier for Ollama models
    GROUP = "Ollama"

    # Supported Ollama/SLM models with max output tokens (estimates)
    MODELS = {
        "phi": 2048,  # Phi model
        "phi3:mini": 2048,  # Phi3 mini model
        "phi3.5": 2048,  # Phi3.5 model
        "tinyllama": 2048,  # TinyLlama model
        "llama3.2:1b": 4096,  # Llama3.2:1b model
        "llama3.2:3b": 4096,  # Llama3.2:3b model
        "mistral:7b": 8192,  # Mistral 7B model
        "qwen2.5:3b": 4096,  # Qwen 2.5 3B model
    }

    TIMEOUT = 300  # 5 minute timeout for local processing

    def __init__(self, model: str = "phi", logger: Optional[Callable] = None):
        """
        Initialize Ollama handler.

        Args:
            model: Model name to use (default: phi)
            logger: Optional logging function
        """
        super().__init__(logger=logger)
        self.model = model

    def call(
        self,
        text: str,
        system_prompt: str,
        max_tokens: int,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, int]]:
        """
        Call local SLM via Ollama subprocess.

        Args:
            text: Input text to process
            system_prompt: System prompt to guide the model
            max_tokens: Maximum output tokens (informational, not enforced by local model)

        Returns:
            Tuple of (parsed_json_response, token_usage)
        """
        token_usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            # Combine system prompt and text for the model
            full_prompt = f"{system_prompt}\n\n{text}"

            # Call Ollama via subprocess
            result = subprocess.run(
                ["ollama", "run", self.model, full_prompt],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            if result.returncode != 0:
                self.log(f"Ollama error: {result.stderr}")
                return (None, token_usage)

            response_text = result.stdout.strip()
            parsed_response = parse_json_response(response_text)

            # If JSON parsing failed, log the raw response for debugging
            if parsed_response is None:
                self.log(f"Warning: Failed to parse JSON response from Ollama.\nMessage: {response_text[:500]}")
                return (None, token_usage)

            # Estimate tokens (rough approximation: 4 chars ≈ 1 token)
            token_usage["input_tokens"] = self._estimate_tokens(full_prompt)
            token_usage["output_tokens"] = self._estimate_tokens(response_text)

            return (parsed_response, token_usage)

        except FileNotFoundError:
            self.log("Error: Ollama command not found. Install Ollama to use SLM models")
            return (None, token_usage)
        except subprocess.TimeoutExpired:
            self.log(f"Error: Ollama request timed out after {self.TIMEOUT}s")
            return (None, token_usage)
        except Exception as e:
            self.log(f"Error calling Ollama: {e}")
            return (None, token_usage)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4
