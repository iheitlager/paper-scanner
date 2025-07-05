import json
import re
import argparse


class AcademicPaperParser:
    """
    Parser for academic paper analysis with section headers.
    Supports multiple section header formats and provides various utility functions.
    """
    
    def __init__(self):
        # Dictionary to store normalized section names and their variations
        self.section_aliases = {
            "PAPER_HEADER": ["TITLE_AND_AUTHORS"],
            # "ABSTRACT_SUMMARY": ["ABSTRACT", "SUMMARY", "DOCUMENT_SUMMARY"],
            "RESEARCH_QUESTION": ["RESEARCH_QUESTIONS", "RESEARCH_OBJECTIVES", "HYPOTHESIS"],
            "METHODOLOGY": ["METHODS", "RESEARCH_METHODOLOGY", "APPROACH"],
            "KEY_FINDINGS": ["FINDINGS", "RESULTS", "MAIN_FINDINGS, KEY_POINTS"],
            "LIMITATIONS": ["LIMITATIONS_AND_CONSTRAINTS", "CONSTRAINTS", "STUDY_LIMITATIONS"],
            "FUTURE_WORK": ["FUTURE_RESEARCH", "FURTHER_WORK"],
            "CONCLUSIONS": ["RESULTS"],
            "CITATIONS": ["REFERENCES", "BIBLIOGRAPHY", "CITED_WORKS"],
        }
        
        # Create reverse mapping for normalization
        self.normalize_map = {}
        for standard, aliases in self.section_aliases.items():
            for alias in aliases:
                self.normalize_map[alias] = standard
            self.normalize_map[standard] = standard  # Map standard to itself
    
    def normalize_section_name(self, section_name):
        """
        Convert various section name formats to standard format.
        """
        # Remove any non-alphanumeric characters and convert to uppercase
        clean_name = re.sub(r'[^A-Z0-9_]', '', section_name.upper())
        
        # Return normalized name if it exists in our mapping
        return self.normalize_map.get(clean_name, clean_name)
    
    def parse_sections(self, text):
        """
        Parse text into sections based on different header formats.
        """
        # Try multiple header patterns
        patterns = [
            # ## SECTION_NAME
            r'##[0-9\.\s]+([A-Z_\:]+)\s*\n+(.*?)(?=##[0-9\.\s]+[A-Z_]+|\Z)',
            
            # # SECTION_NAME:
            # r'([A-Z_]+):\s*\n(.*?)(?=(?:[A-Z_]+):\s*\n|\Z)',
            
            # # SECTION_NAME
            # r'(?:^|\n)([A-Z_]+)\s*\n(.*?)(?=(?:^|\n)[A-Z_]+\s*\n|\Z)'
        ]
        
        sections = {}
        
        # Try each pattern until we find matches
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                for section_name, content in matches:
                    normalized_name = self.normalize_section_name(section_name)
                    sections[normalized_name] = content.strip()
                break
        return sections
    
    def extract_paper_header(self, header_text):
        """
        Separate title and authors from combined paper_header section.
        """
        # Try to find paper header patterns 
        fields = ["TITLE",'AUTHORS','YEAR']
        items = {}

        for l in header_text.split('\n\n'):
            match = re.search(r'\**\d+\.\d+\.\s+\**(.*)\:\*+\s+(.*)', l)
            if match:
                key = match.group(1).strip()
                if key in fields:
                    items[key] = match.group(2).strip()

        return items
    
    def extract_research_questions(self, research_question_text):
        """
        Extract individual research questions if multiple are present.
        """
        # Look for numbered questions (1., 2., etc.)
        numbered_questions = re.findall(r'\d+\.\s*(.+?)(?=\d+\.|\Z)', research_question_text, re.DOTALL)
        
        if numbered_questions:
            return [q.strip() for q in numbered_questions]
        
        # Look for bullet points
        bulleted_questions = re.findall(r'[•*-]\s*(.+?)(?=[•*-]|\Z)', research_question_text, re.DOTALL)
        
        if bulleted_questions:
            return [q.strip() for q in bulleted_questions]
        
        # Just split by periods if no clear structure
        if '.' in research_question_text:
            return [q.strip() + '.' for q in research_question_text.split('.') if q.strip()]
        
        # Return as a single question if no separators found
        return [research_question_text.strip()]

    def parse_methodology_steps(self, methodology_text):
        """
        Extract methodology separate items.
        """
        fields = ["EMPIRICAL_BASE",'METHODOLOGY_CLASS']
        items = {}

        for l in methodology_text.split('\n\n'):
            match = re.search(r'\**\d+\.\d+\.\s+\**([A-Z_]*)\:\*+\s+(.*)', l)
            if match:
                key = match.group(1).strip()
                if key in fields:
                    items[key] = match.group(2).strip()

        return items
        
    def parse_innovation_mechanisms(self, methodology_text):
        """
        Extract innovation mechanisms separate items.
        """
        items = []

        for l in methodology_text.split('\n\n'):
            camo, description = l.split(' - ')
            match = re.search(r'\[(.+)\], \[(.+)\], \[(.+)\], \[(.+)\]', camo)
            if match:
                camo = {
                    "c": match.group(1).strip(),
                    "a": match.group(2).strip(),
                    "m": match.group(3).strip(),
                    "o": match.group(4).strip(),
                    'description': description
                }
            else:
                camo = {'camo': camo, 'description': description}
            items.append(camo)

        return {'CAMO': items}
    

    def parse_vendors(self, vendors_text):
        """
        Extract vendors separate items.
        """
        fields = ["IT_SUPPLIER", 'REGULAR_SUPPLIER']
        items = {}

        for l in vendors_text.split('\n\n'):
            matches = re.findall(r'\**\d+\.\d+\.\s+\**([A-Z_]+)\:\*+\s+(.*)', l, re.DOTALL)
            if matches:
                for section_name, content in matches:
                    section_name = section_name.strip()
                    if section_name in fields:
                        items[section_name] = content.strip().split('\n')

        return items

    def parse_steps(self, steps_text):
        """
        Extract steps into a structured list.
        """
        patterns = [
            r'\d+\.\s*(.+?)(?=\d+\.|\Z)',   # starts with numbers.
            r'(.+)'                         # basically catch all
        ]
        
        results = []

        # Split by paragraphs
        paragraphs = [p.strip() for p in steps_text.replace('\n\n','\n').split('\n') if p.strip()]

        for paragraph in paragraphs:
            for pattern in patterns:
                # Look for steps
                steps = re.findall(pattern, paragraph)
                if steps:
                    for step in steps:
                        results.append(step)
                    break

        return results


    def process_paper_analysis(self, text):
        """
        Process academic paper analysis and return structured data.
        """
        # Parse basic sections
        sections = self.parse_sections(text)
        
        # Process specific sections further
        result = {}
        
        # Copy all sections to result
        for key, value in sections.items():
            result[key] = value
        
        # # Process PAPER_HEADER if present
        if "PAPER_HEADER" in sections:
            paper_header = self.extract_paper_header(sections["PAPER_HEADER"])
            result.update(paper_header)
        
        # # Process RESEARCH_QUESTION if present
        # if "RESEARCH_QUESTION" in sections:
        #     result["RESEARCH_QUESTIONS"] = self.extract_research_questions(sections["RESEARCH_QUESTION"])
        
        # # Process METHODOLOGY if present
        if "METHODOLOGY" in sections:
            methodology = self.parse_methodology_steps(sections["METHODOLOGY"])
            result.update(methodology)
        
        # # Process MECHANISMS if present
        if "INNOVATION_MECHANISMS" in sections:
            mechanisms = self.parse_innovation_mechanisms(sections["INNOVATION_MECHANISMS"])
            result.update(mechanisms)
        # if "MECHANISMS" in sections:
        #     result["MECHANISMS"] = self.parse_steps(sections["MECHANISMS"])

        # # Process VENDORS if present
        if "VENDORS" in sections:
            vendors = self.parse_vendors(sections["VENDORS"])
            result.update(vendors)

        return result
    
    def to_json(self, structured_data, indent=2):
        """
        Convert structured data to JSON string.
        """
        return json.dumps(structured_data, indent=indent)
    
    def save_to_file(self, structured_data, output_file="paper_analysis.json", indent=2):
        """
        Save structured data to JSON file.
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=indent)
            return True
        except Exception as e:
            print(f"Error saving to JSON file: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Parse academic paper sections")
    parser.add_argument("--input", help="Input text file with section headers")
    parser.add_argument("--output", default="paper_analysis.json", help="Output JSON file")
    
    args = parser.parse_args()
    
    # Initialize parser
    paper_parser = AcademicPaperParser()
    
    # Read from file or use sample text
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            print(f"Error reading input file: {e}")
            return
    else:
        # You can use this for testing when no input file is provided
        text = """## TITLE_AUTHORS
