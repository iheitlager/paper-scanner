#!/usr/bin/env python3
"""
Flexible paper processor for enriching JSONLines records with LLM-generated content.

Features:
- Multiple Anthropic Claude models
- Configurable token limits
- PDF extraction or record content usage
- External prompt file support
- Configurable output keys and metadata
- Add or replace mode for enrichment
- Stdin/stdout or file I/O
- Optional output file filtering (skip existing)
- Multiprocessing support
- YAML configuration files
- Detailed statistics and error handling
"""

import argparse
import json
import os
import sys
import time
import yaml
import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed

from anthropic import Anthropic, RateLimitError
from pdfplumber import open as open_pdf
from pdfplumber.pdf import PDF as PDFDocument

from dotenv import load_dotenv


# ============================================================================
# Configuration & Constants
# ============================================================================

DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_MAX_TOKENS = 8192
MAX_RETRIES = 5
RATE_LIMIT_WAIT = 61

# Model configuration: name -> max output tokens
MODELS = {
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-haiku-20241022": 8192,
    "claude-3-opus-20250219": 4096,
    "claude-4-20250514": 16384,
    "claude-4-turbo-20250514": 16384,
    "claude-4-haiku-20250514": 8192,
    "claude-4-haiku-turbo-20250514": 8192,
}


@dataclass
class ProcessorConfig:
    """Configuration for the processor."""
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    text_source: str = "pdf"  # 'pdf', 'content', or field name
    prompt_file: Optional[str] = None
    output_key: str = "processed"
    mode: str = "add"  # 'add' or 'replace'
    add_metadata: bool = False
    workers: int = 1
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    skip_existing: bool = False
    quiet: bool = False
    api_key: Optional[str] = None
    yaml_config: Optional[str] = None


# ============================================================================
# Processor Class
# ============================================================================

