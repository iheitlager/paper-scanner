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
import argparse
import sys
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
from colorama import Fore, Back, Style, init

# Initialize colorama for cross-platform color support
init(autoreset=True)

# Configure logging - will be set based on verbose flag
logger = logging.getLogger(__name__)
verbose_mode = False


def setup_logging(verbose: bool):
    """Configure logging based on verbose flag."""
    global verbose_mode
    verbose_mode = verbose
    
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - %(levelname)s - %(message)s'
        )
        logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - %(levelname)s - %(message)s'
        )
        logger.setLevel(logging.WARNING)


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


class BibtexTranslator:
    """Base class for translating BibTeX entries to Paper objects."""
    
    def translate(self, citekey: str, entry_type: str, fields: Dict[str, str]) -> Optional[Paper]:
        """Translate fields to a Paper object. Override in subclasses."""
        raise NotImplementedError
    
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


class WOSTranslator(BibtexTranslator):
    """Translator for Web of Science BibTeX entries."""
    
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
        'keywords-plus': 'keywords_extra',
        'type': 'paper_type',
    }
    
    SOURCE_DETAIL_FIELDS = {
        'address', 'affiliation', 'affiliations', 'doc-delivery-number',
        'earlyaccessdate', 'eissn', 'issn', 'funding-acknowledgement',
        'language', 'unique-id', 'web-of-science-categories', 'web-of-science-index'
    }
    
    def translate(self, citekey: str, entry_type: str, fields: Dict[str, str]) -> Optional[Paper]:
        """Translate WOS BibTeX fields to a Paper object."""
        paper = Paper(citekey=citekey, paper_type=entry_type, raw_data=fields)
        paper.source_type = 'Web of Science'
        
        # Handle keywords separately: keywords and keywords-plus
        keywords_str = fields.get('keywords')
        keywords_plus_str = fields.get('keywords-plus')
        
        if keywords_str or keywords_plus_str:
            paper.keywords = self._parse_keywords(keywords_str) if keywords_str else None
            paper.keywords_extra = self._parse_keywords(keywords_plus_str) if keywords_plus_str else None
        
        # Map fields to paper attributes
        for bibtex_field, value in fields.items():
            bibtex_field_lower = bibtex_field.lower()
            
            # Skip keywords fields (already handled above)
            if bibtex_field_lower in ('keywords', 'keywords-plus', 'keyword'):
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
        
        # Store extra source details with source identifier
        paper.source_details = {
            'source': 'Web of Science',
            **{k: fields.get(k) for k in self.SOURCE_DETAIL_FIELDS if k in fields}
        }
        
        return paper


class ScopusTranslator(BibtexTranslator):
    """Translator for Scopus BibTeX entries."""
    
    FIELD_MAPPINGS = {
        'title': 'title',
        'author': 'authors',
        'year': 'year',
        'journal': 'journal',
        'volume': 'volume',
        'number': 'issue',
        'pages': 'pages',
        'doi': 'doi',
        'publisher': 'publisher',
        'abstract': 'abstract',
        'type': 'paper_type',
    }
    
    SOURCE_DETAIL_FIELDS = {
        'url', 'source', 'publication_stage', 'note'
    }
    
    def translate(self, citekey: str, entry_type: str, fields: Dict[str, str]) -> Optional[Paper]:
        """Translate Scopus BibTeX fields to a Paper object."""
        paper = Paper(citekey=citekey, paper_type=entry_type, raw_data=fields)
        paper.source_type = 'Scopus'
        
        # Handle keywords: Scopus uses author_keywords and keywords separately
        author_keywords_str = fields.get('author_keywords')
        keywords_str = fields.get('keywords')
        
        if author_keywords_str or keywords_str:
            paper.keywords = self._parse_keywords(author_keywords_str) if author_keywords_str else None
            paper.keywords_extra = self._parse_keywords(keywords_str) if keywords_str else None
        
        # Map fields to paper attributes
        for bibtex_field, value in fields.items():
            bibtex_field_lower = bibtex_field.lower()
            
            # Skip keywords fields (already handled above)
            if bibtex_field_lower in ('author_keywords', 'keywords', 'keyword'):
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
        
        # Store extra source details with source identifier
        paper.source_details = {
            'source': 'Scopus',
            **{k: fields.get(k) for k in self.SOURCE_DETAIL_FIELDS if k in fields}
        }
        
        return paper


