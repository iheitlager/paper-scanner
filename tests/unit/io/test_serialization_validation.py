"""
Test script to validate Paper serialization to dict with self-references
Tests the JSONL export path: export.py -> papers_to_jsonl -> paper_to_dict
"""

import json

from paper_scanner.core.models import Author, Citation, Discovery, DiscoveryMethod, Paper
from paper_scanner.io.json import paper_to_dict, papers_to_jsonl


def test_paper_self_reference_serialization():
    """Test that Paper self-references serialize to IDs in dict mode"""

    # Create two papers
    paper1 = Paper(
        cite_key="Smith2023",
        title="Original Paper",
        authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    paper2 = Paper(
        cite_key="Smith2023_dup",
        title="Duplicate Paper",
        authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=paper1  # Self-reference!
    )

    # Convert to dict
    paper2_dict = paper_to_dict(paper2)

    assert isinstance(paper2_dict.get('duplicate_of'), str), "duplicate_of should be string ID"
    assert paper2_dict.get('duplicate_of') == paper1.id, "duplicate_of should match Paper1.id"


def test_citation_resolved_paper_serialization():
    """Test that Citation.resolved_paper serializes to ID in dict mode"""

    # Create a paper
    paper = Paper(
        cite_key="ResearchPaper2023",
        title="Research Paper",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    # Create a citation with resolved_paper reference
    citation = Citation(
        title="Referenced Work",
        authors=["Author A", "Author B"],
        year=2022,
        extraction_method="grobid",
        confidence=0.95,
        direction="backward",
        resolved_paper=paper  # Self-reference!
    )

    # Convert paper with citation to dict
    paper.citations = [citation]
    paper_dict = paper_to_dict(paper)

    citation_dict = paper_dict['citations'][0]

    assert isinstance(citation_dict.get('resolved_paper'), str), "resolved_paper should be string ID"
    assert citation_dict.get('resolved_paper') == paper.id, "resolved_paper should match Paper.id"


def test_cited_papers_serialization():
    """Test that Paper.cited_papers list serializes to ID list in dict mode"""

    # Create papers
    cited_paper1 = Paper(
        cite_key="Cited2020",
        title="Cited Paper 1",
        year=2020,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    cited_paper2 = Paper(
        cite_key="Cited2021",
        title="Cited Paper 2",
        year=2021,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    main_paper = Paper(
        cite_key="MainPaper2023",
        title="Main Paper",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        cited_papers=[cited_paper1, cited_paper2]  # List of Paper references!
    )

    # Convert to dict
    paper_dict = paper_to_dict(main_paper)

    cited_ids = paper_dict.get('cited_papers', [])
    assert isinstance(cited_ids, list), "cited_papers should be list"
    assert len(cited_ids) == 2, "cited_papers should have 2 items"
    assert cited_ids[0] == cited_paper1.id, "First cited_paper ID should match"
    assert cited_ids[1] == cited_paper2.id, "Second cited_paper ID should match"


def test_cited_by_papers_serialization():
    """Test that Paper.cited_by_papers list serializes to ID list in dict mode"""

    # Create papers
    citing_paper1 = Paper(
        cite_key="Citing2022",
        title="Citing Paper 1",
        year=2022,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    citing_paper2 = Paper(
        cite_key="Citing2023",
        title="Citing Paper 2",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    cited_paper = Paper(
        cite_key="CitedPaper2020",
        title="Cited Paper",
        year=2020,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        cited_by_papers=[citing_paper1, citing_paper2]  # List of Paper references!
    )

    # Convert to dict
    paper_dict = paper_to_dict(cited_paper)

    citing_ids = paper_dict.get('cited_by_papers', [])
    assert isinstance(citing_ids, list), "cited_by_papers should be list"
    assert len(citing_ids) == 2, "cited_by_papers should have 2 items"
    assert citing_ids[0] == citing_paper1.id, "First cited_by_paper ID should match"
    assert citing_ids[1] == citing_paper2.id, "Second cited_by_paper ID should match"


def test_jsonl_export_with_self_references():
    """Test that papers_to_jsonl correctly handles self-references"""

    # Create papers with various self-references
    paper1 = Paper(
        cite_key="Paper1",
        title="Paper 1",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    paper2 = Paper(
        cite_key="Paper2",
        title="Paper 2",
        year=2023,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=paper1,
        cited_papers=[paper1],
        cited_by_papers=[]
    )

    # Export to JSONL
    jsonl_output = papers_to_jsonl([paper1, paper2])

    # Parse back to verify structure
    lines = jsonl_output.strip().split('\n')
    assert len(lines) == 2, "Should have 2 lines for 2 papers"

    paper2_json = json.loads(lines[1])

    assert isinstance(paper2_json.get('duplicate_of'), str), "duplicate_of should be string ID"
    assert isinstance(paper2_json.get('cited_papers'), list), "cited_papers should be list of IDs"


def test_complete_serialization_chain():
    """Test the complete export chain from export.py"""

    # Create a more complex paper setup
    paper_a = Paper(
        cite_key="PaperA",
        title="Paper A - Original",
        year=2020,
        authors=[Author(family_name="Author", given_name="A", full_name="Author A")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH)
    )

    paper_b = Paper(
        cite_key="PaperB",
        title="Paper B - Duplicate",
        year=2020,
        authors=[Author(family_name="Author", given_name="A", full_name="Author A")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=paper_a
    )

    paper_c = Paper(
        cite_key="PaperC",
        title="Paper C - References A and B",
        year=2021,
        authors=[Author(family_name="Author", given_name="C", full_name="Author C")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        cited_papers=[paper_a, paper_b]
    )

    # Simulate export step's behavior
    papers = [paper_a, paper_b, paper_c]
    jsonl_content = papers_to_jsonl(papers, exclude_none=True)

    # Verify each line
    lines = jsonl_content.strip().split('\n')
    for i, line in enumerate(lines, 1):
        data = json.loads(line)
        assert all(isinstance(x, str) for x in data.get('cited_papers', []))

