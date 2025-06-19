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

class PDFClaudeScanner:
    def __init__(self, api_key, model="claude-3-7-sonnet-20250219"):
        """Initialize the PDF scanner with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.model = model


        self.system_prompt = """
        The methodological framework adopted in this study employs a context-mechanism-outcome (CMO) 
        configuration, as initially developed by Pawson and Tilley (1997) in their realist evaluation 
        approach. This framework enables an in-depth analysis of how IT suppliers contribute to digital 
        innovation processes within incumbent organizations, yielding a nuanced understanding of the 
        causal pathways between contextual factors, activation mechanisms, and paradoxical outcomes—wherein 
        suppliers may simultaneously function as knowledge providers, resource providers, and service providers 
        (Nambisan et al., 2019). The CMO configuration is particularly suited for this investigation as it 
        accommodates the complex, non-linear nature of digital innovation processes and the multi-faceted 
        roles assumed by external IT partners (Lycett, 2013). For data collection and analysis, we conducted 
        a research synthesis based on a structured literature review, following the methodological guidelines 
        established by Tranfield et al. (2003) and refined by Denyer and Tranfield (2009). The systematic 
        review process encompassed: (1) formulation of research questions; (2) location of studies through 
        database searches in Scopus, Web of Science, and AIS electronic library, using predetermined keywords 
        related to IT suppliers, digital innovation, and incumbent transformation; (3) study selection and 
        evaluation based on explicit inclusion/exclusion criteria; (4) analysis, by using LLMs to extract, and 
        synthesis, by using LLMs to combine, of findings; and (5) reporting and dissemination. This approach 
        enabled us to extract and synthesize relevant mechanisms from a diverse body of empirical studies spanning 
        information systems, innovation management, and organizational studies (Webster and Watson, 2002). The 
        analytical procedure involved iterative coding of the identified literature to extract contextual 
        conditions, mechanisms, and outcomes related to IT supplier contributions to digital innovation. Following 
        Saldaña's (2021) approach to qualitative coding, we first employed descriptive coding to identify key 
        concepts, followed by pattern coding to establish relationships between these concepts. The synthesis 
        phase utilized the CMO framework to organize the findings into coherent, more general, configurations 
        that explicate how specific contextual factors trigger mechanisms leading to the paradoxical outcomes 
        where IT suppliers simultaneously function in knowledge provision, resource allocation, and service 
        delivery capacities (Berente and Yoo, 2012). This analytical approach aligns with recent methodological 
        developments in information systems research that emphasize the importance of contextual sensitivity and 
        mechanism-based explanations (Avgerou, 2019). 

        ## Academic Paper Analysis
        You are a research assistant analyzing academic papers, take the paper and summarize this:  
        1. TITLE_AUTHORS: Extract the paper title , authors and publication year
        2. SUMMARY: Provide a two paragraph summary  
        3. IT_SUPPLIER: Identify the various IT suppliers in the paper, if any. Be sure to be clear on regular suppliers 
        4. SUPPLIER_ROLE: Summarize the roles these IT suppliers play, if any 
        5. METHODOLOGY: Research Methodology, be clear if there is an empirical base and if this is qualitative or quantitative research  
        6. Find all mechanisms of innovation between client and suppliers  
        6.1. CONTEXTS: in which incumbents and client attract suppliers to support them  
        6.2. MECHANISMS: of innovation following the pattern [Action Verb]-Driven [Outcome]: [Brief definition highlighting key practice and value].  
        6.3. OUTCOMES: describing benefits for clients per benefit

        Structure your analysis for easy conversion to JSON format.
        """

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
                    
                    print(f"Rate limit exceeded. Waiting for {wait_time} seconds before retry {retries}/{max_retries}...", 
                        file=sys.stderr)
                    time.sleep(wait_time)
                    continue
                
                # Log the other/unexpected error
                print(f"Error calling Claude API: {e}", file=sys.stderr)
                return None

        print(f"Maximum retries ({max_retries}) reached. Giving up.", file=sys.stderr)
        return None

    def process_pdfs(self, f_in, f_out, custom_prompt=None, include_metadata=True):
        """Process all PDFs in a directory and save results to a JSON file."""
        results = []
        
        for line in f_in:
            pdf_file = json.loads(line.strip())['file_path']
            processing_time = {
                'start_time': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            print(f"Processing {pdf_file} ...", file=sys.stderr)
            pdf_text = self.extract_text_from_pdf(pdf_file)
            print(f"length {len(pdf_text.split())} ...", file=sys.stderr)
            
            if pdf_text:
                analysis = self.analyze_with_claude(pdf_text, custom_prompt)
                if analysis:
                    processing_time['end_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    item = {
                        "file_path": str(pdf_file),
                        "analysis": analysis
                    }
                    if include_metadata:
                        item['timing'] = processing_time

                    f_out.write(json.dumps(item) + '\n')
                    f_out.flush()
                    results += [item]
           
        return results


def main():
    parser = argparse.ArgumentParser(description="Scan PDFs with Claude.ai and store results in JSON")
    parser.add_argument("-i", "--input", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="Input JSONLines file with file pathnames (default: stdin)")
    parser.add_argument("-o", "--output", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="Output JSONLines file (default: stdout)")
    parser.add_argument("--no-metadata", action="store_true", help="Don't include file metadata")
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
    parser.add_argument("--custom_prompt", help="Path to file containing custom system prompt")
    parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Be verbose")

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
    scanner = PDFClaudeScanner(api_key, model=args.model)
    results = scanner.process_pdfs(
        args.input, 
        args.output,
        custom_prompt,
        include_metadata=not args.no_metadata)
    
    if args.verbose:
        print(f"Analysis complete! {len(results)} results returned", file=sys.stderr)


    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

if __name__ == "__main__":
    sys.exit(main())