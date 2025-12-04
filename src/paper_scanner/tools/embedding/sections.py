import re


def detect_sections(text: str) -> List[Dict]:
    """Detect sections in academic paper"""

    section_patterns = [
        # Markdown headers
        r"^#+\s+(.+)$",
        # Numbered sections (various formats)
        r"^(\d+\.?\s+[A-Z][^.!?]+)$",  # "1. Introduction" or "1 Introduction"
        r"^(\d+\.\d+\.?\s+[A-Z][^.!?]+)$",  # "1.1 Background" or "1.1. Background"
        r"^(\d+\.\d+\.\d+\.?\s+[A-Z][^.!?]+)$",  # "1.1.1 Subsection"
        r"^([IVX]+\.?\s+[A-Z][^.!?]+)$",  # Roman numerals: "I. Introduction"
        r"^([A-Z]\.?\s+[A-Z][^.!?]+)$",  # Letter sections: "A. Methods"
        # ALL CAPS headers (at least 3 chars)
        r"^([A-Z][A-Z\s]{2,}:?)$",
        # Common academic paper sections (case-insensitive)
        r"^(Abstract)s?$",
        r"^(Executive\s+Summary)$",
        r"^(Keywords?)$",
        r"^(Introduction)$",
        r"^(Background)$",
        r"^(Literature\s+Review)$",
        r"^(Related\s+Work)$",
        r"^(Theoretical\s+Framework)$",
        r"^(Conceptual\s+Framework)$",
        r"^(Research\s+Question)s?$",
        r"^(Hypothes[ei]s)$",
        # Methods sections
        r"^(Methods?)$",
        r"^(Methodology)$",
        r"^(Materials?\s+and\s+Methods?)$",
        r"^(Research\s+Methods?)$",
        r"^(Research\s+Design)$",
        r"^(Experimental\s+Design)$",
        r"^(Data\s+Collection)$",
        r"^(Data\s+Analysis)$",
        r"^(Analytical\s+Approach)$",
        r"^(Case\s+Study)$",
        r"^(Sample)$",
        r"^(Participants?)$",
        # Results sections
        r"^(Results?)$",
        r"^(Findings?)$",
        r"^(Empirical\s+Results?)$",
        r"^(Empirical\s+Findings?)$",
        r"^(Analysis)$",
        r"^(Empirical\s+Analysis)$",
        # Discussion sections
        r"^(Discussion)$",
        r"^(Interpretation)$",
        r"^(Results?\s+and\s+Discussion)$",
        # Implications/contributions
        r"^(Implications?)$",
        r"^(Theoretical\s+Implications?)$",
        r"^(Practical\s+Implications?)$",
        r"^(Managerial\s+Implications?)$",
        r"^(Policy\s+Implications?)$",
        r"^(Contributions?)$",
        r"^(Theoretical\s+Contributions?)$",
        # Limitations and future work
        r"^(Limitations?)$",
        r"^(Future\s+Research)$",
        r"^(Future\s+Work)$",
        r"^(Research\s+Agenda)$",
        # Conclusions
        r"^(Conclusion)s?$",
        r"^(Concluding\s+Remarks?)$",
        r"^(Summary)$",
        r"^(Summary\s+and\s+Conclusion)s?$",
        # References and appendices
        r"^(References?)$",
        r"^(Bibliography)$",
        r"^(Works?\s+Cited)$",
        r"^(Appendix|Appendices)$",
        r"^(Supplementary\s+Materials?)$",
        r"^(Acknowledgements?)$",
        r"^(Acknowledgments?)$",
        r"^(Funding)$",
        r"^(Conflict\s+of\s+Interest)s?$",
        r"^(Author\s+Contributions?)$",
        r"^(Data\s+Availability)$",
        # Common subsection patterns
        r"^(Overview)$",
        r"^(Summary)$",
        r"^(Definitions?)$",
        r"^(Propositions?)$",
        r"^(Model)$",
        r"^(Framework)$",
        r"^(Approach)$",
        r"^(Context)$",
        r"^(Setting)$",
        r"^(Procedure)$",
        r"^(Measures?)$",
        r"^(Variables?)$",
        r"^(Instruments?)$",
        r"^(Statistics)$",
        r"^(Statistical\s+Analysis)$",
        # Domain-specific sections (business/management)
        r"^(Business\s+Model)$",
        r"^(Value\s+Proposition)$",
        r"^(Competitive\s+Advantage)$",
        r"^(Strategy)$",
        r"^(Implementation)$",
        # Domain-specific sections (digital transformation)
        r"^(Digital\s+Transformation)$",
        r"^(Digital\s+Strategy)$",
        r"^(Technology\s+Adoption)$",
        r"^(Innovation)$",
        r"^(Capabilities?)$",
        r"^(Resources?)$",
        # Case study specific
        r"^(Case\s+Description)$",
        r"^(Company\s+Background)$",
        r"^(Industry\s+Context)$",
        r"^(Within-case\s+Analysis)$",
        r"^(Cross-case\s+Analysis)$",
    ]

    sections = []
    lines = text.split("\n")
    current_section = None
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is a section header
        is_header = False
        for pattern in section_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                # Save previous section
                if current_section:
                    sections.append({"title": current_section, "content": "\n".join(current_content)})

                # Extract the section title (use the captured group or full match)
                current_section = match.group(1) if match.groups() else line
                current_content = []
                is_header = True
                break

        if not is_header:
            current_content.append(line)

    # Add final section
    if current_section:
        sections.append({"title": current_section, "content": "\n".join(current_content)})

    return sections
