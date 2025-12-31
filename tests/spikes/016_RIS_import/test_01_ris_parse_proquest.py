"""
Test 01: RIS Parser Prototype - Parse ProQuest Example
Validates RIS file parsing and field extraction from ProQuest export
"""

import json
from pathlib import Path

# Minimal RIS parser prototype
class RISRecord:
    """Represents a single RIS record"""
    
    def __init__(self):
        self.fields = {}
    
    def add_field(self, tag: str, value: str):
        """Add a field to the record. Multi-value fields stored as lists."""
        if tag in self.fields:
            if isinstance(self.fields[tag], list):
                self.fields[tag].append(value)
            else:
                self.fields[tag] = [self.fields[tag], value]
        else:
            self.fields[tag] = value
    
    def get(self, tag: str, default=None):
        """Get field value, handling both single and multi-value fields."""
        return self.fields.get(tag, default)
    
    def get_list(self, tag: str) -> list:
        """Get field as list, even if single value."""
        value = self.fields.get(tag)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]
    
    def __repr__(self):
        return f"RISRecord({len(self.fields)} fields)"


class RISParser:
    """Parse RIS format files"""
    
    @staticmethod
    def parse_file(file_path: str) -> list[RISRecord]:
        """Parse RIS file and return list of records"""
        records = []
        current_record = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # RIS format: TAG - value
                if ' - ' not in line:
                    # Continuation of previous field
                    if current_record and len(records) > 0 or current_record:
                        # Skip malformed lines
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


# Normalization functions (learned from BibTeX implementation)
def normalize_ampersands(text: str | None) -> str | None:
    """Normalize ampersands: replace \\& and &amp; with &"""
    if not text:
        return text
    text = text.replace(r'\&', '&')
    text = text.replace('&amp;', '&')
    return text


def normalize_whitespace(text: str | None) -> str | None:
    """Normalize whitespace: collapse multiple spaces, remove newlines"""
    if not text:
        return text
    import re
    return re.sub(r'\s+', ' ', text).strip()


def parse_authors_ris(authors_list: list[str]) -> list[dict]:
    """
    Parse RIS author list (AU fields are separate lines)
    
    RIS format: AU  - Last, First
    """
    from titlecase import titlecase
    
    parsed = []
    for author_str in authors_list:
        author_str = author_str.strip()
        if not author_str:
            continue
        
        author_str = titlecase(author_str.lower())
        
        # RIS uses "Last, First" format
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
        
        parsed.append({
            'family_name': family_name,
            'given_name': given_name,
            'full_name': full_name
        })
    
    return parsed


def parse_keywords_ris(keywords_list: list[str]) -> list[str]:
    """
    Parse RIS keyword list (KW fields are separate lines in RIS)
    """
    keywords = []
    for kw_str in keywords_list:
        kw_str = kw_str.strip().lower()
        if kw_str:
            keywords.append(kw_str)
    return keywords


