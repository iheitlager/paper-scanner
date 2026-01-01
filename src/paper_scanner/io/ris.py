"""
RIS format ↔ Pydantic conversion functions
Handles import/export of papers from/to RIS format

RIS (Research Information Systems) is a tagged format used by many academic databases
(Zotero, Mendeley, Web of Science, Scopus, ProQuest, etc.)
"""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.models import Author, Discovery, DiscoveryMethod, Paper
from ..core.enum import PaperType
from ..core.doi import DOI
from ..core.normalization import Normalizer

# ============================================================================
# RIS PARSING
# ============================================================================

class RISRecord:
    """Represents a single RIS record"""

    def __init__(self):
        self.fields: Dict[str, Any] = {}

    def add_field(self, tag: str, value: str):
        """Add a field to the record. Multi-value fields stored as lists."""
        if tag in self.fields:
            if isinstance(self.fields[tag], list):
                self.fields[tag].append(value)
            else:
                self.fields[tag] = [self.fields[tag], value]
        else:
            self.fields[tag] = value

    def get(self, tag: str, default: Any = None) -> Any:
        """Get field value, handling both single and multi-value fields."""
        return self.fields.get(tag, default)

    def get_list(self, tag: str) -> List[str]:
        """Get field as list, even if single value."""
        value = self.fields.get(tag)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


class RISParser:
    """Parse RIS format files"""

    @staticmethod
    def parse_file(file_path: str) -> List[RISRecord]:
        """Parse RIS file and return list of records"""
        records = []
        current_record: Optional[RISRecord] = None

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')

                # Skip empty lines
                if not line.strip():
                    continue

                # Parse RIS format: TAG - value
                if ' - ' not in line:
                    continue

                parts = line.split(' - ', 1)
                if len(parts) != 2:
                    continue

                tag = parts[0].strip()
                value = parts[1].strip()

                # TY marks start of new record
                if tag == 'TY':
                    if current_record:
                        records.append(current_record)
                    current_record = RISRecord()

                # ER marks end of record
                if tag == 'ER':
                    if current_record:
                        records.append(current_record)
                    current_record = None
                    continue

                if current_record:
                    current_record.add_field(tag, value)

        # Don't forget last record if file doesn't end with ER
        if current_record:
            records.append(current_record)

        return records


# ============================================================================
# NORMALIZATION FUNCTIONS (Shared with BibTeX)
# ============================================================================


def normalize_ampersands(text: Optional[str]) -> Optional[str]:
    """
    Normalize ampersands in text: replace \\& and &amp; with &
    
    DEPRECATED: Use Normalizer._normalize_ampersands() instead.
    This function is maintained for backward compatibility.
    """
    return Normalizer._normalize_ampersands(text)


def normalize_whitespace(text: Optional[str]) -> Optional[str]:
    """
    Normalize whitespace: collapse multiple spaces, remove newlines
    
    DEPRECATED: Use Normalizer._collapse_whitespace() instead.
    This function is maintained for backward compatibility.
    """
    return Normalizer._collapse_whitespace(text)


def parse_authors_ris(authors_list: List[str]) -> List[Author]:
    """
    Parse RIS author list (AU fields are separate lines)

    DEPRECATED: Use Normalizer.normalize_authors() instead.
    This function is maintained for backward compatibility.

    RIS format: AU  - Last, First
    """
    normalized_names = Normalizer.normalize_authors(authors_list)
    
    # Convert normalized author strings to Author objects
    parsed = []
    for author_str in normalized_names:
        # RIS uses "Last, First" format (preserved by Normalizer)
        if ',' in author_str:
            parts = author_str.split(',', 1)
            family_name = parts[0].strip()
            given_name = parts[1].strip() if len(parts) > 1 else None
            full_name = f"{given_name} {family_name}" if given_name else family_name
        else:
            # Fallback for improperly formatted names
            parts = author_str.split()
            if len(parts) > 1:
                family_name = parts[-1]
                given_name = ' '.join(parts[:-1])
            else:
                family_name = author_str
                given_name = None
            full_name = author_str

        parsed.append(Author(
            family_name=family_name,
            given_name=given_name,
            full_name=full_name
        ))

    return parsed


def parse_keywords_ris(keywords_list: List[str]) -> List[str]:
    """
    Parse RIS keyword list (KW fields are separate lines in RIS)
    
    DEPRECATED: Use Normalizer.normalize_keywords() instead.
    This function is maintained for backward compatibility.
    """
    # Join with semicolon and use Normalizer
    if not keywords_list:
        return []
    return Normalizer.normalize_keywords(';'.join(keywords_list))


