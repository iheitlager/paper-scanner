import os
import json
import base64
import argparse
import requests
from pathlib import Path
from pypdf import PdfReader
from anthropic import Anthropic

class PDFClaudeScanner:
    def __init__(self, api_key, model="claude-3-7-sonnet-20250219"):
        """Initialize the PDF scanner with Claude API credentials."""
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = """
        You are an expert PDF analyzer. Extract and summarize the key information from the PDF content provided.
        Organize your response in these sections:
        1. DOCUMENT_SUMMARY: A concise summary of what this document is about (2-3 sentences)
        2. KEY_POINTS: The 3-5 most important points or findings in the document
        3. ENTITIES: Important people, organizations, or products mentioned
        4. DATA_ELEMENTS: Key statistics, figures, or data points
        5. CONCLUSIONS: Main conclusions or recommendations if any
        
        Format your response in a way that could be easily parsed into a structured format.
        """
        self.system_prompt = """
        ## Academic Paper Analysis
        You are a research assistant analyzing academic papers. For the provided PDF content:

        1. TITLE_AUTHORS: Extract the paper title and authors
        2. ABSTRACT_SUMMARY: Summarize the abstract in 2-3 sentences
        3. RESEARCH_QUESTION: Identify the main research question or hypothesis
        4. METHODOLOGY: Describe the research methodology used
        5. KEY_FINDINGS: List the 3-5 most significant findings or results
        6. LIMITATIONS: Note any limitations or constraints mentioned
        7. FUTURE_WORK: Highlight suggestions for future research
        8. CITATIONS: Extract key papers cited that appear important to the research

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
            print(f"Error extracting text from {pdf_path}: {e}")
            return None

    def analyze_with_claude(self, pdf_text, custom_prompt=None):
        """Send the PDF text to Claude for analysis."""
        try:
            # Use custom prompt if provided, otherwise use default system prompt
            system_message = custom_prompt if custom_prompt else self.system_prompt
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                system=system_message,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": f"Here is the PDF content to analyze:\n\n{pdf_text}"}
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return None

    def process_pdfs(self, pdf_dir, output_file, custom_prompt=None):
        """Process all PDFs in a directory and save results to a JSON file."""
        results = {}
        pdf_files = list(Path(pdf_dir).glob("*.pdf"))
        
        print(f"Found {len(pdf_files)} PDF files to process")
        
        for pdf_path in pdf_files:
            print(f"Processing {pdf_path.name}...")
            pdf_text = self.extract_text_from_pdf(pdf_path)
            
            if pdf_text:
                analysis = self.analyze_with_claude(pdf_text, custom_prompt)
                print(analysis)
                if analysis:
                    results[pdf_path.name] = {
                        "file_path": str(pdf_path),
                        "analysis": analysis
                    }
        
        # Save results to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Analysis complete! Results saved to {output_file}")
        return results

def main():
    parser = argparse.ArgumentParser(description="Scan PDFs with Claude.ai and store results in JSON")
    parser.add_argument("--pdf_dir", required=True, help="Directory containing PDF files")
    parser.add_argument("--output", default="claude_pdf_analysis.json", help="Output JSON file")
    parser.add_argument("--api_key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default="claude-3-7-sonnet-20250219", help="Claude model to use")
    parser.add_argument("--custom_prompt", help="Path to file containing custom system prompt")
    
    args = parser.parse_args()
    
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
    scanner.process_pdfs(args.pdf_dir, args.output, custom_prompt)

if __name__ == "__main__":
    main()