class IEEETranslator(BibtexTranslator):
    """Translator for IEEE Xplore BibTeX entries."""
    
    FIELD_MAPPINGS = {
        'title': 'title',
        'author': 'authors',
        'year': 'year',
        'journal': 'journal',
        'booktitle': 'journal',  # IEEE uses booktitle for conference proceedings
        'volume': 'volume',
        'number': 'issue',
        'pages': 'pages',
        'doi': 'doi',
        'publisher': 'publisher',
        'abstract': 'abstract',
        'keywords': 'keywords',
        'type': 'paper_type',
    }
    
    SOURCE_DETAIL_FIELDS = {
        'url', 'issn', 'isbn', 'month', 'note', 'series'
    }
    
    def translate(self, citekey: str, entry_type: str, fields: Dict[str, str]) -> Optional[Paper]:
        """Translate IEEE BibTeX fields to a Paper object."""
        paper = Paper(citekey=citekey, paper_type=entry_type, raw_data=fields)
        paper.source_type = 'IEEE Xplore'
        
        # Handle keywords: IEEE uses semicolon-separated keywords
        keywords_str = fields.get('keywords')
        
        if keywords_str:
            paper.keywords = self._parse_keywords(keywords_str)
        
        # Map fields to paper attributes
        for bibtex_field, value in fields.items():
            bibtex_field_lower = bibtex_field.lower()
            
            # Skip keywords fields (already handled above)
            if bibtex_field_lower in ('keywords', 'keyword'):
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
        
        # Store extra source details with source identifier
        paper.source_details = {
            'source': 'IEEE Xplore',
            **{k: fields.get(k) for k in self.SOURCE_DETAIL_FIELDS if k in fields}
        }
        
        return paper


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
    source_type: Optional[str] = None  # Source identifier (e.g., 'Web of Science', 'Scopus', 'IEEE Xplore')
    source_details: Optional[Dict[str, Any]] = None
    title_details: Optional[Dict[str, Any]] = None
    
    # Extra fields that don't map directly
    raw_data: Optional[Dict[str, str]] = None
    _is_bibdesk_metadata: bool = False  # Flag for BibDesk metadata entries

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion.
        
        Generates source_key combining source_type and citekey.
        This key is used to detect and reject duplicate papers from the same source.
        """
        source = self.source_type or (self.source_details.get('source', 'Unknown') if self.source_details else 'Unknown')
        source_key = f"{source}:{self.citekey}"
        
        data = {
            'source_key': source_key,
            'source_type': self.source_type,
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
            'paper_type': self.paper_type.lower() if self.paper_type else None,  # Normalize to lowercase
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
    
    # Field mappings for auto-detection of source
    WOS_INDICATOR_FIELDS = {'web-of-science-index', 'web-of-science-categories'}
    SCOPUS_INDICATOR_FIELDS = {'source', 'author_keywords'}
    IEEE_INDICATOR_FIELDS = {'issn', 'booktitle', 'month'}  # IEEE uses these

    def __init__(self, filepath: str):
        """Initialize the reader with a bibtex file path."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"BibTeX file not found: {filepath}")
        logger.info(f"Initialized BibtexReader with {filepath}")

    def parse(self) -> List[Paper]:
        """Parse the BibTeX file and return a list of Paper objects."""
        papers = []
        seen_citekeys = {}  # Track citekeys to make duplicates unique
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into entries using regex
        entries = self._extract_entries(content)
        logger.info(f"Found {len(entries)} BibTeX entries")
        
        for entry in entries:
            try:
                paper = self._parse_entry(entry)
                if paper:
                    # Handle duplicate citekeys within the same file
                    original_citekey = paper.citekey
                    if original_citekey in seen_citekeys:
                        # This is a duplicate citekey, make it unique
                        count = seen_citekeys[original_citekey]
                        seen_citekeys[original_citekey] += 1
                        # Append suffix like _2, _3, etc.
                        paper.citekey = f"{original_citekey}_{count}"
                        logger.debug(f"Made duplicate citekey unique: {original_citekey} -> {paper.citekey}")
                    else:
                        seen_citekeys[original_citekey] = 2  # Next duplicate will be _2
                    
                    papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(papers)} papers")
        return papers
    
    def _detect_source(self, fields: Dict[str, str], citekey: str) -> str:
        """Detect paper source (WOS, Scopus, or IEEE) based on fields and citekey."""
        fields_lower = {k.lower() for k in fields.keys()}
        
        # Check for explicit source field (Scopus)
        if 'source' in fields_lower and 'scopus' in fields.get('source', '').lower():
            return 'scopus'
        
        # Check for Scopus-specific fields
        if any(field in fields_lower for field in self.SCOPUS_INDICATOR_FIELDS):
            return 'scopus'
        
        # Check for WOS-specific fields
        if any(field in fields_lower for field in self.WOS_INDICATOR_FIELDS):
            return 'wos'
        
        # Check citekey pattern: IEEE uses fully numeric keys
        if citekey.isdigit():
            return 'ieee'
        
        # Check for WOS citekey pattern
        if citekey.startswith('WOS:'):
            return 'wos'
        
        # Check for IEEE-specific field combinations
        if 'booktitle' in fields_lower and ('issn' in fields_lower or 'month' in fields_lower):
            return 'ieee'
        
        # Default to WOS for backward compatibility
        return 'wos'

    def _extract_entries(self, content: str) -> List[str]:
        """Extract individual BibTeX entries from the content."""
        # Match @type{...} patterns, handling nested braces
        # Pattern allows entry types with spaces (e.g., "BibDesk Static Groups")
        # Pattern matches @ that is either at start of line or preceded by closing brace
        entries = []
        pattern = r'(?:^|\})\s*@([^\{]+)\{'
        
        for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
            # Find the position of @ symbol
            match_start = match.start()
            # Skip back past any preceding } or whitespace to find @ position
            at_pos = match.start() + (match.group(0).index('@') if '@' in match.group(0) else 0)
            
            # Find matching closing brace starting from the opening brace
            brace_count = 0
            pos = match.end() - 1  # Start from the opening brace
            
            while pos < len(content):
                if content[pos] == '{' and (pos == 0 or content[pos-1] != '\\'):
                    brace_count += 1
                elif content[pos] == '}' and (pos == 0 or content[pos-1] != '\\'):
                    brace_count -= 1
                    if brace_count == 0:
                        entries.append(content[at_pos:pos+1])
                        break
                pos += 1
        
        return entries

    def _parse_entry(self, entry: str) -> Optional[Paper]:
        """Parse a single BibTeX entry into a Paper object."""
        # Extract entry type and citekey
        # Pattern allows entry types with spaces (e.g., "BibDesk Static Groups")
        # Citekey must not contain comma or newline
        match = re.match(r'@([^\{]+)\{\s*([^,\n}]+)', entry, re.IGNORECASE)
        if not match:
            logger.debug(f"Could not extract entry type and citekey from: {entry[:100]}")
            return None
        
        entry_type = match.group(1).strip().lower()
        citekey = match.group(2).strip()
        
        # Skip BibDesk metadata entries (Static Groups, Smart Groups)
        if entry_type in ('bibdesk static groups', 'bibdesk smart groups'):
            logger.debug(f"Skipping BibDesk metadata entry: {citekey}")
            # Return a special marker that this should be skipped and reported differently
            paper = Paper(citekey=citekey, paper_type=entry_type, raw_data={})
            paper._is_bibdesk_metadata = True
            return paper
        
        # Parse fields
        fields = self._parse_fields(entry)
        
        # Detect source and use appropriate translator
        source = self._detect_source(fields, citekey)
        
        if source == 'scopus':
            translator = ScopusTranslator()
        elif source == 'ieee':
            translator = IEEETranslator()
        else:
            translator = WOSTranslator()
        
        paper = translator.translate(citekey, entry_type, fields)
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
            value = None  # Initialize value to handle all code paths
            
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
                # If loop ended without finding closing brace, use remaining content
                if value is None:
                    value = content[value_start+1:pos]
            elif pos < len(content) and content[pos] == '"':
                # Quote-delimited value
                pos += 1
                while pos < len(content) and content[pos] != '"':
                    if content[pos] == '\\':
                        pos += 2
                    else:
                        pos += 1
                value = content[value_start+1:pos]
                if pos < len(content):
                    pos += 1
            else:
                # Unquoted value (ends at comma or closing brace)
                while pos < len(content) and content[pos] not in ',}':
                    pos += 1
                value = content[value_start:pos]
            
            # Clean up value
            if value is not None:
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


