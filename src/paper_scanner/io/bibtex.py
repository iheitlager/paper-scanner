# src/paper_scanner/io/bibtex_converter.py

"""
BibTeX ↔ Pydantic conversion functions
Handles import/export of papers from/to BibTeX format
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

import bibtexparser
import yaml
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter

from ..core.models import Author, Discovery, DiscoveryMethod, Paper, PaperType

# ============================================================================
# TYPE MAPPING CONFIGURATION
# ============================================================================

# Cache for loaded type mappings
_type_mapping_cache: Optional[Dict[str, Any]] = None


def load_type_mapping_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load BibTeX type mapping configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file. If None, uses default location.
        
    Returns:
        Dictionary with type mappings and source-specific overrides
    """
    global _type_mapping_cache

    if _type_mapping_cache is not None:
        return _type_mapping_cache

    if config_path is None:
        # Use default location relative to this module
        config_path = Path(__file__).parent.parent.parent.parent / "etc" / "bibtex_type_mapping.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        # Return minimal default mappings if config file not found
        return {
            'type_mappings': {
                'article': {'paper_type': 'journal_article', 'confidence': 0.95},
                'inproceedings': {'paper_type': 'conference_paper', 'confidence': 0.95},
                'book': {'paper_type': 'book', 'confidence': 0.95},
                'incollection': {'paper_type': 'book_chapter', 'confidence': 0.90},
                'inbook': {'paper_type': 'book_chapter', 'confidence': 0.90},
                'phdthesis': {'paper_type': 'thesis', 'confidence': 0.95},
                'mastersthesis': {'paper_type': 'thesis', 'confidence': 0.95},
                'techreport': {'paper_type': 'technical_report', 'confidence': 0.90},
                'unpublished': {'paper_type': 'working_paper', 'confidence': 0.75},
                'misc': {'paper_type': 'other', 'confidence': 0.5},
            },
            'source_overrides': {},
            'custom_mappings': {}
        }

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

    _type_mapping_cache = config
    return config


def evaluate_paper_type(
    entry: Dict,
    source_type: Optional[str] = None,
    type_mapping_config: Optional[Dict[str, Any]] = None
) -> tuple[Optional[str], float]:
    """
    Evaluate paper type from BibTeX entry using configurable mappings.
    
    This function tries multiple strategies:
    1. Source-specific type field and mapping
    2. Standard BibTeX entry type mapping
    3. Custom field mappings
    4. Fallback to entry type
    
    Args:
        entry: BibTeX entry dictionary
        source_type: Source database type (scopus, wos, ieee, etc.)
        type_mapping_config: Loaded type mapping configuration
        
    Returns:
        Tuple of (paper_type: str, confidence: float)
        Returns (None, 0.0) if no type could be determined
    """

    if type_mapping_config is None:
        type_mapping_config = load_type_mapping_config()

    entry_type = entry.get('ENTRYTYPE', '').lower()

    # Strategy 1: Check source-specific overrides
    if source_type and 'source_overrides' in type_mapping_config:
        source_config = type_mapping_config['source_overrides'].get(source_type.lower())
        if source_config:
            # Try to get type from source-specific field
            type_field = source_config.get('article_type_field')
            if type_field and type_field in entry:
                source_type_value = entry[type_field].strip()
                type_value_mappings = source_config.get('type_value_mappings', {})

                if source_type_value in type_value_mappings:
                    paper_type = type_value_mappings[source_type_value]
                    # Look up confidence from main mappings
                    confidence = 0.85  # Default for source-specific match
                    if paper_type in type_mapping_config.get('type_mappings', {}):
                        confidence = type_mapping_config['type_mappings'][paper_type].get('confidence', 0.85)
                    return paper_type, confidence

    # Strategy 2: Use standard type mapping from BibTeX entry type
    type_mappings = type_mapping_config.get('type_mappings', {})
    if entry_type in type_mappings:
        mapping = type_mappings[entry_type]
        return mapping.get('paper_type'), mapping.get('confidence', 0.5)

    # Strategy 3: Try custom mappings
    custom_mappings = type_mapping_config.get('custom_mappings', {})
    if entry_type in custom_mappings:
        mapping = custom_mappings[entry_type]
        return mapping.get('paper_type'), mapping.get('confidence', 0.5)

    # Strategy 4: Fallback - check common field variations
    for field_name in ('type', 'document_type', 'article_type'):
        if field_name in entry:
            field_value = entry[field_name].strip().lower()
            # Try to match against known types
            if 'article' in field_value:
                return 'journal_article', 0.6
            elif 'conference' in field_value or 'proceedings' in field_value:
                return 'conference_paper', 0.6
            elif 'book' in field_value:
                if 'chapter' in field_value:
                    return 'book_chapter', 0.6
                return 'book', 0.6

    # Last resort: map entry type if it exists
    if entry_type:
        # Try case-insensitive match
        for known_type, mapping in type_mappings.items():
            if known_type.lower() == entry_type.lower():
                return mapping.get('paper_type'), mapping.get('confidence', 0.5)

    return None, 0.0


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
    keywords = [k.strip().lower() for k in keywords if k.strip()]

    return keywords