def infer_paper_type_ris(pub_type: str) -> PaperType:
    """Infer paper type from RIS publication type"""
    pub_type_lower = pub_type.lower() if pub_type else ''

    type_mapping = {
        'jour': PaperType.JOURNAL_ARTICLE,
        'article': PaperType.JOURNAL_ARTICLE,
        'conf': PaperType.CONFERENCE_PAPER,
        'cpaper': PaperType.CONFERENCE_PAPER,
        'inproceedings': PaperType.CONFERENCE_PAPER,
        'book': PaperType.BOOK,
        'chap': PaperType.BOOK_CHAPTER,
        'book_chapter': PaperType.BOOK_CHAPTER,
        'thes': PaperType.THESIS,
        'thesis': PaperType.THESIS,
        'rep': PaperType.TECHNICAL_REPORT,
        'report': PaperType.TECHNICAL_REPORT,
        'phdthesis': PaperType.THESIS,
        'mastersthesis': PaperType.THESIS,
        'unpublished': PaperType.WORKING_PAPER,
        'misc': PaperType.OTHER,
    }

    return type_mapping.get(pub_type_lower, PaperType.OTHER)


# ============================================================================
# RIS → PAPER MODEL CONVERSION
# ============================================================================


def ris_record_to_paper(
    record: RISRecord,
    discovery: Optional[Discovery] = None,
    source_database: Optional[str] = None,
) -> Paper:
    """
    Convert single RIS record to Paper Pydantic model

    Args:
        record: RIS record
        discovery: Discovery object for tracking import
        source_database: Source database name (ProQuest, Scopus, etc.)

    Returns:
        Paper Pydantic model
    """
    if not discovery:
        discovery = Discovery(method=DiscoveryMethod.KEYWORD_SEARCH, source_database=source_database)

    # RIS Field Mappings
    # TY  = Publication Type
    # T1  = Title
    # AU  = Author
    # AB  = Abstract
    # JF  = Journal Name
    # PY  = Publication Year
    # VL  = Volume
    # IS  = Issue
    # SP  = Start Page
    # KW  = Keywords
    # DO  = DOI
    # UR  = URL
    # PB  = Publisher
    # CY  = City
    # AN  = Accession Number (database ID)
    # DB  = Database name
    # N1  = Note

    # Title (required)
    title = record.get('T1', '').strip()
    if not title:
        raise ValueError("RIS record missing T1 (title)")

    # Use Normalizer for field normalization
    normalized = Normalizer.normalize({
        'title': title,
        'abstract': record.get('AB', ''),
        'authors': record.get_list('AU'),
        'keywords': record.get_list('KW'),
        'journal': record.get('JF', ''),
        'publisher': record.get('PB', ''),
        'year': record.get('PY', ''),
        'doi': record.get('DO', ''),
        'paper_type': None  # Will be determined by infer_paper_type_ris
    })

    # Extract normalized values
    title = normalized['title']
    abstract = normalized['abstract']
    keywords = normalized['keywords'] or []
    year = normalized['year']
    doi = normalized['doi']
    journal = normalized['journal'] or None
    publisher = normalized['publisher'] or None

    # Authors
    authors = []
    if normalized['authors']:
        for author_str in normalized['authors']:
            # RIS uses "Last, First" format (preserved by Normalizer)
            if ',' in author_str:
                parts = author_str.split(',', 1)
                family_name = parts[0].strip()
                given_name = parts[1].strip() if len(parts) > 1 else None
                full_name = f"{given_name} {family_name}" if given_name else family_name
            else:
                parts = author_str.split()
                if len(parts) > 1:
                    family_name = parts[-1]
                    given_name = ' '.join(parts[:-1])
                else:
                    family_name = author_str
                    given_name = None
                full_name = author_str

            authors.append(Author(
                family_name=family_name,
                given_name=given_name,
                full_name=full_name
            ))

    # Identifiers
    url = record.get('UR', '').strip() or None

    # Volume, Issue, Pages
    volume = record.get('VL', '').strip() or None
    number = record.get('IS', '').strip() or None
    pages = record.get('SP', '').strip() or None

    # Database tracking
    accession_number = record.get('AN', '').strip() or None
    database = record.get('DB', '').strip() or source_database or None

    # ============================================================================
    # Cite Key & Source Key Strategy
    # ============================================================================
    # At load time, both are set to same value (can be transformed later in pipeline)
    # Priority: Accession Number > DOI > Auto-generated hash

    if accession_number:
        # Primary: Use accession number (database-specific, unique)
        source_key = f"ris_an_{accession_number}"
    elif doi:
        # Secondary: Use DOI (persistent but may not exist for all records)
        source_key = f"ris_doi_{doi}"
    else:
        # Tertiary: Auto-generate from title + first author
        hash_input = f"{title}|{authors[0].full_name if authors else ''}"
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        source_key = f"ris_auto_{hash_digest}"

    # At load time, cite_key same as source_key
    # (Downstream pipeline can transform to human-readable form)
    cite_key = source_key

    # Publication type
    pub_type = record.get('TY', 'JOUR')
    paper_type = infer_paper_type_ris(pub_type)

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
        url=url,
        journal=journal,
        publisher=publisher,
        volume=volume,
        number=number,
        pages=pages,
        paper_type=paper_type,
        discovery=discovery,
    )

    return paper


