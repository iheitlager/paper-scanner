# src/paper_scanner/io/bibtex_converter.py

"""
BibTeX ↔ Pydantic conversion functions
Handles import/export of papers from/to BibTeX format
"""

from typing import List, Dict, Optional
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
import re

from ..core.models import (
    Paper, Author, Discovery, 
    DiscoveryMethod, PaperType
)


# ============================================================================
# BIBTEX → PYDANTIC
# ============================================================================

def parse_authors(author_string: str) -> List[Author]:
    """
    Parse author string from BibTeX format
    
    BibTeX formats:
    - "Smith, John and Doe, Jane"
    - "Smith, J. and Doe, J."
    - "John Smith and Jane Doe"
    """

    if not author_string:
        return []

    authors = []

    # Split by 'and'
    author_parts = re.split(r'\s+and\s+', author_string, flags=re.IGNORECASE)

    for author_str in author_parts:
        author_str = author_str.strip()
        if not author_str:
            continue

        # Try to parse: "Last, First" format
        if ',' in author_str:
            parts = author_str.split(',', 1)
            family_name = parts[0].strip()
            given_name = parts[1].strip() if len(parts) > 1 else None
            full_name = f"{given_name} {family_name}" if given_name else family_name
        else:
            # "First Last" format - take last word as family name
            parts = author_str.split()
            if len(parts) > 1:
                family_name = parts[-1]
                given_name = ' '.join(parts[:-1])
                full_name = author_str
            else:
                family_name = author_str
                given_name = None
                full_name = author_str

        authors.append(Author(
            family_name=family_name,
            given_name=given_name,
            full_name=full_name
        ))

    return authors


def parse_keywords(keywords_string: str) -> List[str]:
    """
    Parse keywords from BibTeX format

    Formats:
    - "keyword1; keyword2; keyword3"
    - "keyword1, keyword2, keyword3"
    - "keyword1 and keyword2"
    """

    if not keywords_string:
        return []

    # Try semicolon separator first
    if ';' in keywords_string:
        keywords = keywords_string.split(';')
    # Try comma separator
    elif ',' in keywords_string:
        keywords = keywords_string.split(',')
    # Try 'and' separator
    elif ' and ' in keywords_string.lower():
        keywords = re.split(r'\s+and\s+', keywords_string, flags=re.IGNORECASE)
    else:
        # Single keyword or space-separated
        keywords = [keywords_string]

    # Clean up
    keywords = [k.strip() for k in keywords if k.strip()]

    return keywords


def infer_paper_type(entry: Dict) -> PaperType:
    """Infer paper type from BibTeX entry type"""
    
    entry_type = entry.get('ENTRYTYPE', '').lower()
    
    type_mapping = {
        'article': PaperType.ARTICLE,
        'inproceedings': PaperType.CONFERENCE,
        'conference': PaperType.CONFERENCE,
        'book': PaperType.BOOK,
        'incollection': PaperType.BOOK_CHAPTER,
        'inbook': PaperType.BOOK_CHAPTER,
        'phdthesis': PaperType.THESIS,
        'mastersthesis': PaperType.THESIS,
        'techreport': PaperType.TECHNICAL_REPORT,
        'unpublished': PaperType.WORKING_PAPER,
        'misc': PaperType.OTHER,
    }
    
    return type_mapping.get(entry_type, PaperType.OTHER)


def bibtex_entry_to_paper(
    entry: Dict,
    discovery: Optional[Discovery] = None
) -> Paper:
    """
    Convert single BibTeX entry to Paper Pydantic model
    
    Args:
        entry: BibTeX entry dictionary
        discovery: Discovery object for tracking import
    
    Returns:
        Paper Pydantic model
    """
    
    # Get citekey (required)
    citekey = entry.get('ID')
    if not citekey:
        raise ValueError("BibTeX entry missing ID (citekey)")
    
    # Basic fields
    title = entry.get('title', '').strip()
    if not title:
        raise ValueError(f"BibTeX entry {citekey} missing title")
    
    # Remove LaTeX braces from title
    title = re.sub(r'[{}]', '', title)
    
    # Abstract
    abstract = entry.get('abstract', '').strip() or None
    if abstract:
        abstract = re.sub(r'[{}]', '', abstract)
    
    # Authors
    author_string = entry.get('author', '')
    authors = parse_authors(author_string)
    
    # Year
    year_str = entry.get('year', '')
    year = None
    if year_str:
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            # Try to extract year from date field
            date_str = entry.get('date', '')
            if date_str:
                year_match = re.search(r'\b(\d{4})\b', date_str)
                if year_match:
                    year = int(year_match.group(1))
    
    # Keywords - check both 'keywords' and 'author_keywords' (Scopus uses both)
    keywords_string = entry.get('keywords', '') or entry.get('author_keywords', '')
    keywords = parse_keywords(keywords_string)
    
    # Identifiers
    doi = entry.get('doi', '').strip() or None
    url = entry.get('url', '').strip() or None
    
    # ISBN/ISSN
    isbn = entry.get('isbn', '').strip() or None
    issn = entry.get('issn', '').strip() or None
    
    # Publication venue
    journal = entry.get('journal', '').strip() or None
    booktitle = entry.get('booktitle', '').strip() or None
    publisher = entry.get('publisher', '').strip() or None
    
    # Volume/Issue/Pages
    volume = entry.get('volume', '').strip() or None
    number = entry.get('number', '').strip() or None
    pages = entry.get('pages', '').strip() or None
    
    # Source key - use original BibTeX ID
    source_key = citekey
    
    # Create Paper model
    paper = Paper(
        citekey=citekey,
        source_key=source_key,
        title=title,
        abstract=abstract,
        authors=authors,
        year=year,
        keywords=keywords,
        doi=doi,
        isbn=isbn,
        issn=issn,
        url=url,
        journal=journal,
        booktitle=booktitle,
        publisher=publisher,
        volume=volume,
        number=number,
        pages=pages,
        discovery=discovery,
        raw_bibtex=format_bibtex_entry(entry)
    )
    
    return paper