def infer_paper_type(entry: Dict) -> PaperType:
    """Infer paper type from BibTeX entry type"""

    entry_type = entry.get('ENTRYTYPE', '').lower()

    type_mapping = {
        'article': PaperType.JOURNAL_ARTICLE,
        'inproceedings': PaperType.CONFERENCE_PAPER,
        'conference': PaperType.CONFERENCE_PAPER,
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
    discovery: Optional[Discovery] = None,
    source_type: Optional[str] = None,
    type_mapping_config: Optional[Dict[str, Any]] = None
) -> Paper:
    """
    Convert single BibTeX entry to Paper Pydantic model

    Args:
        entry: BibTeX entry dictionary
        discovery: Discovery object for tracking import
        source_type: Source database type (scopus, wos, ieee, etc.)
        type_mapping_config: Loaded type mapping configuration

    Returns:
        Paper Pydantic model
    """

    # Get cite_key (required)
    cite_key = entry.get('ID')
    if not cite_key:
        raise ValueError("BibTeX entry missing ID (cite_key)")

    # Basic fields
    title = entry.get('title', '').strip()
    if not title:
        raise ValueError(f"BibTeX entry {cite_key} missing title")

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
    keywords_string = ""
    for kw in ('keyword', 'keywords', 'author_keywords', 'keywords-plus'):
        if kw in entry:
            keywords_string += entry[kw] + ';'
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
    source_key = cite_key

    # Evaluate paper type from BibTeX entry
    paper_type, type_confidence = evaluate_paper_type(
        entry,
        source_type=source_type,
        type_mapping_config=type_mapping_config
    )

    # Create Paper model
    paper = Paper(
        cite_key=cite_key,
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
        paper_type=paper_type,
        discovery=discovery,
        raw_bibtex=format_bibtex_entry(entry)
    )

    return paper


def bibtex_to_papers(
    bibtex_string: str,
    discovery: Optional[Discovery] = None,
    source_type: Optional[str] = None,
    discovery_method: Optional[DiscoveryMethod] = None,
    type_mapping_config: Optional[Dict[str, Any]] = None
) -> List[Paper]:
    """
    Parse BibTeX string and convert to list of Paper models

    Args:
        bibtex_string: BibTeX content as string
        discovery: Optional Discovery object for tracking import
        source_type: Source database ('scopus', 'wos', 'ieee', 'manual', etc.)
        discovery_method: How papers were discovered
        type_mapping_config: Optional pre-loaded type mapping configuration

    Returns:
        List of Paper Pydantic models
    """

    # Build discovery object if parameters provided
    if source_type or discovery_method:
        if discovery is None:
            discovery = Discovery(
                method=discovery_method or DiscoveryMethod.MANUAL,
                source_database=source_type,
            )
        else:
            # Update provided discovery object with new values
            if source_type:
                discovery.source_database = source_type
            if discovery_method:
                discovery.method = discovery_method

    # Load type mapping configuration if not provided
    if type_mapping_config is None:
        type_mapping_config = load_type_mapping_config()

    # Parse BibTeX
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = True

    bib_database = bibtexparser.loads(bibtex_string, parser=parser)

    papers = []

    for entry in bib_database.entries:
        paper = bibtex_entry_to_paper(
            entry,
            discovery=discovery,
            source_type=source_type,
            type_mapping_config=type_mapping_config
        )
        papers.append(paper)

    return papers