def ris_to_papers(
    ris_string: str,
    discovery: Optional[Discovery] = None,
    source_database: Optional[str] = None,
    discovery_method: Optional[DiscoveryMethod] = None,
) -> List[Paper]:
    """
    Parse RIS string and convert to list of Paper models

    Args:
        ris_string: RIS content as string
        discovery: Optional Discovery object for tracking import
        source_database: Source database name
        discovery_method: How papers were discovered

    Returns:
        List of Paper Pydantic models
    """

    # Build discovery object if parameters provided
    if source_database or discovery_method:
        if discovery is None:
            discovery = Discovery(
                method=discovery_method or DiscoveryMethod.KEYWORD_SEARCH,
                source_database=source_database,
            )
        else:
            if source_database:
                discovery.source_database = source_database
            if discovery_method:
                discovery.method = discovery_method

    # Parse RIS (simple string-based approach for inline parsing)
    records = []
    current_record: Optional[RISRecord] = None

    for line in ris_string.split('\n'):
        line = line.rstrip('\n\r')

        if not line.strip():
            continue

        if ' - ' not in line:
            continue

        parts = line.split(' - ', 1)
        if len(parts) != 2:
            continue

        tag = parts[0].strip()
        value = parts[1].strip()

        if tag == 'TY':
            if current_record:
                records.append(current_record)
            current_record = RISRecord()

        if tag == 'ER':
            if current_record:
                records.append(current_record)
            current_record = None
            continue

        if current_record:
            current_record.add_field(tag, value)

    if current_record:
        records.append(current_record)

    # Convert records to papers
    papers = []
    for record in records:
        try:
            paper = ris_record_to_paper(
                record,
                discovery=discovery,
                source_database=source_database
            )
            papers.append(paper)
        except ValueError as e:
            # Skip invalid records, log error
            print(f"Warning: Skipping invalid RIS record: {e}")
            continue

    return papers


def ris_file_to_papers(
    filepath: str,
    discovery: Optional[Discovery] = None,
    source_database: Optional[str] = None,
    discovery_method: Optional[DiscoveryMethod] = None,
) -> List[Paper]:
    """
    Load RIS file and convert to Paper models

    Args:
        filepath: Path to .ris file
        discovery: Optional Discovery object for tracking import
        source_database: Source database name (ProQuest, Scopus, etc.)
        discovery_method: How papers were discovered

    Returns:
        List of Paper models
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        ris_string = f.read()

    return ris_to_papers(
        ris_string,
        discovery=discovery,
        source_database=source_database,
        discovery_method=discovery_method,
    )


# ============================================================================
# BATCH IMPORT FUNCTIONS
# ============================================================================


def import_ris_files(
    filepaths: List[str],
    discovery: Optional[Discovery] = None,
) -> List[Paper]:
    """
    Import multiple RIS files

    Args:
        filepaths: List of .ris file paths
        discovery: Optional Discovery object for tracking import

    Returns:
        List of all imported Paper models
    """

    all_papers = []

    for filepath in filepaths:
        # Infer source database from filename
        filename = Path(filepath).name.lower()
        if 'proquest' in filename:
            source_database = 'ProQuest'
        elif 'scopus' in filename:
            source_database = 'Scopus'
        elif 'wos' in filename or 'webofscience' in filename:
            source_database = 'Web of Science'
        elif 'mendeley' in filename:
            source_database = 'Mendeley'
        elif 'zotero' in filename:
            source_database = 'Zotero'
        else:
            source_database = 'RIS Import'

        papers = ris_file_to_papers(
            filepath,
            discovery=discovery,
            source_database=source_database,
        )

        all_papers.extend(papers)

    return all_papers
