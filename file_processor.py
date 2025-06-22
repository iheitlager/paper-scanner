#!/usr/bin/env -S python

"""
PDF to Claude processor

Takes a JSONLines list with filenames
Each line is a PDF file and forwarded to Claude with the same system_prompt
Results are stored in JSONLines
"""

import os
import json
import sys
import argparse
import time
import datetime
from pypdf import PdfReader
from anthropic import Anthropic


MAX_TOKENS = 20_000
WAIT_TIME = 61
DEFAULT_MODEL = "claude-sonnet-4-20250514"

class PDFClaudeScanner:
    def __init__(self, api_key, verbose=False, model=DEFAULT_MODEL):
        """Initialize the PDF scanner with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.verbose = verbose
        self.model = model

        self.system_prompt = """
        # Methodological Approach
        This study adopts a research synthesis approach grounded in critical realist principles to 
        investigate the strategic role of IT suppliers in incumbent firms' digital innovation 
        processes (Pawson & Tilley, 1997; Bygstad et al., 2016). The research employs the 
        Context-Mechanisms-Outcome (CMO) framework as an analytical lens to unpack the generative 
        mechanisms through which IT suppliers contribute to digital transformation initiatives within 
        established organizations (Pawson, 2006). This configurational approach enables the 
        identification of paradoxical outcomes wherein IT suppliers simultaneously function as 
        knowledge providers, resource providers, and service providers, thereby revealing the complex, 
        multi-faceted nature of supplier-incumbent relationships in digital innovation 
        contexts (Hedström & Swedberg, 1998).

        # Literature Review and Selection Process
        The empirical foundation for this research synthesis is established through a systematic 
        literature review following established guidelines for rigorous academic 
        inquiry (Tranfield et al., 2003; Moher et al., 2009). The review process employs 
        structured keyword-based search strategies across relevant databases, with selection 
        criteria aligned with the research objectives of understanding IT supplier roles in 
        incumbent digital innovation (Webster & Watson, 2002). The systematic approach ensures 
        comprehensive coverage of the literature while maintaining methodological rigor in accordance 
        with evidence-informed management research principles (Denyer & Tranfield, 2009).

        # Dual-Level Coding and Synthesis
        The analysis follows a dual-level coding technique adapted from grounded theory 
        methodologies to systematically extract and synthesize CMO configurations from the 
        selected literature (Strauss & Corbin, 1998; Wolfswinkel et al., 2013). In the first 
        level, contexts, mechanisms, and outcomes are extracted from individual studies using large 
        language model assistance to ensure consistent identification of relevant theoretical 
        constructs. The second level involves synthesizing these extracted elements into 
        igher-order theoretical configurations that reveal the paradoxical nature of IT supplier roles, 
        providing the conceptual foundation for subsequent design science research phases. This 
        methodological approach enables the systematic development of theoretical insights while 
        maintaining transparency and reproducibility in the synthesis process.

        # Mechanism Template Selection
        To ensure systematic and consistent extraction of generative mechanisms across the 
        literature, several template formats were evaluated for their analytical utility and 
        alignment with the research objectives. After comparing process-oriented, capability-resource, 
        relational-configuration, action-impact, and value-based approaches across criteria of 
        understandability, self-explanation, and generalization potential, the value-based format 
        was selected as most appropriate for this study. The chosen template structure—
        "[Value Proposition] through [Method]: [How it addresses specific business challenge]"—provides 
        optimal support for the dual-level coding approach by explicitly connecting IT supplier 
        contributions to business value creation while maintaining clear linkages between implementation 
        methods and organizational challenges. This format facilitates both reliable mechanism 
        extraction in the first coding level and meaningful clustering in the subsequent synthesis 
        phase, as value propositions naturally align with the theoretical framework's knowledge provider, 
        resource provider, and service provider roles. Furthermore, the business-oriented framing 
        enhances the practical applicability of findings for the intended design science research phase, 
        ensuring that extracted mechanisms remain grounded in managerial relevance while supporting 
        theoretical development.

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
        7. INNOVATION_MECHANISMS: Find all mechanisms of innovation between client and suppliers
        7.1. CONTEXTS: in which incumbents and client attract suppliers to support them
        7.2. MECHANISMS: of innovation following the pattern [Value Proposition] through [Method]: [How it addresses specific business challenge].
        7.3. OUTCOMES: describing benefits for clients per benefit
        Structure your analysis for easy conversion to JSON format.
        """

    def log(self, message):
        if self.verbose:
            print(message, file=sys.stderr)
           
    def extract_text_from_pdf(self, pdf_path):
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
                        {"role": "user", "content": f"Here is the PDF content to analyze:\n\n{pdf_text}"}
                    ]
                )
                return response.content[0].text
                
            except Exception as e:
                # Check if it's a rate limit error (429)
                if hasattr(e, 'status_code') and e.status_code == 429:
                    retries += 1
                    wait_time = WAIT_TIME  # X seconds sleep
                    
                    self.log(f"Rate limit exceeded. Waiting for {wait_time} seconds before retry {retries}/{max_retries}...")
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
            pdf_file = item['file_path']
            processing_time = {
                'start_time': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            self.log(f"Processing {pdf_file} ...")
            pdf_text = self.extract_text_from_pdf(pdf_file)
            self.log(f"length {len(pdf_text.split())} ...")
            
            if pdf_text:
                analysis = self.analyze_with_claude(pdf_text, custom_prompt)
                if analysis:
                    processing_time['end_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    item["analysis"] = analysis
                    if include_metadata:
                        item['timing'] = processing_time

                    f_out.write(json.dumps(item) + '\n')
                    f_out.flush()
                    results += [item]
           
    
        self.log(f"Analysis complete! {len(results)} results returned")
        return results


def main():
    parser = argparse.ArgumentParser(description="Scan PDFs with Claude.ai and store results in JSON")
    parser.add_argument("-i", "--input", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="Input JSONLines file with file pathnames (default: stdin)")
    parser.add_argument("-o", "--output", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="Output JSONLines file (default: stdout)")
    parser.add_argument("--no-metadata", action="store_true", help="Don't include file metadata")
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model to use")
    parser.add_argument("--custom_prompt", help="Path to file containing custom system prompt")
    parser.add_argument("-q", "--quiet", dest='verbose', default=True, action="store_false", help="Be quiet")

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
        with open(args.custom_prompt, 'r', encoding='utf-8') as f:
            custom_prompt = f.read()

    # Initialize scanner and process PDFs
    scanner = PDFClaudeScanner(api_key, verbose=args.verbose, model=args.model)
    results = scanner.process_pdfs(
        args.input, 
        args.output,
        custom_prompt,
        include_metadata=not args.no_metadata
    )

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

if __name__ == "__main__":
    sys.exit(main())