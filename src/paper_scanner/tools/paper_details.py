#!/usr/bin/env -S python

"""
Paper Details Extractor

Extracts bibliographic details from academic papers by processing JSONLines records.
Sends each record to Claude API to extract title, authors, publication details, etc.
Adds a "title-details" field with extracted information as JSON.
"""

import argparse
import datetime
import json
import os
import sys
import time
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pypdf import PdfReader

MAX_TOKENS = 2_000
WAIT_TIME = 61
DEFAULT_MODEL = "claude-sonnet-4-20250514"


class PaperDetailsExtractor:
    """Extract bibliographic details from academic paper analysis."""

    def __init__(self, api_key: str, verbose: bool = False, model: str = DEFAULT_MODEL) -> None:
        """Initialize the details extractor with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.verbose = verbose
        self.model = model

        self.system_prompt = """
        You are a research librarian expert at extracting and formatting bibliographic metadata from academic papers.

        Extract the following bibliographic information from the provided academic paper analysis and format it as JSON:

        1. Full citation in APA style (7th edition)
        2. Cite key in the format: FirstAuthorLastNameYear (e.g., SmithJones2023)
        3. DOI (if available)
        4. Individual components:
           - Authors (as array)
           - Publication year
           - Article title
           - Journal name
           - Volume number
           - Issue number (if available)
           - Page range
           - Publisher (if applicable)

        Format the output EXACTLY as valid JSON with this structure:

        {
          "citekey": "string",
          "doi": "string",
          "citation_apa": "string",
          "authors": ["string"],
          "year": "string",
          "title": "string",
          "journal": "string",
          "volume": "string",
          "issue": "string",
          "pages": "string",
          "publisher": "string"
        }

        Ensure all fields are properly escaped for JSON format. If any information is not available, use null for that field.
        Return ONLY the JSON object, no additional text.
        """

    def log(self, message: str) -> None:
        """Log a message to stderr if verbose mode is enabled."""
        if self.verbose:
            print(message, file=sys.stderr)

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extract text content from a PDF file."""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}", file=sys.stderr)
            return None

    def extract_details_with_claude(self, pdf_text: str, max_retries: int = 5) -> Optional[dict]:
        """Send PDF text to Claude for bibliographic detail extraction."""
        retries = 0

        while retries <= max_retries:
            try:
                # Call Claude API with the PDF text
                response = self.client.messages.create(
                    model=self.model,
                    system=self.system_prompt,
                    max_tokens=MAX_TOKENS,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Extract bibliographic details from this academic paper:\n\n{pdf_text}",
                        }
                    ],
                )

                response_text = response.content[0].text.strip()

                # Remove markdown code block wrapping if present
                if response_text.startswith("```"):
                    # Remove opening code fence (e.g., ```json)
                    lines = response_text.split("\n", 1)
                    if len(lines) > 1:
                        response_text = lines[1]
                    # Remove closing code fence
                    if response_text.endswith("```"):
                        response_text = response_text[:-3].rstrip()

                # Parse the JSON response
                try:
                    details = json.loads(response_text)
                    return details
                except json.JSONDecodeError as e:
                    self.log(f"Failed to parse JSON response: {e}")
                    self.log(f"Response was: {response_text[:200]}...")
                    return None

            except Exception as e:
                # Check if it's a rate limit error (429)
                if hasattr(e, "status_code") and e.status_code == 429:
                    retries += 1
                    wait_time = WAIT_TIME

                    self.log(
                        f"Rate limit exceeded. Waiting for {wait_time} seconds before retry {retries}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                    continue

                # Log the other/unexpected error
                print(f"Error calling Claude API: {e}", file=sys.stderr)
                return None

        self.log(f"Maximum retries ({max_retries}) reached. Giving up.")
        return None

    def process_records(self, f_in, f_out, include_metadata: bool = True) -> list:
        """Process all records from input, extract PDF text, and add paper details to each."""
        results = []
        record_count = 0

        for line in f_in:
            try:
                record = json.loads(line.strip())
                record_count += 1
                processing_time = {"start_time": datetime.datetime.now(datetime.timezone.utc).isoformat()}

                pdf_file = record.get("file_path")
                if not pdf_file:
                    self.log(f"Record {record_count} missing 'file_path' field, skipping")
                    continue

                self.log(f"Processing record {record_count} ({pdf_file})...")

                # Extract PDF text
                pdf_text = self.extract_text_from_pdf(pdf_file)
                if not pdf_text:
                    self.log(f"Failed to extract text from {pdf_file}")
                    continue

                self.log(f"PDF extracted, length: {len(pdf_text.split())} words")

                # Extract details
                details = self.extract_details_with_claude(pdf_text)

                if details:
                    processing_time["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    # Add details to record
                    record["title-details"] = details
                    if include_metadata:
                        record["details-timing"] = processing_time

                    # Write output
                    f_out.write(json.dumps(record) + "\n")
                    f_out.flush()
                    results.append(record)
                else:
                    self.log(f"Failed to extract details for record {record_count}")

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON on line {record_count}: {e}", file=sys.stderr)
                continue

        self.log(f"Processing complete! {len(results)} records with details returned")
        return results


def main() -> int:
    """Main entry point for the paper details extractor."""
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Extract bibliographic details from paper analysis JSONLines records"
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with paper analysis records (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file with added title-details (default: stdout)",
    )
    parser.add_argument("--no-metadata", action="store_true", help="Don't include extraction timing metadata")
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model to use")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
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

    # Initialize extractor and process records
    extractor = PaperDetailsExtractor(api_key, verbose=args.verbose, model=args.model)
    results = extractor.process_records(args.input, args.output, include_metadata=not args.no_metadata)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
