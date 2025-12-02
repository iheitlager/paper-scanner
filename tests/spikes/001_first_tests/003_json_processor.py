import argparse
import json
import re
from pathlib import Path


class ClaudeAnalysisProcessor:
    def __init__(self, input_file, output_file=None):
        """Initialize the processor with input and output file paths."""
        self.input_file = Path(input_file)

        # If no output file is specified, create one with '_processed' suffix
        if output_file:
            self.output_file = Path(output_file)
        else:
            self.output_file = self.input_file.with_stem(f"{self.input_file.stem}_processed")

    def load_json(self):
        """Load JSON data from input file."""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            return None

    def parse_analysis_sections(self, analysis_text):
        """Parse analysis text into sections based on section headers."""
        # Define regex pattern for section headers (both ## SECTION and 1. SECTION formats)
        # This pattern captures both Markdown-style headers and numbered list items
        patterns = [
            r'(?:^|\n)##\s+([A-Z_]+):\s*(.*?)(?=(?:\n##\s+[A-Z_]+:|\Z))',  # Markdown headers
            r'(?:^|\n)(\d+)\.\s+([A-Z_]+):\s*(.*?)(?=(?:\n\d+\.\s+[A-Z_]+:|\Z))',  # Numbered list items
            r'(?:^|\n)([A-Z_]+):\s*(.*?)(?=(?:\n[A-Z_]+:|\Z))'  # Plain headers with colon
        ]

        sections = {}

        # Try each pattern until we find one that works
        for pattern in patterns:
            matches = re.findall(pattern, analysis_text, re.DOTALL)
            if matches:
                # Handle different match structures
                if len(matches[0]) == 2:  # Markdown headers or plain headers
                    for section_name, content in matches:
                        sections[section_name] = content.strip()
                elif len(matches[0]) == 3:  # Numbered list items
                    for _, section_name, content in matches:
                        sections[section_name] = content.strip()
                break

        # If no patterns matched, try a fallback approach
        if not sections:
            # Split by empty lines and look for "SECTION:" at the beginning of lines
            lines = analysis_text.split('\n\n')
            for line in lines:
                if ':' in line:
                    parts = line.split(':', 1)
                    if parts[0].strip().isupper():
                        sections[parts[0].strip()] = parts[1].strip()

        return sections

    def process_json(self):
        """Process the JSON data and split analysis fields."""
        data = self.load_json()
        if not data:
            return False

        processed_data = {}

        for pdf_name, pdf_info in data.items():
            file_path = pdf_info.get('file_path', '')
            analysis_text = pdf_info.get('analysis', '')

            # Parse analysis into sections
            sections = self.parse_analysis_sections(analysis_text)

            # Create processed entry
            processed_data[pdf_name] = {
                'file_path': file_path,
                'sections': sections
            }

        # Save processed data
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=2, ensure_ascii=False)
            print(f"Processed data saved to {self.output_file}")
            return True
        except Exception as e:
            print(f"Error saving processed data: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Process Claude PDF analysis JSON file")
    parser.add_argument("--input", required=True, help="Input JSON file from Claude PDF analysis")
    parser.add_argument("--output", help="Output processed JSON file (optional)")

    args = parser.parse_args()

    processor = ClaudeAnalysisProcessor(args.input, args.output)
    processor.process_json()


if __name__ == "__main__":
    main()
