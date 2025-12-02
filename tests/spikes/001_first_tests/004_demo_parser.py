from paper_scanner.core.advanced_section_parser import AcademicPaperParser


def demo_paper_section_parser():
    """
    Demonstrate the usage of the academic paper section parser.
    """
    # Sample text from an academic paper analysis
    sample_text = """## TITLE_AUTHORS
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

    # Initialize the parser
    parser = AcademicPaperParser()

    # Process the text
    result = parser.process_paper_analysis(sample_text)

    # Convert to JSON string with indentation for readability
    json_str = parser.to_json(result)

    # Print the JSON in a nice format
    print("=== PARSED ACADEMIC PAPER SECTIONS ===")
    print(json_str)
    print("\n=== ACCESSING INDIVIDUAL SECTIONS ===")

    # Demonstrate accessing individual sections
    if "TITLE" in result:
        print(f"Title: {result['TITLE']}")

    if "AUTHORS" in result and result["AUTHORS"]:
        print(f"Authors: {', '.join(result['AUTHORS'])}")

    if "ABSTRACT_SUMMARY" in result:
        print(f"Abstract: {result['ABSTRACT_SUMMARY'][:100]}...")

    if "METHODOLOGY_STEPS" in result:
        print("Methodology Steps:")
        for i, step in enumerate(result["METHODOLOGY_STEPS"], 1):
            print(f"  {i}. {step[:50]}...")

    # Save to file
    output_file = "parsed_paper.json"
    if parser.save_to_file(result, output_file):
        print(f"\nSaved to {output_file}")

if __name__ == "__main__":
    demo_paper_section_parser()