class PostgreSQLLoader:
    """Loads Paper objects into PostgreSQL database."""

    def __init__(self, connection_string: str):
        """Initialize the loader with PostgreSQL connection string."""
        self.connection_string = connection_string
        self.connection = None
        self.seen_source_keys = set()  # Track source_keys to reject duplicates
        self.failed_papers = []  # Track failed papers for reporting
        self.sources_loaded = {}  # Track loaded papers by source
        logger.info(f"Initialized PostgreSQLLoader")

    def connect(self):
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(self.connection_string)
            logger.info("Connected to PostgreSQL database")
            # Load existing source_keys from database to avoid duplicates
            cursor = self.connection.cursor()
            cursor.execute("SELECT source_key FROM papers WHERE source_key IS NOT NULL")
            self.seen_source_keys = {row[0] for row in cursor.fetchall()}
            cursor.close()
            logger.info(f"Loaded {len(self.seen_source_keys)} existing source_keys from database")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from PostgreSQL database")

    def load_papers(self, papers: List[Paper]) -> tuple:
        """Load papers into the database. Returns (loaded_count, rejected_count, failed_count, failed_papers_list, sources_dict, skipped_metadata_count)."""
        loaded_count = 0
        rejected_count = 0
        failed_count = 0
        skipped_metadata_count = 0
        rejected_keys = []
        self.failed_papers = []
        self.sources_loaded = {}
        
        try:
            for paper in papers:
                # Check if this is BibDesk metadata - skip and don't count as failure
                if getattr(paper, '_is_bibdesk_metadata', False):
                    logger.debug(f"Skipping BibDesk metadata: {paper.citekey}")
                    skipped_metadata_count += 1
                    continue
                
                # Get source_key for duplicate check
                paper_data = paper.to_dict()
                source_key = paper_data.get('source_key')
                source = paper_data.get('source_details', {}).get('source', 'Unknown') if isinstance(paper_data.get('source_details'), dict) else 'Unknown'
                
                # Check if source_key already exists (duplicate)
                if source_key and source_key in self.seen_source_keys:
                    logger.warning(f"Rejecting duplicate: {paper.citekey} (source_key: {source_key})")
                    rejected_keys.append(source_key)
                    rejected_count += 1
                    continue
                
                # Create fresh connection for each paper to avoid transaction abort cascades
                if not self.connection:
                    self.connect()
                
                cursor = self.connection.cursor()
                try:
                    if self._insert_paper(cursor, paper):
                        self.connection.commit()
                        # Track this source_key to prevent future duplicates
                        if source_key:
                            self.seen_source_keys.add(source_key)
                        loaded_count += 1
                        # Track source
                        self.sources_loaded[source] = self.sources_loaded.get(source, 0) + 1
                    else:
                        failed_count += 1
                        self.failed_papers.append((paper.citekey, "Skipped: no title or abstract"))
                except Exception as e:
                    # Rollback and close connection if there was an error
                    try:
                        self.connection.rollback()
                    except Exception:
                        pass  # Connection might already be in bad state
                    
                    # Close and reset connection to avoid "transaction aborted" cascade
                    try:
                        self.connection.close()
                    except Exception:
                        pass
                    self.connection = None
                    
                    error_msg = str(e)
                    logger.warning(f"Failed to insert paper {paper.citekey}: {error_msg}")
                    self.failed_papers.append((paper.citekey, error_msg))
                    failed_count += 1
                finally:
                    cursor.close()
            
            logger.info(f"Loaded {loaded_count} papers, {rejected_count} rejected (duplicates), {failed_count} failed, {skipped_metadata_count} skipped (BibDesk metadata)")
        
        except Exception as e:
            logger.error(f"Fatal error during load: {e}")
            raise
        finally:
            # Clean up connection
            if self.connection:
                try:
                    self.connection.close()
                except Exception:
                    pass
                self.connection = None
        
        return loaded_count, rejected_count, failed_count, self.failed_papers, self.sources_loaded, skipped_metadata_count

    def _insert_paper(self, cursor, paper: Paper) -> bool:
        """Insert a single paper into the database. Returns True on success."""
        try:
            # Prepare data
            data = paper.to_dict()
            
            # Validate that we have at least a title or abstract to make sense
            if not data.get('title') and not data.get('abstract'):
                logger.debug(f"Skipping paper {paper.citekey}: no title or abstract")
                return False
            
            # Define field size limits (must match schema)
            FIELD_LIMITS = {
                'volume': 50,
                'issue': 100,  # Updated schema allows 100 chars
                'pages': 100,
                'journal_iso': 500,
                'doi': 255,
                'publisher': 255,
                'paper_type': 50,
            }
            
            # Truncate fields that exceed their size limits
            for field, max_len in FIELD_LIMITS.items():
                if field in data and isinstance(data[field], str):
                    if len(data[field]) > max_len:
                        original = data[field]
                        data[field] = data[field][:max_len]
                        logger.debug(f"Truncated {field} for {paper.citekey}: {len(original)} -> {max_len} chars")
            
            # Clean up paper_type: remove "; Early Access" suffix (WOS specific) and normalize to lowercase
            if 'paper_type' in data and isinstance(data['paper_type'], str):
                # Remove "; Early Access" suffix (case-insensitive)
                paper_type_lower = data['paper_type'].lower()
                if '; early access' in paper_type_lower:
                    # Find and remove the suffix while preserving the base type
                    data['paper_type'] = data['paper_type'][:data['paper_type'].lower().index('; early access')].strip()
                    logger.debug(f"Cleaned paper_type for {paper.citekey}: removed 'Early Access' suffix")
                # Ensure lowercase normalization
                data['paper_type'] = data['paper_type'].lower()
                logger.debug(f"Normalized paper_type for {paper.citekey}: {data['paper_type']}")
            
            # Convert complex types to PostgreSQL format
            # Authors: list of dicts -> JSON
            if 'authors' in data and isinstance(data['authors'], list):
                data['authors'] = Json(data['authors'])
            
            # Keywords: ensure list for PostgreSQL array type
            if 'keywords' in data and data['keywords'] is not None:
                if not isinstance(data['keywords'], list):
                    data['keywords'] = [data['keywords']]
            
            # Keywords extra: ensure list for PostgreSQL array type
            if 'keywords_extra' in data and data['keywords_extra'] is not None:
                if not isinstance(data['keywords_extra'], list):
                    data['keywords_extra'] = [data['keywords_extra']]
            
            # Source details: dict -> JSON (including empty dicts!)
            if 'source_details' in data and isinstance(data['source_details'], dict):
                data['source_details'] = Json(data['source_details'])
            
            # Title details: dict -> JSON (including empty dicts!)
            if 'title_details' in data and isinstance(data['title_details'], dict):
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


