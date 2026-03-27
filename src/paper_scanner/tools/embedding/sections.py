import re
from typing import Dict, List, Optional

# Canonical paper structure (every academic paper should map to these top-level sections)
CANONICAL_SECTIONS = {
    "title": ["title", "paper title"],
    "abstract": ["abstract", "summary", "executive summary"],
    "keywords": ["keywords", "key words", "key terms", "keywords and phrases"],
    "introduction": ["introduction", "context", "overview"],
    "background": ["background", "background and context", "theoretical background", "conceptual background"],
    "research_question": ["research question", "research questions", "research objectives", "research aims", "research questions:"],
    "literature": ["literature review", "related work", "theoretical framework", "literature"],
    "methods": ["methods", "methodology", "research design", "approach", "technical approach", "materials and methods"],
    "findings": ["results", "findings", "results and discussion", "analysis", "empirical results", "evaluation"],
    "conclusion": ["conclusion", "conclusions", "summary", "concluding remarks"],
}


def detect_sections(text: str) -> List[Dict]:
    """Detect sections in academic paper text.

    Scans text for section headers using 70+ regex patterns covering:
    - Markdown headers (# ## ###)
    - Numbered sections (1. 1.1. I. A.)
    - ALL CAPS sections
    - Common academic section names (Abstract, Introduction, Methods, etc.)

    Returns structured list of sections with title and content.
    """

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
        r".*:\s+(Abstract)s?$",  # Abstract after colon (e.g., "*Correspondence: Abstract")
        r"^(Executive\s+Summary)$",
        r"^(Keywords?(?:\s+and\s+Phrases)?):?",  # Keywords with optional colon and content
        r"^(Introduction)$",
        r"^(Background)$",
        r"^(Literature\s+Review)$",
        r"^(Related\s+Work)$",
        r"^(Theoretical\s+Framework)$",
        r"^(Conceptual\s+Framework)$",
        r"^(Research\s+Question)s?$",
        r"^(.+?research\s+question.*)$",
        r"^(Hence,\s+we\s+ask\s+the\s+following\s+research\s+questions)$",
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

    # Post-process: extract paper title (if not already detected as section header)
    sections = _extract_title(sections, text)

    # Post-process: split combined headers like "ABSTRACT KEYWORDS AND PHRASES"
    sections = _split_combined_headers(sections)

    # Post-process: extract research questions from introduction sections
    sections = _extract_research_questions(sections)

    return sections


def _extract_title(sections: List[Dict], text: str) -> List[Dict]:
    """Extract paper title if not already detected as a section.

    The paper title typically appears before abstract/introduction and is often missed
    when it spans multiple lines or appears inline (e.g., after metadata).
    """
    # Check if title already exists
    if any(normalize_section_name(s['title']) == 'title' for s in sections):
        return sections

    # Look for "Abstract" section - title should be before it
    abstract_index = None
    for i, section in enumerate(sections):
        if normalize_section_name(section['title']) == 'abstract':
            abstract_index = i
            break

    if abstract_index is None or abstract_index == 0:
        return sections

    # Collect text before abstract from non-header sections
    title_candidates = []
    for i in range(abstract_index):
        section = sections[i]
        # Skip known metadata/header-like sections
        if not _is_metadata_section(section['title']):
            # Prefer longer content that looks like a title
            content = section['content'].strip()
            if content and len(content) > 20:  # Likely to be title if non-trivial length
                title_candidates.append(content)

    # Use the longest non-metadata section as title
    if title_candidates:
        best_title = max(title_candidates, key=len)
        # Clean up title (remove extra whitespace, newlines)
        best_title = ' '.join(best_title.split())

        # Insert title at beginning
        sections.insert(0, {"title": "title", "content": best_title})

    return sections


def _is_metadata_section(title: str) -> bool:
    """Check if a section title looks like metadata/header rather than content."""
    metadata_keywords = [
        'journal', 'issn', 'doi', 'homepage', 'correspondence', 'department',
        'university', 'affiliation', 'institute', 'group', 'psychology',
        'ergonomics', 'aesthetics', 'url', 'https://', 'www.', '@',
        'research', 'license', 'supplementary', 'article', 'terms',
        'conditions', 'access', 'open access'
    ]
    title_lower = title.lower()

    # Check if it's too short (likely metadata)
    if len(title) < 5:
        return True

    # Check for metadata keywords
    for keyword in metadata_keywords:
        if keyword in title_lower:
            return True

    return False


def _split_combined_headers(sections: List[Dict]) -> List[Dict]:
    """Split combined headers into separate sections.

    Some PDFs combine headers on one line (e.g., "ABSTRACT KEYWORDS AND PHRASES").
    This function detects and splits them into separate sections.
    """
    result = []
    combined_patterns = [
        (r"abstract\s+keywords", ["abstract", "keywords"]),
        (r"abstract\s+key\s+words", ["abstract", "keywords"]),
    ]

    for section in sections:
        title = section['title'].lower()
        split = False

        for pattern, headers in combined_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                # Split into multiple sections
                content = section['content']
                for header in headers:
                    result.append({"title": header, "content": content})
                split = True
                break

        if not split:
            result.append(section)

    return result