"Integrating digital transformation with human-centric factors strategies to enhance organisational process performance: The H.O.P.E. model" by Camilla Buttura Chrusciak, Anderson Luis Szejka, and Osiris Canciglieri Junior.
## ABSTRACT_SUMMARY
This research examines how technology implementation, employee engagement, usability awareness, and strategic management practices can improve organizational processes. Through a systematic literature review and Structural Equation Modeling, the study identifies critical success factors for digital transformation (DX), revealing that digital tools streamline operations and support data-driven decisions while reducing cognitive overload through user-centered design. The authors propose the Human-Oriented Process Enhancement (H.O.P.E.) model, which integrates DX with human-centric factors to guide technology applications and improve organizational performance.
## RESEARCH_QUESTION
How can digital transformation technologies enhance the quality and efficiency of organizational management processes while also promoting human well-being?
## METHODOLOGY
The research employed a three-phase approach:
1. Systematic Literature Review (SLR) to explore research on Digital Transformation, Business Process Management, Emerging Technologies, and Human Factors
2. Bibliometric and Content Analysis to identify gaps and trends in existing literature
3. Structural Equation Modeling (SEM) to test hypotheses examining relationships between Digital Transformation, Human Factors and Ergonomics, Business Process Management, and emerging technologies
4. Development and validation of the H.O.P.E. model through an experimental case study in a litigation management project at an automotive supplier manufacturing plant"""
    
    # Process the text
    structured_data = paper_parser.process_paper_analysis(text)
    
    # Print JSON
    print(paper_parser.to_json(structured_data))
    
    # Save to file
    if paper_parser.save_to_file(structured_data, args.output):
        print(f"Successfully saved to {args.output}")


if __name__ == "__main__":
    main()