def setup_parser():
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='Load BibTeX files into PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python load_bibtex.py papers.bib --list
    python load_bibtex.py papers.bib --sample 10
    python load_bibtex.py papers.bib
    python load_bibtex.py papers.bib --db postgresql://user:pass@host/db
        """
    )
    
    parser.add_argument(
        'bibtex_file',
        help='Path to BibTeX file'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List papers without loading to database'
    )
    
    parser.add_argument(
        '--sample',
        type=int,
        default=None,
        help='Load only first N papers'
    )
    
    parser.add_argument(
        '--db',
        default=None,
        help='Database connection string (default: env var DATABASE_URL)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--try',
        action='store_true',
        dest='try_mode',
        help='Dry run: read and validate papers without loading to database'
    )
    
    return parser


def list_papers(papers, limit=None):
    """Display papers in a table format."""
    print("\n" + "="*100)
    print(f"{Fore.CYAN}{Style.BRIGHT}PAPERS{Style.RESET_ALL}")
    print("="*100 + "\n")
    
    papers_to_show = papers[:limit] if limit else papers
    
    for i, paper in enumerate(papers_to_show, 1):
        print(f"{Fore.YELLOW}{i}.{Style.RESET_ALL} {Fore.CYAN}Citekey:{Style.RESET_ALL} {paper.citekey}")
        if paper.title:
            print(f"   {Fore.GREEN}Title:{Style.RESET_ALL} {paper.title[:80]}")
        if paper.authors:
            author_names = ', '.join([
                f"{a.get('first_name', '')} {a.get('last_name', '')}"
                for a in paper.authors[:3]
            ])
            if len(paper.authors) > 3:
                author_names += f" (+{len(paper.authors)-3} more)"
            print(f"   {Fore.GREEN}Authors:{Style.RESET_ALL} {author_names}")
        if paper.year:
            print(f"   {Fore.GREEN}Year:{Style.RESET_ALL} {paper.year}")
        if paper.journal:
            print(f"   {Fore.GREEN}Journal:{Style.RESET_ALL} {paper.journal}")
        if paper.doi:
            print(f"   {Fore.GREEN}DOI:{Style.RESET_ALL} {paper.doi}")
        print()
    
    if limit and len(papers) > limit:
        print(f"... and {Fore.YELLOW}{len(papers) - limit}{Style.RESET_ALL} more papers\n")


def validate_papers(papers, sample_limit=None):
    """Validate papers without loading to database. Returns validation summary."""
    if sample_limit:
        papers = papers[:sample_limit]
    
    print(f"\n{Fore.BLUE}{Style.BRIGHT}Validating {len(papers)} papers...{Style.RESET_ALL}\n")
    
    stats = {
        'total': len(papers),
        'valid': 0,
        'errors': [],
        'skipped_metadata': 0
    }
    
    # Group by source
    sources = {'wos': 0, 'scopus': 0, 'ieee': 0, 'unknown': 0}
    
    # Create a detector for source detection
    reader = BibtexReader.__new__(BibtexReader)
    reader.WOS_INDICATOR_FIELDS = BibtexReader.WOS_INDICATOR_FIELDS
    reader.SCOPUS_INDICATOR_FIELDS = BibtexReader.SCOPUS_INDICATOR_FIELDS
    reader.IEEE_INDICATOR_FIELDS = BibtexReader.IEEE_INDICATOR_FIELDS
    
    for i, paper in enumerate(papers, 1):
        # Skip BibDesk metadata entries
        if getattr(paper, '_is_bibdesk_metadata', False):
            stats['skipped_metadata'] += 1
            continue
        
        try:
            data = paper.to_dict()
            
            # Check critical fields
            if not data.get('title') and not data.get('abstract'):
                stats['errors'].append(f"  {i}. {paper.citekey}: Missing title and abstract")
                continue
            
            # Detect source using the same logic as the reader
            if paper.raw_data:
                source = reader._detect_source(paper.raw_data, paper.citekey)
                sources[source] += 1
            else:
                sources['unknown'] += 1
            
            stats['valid'] += 1
        
        except Exception as e:
            stats['errors'].append(f"  {i}. {paper.citekey}: {str(e)}")
    
    # Print summary
    print("="*80)
    print(f"{Fore.CYAN}{Style.BRIGHT}VALIDATION SUMMARY{Style.RESET_ALL}")
    print("="*80)
    print(f"\n{Fore.GREEN}Total papers:{Style.RESET_ALL}     {stats['total']}")
    print(f"{Fore.GREEN}Valid papers:{Style.RESET_ALL}     {Fore.LIGHTGREEN_EX}{stats['valid']}{Style.RESET_ALL}")
    
    if stats['skipped_metadata'] > 0:
        print(f"{Fore.CYAN}Skipped (metadata):{Style.RESET_ALL} {stats['skipped_metadata']}")
    
    if stats['errors']:
        print(f"{Fore.RED}Invalid papers:{Style.RESET_ALL}   {len(stats['errors'])}")
    else:
        print(f"{Fore.LIGHTGREEN_EX}Invalid papers:{Style.RESET_ALL}   {len(stats['errors'])}")
    
    print(f"\n{Fore.CYAN}By source:{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}WOS:{Style.RESET_ALL}            {sources['wos']}")
    print(f"  {Fore.YELLOW}Scopus:{Style.RESET_ALL}         {sources['scopus']}")
    print(f"  {Fore.YELLOW}IEEE:{Style.RESET_ALL}           {sources['ieee']}")
    print(f"  {Fore.YELLOW}Unknown:{Style.RESET_ALL}        {sources['unknown']}")
    
    if stats['errors']:
        print(f"\n{Fore.RED}Errors found:{Style.RESET_ALL}")
        for error in stats['errors'][:10]:  # Show first 10 errors
            print(f"{Fore.RED}{error}{Style.RESET_ALL}")
        if len(stats['errors']) > 10:
            print(f"  {Fore.YELLOW}... and {len(stats['errors']) - 10} more errors{Style.RESET_ALL}")
    
    print("\n" + "="*80)
    
    # Return success if no errors (metadata entries don't count as failures)
    return len(stats['errors']) == 0


def main():
    """Main entry point for CLI."""
    parser = setup_parser()
    args = parser.parse_args()
    
    # Configure logging
    setup_logging(args.verbose)
    
    # Validate bibtex file
    bibtex_file = Path(args.bibtex_file)
    if not bibtex_file.exists():
        print(f"{Fore.RED}{Style.BRIGHT}❌ Error: File not found: {bibtex_file}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Read BibTeX file
    print(f"\n{Fore.BLUE}{Style.BRIGHT}Reading BibTeX file:{Style.RESET_ALL} {Fore.CYAN}{bibtex_file}{Style.RESET_ALL}")
    try:
        reader = BibtexReader(str(bibtex_file))
        papers = reader.parse()
        print(f"{Fore.LIGHTGREEN_EX}✓{Style.RESET_ALL} Read {Fore.YELLOW}{len(papers)}{Style.RESET_ALL} papers\n")
    except Exception as e:
        print(f"{Fore.RED}❌ Error reading BibTeX: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    # If --list, just display papers
    if args.list:
        list_papers(papers, limit=args.sample or 5)
        return
    
    # If --try, validate without loading
    if args.try_mode:
        valid = validate_papers(papers, sample_limit=args.sample)
        if valid:
            print(f"\n{Fore.LIGHTGREEN_EX}{Style.BRIGHT}✓ All papers validated successfully!{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠ Some papers have validation issues{Style.RESET_ALL}\n")
        sys.exit(0 if valid else 1)
    
    # Otherwise, load into database
    if args.sample:
        papers = papers[:args.sample]
        print(f"{Fore.BLUE}Loading first {Fore.YELLOW}{len(papers)}{Fore.BLUE} papers into database...{Style.RESET_ALL}")
    else:
        print(f"{Fore.BLUE}Loading {Fore.YELLOW}{len(papers)}{Fore.BLUE} papers into database...{Style.RESET_ALL}")
    
    # Get database connection string
    db_url = args.db or os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb')
    
    loader = PostgreSQLLoader(db_url)
    
    try:
        loader.connect()
        loaded_count, rejected_count, failed_count, failed_papers, sources_loaded, skipped_metadata_count = loader.load_papers(papers)
        
        print(f"\n{Fore.LIGHTGREEN_EX}{Style.BRIGHT}✓ Load complete!{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}Loaded:{Style.RESET_ALL}   {Fore.LIGHTGREEN_EX}{loaded_count}{Style.RESET_ALL} papers")
        if rejected_count > 0:
            print(f"  {Fore.YELLOW}Rejected:{Style.RESET_ALL}  {Fore.YELLOW}{rejected_count}{Style.RESET_ALL} duplicates")
        if skipped_metadata_count > 0:
            print(f"  {Fore.CYAN}Skipped:{Style.RESET_ALL}   {Fore.CYAN}{skipped_metadata_count}{Style.RESET_ALL} not a BibTeX record")
        if failed_count > 0:
            print(f"  {Fore.RED}Failed:{Style.RESET_ALL}    {Fore.RED}{failed_count}{Style.RESET_ALL} errors")
        
        # Show source breakdown
        if sources_loaded:
            print(f"\n{Fore.CYAN}By source:{Style.RESET_ALL}")
            for source in sorted(sources_loaded.keys()):
                count = sources_loaded[source]
                print(f"  {Fore.YELLOW}{source}:{Style.RESET_ALL} {count}")
        
        if failed_papers:
            print(f"\n{Fore.RED}Failed papers:{Style.RESET_ALL}")
            for citekey, error in failed_papers:
                print(f"  • {citekey}: {error}")
        print()
    except Exception as e:
        print(f"{Fore.RED}❌ Error loading papers: {e}{Style.RESET_ALL}")
        sys.exit(1)
    finally:
        loader.disconnect()


if __name__ == '__main__':
    import argparse
    main()
