#!/usr/bin/env python3
"""
BibTeX loader: reads BibTeX files and loads them into PostgreSQL.

This module provides two main classes:
1. BibtexReader: Parses BibTeX files into structured data
2. PostgreSQLLoader: Loads parsed papers into PostgreSQL

Usage:
    reader = BibtexReader(filepath)
    papers = reader.parse()
    
    loader = PostgreSQLLoader(connection_string)
    loader.load_papers(papers)
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2.extras import Json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Author:
    """Represents an author in BibTeX format."""
    last_name: str
    first_name: str
    initials: Optional[str] = None
    order: int = 0

    def to_dict(self):
        """Convert to dictionary for JSON storage."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Paper:
    """Represents a paper from BibTeX."""
    citekey: str
    title: Optional[str] = None
    authors: Optional[List[Dict[str, Any]]] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    journal_iso: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    publisher: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    keywords_extra: Optional[List[str]] = None
    paper_type: Optional[str] = None
    source_details: Optional[Dict[str, Any]] = None
    title_details: Optional[Dict[str, Any]] = None
    
    # Extra fields that don't map directly
    raw_data: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        data = {
            'citekey': self.citekey,
            'title': self.title,
            'authors': self.authors,
            'year': self.year,
            'journal': self.journal,
            'journal_iso': self.journal_iso,
            'volume': self.volume,
            'issue': self.issue,
            'pages': self.pages,
            'doi': self.doi,
            'publisher': self.publisher,
            'abstract': self.abstract,
            'keywords': self.keywords,
            'keywords_extra': self.keywords_extra,
            'paper_type': self.paper_type,
            'source_details': self.source_details,
            'title_details': self.title_details,
        }
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