def bibtex_to_papers(
    bibtex_string: str,
    discovery: Optional[Discovery] = None
) -> List[Paper]:
    """
    Parse BibTeX string and convert to list of Paper models

    Args:
        bibtex_string: BibTeX content as string
        source_type: Source database ('scopus', 'wos', 'ieee', 'manual', etc.)
        discovery_method: How papers were discovered
        import_batch_id: Optional batch ID for tracking

    Returns:
        List of Paper Pydantic models
    """

    # Parse BibTeX
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = True

    bib_database = bibtexparser.loads(bibtex_string, parser=parser)

    papers = []

    for entry in bib_database.entries:
        try:
            paper = bibtex_entry_to_paper(
                entry,
                discovery=discovery
            )
            papers.append(paper)
        except Exception as e:
            citekey = entry.get('ID', 'unknown')
            print(f"Warning: Failed to parse BibTeX entry {citekey}: {e}")
            continue
    
    return papers


def bibtex_file_to_papers(
    filepath: str,
    discovery: Optional[Discovery] = None
) -> List[Paper]:
    """
    Load BibTeX file and convert to Paper models

    Args:
        filepath: Path to .bib file
        discovery: Optional Discovery object for tracking import

    Returns:
        List of Paper models
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        bibtex_string = f.read()

    return bibtex_to_papers(
        bibtex_string,
        discovery=discovery
    )


# ============================================================================
# PYDANTIC → BIBTEX
# ============================================================================

def format_authors_bibtex(authors: List[Author]) -> str:
    """
    Format authors for BibTeX
    
    Format: "Last1, First1 and Last2, First2"
    """
    
    if not authors:
        return ""
    
    author_strings = []
    for author in authors:
        if author.given_name:
            author_strings.append(f"{author.family_name}, {author.given_name}")
        else:
            author_strings.append(author.family_name)
    
    return " and ".join(author_strings)


def format_keywords_bibtex(keywords: List[str]) -> str:
    """
    Format keywords for BibTeX
    
    Format: "keyword1, keyword2, keyword3"
    """
    
    if not keywords:
        return ""
    
    return ", ".join(keywords)


def infer_bibtex_type(paper: Paper) -> str:
    """
    Infer BibTeX entry type from Paper
    
    Uses paper_type if available in screening,
    otherwise infers from other fields
    """
    
    # Try to get from screening categorization
    if paper.screening.categorization:
        paper_type = paper.screening.categorization.paper_type
        
        type_mapping = {
            PaperType.ARTICLE: 'article',
            PaperType.CONFERENCE: 'inproceedings',
            PaperType.BOOK: 'book',
            PaperType.BOOK_CHAPTER: 'incollection',
            PaperType.THESIS: 'phdthesis',
            PaperType.TECHNICAL_REPORT: 'techreport',
            PaperType.WORKING_PAPER: 'unpublished',
            PaperType.PREPRINT: 'unpublished',
            PaperType.OTHER: 'misc',
        }
        
        return type_mapping.get(paper_type, 'misc')
    
    # Infer from fields
    if paper.journal:
        return 'article'
    elif paper.booktitle:
        return 'inproceedings'
    else:
        return 'misc'


def paper_to_bibtex_entry(paper: Paper, use_source_key: bool = True) -> Dict:
    """
    Convert Paper Pydantic model to BibTeX entry dictionary
    
    Args:
        paper: Paper Pydantic model
        use_source_key: If True and source_key exists, use it as ID.
                       Otherwise use citekey.
    
    Returns:
        BibTeX entry dictionary
    """
    
    # Determine citekey to use
    if use_source_key and paper.source_key:
        citekey = paper.source_key
    else:
        citekey = paper.citekey
    
    # Build entry
    entry = {
        'ID': citekey,
        'ENTRYTYPE': infer_bibtex_type(paper),
        'title': paper.title,
    }
    
    # Authors
    if paper.authors:
        entry['author'] = format_authors_bibtex(paper.authors)
    
    # Year
    if paper.year:
        entry['year'] = str(paper.year)
    
    # Abstract
    if paper.abstract:
        entry['abstract'] = paper.abstract
    
    # Keywords
    if paper.keywords:
        entry['keywords'] = format_keywords_bibtex(paper.keywords)
    
    # Identifiers
    if paper.doi:
        entry['doi'] = paper.doi
    
    if paper.url:
        entry['url'] = paper.url
    
    if paper.isbn:
        entry['isbn'] = paper.isbn
    
    if paper.issn:
        entry['issn'] = paper.issn
    
    # Publication venue
    if paper.journal:
        entry['journal'] = paper.journal
    
    if paper.booktitle:
        entry['booktitle'] = paper.booktitle
    
    if paper.publisher:
        entry['publisher'] = paper.publisher
    
    # Volume/Issue/Pages
    if paper.volume:
        entry['volume'] = paper.volume
    
    if paper.number:
        entry['number'] = paper.number
    
    if paper.pages:
        entry['pages'] = paper.pages
    
    return entry


def papers_to_bibtex(
    papers: List[Paper],
    use_source_key: bool = True
) -> str:
    """
    Convert list of Paper models to BibTeX string
    
    Args:
        papers: List of Paper Pydantic models
        use_source_key: Use source_key if available, otherwise citekey
    
    Returns:
        BibTeX formatted string
    """
    
    # Create BibDatabase
    bib_database = BibDatabase()
    
    # Convert papers to entries
    entries = []
    for paper in papers:
        try:
            entry = paper_to_bibtex_entry(paper, use_source_key=use_source_key)
            entries.append(entry)
        except Exception as e:
            print(f"Warning: Failed to convert paper {paper.citekey} to BibTeX: {e}")
            continue
    
    bib_database.entries = entries
    
    # Write to string
    writer = BibTexWriter()
    writer.indent = '  '
    writer.order_entries_by = ('ID', 'ENTRYTYPE')
    
    bibtex_string = bibtexparser.dumps(bib_database, writer)
    
    return bibtex_string


def papers_to_bibtex_file(
    papers: List[Paper],
    filepath: str,
    use_source_key: bool = True
) -> None:
    """
    Write papers to BibTeX file
    
    Args:
        papers: List of Paper models
        filepath: Output .bib file path
        use_source_key: Use source_key if available
    """
    
    bibtex_string = papers_to_bibtex(papers, use_source_key=use_source_key)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(bibtex_string)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_bibtex_entry(entry: Dict) -> str:
    """
    Format single BibTeX entry dict as string
    
    Useful for storing raw_bibtex in Paper model
    """
    
    bib_database = BibDatabase()
    bib_database.entries = [entry]
    
    writer = BibTexWriter()
    writer.indent = '  '
    
    return bibtexparser.dumps(bib_database, writer)


def clean_bibtex_string(bibtex_string: str) -> str:
    """
    Clean common issues in BibTeX strings
    
    - Remove excessive whitespace
    - Remove empty entries
    - Standardize line endings
    """
    
    # Standardize line endings
    bibtex_string = bibtex_string.replace('\r\n', '\n')
    
    # Remove excessive blank lines
    bibtex_string = re.sub(r'\n\s*\n\s*\n', '\n\n', bibtex_string)
    
    # Remove trailing whitespace
    lines = [line.rstrip() for line in bibtex_string.split('\n')]
    bibtex_string = '\n'.join(lines)
    
    return bibtex_string.strip()


# ============================================================================
# BATCH IMPORT/EXPORT FUNCTIONS
# ============================================================================

def import_bibtex_files(
    filepaths: List[str],
    discovery: Optional[Discovery] = None
) -> List[Paper]:
    """
    Import multiple BibTeX files

    Args:
        filepaths: List of .bib file paths
        discovery: Optional Discovery object for tracking import

    Returns:
        List of all imported Paper models
    """

    all_papers = []

    for filepath in filepaths:
        # Determine source type
        if source_types and filepath in source_types:
            source_type = source_types[filepath]
        else:
            # Infer from filename
            filename = filepath.lower()
            if 'scopus' in filename:
                source_type = 'scopus'
            elif 'wos' in filename or 'webofscience' in filename:
                source_type = 'wos'
            elif 'ieee' in filename:
                source_type = 'ieee'
            else:
                source_type = 'bibtex'
        
        print(f"Importing {filepath} (source: {source_type})...")
        
        discovery = Discovery(
            source_type=source_type,
            discovery_method=DiscoveryMethod.KEYWORD_SEARCH,
            import_batch_id=import_batch_id
        )

        papers = bibtex_file_to_papers(
            filepath,
            discovery=discovery
        )
        
        print(f"  Loaded {len(papers)} papers")
        all_papers.extend(papers)
    
    return all_papers


def export_papers_by_source(
    papers: List[Paper],
    output_dir: str = "./exports"
) -> Dict[str, str]:
    """
    Export papers to separate BibTeX files by source type
    
    Args:
        papers: List of Paper models
        output_dir: Directory to write files
    
    Returns:
        Dict mapping source_type to output filepath
    """
    
    import os
    from collections import defaultdict
    
    # Group papers by source_type
    papers_by_source = defaultdict(list)
    for paper in papers:
        papers_by_source[paper.source_type].append(paper)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Write files
    output_files = {}
    
    for source_type, source_papers in papers_by_source.items():
        filename = f"{source_type}_export.bib"
        filepath = os.path.join(output_dir, filename)
        
        papers_to_bibtex_file(source_papers, filepath, use_source_key=True)
        
        output_files[source_type] = filepath
        print(f"Exported {len(source_papers)} papers to {filepath}")
    
    return output_files


def export_papers_by_decision(
    papers: List[Paper],
    output_dir: str = "./exports"
) -> Dict[str, str]:
    """
    Export papers to separate files by screening decision
    
    Args:
        papers: List of Paper models
        output_dir: Directory to write files
    
    Returns:
        Dict mapping decision to output filepath
    """
    
    import os
    from collections import defaultdict
    
    # Group by decision
    papers_by_decision = defaultdict(list)
    for paper in papers:
        decision = paper.screening.final_decision.value
        papers_by_decision[decision].append(paper)
    
    os.makedirs(output_dir, exist_ok=True)
    
    output_files = {}
    
    for decision, decision_papers in papers_by_decision.items():
        filename = f"papers_{decision}.bib"
        filepath = os.path.join(output_dir, filename)
        
        papers_to_bibtex_file(decision_papers, filepath, use_source_key=False)
        
        output_files[decision] = filepath
        print(f"Exported {len(decision_papers)} {decision} papers to {filepath}")
    
    return output_files


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    # ========================================
    # Example 1: Import BibTeX file
    # ========================================
    
    print("="*60)
    print("Example 1: Import BibTeX file")
    print("="*60)
    
    papers = bibtex_file_to_papers(
        "scopus_export.bib",
        source_type="scopus",
        discovery_method=DiscoveryMethod.KEYWORD_SEARCH,
        import_batch_id="batch_2024_001"
    )
    
    print(f"Imported {len(papers)} papers")
    print(f"\nFirst paper:")
    print(f"  Citekey: {papers[0].citekey}")
    print(f"  Title: {papers[0].title[:60]}...")
    print(f"  Authors: {papers[0].author_string}")
    print(f"  Year: {papers[0].year}")
    
    # ========================================
    # Example 2: Export to BibTeX
    # ========================================
    
    print("\n" + "="*60)
    print("Example 2: Export to BibTeX")
    print("="*60)
    
    bibtex_string = papers_to_bibtex(papers[:5], use_source_key=True)
    print(bibtex_string[:500])
    print("...")
    
    # ========================================
    # Example 3: Import multiple files
    # ========================================
    
    print("\n" + "="*60)
    print("Example 3: Import multiple files")
    print("="*60)
    
    all_papers = import_bibtex_files(
        filepaths=[
            "scopus_export.bib",
            "wos_export.bib",
            "ieee_export.bib"
        ],
        source_types={
            "scopus_export.bib": "scopus",
            "wos_export.bib": "wos",
            "ieee_export.bib": "ieee"
        },
        import_batch_id="batch_2024_001"
    )
    
    print(f"Total imported: {len(all_papers)} papers")
    
    # Count by source
    from collections import Counter
    source_counts = Counter(p.source_type for p in all_papers)
    print("\nBy source:")
    for source, count in source_counts.items():
        print(f"  {source}: {count}")
    
    # ========================================
    # Example 4: Export by decision
    # ========================================
    
    print("\n" + "="*60)
    print("Example 4: Export by decision")
    print("="*60)
    
    # (Assuming papers have screening decisions)
    output_files = export_papers_by_decision(all_papers, "./exports")
    
    print("\nExported files:")
    for decision, filepath in output_files.items():
        print(f"  {decision}: {filepath}")