import unittest
import sys
from io import StringIO
from paper_scanner.advanced_section_parser import AcademicPaperParser  # Assuming the class is in a file called academic_paper_parser.py

class TestAcademicPaperParser(unittest.TestCase):
    def setUp(self):
        self.parser = AcademicPaperParser()
        self.maxDiff = None  # Show full diff if assertion fails
        
        # Capture stderr to avoid printing during tests
        self.stderr_backup = sys.stderr
        sys.stderr = StringIO()
        
    def tearDown(self):
        # Restore stderr
        sys.stderr = self.stderr_backup
        
    def test_single_line(self):
        INPUT1 = """## TITLE_AUTHORS
        Integrating digital transformation"""

        EXPECTED_OUTPUT = 'Integrating digital transformation'
        
        # Parse the input
        parsed_sections = self.parser.parse_sections(INPUT1)
        # Check if TITLE_AUTHORS section exists and matches expected output
        self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
        self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT, 
                         "TITLE_AUTHORS content does not match expected output")

    def test_single_line_item(self):
        INPUT1 = """## 1. TITLE_AUTHORS
        Integrating digital transformation"""

        EXPECTED_OUTPUT = 'Integrating digital transformation'
        
        # Parse the input
        parsed_sections = self.parser.parse_sections(INPUT1)
        # Check if TITLE_AUTHORS section exists and matches expected output
        self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
        self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT, 
                         "TITLE_AUTHORS content does not match expected output")

    def test_section_header_skipped(self):
        INPUT1 = """# Academic Paper Analysis\n\n## 1. TITLE_AUTHORS
        Integrating digital transformation"""

        EXPECTED_OUTPUT = 'Integrating digital transformation'
        
        # Parse the input
        parsed_sections = self.parser.parse_sections(INPUT1)
        # Check if TITLE_AUTHORS section exists and matches expected output
        self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
        self.assertEqual(len(parsed_sections), 1,  
                         "Header not skipped")

    def test_multi_line_item(self):
        INPUT = """# Academic Paper Analysis\n\n## 1. TITLE_AUTHORS\nIntegrating digital transformation\n## 2. ABSTRACT_SUMMARY\nThis study explores how digital"""

        EXPECTED_OUTPUT1 = 'Integrating digital transformation'
        EXPECTED_OUTPUT2 = 'This study explores how digital'

        # Parse the input
        parsed_sections = self.parser.parse_sections(INPUT)
        # Check if TITLE_AUTHORS section exists and matches expected output
        self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
        self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT1, 
                         "TITLE_AUTHORS content does not match expected output")
        self.assertIn("ABSTRACT_SUMMARY", parsed_sections, "ABSTRACT_SUMMARY section not found in parsed result")
        self.assertEqual(parsed_sections["ABSTRACT_SUMMARY"], EXPECTED_OUTPUT2, 
                         "ABSTRACT_SUMMARY content does not match expected output")
        
if __name__ == "__main__":
    unittest.main()