class BibtexReader:
    """Reads and parses BibTeX files into structured Paper objects."""

    # BibTeX field mappings to Paper attributes
    FIELD_MAPPINGS = {
        'title': 'title',
        'author': 'authors',
        'year': 'year',
        'journal': 'journal',
        'journal-iso': 'journal_iso',
        'volume': 'volume',
        'number': 'issue',
        'pages': 'pages',
        'pages-range': 'pages',
        'doi': 'doi',
        'publisher': 'publisher',
        'abstract': 'abstract',
        'keywords': 'keywords',
        'keywords-plus': 'keywords',
        'type': 'paper_type',
    }

    def __init__(self, filepath: str):
        """Initialize the reader with a bibtex file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"BibTeX file not found: {filepath}")
        logger.info(f"Initialized BibtexReader with {filepath}")

    def parse(self) -> List[Paper]:
        """Parse the BibTeX file and return a list of Paper objects."""
        papers = []
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into entries using regex
        entries = self._extract_entries(content)
        logger.info(f"Found {len(entries)} BibTeX entries")
        
        for entry in entries:
            try:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(papers)} papers")
        return papers

    def _extract_entries(self, content: str) -> List[str]:
        """Extract individual BibTeX entries from the content."""
        # Match @type{...} patterns, handling nested braces
        entries = []
        pattern = r'@\w+\s*\{'
        
        for match in re.finditer(pattern, content, re.IGNORECASE):
            start = match.start()
            # Find matching closing brace
            brace_count = 0
            pos = match.end() - 1
            
            while pos < len(content):
                if content[pos] == '{' and (pos == 0 or content[pos-1] != '\\'):
                    brace_count += 1
                elif content[pos] == '}' and (pos == 0 or content[pos-1] != '\\'):
                    brace_count -= 1
                    if brace_count == 0:
                        entries.append(content[start:pos+1])
                        break
                pos += 1
        
        return entries

    def _parse_entry(self, entry: str) -> Optional[Paper]:
        """Parse a single BibTeX entry into a Paper object."""
        # Extract entry type and citekey
        match = re.match(r'@(\w+)\s*\{\s*([^,]+)', entry, re.IGNORECASE)
        if not match:
            logger.debug(f"Could not extract entry type and citekey from: {entry[:100]}")
            return None
        
        entry_type = match.group(1).lower()
        citekey = match.group(2).strip()
        
        # Skip BibDesk metadata entries (Static Groups, Smart Groups)
        if entry_type in ('bibdesk static groups', 'bibdesk smart groups'):
            logger.debug(f"Skipping BibDesk metadata entry: {citekey}")
            return None
        
        # Parse fields
        fields = self._parse_fields(entry)
        
        # Create Paper object
        paper = Paper(citekey=citekey, paper_type=entry_type, raw_data=fields)
        
        # Handle keywords separately to support both keywords and keywords-plus
        keywords_str = fields.get('keywords') or fields.get('keyword')
        keywords_plus_str = fields.get('keywords-plus')
        
        if keywords_str or keywords_plus_str:
            paper.keywords, paper.keywords_extra = self._parse_keywords_dual(
                keywords_str, 
                keywords_plus_str
            )
        
        # Map fields to paper attributes
        for bibtex_field, value in fields.items():
            bibtex_field_lower = bibtex_field.lower()
            
            # Skip keywords fields (already handled above)
            if bibtex_field_lower in ('keywords', 'keywords-plus', 'keyword', 'keywords-plus'):
                continue
            
            if bibtex_field_lower == 'author':
                paper.authors = self._parse_authors(value)
            elif bibtex_field_lower == 'year':
                try:
                    paper.year = int(value)
                except (ValueError, TypeError):
                    logger.debug(f"Could not parse year: {value}")
            elif bibtex_field_lower in self.FIELD_MAPPINGS:
                attr = self.FIELD_MAPPINGS[bibtex_field_lower]
                setattr(paper, attr, value)
        
        # Store extra source details
        source_fields = [
            'address', 'affiliation', 'affiliations', 'doc-delivery-number',
            'earlyaccessdate', 'eissn', 'issn', 'funding-acknowledgement',
            'language', 'unique-id', 'web-of-science-categories',
        ]
        paper.source_details = {
            k: fields.get(k) for k in source_fields if k in fields
        }
        
        return paper

    def _parse_fields(self, entry: str) -> Dict[str, str]:
        """Extract all fields from a BibTeX entry."""
        fields = {}
        
        # Remove entry header and closing brace
        content = re.sub(r'^@\w+\s*\{[^,]*,', '', entry, flags=re.IGNORECASE)
        content = content.rstrip('}').strip()
        
        # Parse field=value pairs, handling nested braces and multiline values
        pos = 0
        while pos < len(content):
            # Skip whitespace
            while pos < len(content) and content[pos].isspace():
                pos += 1
            
            if pos >= len(content):
                break
            
            # Find field name
            match = re.match(r'(\w+(?:-\w+)*)\s*=', content[pos:])
            if not match:
                pos += 1
                continue
            
            field_name = match.group(1)
            pos += len(match.group(0))
            
            # Skip whitespace after =
            while pos < len(content) and content[pos].isspace():
                pos += 1
            
            # Extract value (handle braces and quotes)
            value_start = pos
            if pos < len(content) and content[pos] == '{':
                # Brace-delimited value
                brace_count = 0
                while pos < len(content):
                    if content[pos] == '{':
                        brace_count += 1
                    elif content[pos] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            value = content[value_start+1:pos]
                            pos += 1
                            break
                    pos += 1
            elif pos < len(content) and content[pos] == '"':
                # Quote-delimited value
                pos += 1
                while pos < len(content) and content[pos] != '"':
                    if content[pos] == '\\':
                        pos += 2
                    else:
                        pos += 1
                value = content[value_start+1:pos]
                pos += 1
            else:
                # Unquoted value (ends at comma or closing brace)
                while pos < len(content) and content[pos] not in ',}':
                    pos += 1
                value = content[value_start:pos]
            
            # Clean up value
            value = value.strip()
            if value:
                fields[field_name] = value
            
            # Skip comma
            while pos < len(content) and content[pos] in ', \t\n':
                pos += 1
        
        return fields

    def _parse_authors(self, author_str: str) -> Optional[List[Dict[str, Any]]]:
        """Parse author field (format: 'First Last and First Last and ...')."""
        if not author_str:
            return None
        
        authors = []
        # Split by ' and '
        author_parts = re.split(r'\s+and\s+', author_str, flags=re.IGNORECASE)
        
        for order, part in enumerate(author_parts):
            part = part.strip()
            if not part:
                continue
            
            # Try to parse name: "First Middle Last" or "Last, First Middle"
            if ',' in part:
                # Format: "Last, First Middle"
                parts = [p.strip() for p in part.split(',')]
                last_name = parts[0]
                first_name = parts[1] if len(parts) > 1 else ''
            else:
                # Format: "First Middle Last"
                parts = part.split()
                if len(parts) >= 2:
                    last_name = parts[-1]
                    first_name = ' '.join(parts[:-1])
                elif len(parts) == 1:
                    last_name = parts[0]
                    first_name = ''
                else:
                    continue
            
            # Extract initials from first name
            initials = ''.join([p[0].upper() for p in first_name.split() if p])
            
            author = Author(
                last_name=last_name,
                first_name=first_name,
                initials=initials,
                order=order
            )
            authors.append(author.to_dict())
        
        return authors if authors else None

    def _parse_keywords(self, keywords_str: str) -> Optional[List[str]]:
        """Parse keywords field into a list, cleaning quotes, BibTeX sequences, and HTML entities."""
        if not keywords_str:
            return None
        
        # Split by semicolon or comma
        keywords = re.split(r'[;,]', keywords_str)
        
        # Clean each keyword: strip whitespace and remove quotes
        cleaned = []
        for k in keywords:
            k = k.strip()
            if not k:
                continue
            
            # Remove doubled quotes like `` or '' (do this first)
            k = re.sub(r'``|\'\'', '', k)
            
            # Remove backtick-space-s pattern (` s -> 's)
            k = re.sub(r'`\s+s\b', "'s", k)
            k = re.sub(r'`', '', k)  # Remove any remaining backticks
            
            # Remove surrounding quotes (both single and double)
            k = k.strip('\"\\\"').strip()
            
            # Remove leading/trailing curly braces (common in BibTeX)
            k = k.strip('{}').strip()
            
            # Remove BibTeX special character sequences like \~{} or \'{} 
            k = re.sub(r'\\[`\'"^~]{[^}]*}', '', k)  # \~{...}, \'{...}, etc.
            k = re.sub(r'\\[`\'"^~]', '', k)  # \~, \', etc. without braces
            k = re.sub(r'\\&', '&', k)  # \& -> &
            k = re.sub(r'~{}', '', k)  # Remove ~{} sequences
            k = re.sub(r'{}\s*', '', k)  # Remove {} sequences
            k = re.sub(r'\{\}', '', k)  # Remove {} anywhere (already done but be thorough)
            
            # Remove HTML entities (like &eacute;, &amp;, etc.) - including incomplete ones
            k = re.sub(r'&\w*;?', '', k)  # Remove &...;
            
            # Remove backslash escapes
            k = re.sub(r'\\(?=[A-Z])', '', k)  # Remove \A -> A
            k = re.sub(r'\\', '', k)  # Remove any remaining backslashes
            
            # Clean up any remaining whitespace (including new spaces from regex removals)
            k = re.sub(r'\s+', ' ', k).strip()
            
            if k:  # Only add if not empty after cleaning
                cleaned.append(k)
        
        return cleaned if cleaned else None
    
    def _parse_keywords_dual(self, keywords_str: str, keywords_plus_str: str) -> tuple:
        """Parse both keywords and keywords-plus fields, keeping them separate.
        
        Args:
            keywords_str: Regular keywords field (author-provided)
            keywords_plus_str: Keywords-plus field (from Web of Science, etc.)
        
        Returns:
            Tuple of (keywords list, keywords_extra list)
        """
        keywords = self._parse_keywords(keywords_str) if keywords_str else None
        keywords_extra = self._parse_keywords(keywords_plus_str) if keywords_plus_str else None
        
        # Remove duplicates between the two lists (keep in keywords, remove from extra)
        if keywords and keywords_extra:
            keywords_lower = {k.lower() for k in keywords}
            keywords_extra = [k for k in keywords_extra if k.lower() not in keywords_lower]
            keywords_extra = keywords_extra if keywords_extra else None
        
        return keywords, keywords_extra


class PostgreSQLLoader:
    """Loads Paper objects into PostgreSQL database."""

    def __init__(self, connection_string: str):
        """Initialize the loader with PostgreSQL connection string."""
        self.connection_string = connection_string
        self.connection = None
        logger.info(f"Initialized PostgreSQLLoader")

    def connect(self):
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(self.connection_string)
            logger.info("Connected to PostgreSQL database")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from PostgreSQL database")

    def load_papers(self, papers: List[Paper]) -> int:
        """Load papers into the database. Returns count of loaded papers."""
        if not self.connection:
            self.connect()
        
        loaded_count = 0
        failed_count = 0
        
        cursor = self.connection.cursor()
        
        try:
            for paper in papers:
                try:
                    if self._insert_paper(cursor, paper):
                        loaded_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert paper {paper.citekey}: {e}")
                    failed_count += 1
                    continue
            
            self.connection.commit()
            logger.info(f"Loaded {loaded_count} papers, {failed_count} failed")
        
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            cursor.close()
        
        return loaded_count

    def _insert_paper(self, cursor, paper: Paper) -> bool:
        """Insert a single paper into the database. Returns True on success."""
        try:
            # Prepare data
            data = paper.to_dict()
            
            # Validate that we have at least a title or abstract to make sense
            if not data.get('title') and not data.get('abstract'):
                logger.debug(f"Skipping paper {paper.citekey}: no title or abstract")
                return False
            
            # Convert lists to PostgreSQL format where needed
            if data.get('authors'):
                if isinstance(data['authors'], list) and isinstance(data['authors'][0], dict):
                    data['authors'] = Json(data['authors'])
            
            if data.get('keywords'):
                # Ensure it's a list for PostgreSQL array
                if isinstance(data['keywords'], list):
                    pass  # Already a list
                else:
                    data['keywords'] = [data['keywords']]
            
            if data.get('keywords_extra'):
                # Ensure it's a list for PostgreSQL array
                if isinstance(data['keywords_extra'], list):
                    pass  # Already a list
                else:
                    data['keywords_extra'] = [data['keywords_extra']]
            
            if data.get('source_details'):
                if isinstance(data['source_details'], dict):
                    data['source_details'] = Json(data['source_details'])
            
            if data.get('title_details'):
                if isinstance(data['title_details'], dict):
                    data['title_details'] = Json(data['title_details'])
            
            # Build INSERT query
            columns = list(data.keys())
            placeholders = [f'%s' for _ in columns]
            values = [data[col] for col in columns]
            
            query = f"""
                INSERT INTO papers ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """
            
            cursor.execute(query, values)
            logger.debug(f"Inserted paper: {paper.citekey}")
            return True
        
        except Exception as e:
            logger.warning(f"Insert error for {paper.citekey}: {e}")
            return False


def main():
    """Main entry point for testing."""
    import sys
    import os
    
    # Get bibtex file path from command line or use default
    if len(sys.argv) > 1:
        bibtex_file = sys.argv[1]
    else:
        # Try to find a bibtex file in the current directory
        bibtex_files = list(Path('.').glob('*.bib'))
        if not bibtex_files:
            print("Usage: python load_bibtex.py <bibtex_file>")
            print("   or place a .bib file in the current directory")
            sys.exit(1)
        bibtex_file = str(bibtex_files[0])
    
    # Get database connection string
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'
    )
    
    logger.info(f"Starting BibTeX loading from {bibtex_file}")
    
    # Read BibTeX file
    reader = BibtexReader(bibtex_file)
    papers = reader.parse()
    
    if not papers:
        logger.error("No papers parsed from BibTeX file")
        sys.exit(1)
    
    # Load into database
    loader = PostgreSQLLoader(connection_string)
    try:
        loader.connect()
        count = loader.load_papers(papers)
        logger.info(f"Successfully loaded {count} papers")
    finally:
        loader.disconnect()


if __name__ == '__main__':
    main()
