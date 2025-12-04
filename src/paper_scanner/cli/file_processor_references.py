#!/usr/bin/env -S python

"""
Reference Extractor

Takes JSONLines with pre-analyzed papers and extracts references from the PDF files.
Outputs enriched JSONLines with references field added.
Uses cheaper Haiku model for cost-efficient reference extraction.
"""


##################
# Some queries:
# grouped by file with totals
# $ jq '.file_name as $file | (.references.references | length) as $count | "\($file): \($count) references"' full.jsonl

import argparse
import json
import os
import sys
import time
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pypdf import PdfReader

MAX_TOKENS = 8_192  # Haiku max output tokens
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

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extract text content from a PDF file starting from the references section.

        Looks for common reference section markers and extracts only from that point forward
        to avoid exceeding Haiku's 8192 token limit while capturing the references.
        """
        try:
            reader = PdfReader(pdf_path)
            text = ""
            found_references = False

            # Common reference section markers (case-insensitive)
            reference_markers = [
                "references",
                "bibliography",
                "works cited",
                "citations",
                "cited works",
            ]

            for page in reader.pages:
                page_text = page.extract_text()

                # If we haven't found references yet, check this page
                if not found_references:
                    page_lower = page_text.lower()
                    for marker in reference_markers:
                        if marker in page_lower:
                            # Find the position and extract from the marker onwards
                            marker_pos = page_lower.find(marker)
                            text += page_text[marker_pos:]
                            self.log(f"Found '{marker}' section, extracting references from here")
                            found_references = True
                            break
                else:
                    # After finding references, include all subsequent pages
                    text += page_text + "\n"

            # If no reference section found, return empty (better than sending whole PDF)
            if not found_references:
                self.log("No reference section found in PDF")
                return ""

            return text
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}", file=sys.stderr)
            return None

    def extract_references(self, pdf_text: str, max_retries: int = 5) -> Optional[dict]:
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
                            "content": f"Extract references from this academic paper:\n\n{pdf_text}",
                        }
                    ],
                )

                response_text = response.content[0].text.strip()

                # Remove any preamble text before the JSON object
                # Look for the first '{' which starts the JSON
                json_start = response_text.find("{")
                if json_start != -1:
                    response_text = response_text[json_start:]

                # Remove markdown code block wrapping if present
                if response_text.startswith("```"):
                    # Remove opening ```json or ``` and everything before first newline
                    response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]

                if response_text.endswith("```"):
                    # Remove closing ```
                    response_text = response_text[:-3].rstrip()

                # Find the last '}' which ends the JSON object and remove anything after it
                json_end = response_text.rfind("}")
                if json_end != -1:
                    response_text = response_text[: json_end + 1]

                self.log(f"Attempting to parse JSON response (length: {len(response_text)} chars)")

                # Parse the JSON response
                try:
                    references = json.loads(response_text)
                    self.log("Successfully parsed references JSON")
                    return references
                except json.JSONDecodeError as e:
                    self.log(f"Failed to parse references JSON response: {e}")
                    self.log(f"Response text (first 500 chars): {response_text[:500]}")
                    self.log(f"Response text (last 200 chars): {response_text[-200:]}")
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
        success_count = 0

        for line in f_in:
            try:
                item = json.loads(line.strip())
                file_path = item.get("file_path")
                file_name = item.get("file_name", "unknown")

                if not file_path:
                    self.log(f"Warning: No file_path in record for {file_name}, skipping reference extraction")
                    # Write record unchanged
                    f_out.write(json.dumps(item) + "\n")
                    f_out.flush()
                    processed_count += 1
                    continue

                # Extract text from PDF
                self.log(f"Extracting references from {file_name} ...")
                pdf_text = self.extract_text_from_pdf(file_path)

                if pdf_text:
                    references = self.extract_references(pdf_text)

                    if references:
                        item["references"] = references
                        self.log(f"Successfully extracted references for {file_name}")
                        success_count += 1
                    else:
                        self.log(
                            f"Warning: Failed to extract references for {file_name}, continuing without references"
                        )
                else:
                    self.log(f"Warning: Could not extract text from {file_path}")

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

        self.log(
            f"Reference extraction complete! {processed_count} records processed, {success_count} successful, {error_count} errors"
        )
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
