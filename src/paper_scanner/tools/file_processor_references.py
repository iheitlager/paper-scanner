#!/usr/bin/env -S python

"""
Reference Extractor

Takes JSONLines with pre-analyzed papers and extracts references from the raw_text field.
Outputs enriched JSONLines with references field added.
Uses cheaper Haiku model for cost-efficient reference extraction.
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

MAX_TOKENS = 10_000
WAIT_TIME = 61
DEFAULT_MODEL = "claude-3-5-haiku-20241022"


class ReferenceExtractor:
    def __init__(self, api_key: str, verbose: bool = False, model: str = DEFAULT_MODEL) -> None:
        """Initialize the reference extractor with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.verbose = verbose
        self.model = model
        self.reference_prompt = self._load_reference_prompt()

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, file=sys.stderr)

    def _load_reference_prompt(self) -> str:
        """Load the reference extraction prompt from file."""
        try:
            # Build path relative to this module
            module_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(module_dir))
            prompt_path = os.path.join(project_root, "prompts", "extract-references.md")

            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                self.log(f"Warning: Reference prompt not found at {prompt_path}")
                return ""
        except Exception as e:
            self.log(f"Error loading reference prompt: {e}")
            return ""

    def extract_references(self, paper_text: str, max_retries: int = 5) -> Optional[dict]:
        """Extract references from paper text using Claude with automatic retry on rate limits."""
        if not self.reference_prompt:
            self.log("Warning: Reference prompt not loaded, skipping reference extraction")
            return None

        retries = 0

        while retries <= max_retries:
            try:
                # Call Claude API with reference prompt
                response = self.client.messages.create(
                    model=self.model,
                    system=self.reference_prompt,
                    max_tokens=MAX_TOKENS,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Extract references from this academic paper:\n\n{paper_text}",
                        }
                    ],
                )

                response_text = response.content[0].text.strip()

                # Remove markdown code block wrapping if present
                if response_text.startswith("```"):
                    lines = response_text.split("\n", 1)
                    if len(lines) > 1:
                        response_text = lines[1]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3].rstrip()

                # Parse the JSON response
                try:
                    references = json.loads(response_text)
                    return references
                except json.JSONDecodeError as e:
                    self.log(f"Failed to parse references JSON response: {e}")
                    self.log(f"Response was: {response_text[:200]}...")
                    return None

            except Exception as e:
                # Check if it's a rate limit error (429)
                if hasattr(e, "status_code") and e.status_code == 429:
                    retries += 1
                    wait_time = WAIT_TIME

                    self.log(
                        f"Rate limit exceeded during reference extraction. Waiting for {wait_time} seconds before retry {retries}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                    continue

                # Log the other/unexpected error
                print(f"Error calling Claude API for reference extraction: {e}", file=sys.stderr)
                return None

        self.log(f"Maximum retries ({max_retries}) reached for reference extraction. Giving up.")
        return None

    def process_jsonlines(self, f_in, f_out):
        """Process JSONLines records and add references field.
        
        Args:
            f_in: Input file handle with JSONLines records (pre-analyzed)
            f_out: Output file handle for enriched JSONLines results
        """
        processed_count = 0
        error_count = 0

        for line in f_in:
            try:
                item = json.loads(line.strip())
                file_name = item.get("file_name", "unknown")

                # Extract references from raw_text if available
                if "raw_text" in item:
                    self.log(f"Extracting references from {file_name} ...")
                    references = self.extract_references(item["raw_text"])

                    if references:
                        item["references"] = references
                        self.log(f"Successfully extracted references for {file_name}")
                    else:
                        self.log(f"Warning: Failed to extract references for {file_name}, continuing without references")
                else:
                    self.log(f"Warning: No raw_text field found in record for {file_name}, skipping reference extraction")

                # Write enriched record to output with immediate flush
                f_out.write(json.dumps(item) + "\n")
                f_out.flush()
                processed_count += 1

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON line: {e}", file=sys.stderr)
                error_count += 1
                continue
            except Exception as e:
                print(f"Unexpected error processing record: {e}", file=sys.stderr)
                error_count += 1
                continue

        self.log(f"Reference extraction complete! {processed_count} records processed, {error_count} errors")
        return processed_count, error_count


def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract references from pre-analyzed papers in JSONLines format")
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with pre-analyzed papers (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file with references added (default: stdout)",
    )
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model to use (default: Haiku)")
    parser.add_argument(
        "-q",
        "--quiet",
        dest="verbose",
        default=True,
        action="store_false",
        help="Be quiet",
    )

    args = parser.parse_args()

    # if we are interactive, do error message
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 0

    # Get API key from args or environment
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("API key must be provided via --api_key or ANTHROPIC_API_KEY environment variable")

    # Initialize extractor and process JSONLines
    extractor = ReferenceExtractor(api_key, verbose=args.verbose, model=args.model)
    processed_count, error_count = extractor.process_jsonlines(args.input, args.output)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