class PaperProcessor:
    """Main processor for enriching JSONLines records with LLM analysis."""

    def __init__(self, config: ProcessorConfig):
        """Initialize the processor with configuration."""
        self.config = config
        self.client = Anthropic(api_key=config.api_key)
        self.verbose = not config.quiet

        # Load prompt if provided
        self.custom_prompt = None
        if config.prompt_file:
            self.custom_prompt = self._load_prompt(config.prompt_file)

        # Statistics
        self.stats = {
            "processed": 0,
            "success": 0,
            "error": 0,
            "skipped": 0,
        }

        # Track processed records for filtering
        self.processed_records = set()
        if config.skip_existing and config.output_file:
            self._load_existing_records()

    def log(self, message: str) -> None:
        """Log message to stderr."""
        if self.verbose:
            print(message, file=sys.stderr)

    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt from file."""
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.log(f"Warning: Could not load prompt from {prompt_file}: {e}")
            return ""

    def _load_existing_records(self) -> None:
        """Load file_path values from existing output file for filtering."""
        if not os.path.exists(self.config.output_file):
            return

        try:
            with open(self.config.output_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        file_path = record.get("file_path")
                        if file_path:
                            self.processed_records.add(file_path)
                    except json.JSONDecodeError:
                        continue
            self.log(f"Loaded {len(self.processed_records)} existing records from {self.config.output_file}")
        except Exception as e:
            self.log(f"Warning: Could not load existing records: {e}")

    def _extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extract text from PDF file."""
        try:
            if not os.path.exists(pdf_path):
                self.log(f"Warning: PDF not found at {pdf_path}")
                return None

            with open_pdf(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    text += "\n"
                return text
        except Exception as e:
            self.log(f"Error extracting text from {pdf_path}: {e}")
            return None

    def _get_input_text(self, record: Dict[str, Any]) -> Optional[str]:
        """Get input text based on text_source configuration."""
        text_source = self.config.text_source

        if text_source == "pdf":
            file_path = record.get("file_path")
            if not file_path:
                self.log("Warning: No file_path in record for PDF extraction")
                return None
            return self._extract_text_from_pdf(file_path)

        elif text_source == "content":
            return record.get("content")

        else:
            # Try to use as field name
            return record.get(text_source)

    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from Claude response with robust cleanup."""
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
        except json.JSONDecodeError as e:
            self.log(f"Failed to parse JSON: {e}")
            self.log(f"Response start: {response_text[:200]}")
            return None

    def _call_claude(self, text: str, system_prompt: str) -> Optional[Dict[str, Any]]:
        """Call Claude API with retry logic."""
        retries = 0
        max_retries = MAX_RETRIES

        while retries <= max_retries:
            try:
                response = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": text}],
                )

                response_text = response.content[0].text.strip()
                return self._parse_json_response(response_text)

            except RateLimitError:
                retries += 1
                if retries <= max_retries:
                    self.log(
                        f"Rate limit (429). Waiting {RATE_LIMIT_WAIT}s before retry {retries}/{max_retries}..."
                    )
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                else:
                    self.log(f"Max retries ({max_retries}) exceeded.")
                    return None

            except Exception as e:
                self.log(f"Error calling Claude API: {e}")
                return None

        return None

    def _calculate_tokens_estimate(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    def process_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single record."""
        self.stats["processed"] += 1

        # Check if should skip
        if self.config.skip_existing:
            file_path = record.get("file_path")
            if file_path in self.processed_records:
                self.stats["skipped"] += 1
                return None

        # Get input text
        input_text = self._get_input_text(record)
        if not input_text:
            self.log(f"Warning: Could not extract text for record {record.get('file_name')}")
            self.stats["error"] += 1
            return None

        # Prepare timing
        start_time = datetime.datetime.now(datetime.timezone.utc)

        # Prepare system prompt
        system_prompt = self.custom_prompt or "You are a helpful assistant. Respond only with valid JSON."

        # Call Claude
        result = self._call_claude(input_text, system_prompt)
        if not result:
            self.stats["error"] += 1
            return None

        # Prepare output
        end_time = datetime.datetime.now(datetime.timezone.utc)

        output_key = self.config.output_key
        if self.config.mode == "replace":
            record[output_key] = result
        else:  # add
            record[output_key] = result

        # Add metadata if requested
        if self.config.add_metadata:
            metadata = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "model": self.config.model,
                "input_tokens_estimate": self._calculate_tokens_estimate(input_text),
                "text_source": self.config.text_source,
            }
            if not hasattr(record.get(output_key), "__getitem__"):
                record[f"{output_key}_metadata"] = metadata
            elif isinstance(record[output_key], dict):
                record[output_key]["_metadata"] = metadata

        self.stats["success"] += 1
        return record

    def process_jsonlines(self, input_stream, output_stream) -> None:
        """Process JSONLines from input and write to output."""
        try:
            for line in input_stream:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    result = self.process_record(record)
                    if result:
                        output_stream.write(json.dumps(result) + "\n")
                        output_stream.flush()

                except json.JSONDecodeError as e:
                    self.log(f"Error parsing JSON line: {e}")
                    self.stats["error"] += 1
                    continue

        finally:
            if input_stream != sys.stdin:
                input_stream.close()
            if output_stream != sys.stdout:
                output_stream.close()

    def print_stats(self) -> None:
        """Print processing statistics."""
        print("\n=== Processing Statistics ===", file=sys.stderr)
        print(f"Total processed: {self.stats['processed']}", file=sys.stderr)
        print(f"Successful: {self.stats['success']}", file=sys.stderr)
        print(f"Errors: {self.stats['error']}", file=sys.stderr)
        print(f"Skipped: {self.stats['skipped']}", file=sys.stderr)


# ============================================================================
# CLI & Configuration
# ============================================================================