def _extract_research_questions(sections: List[Dict]) -> List[Dict]:
    """Extract research questions from introduction sections.

    Some papers embed research questions in the introduction without a dedicated section.
    This function detects lines like "RQ1:", "RQ2:", etc. and creates a separate section.
    """
    result = []
    rq_content = []
    rq_found = False

    for section in sections:
        title = section['title'].lower()
        content = section['content']

        # Check if this section contains research questions
        if 'rq' in content or 'research question' in title.lower():
            # Extract RQ lines (RQ1:, RQ2:, RQ3:, etc.)
            lines = content.split('\n')
            non_rq_lines = []

            for line in lines:
                # Check if line starts with RQ pattern
                if re.match(r'^\s*RQ\d+:', line, re.IGNORECASE):
                    rq_content.append(line.strip())
                    rq_found = True
                else:
                    non_rq_lines.append(line)

            # If we found RQs, keep the section but with non-RQ content only
            if rq_found and non_rq_lines:
                result.append({
                    "title": section['title'],
                    "content": '\n'.join(non_rq_lines)
                })
            elif not rq_found:
                result.append(section)
        else:
            result.append(section)

    # Add research questions section if we found any
    if rq_content:
        result.append({
            "title": "research_question",
            "content": '\n'.join(rq_content)
        })

    return result


def normalize_section_name(detected_title: str) -> Optional[str]:
    """Map detected section name to canonical section.

    Matches detected section titles against known canonical sections.
    This enables consistent comparison across papers that use different naming conventions.

    Args:
        detected_title: Section title from detect_sections()

    Returns:
        Canonical section name (e.g., "methods", "findings") or None if no match

    Examples:
        - "Research Methods" → "methods"
        - "Results and Discussion" → "findings"
        - "Related Work" → "literature"
        - "Conclusion" → "conclusion"
    """
    detected_lower = detected_title.lower().strip()

    # Direct lookup in canonical sections
    for canonical, aliases in CANONICAL_SECTIONS.items():
        for alias in aliases:
            if detected_lower == alias or alias in detected_lower or detected_lower in alias:
                return canonical

    return None


def group_sections_hierarchically(sections: List[Dict]) -> Dict[str, List[Dict]]:
    """Group detected sections into hierarchical canonical structure.

    Takes raw detected sections and maps each to its canonical parent section.
    Unknown sections are grouped under "other".

    Args:
        sections: List from detect_sections()

    Returns:
        Dict with canonical section names as keys, lists of detected sections as values

    Example:
        Input: [
            {"title": "Methods", "content": "..."},
            {"title": "Research Design", "content": "..."},
            {"title": "Results", "content": "..."},
        ]

        Output: {
            "methods": [
                {"title": "Methods", "content": "...", "canonical": "methods"},
                {"title": "Research Design", "content": "...", "canonical": "methods"},
            ],
            "findings": [
                {"title": "Results", "content": "...", "canonical": "findings"},
            ],
        }
    """
    hierarchical = {canon: [] for canon in CANONICAL_SECTIONS.keys()}
    hierarchical["other"] = []

    for section in sections:
        canonical = normalize_section_name(section["title"])

        # Add canonical mapping to section
        section_with_mapping = {**section, "canonical": canonical}

        if canonical:
            hierarchical[canonical].append(section_with_mapping)
        else:
            hierarchical["other"].append(section_with_mapping)

    return hierarchical


def validate_paper_structure(hierarchical_sections: Dict[str, List[Dict]]) -> Dict:
    """Validate that detected sections cover standard paper structure.

    Checks which canonical sections were found and reports coverage.
    Useful for assessing if PDF extraction was successful.

    Args:
        hierarchical_sections: Output from group_sections_hierarchically()

    Returns:
        Dict with coverage analysis

    Example output:
        {
            "found": ["abstract", "introduction", "methods", "findings", "conclusion"],
            "missing": ["keywords", "literature"],
            "coverage_percentage": 66.7,
            "other_sections": 5,
            "total_detected": 11,
        }
    """
    found = [canon for canon, sections in hierarchical_sections.items()
             if canon != "other" and sections]
    missing = [canon for canon in CANONICAL_SECTIONS.keys() if canon not in found]

    total_canonical = len(CANONICAL_SECTIONS)
    coverage_pct = round(100 * len(found) / total_canonical, 1)

    return {
        "found": found,
        "missing": missing,
        "coverage_percentage": coverage_pct,
        "other_sections": len(hierarchical_sections.get("other", [])),
        "total_detected": sum(len(v) for v in hierarchical_sections.values()),
    }
