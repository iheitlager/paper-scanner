#!/usr/bin/env -S python

"""
PDF to Claude processor

Takes a JSONLines list with filenames
Each line is a PDF file and forwarded to Claude with the same system_prompt
Results are stored in JSONLines
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

MAX_TOKENS = 20_000
WAIT_TIME = 61
DEFAULT_MODEL = "claude-sonnet-4-20250514"


class PDFClaudeScanner:
    def __init__(self, api_key: str, verbose: bool = False, model: str = DEFAULT_MODEL) -> None:
        """Initialize the PDF scanner with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.verbose = verbose
        self.model = model

        self.system_prompt = """
        # Methodological Approach
        This study adopts a research synthesis approach grounded in critical realist principles to 
        investigate the strategic role of IT suppliers in incumbent firms' digital innovation processes 
        (Pawson & Tilley, 1997; Bygstad et al., 2016). We employ Romme's CAMO (Context-Agency-Mechanism-Outcome) 
        framework, which represents a systematic approach to design science research that extends traditional 
        realist evaluation methods for innovation and external resources contexts (Romme & Dimov, 2021; Dimov et al., 2023). 
        Unlike the traditional CMO framework that focuses primarily on interventions, the CAMO framework 
        incorporates "agency" to capture not only what actions are taken but also by whom, recognizing the 
        distributed and socially constructed nature of innovation processes (Denyer et al., 2008; Romme & Dimov, 2021). 
        The framework is grounded in design science methodology, which operates at the interface of creative 
        design and explanatory science to create and test innovative solutions through iterative cycles of 
        creating, evaluating, theorizing, and justifying (Dimov et al., 2023).

        In practice, the CAMO framework guides researchers through systematic development of design propositions 
        that can be formatted as: "In Context C, Agency A triggers Mechanism M to produce Outcome O" (Romme, 2023). 
        This structure enables researchers to develop highly contextualized mid-range theories that can subsequently 
        be decontextualized into more generalized causal relationships through iterative design science cycles 
        (Van Burg et al., 2008; Dimov et al., 2023). The framework is particularly valuable for innovation research 
        because it accommodates the uncertain, complex, and socioeconomic nature of innovation phenomena while 
        maintaining scientific rigor through evidence-based protocols (Romme & Reymen, 2018). Recent applications 
        have demonstrated its effectiveness in designing deep-tech venture builders, sustainable business model tools, 
        and innovation ecosystem interventions, where the CAMO structure helps bridge the gap between practical relevance 
        and theoretical contribution by enabling systematic evaluation of design choices and their boundary conditions 
        (Romme et al., 2023; Dimov et al., 2023).

        The empirical foundation for this research synthesis is established through a systematic literature review 
        following established guidelines for rigorous academic inquiry (Tranfield et al., 2003; Moher et al., 2009). 
        The review process employs structured keyword-based search strategies across relevant databases, with selection 
        criteria aligned with the research objectives of understanding IT supplier roles in incumbent digital 
        innovation (Webster & Watson, 2002). This systematic approach ensures comprehensive coverage of the literature 
        while maintaining methodological rigor in accordance with evidence-informed management research principles 
        (Denyer & Tranfield, 2009). Building on this foundation, the analysis follows a dual-level coding technique 
        adapted from grounded theory methodologies to systematically extract and synthesize CAMO configurations from 
        the selected literature (Strauss & Corbin, 1998; Wolfswinkel et al., 2013). At the first level, we employ 
        AI-assisted extraction techniques using Claude.ai to systematically identify and parse CAMO configurations from 
        literature on IT supplier-incumbent innovation relationships. This involves extracting mechanisms in the 
        standardized format "[CONTEXT], [AGENCY], [MECHANISM], [OUTCOME]" to enable automated processing and systematic 
        comparison across studies, thereby enhancing the rigor and scalability of design science research synthesis 
        in digital innovation contexts. The second level involves synthesizing these extracted elements into higher-order 
        theoretical configurations that reveal the paradoxical nature of IT supplier roles, providing the conceptual 
        foundation for subsequent design science research phases. This methodological approach enables the systematic 
        development of theoretical insights while maintaining transparency and reproducibility in the synthesis process.

        You are a research assistant analyzing academic papers, take the paper and summarize this:

        # Academic Paper Analysis
        1. PAPER_HEADER:
        1.1. TITLE: Extract the paper title
        1.2. AUTHORS: Extract the authors
        1.3. YEAR: Extract the publication year
        2. SUMMARY: Provide a two paragraph summary
        3. RESEARCH_QUESTION: Identify the main research question or hypothesis
        4. METHODOLOGY: Describe the research methodology
        4.1. EMPIRICAL_BASE: be clear if there is an empirical base
        4.2. METHODOLOGY_CLASS: is this qualitative or quantitative research
        5. RESULTS: from the paper
        5.1. CONCLUSION: provide a short conclusion
        5.2. LIMITATIONS: describe the limitation of this research
        6. VENDORS: Identify the various vendors and suppliers in the paper
        6.1. IT_SUPPLIER: List the individual IT suppliers and their role for innovation, these are not regular suppliers
        6.2. REGULAR_SUPPLIER: list the regular suppliers
        7. INNOVATION_MECHANISMS: Find all mechanisms, one per line, of innovation between client and suppliers. Use Format [CONTEXT], [AGENCY], [MECHANISM], [OUTCOME] - [Description]

        Structure your analysis for easy conversion to JSON format.
        """

    def log(self, message: str) -> None:
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

    def analyze_with_claude(self, pdf_text, custom_prompt=None, max_retries=5):
        """Send the PDF text to Claude for analysis with automatic retry on rate limits."""
        retries = 0

        while retries <= max_retries:
            try:
                # Use custom prompt if provided, otherwise use default system prompt
                system_message = custom_prompt if custom_prompt else self.system_prompt

                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    system=system_message,
                    max_tokens=MAX_TOKENS,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Here is the PDF content to analyze:\n\n{pdf_text}",
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
                    wait_time = WAIT_TIME  # X seconds sleep

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

    def process_pdfs(self, f_in, f_out, custom_prompt=None, include_metadata=True, verbose=False):
        """Process all PDFs in a directory and save results to a JSON file."""
        results = []

        for line in f_in:
            item = json.loads(line.strip())
            pdf_file = item["file_path"]
            processing_time = {"start_time": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            self.log(f"Processing {pdf_file} ...")
            pdf_text = self.extract_text_from_pdf(pdf_file)
            self.log(f"length {len(pdf_text.split())} ...")

            if pdf_text:
                analysis = self.analyze_with_claude(pdf_text, custom_prompt)
                if analysis:
                    processing_time["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    item["analysis"] = analysis
                    if include_metadata:
                        analysis["timing"] = processing_time

                    f_out.write(json.dumps(item) + "\n")
                    f_out.flush()
                    results += [item]

        self.log(f"Analysis complete! {len(results)} results returned")
        return results


def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Scan PDFs with Claude.ai and store results in JSON")
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with file pathnames (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file (default: stdout)",
    )
    parser.add_argument("--no-metadata", action="store_true", help="Don't include file metadata")
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model to use")
    parser.add_argument("--custom_prompt", help="Path to file containing custom system prompt")
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

    # Load custom prompt if provided
    custom_prompt = None
    if args.custom_prompt:
        with open(args.custom_prompt, "r", encoding="utf-8") as f:
            custom_prompt = f.read()

    # Initialize scanner and process PDFs
    scanner = PDFClaudeScanner(api_key, verbose=args.verbose, model=args.model)
    results = scanner.process_pdfs(args.input, args.output, custom_prompt, include_metadata=not args.no_metadata)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