def bibtex_file_to_papers(
    filepath: str,
    discovery: Optional[Discovery] = None,
    source_type: Optional[str] = None,
    discovery_method: Optional[DiscoveryMethod] = None,
    type_mapping_config: Optional[Dict[str, Any]] = None
) -> List[Paper]:
    """
    Load BibTeX file and convert to Paper models

    Args:
        filepath: Path to .bib file
        discovery: Optional Discovery object for tracking import
        source_type: Source database ('scopus', 'wos', 'ieee', 'manual', etc.)
        discovery_method: How papers were discovered
        type_mapping_config: Optional pre-loaded type mapping configuration

    Returns:
        List of Paper models
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        bibtex_string = f.read()

    return bibtex_to_papers(
        bibtex_string,
        discovery=discovery,
        source_type=source_type,
        discovery_method=discovery_method,
        type_mapping_config=type_mapping_config
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
    
    Uses paper_type if available (from screening or direct),
    otherwise infers from other fields
    """

    type_mapping = {
        PaperType.JOURNAL_ARTICLE: 'article',
        PaperType.CONFERENCE_PAPER: 'inproceedings',
        PaperType.BOOK: 'book',
        PaperType.BOOK_CHAPTER: 'incollection',
        PaperType.THESIS: 'phdthesis',
        PaperType.TECHNICAL_REPORT: 'techreport',
        PaperType.WORKING_PAPER: 'unpublished',
        PaperType.PREPRINT: 'unpublished',
        PaperType.OTHER: 'misc',
    }

    # Try paper_type directly first
    if paper.paper_type:
        return type_mapping.get(paper.paper_type, 'misc')

    # Try to get from screening categorization
    if paper.screening.categorization and paper.screening.categorization.paper_type:
        paper_type = paper.screening.categorization.paper_type
        return type_mapping.get(paper_type, 'misc')

    # Infer from fields
    if paper.journal:
        return 'article'
    elif paper.booktitle:
        return 'inproceedings'
    else:
        return 'misc'


def paper_to_bibtex_entry(paper: Paper, use_source_key: bool = False) -> Dict:
    """
    Convert Paper Pydantic model to BibTeX entry dictionary
    
    Args:
        paper: Paper Pydantic model
        use_source_key: If True and source_key exists, use it as ID.
                       Otherwise use cite_key.
    
    Returns:
        BibTeX entry dictionary
    """

    # Determine cite_key to use
    if use_source_key and paper.source_key:
        cite_key = paper.source_key
    else:
        cite_key = paper.cite_key

    # Build entry
    entry = {
        'ID': cite_key,
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
    use_source_key: bool = False
) -> str:
    """
    Convert list of Paper models to BibTeX string
    
    Args:
        papers: List of Paper Pydantic models
        use_source_key: Use source_key if available, otherwise cite_key
    
    Returns:
        BibTeX formatted string
    """

    # Create BibDatabase
    bib_database = BibDatabase()

    # Convert papers to entries
    entries = []
    for paper in papers:
        entry = paper_to_bibtex_entry(paper, use_source_key=use_source_key)
        entries.append(entry)

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

        discovery = Discovery(
            source_type=source_type,
            discovery_method=DiscoveryMethod.KEYWORD_SEARCH
        )

        papers = bibtex_file_to_papers(
            filepath,
            discovery=discovery
        )

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
        discovery_method=DiscoveryMethod.KEYWORD_SEARCH
    )

    print(f"Imported {len(papers)} papers")
    print("\nFirst paper:")
    print(f"  cite_key: {papers[0].cite_key}")
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
        }
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