def ris_to_dict(record: RISRecord) -> dict:
    """
    Convert RIS record to normalized dictionary
    Maps RIS tags to normalized fields
    
    Special handling for cite_key and source_key:
    - Prefer AN (Accession Number) as primary source_key
    - Fallback to DOI, then auto-generate from title+authors
    - Both cite_key and source_key set to same value at load time
    - Downstream pipeline can transform cite_key separately
    """
    import re
    import hashlib
    from titlecase import titlecase
    
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
    
    paper_dict = {}
    
    # Type
    pub_type = record.get('TY', 'JOUR')
    paper_dict['publication_type'] = pub_type
    
    # Title
    title = record.get('T1', '').strip()
    if title:
        title = titlecase(title.lower())
        title = re.sub(r'[{}]', '', title)
        title = normalize_ampersands(title)
    paper_dict['title'] = title or None
    
    # Abstract
    abstract = record.get('AB', '').strip()
    if abstract:
        abstract = re.sub(r'[{}]', '', abstract)
        abstract = normalize_whitespace(abstract)
        abstract = normalize_ampersands(abstract)
    paper_dict['abstract'] = abstract or None
    
    # Authors
    authors_list = record.get_list('AU')
    paper_dict['authors'] = parse_authors_ris(authors_list)
    
    # Year
    year_str = record.get('PY', '')
    year = None
    if year_str:
        try:
            year = int(year_str)
        except ValueError:
            pass
    paper_dict['year'] = year
    
    # Journal
    journal = record.get('JF', '')
    if journal:
        journal = titlecase(journal.strip().lower())
        journal = normalize_ampersands(journal)
    paper_dict['journal'] = journal or None
    
    # Volume, Issue, Pages
    paper_dict['volume'] = record.get('VL', '').strip() or None
    paper_dict['issue'] = record.get('IS', '').strip() or None
    paper_dict['pages'] = record.get('SP', '').strip() or None
    
    # Keywords
    keywords_list = record.get_list('KW')
    paper_dict['keywords'] = parse_keywords_ris(keywords_list)
    
    # DOI
    doi = record.get('DO', '').strip()
    if doi:
        # Clean up DOI format
        doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
    paper_dict['doi'] = doi or None
    
    # URL
    paper_dict['url'] = record.get('UR', '').strip() or None
    
    # Publisher
    publisher = record.get('PB', '')
    if publisher:
        publisher = titlecase(publisher.strip().lower())
    paper_dict['publisher'] = publisher or None
    
    # Note field (for additional metadata)
    notes = record.get('N1')
    if isinstance(notes, list) and notes:
        notes = ' '.join(notes)
    paper_dict['notes'] = (notes.strip() if isinstance(notes, str) else None) or None
    
    # Database/Source tracking
    paper_dict['database'] = record.get('DB', '').strip() or None
    paper_dict['accession_number'] = record.get('AN', '').strip() or None
    
    # ============================================================================
    # Cite Key & Source Key Strategy
    # ============================================================================
    # At load time, both are set to same value (can be transformed later in pipeline)
    # Priority: Accession Number > DOI > Auto-generated hash
    
    if paper_dict['accession_number']:
        # Primary: Use accession number (database-specific, unique)
        source_key = f"ris_an_{paper_dict['accession_number']}"
    elif paper_dict['doi']:
        # Secondary: Use DOI (persistent but may not exist for all records)
        source_key = f"ris_doi_{paper_dict['doi']}"
    else:
        # Tertiary: Auto-generate from title + first author
        hash_input = f"{paper_dict['title']}|{paper_dict['authors'][0]['full_name'] if paper_dict['authors'] else ''}"
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        source_key = f"ris_auto_{hash_digest}"
    
    # At load time, cite_key same as source_key
    # (Downstream pipeline can transform to human-readable form)
    paper_dict['source_key'] = source_key
    paper_dict['cite_key'] = source_key
    
    return paper_dict


# Test execution
if __name__ == '__main__':
    test_file = Path(__file__).parent / 'ProQuestDocuments-2025-12-31.ris'
    
    print(f"Parsing: {test_file}")
    
    # Parse RIS file
    parser = RISParser()
    records = parser.parse_file(str(test_file))
    
    print(f"✓ Found {len(records)} records\n")
    
    # Extract first 2 records as examples
    for i, record in enumerate(records[:2]):
        print(f"Record {i+1}:")
        paper_data = ris_to_dict(record)
        
        print(f"  Title: {paper_data['title']}")
        print(f"  Source Key: {paper_data['source_key']}")
        print(f"  Cite Key: {paper_data['cite_key']}")
        print(f"  Authors: {len(paper_data['authors'])} authors")
        if paper_data['authors']:
            print(f"    - {paper_data['authors'][0]['full_name']}")
        print(f"  Journal: {paper_data['journal']}")
        print(f"  Year: {paper_data['year']}")
        print(f"  Keywords: {len(paper_data['keywords'])} keywords")
        if paper_data['keywords']:
            print(f"    - {paper_data['keywords'][0]}")
        print(f"  DOI: {paper_data['doi']}")
        print(f"  Accession Number: {paper_data['accession_number']}")
        print(f"  Database: {paper_data['database']}")
        print(f"  Abstract length: {len(paper_data['abstract']) if paper_data['abstract'] else 0} chars")
        print()
    
    # Output statistics
    print("\nFile Statistics:")
    print(f"  Total records: {len(records)}")
    
    # Aggregate field usage
    field_usage = {}
    for record in records:
        for tag in record.fields.keys():
            field_usage[tag] = field_usage.get(tag, 0) + 1
    
    print(f"\n  Field usage (top 10):")
    for tag, count in sorted(field_usage.items(), key=lambda x: -x[1])[:10]:
        print(f"    {tag}: {count} records")