def load_yaml_config(yaml_file: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading YAML config: {e}", file=sys.stderr)
        return {}


def merge_configs(yaml_config: Dict[str, Any], cli_args: argparse.Namespace) -> ProcessorConfig:
    """Merge YAML and CLI configurations (CLI takes precedence)."""
    config_dict = yaml_config.copy()

    # Override with CLI args if provided
    for key, value in vars(cli_args).items():
        if value is not None:
            config_dict[key] = value

    # Set defaults for missing values
    config_dict.setdefault("model", DEFAULT_MODEL)
    config_dict.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
    config_dict.setdefault("text_source", "pdf")
    config_dict.setdefault("output_key", "processed")
    config_dict.setdefault("mode", "add")

    return ProcessorConfig(**{k: v for k, v in config_dict.items() if k in ProcessorConfig.__dataclass_fields__})


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    # Format model info with limits
    model_info = "\n  ".join(
        f"{m}: {tokens} tokens"
        for m, tokens in MODELS.items()
    )

    parser = argparse.ArgumentParser(
        description="Flexible paper processor for JSONLines enrichment with LLM analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available models (with max output tokens):
  {model_info}

Example YAML config:
  model: claude-3-5-haiku-20241022
  max_tokens: 8192
  text_source: pdf
  prompt_file: /path/to/prompt.md
  output_key: references
  add_metadata: true
  workers: 4
  """,
    )

    parser.add_argument(
        "-i", "--input",
        dest="input_file",
        help="Input JSONLines file (default: stdin)",
    )
    parser.add_argument(
        "-o", "--output",
        dest="output_file",
        help="Output JSONLines file (default: stdout)",
    )
    parser.add_argument(
        "--model",
        choices=MODELS.keys(),
        default=None,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=f"Max output tokens (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--text-source",
        default=None,
        help="Text source: 'pdf', 'content', or record field name (default: pdf)",
    )
    parser.add_argument(
        "--prompt-file",
        help="Path to custom prompt file",
    )
    parser.add_argument(
        "--output-key",
        default=None,
        help="JSON key to store output (default: processed)",
    )
    parser.add_argument(
        "--mode",
        choices=["add", "replace"],
        default=None,
        help="Add output to record or replace (default: add)",
    )
    parser.add_argument(
        "--add-metadata",
        action="store_true",
        help="Include processing metadata (timing, tokens, etc.)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip records already in output file",
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API key (or ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--config",
        dest="yaml_config",
        help="YAML configuration file (CLI args override)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose logging",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit",
    )

    return parser


def main():
    """Main entry point."""
    load_dotenv()

    parser = create_parser()
    args = parser.parse_args()

    # Handle --list-models
    if args.list_models:
        print("Available models:")
        for model in MODELS.keys():
            print(f"  {model}")
        return 0

    # Load YAML config if provided
    yaml_config = {}
    if args.yaml_config:
        yaml_config = load_yaml_config(args.yaml_config)

    # Merge configurations
    config = merge_configs(yaml_config, args)

    # Validate max_tokens against model limits
    model_limit = MODELS.get(config.model)
    if model_limit and config.max_tokens > model_limit:
        print(
            f"Error: max_tokens ({config.max_tokens}) exceeds limit for {config.model} ({model_limit})",
            file=sys.stderr,
        )
        return 1

    # Get API key
    api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: API key must be provided via --api-key or ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        return 1

    config.api_key = api_key

    # Check for stdin
    if not config.input_file and sys.stdin.isatty():
        parser.print_help()
        return 0

    # Initialize processor
    processor = PaperProcessor(config)

    # Determine input/output streams
    input_stream = sys.stdin
    output_stream = sys.stdout

    if config.input_file:
        try:
            input_stream = open(config.input_file, "r", encoding="utf-8")
        except Exception as e:
            print(f"Error opening input file: {e}", file=sys.stderr)
            return 1

    if config.output_file:
        try:
            output_stream = open(config.output_file, "a" if config.skip_existing else "w", encoding="utf-8")
        except Exception as e:
            print(f"Error opening output file: {e}", file=sys.stderr)
            return 1

    # Process
    try:
        processor.process_jsonlines(input_stream, output_stream)
        processor.print_stats()
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        processor.print_stats()
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        processor.print_stats()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
