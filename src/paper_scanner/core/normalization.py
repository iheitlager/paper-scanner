"""
Centralized field normalization for Paper Scanner

This module provides the Normalizer class as the SINGLE source of truth for all
field formatting and cleaning. All IO handlers, fetchers, and pipeline steps
should use this module instead of implementing their own normalization logic.

Design principle: Normalizer handles ALL formatting; Paper/Author models are
passive data containers with NO validators or transformations.
"""

import re
from typing import Any, Dict, List, Optional

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import PaperType


class Normalizer:
    """
    Centralized field normalization for all IO handlers and fetchers.
    
    This class provides methods to normalize bibliographic fields extracted
    from various sources (BibTeX, RIS, Crossref, OpenAlex, etc.).
    
    All methods are stateless and can be called as static methods or on an instance.
    """

    @staticmethod
    def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize all standardized fields in a data dictionary.
        
        This is the primary entry point. Fields not in the normalization list
        are passed through unchanged.
        
        Args:
            data: Dictionary with raw field values (from IO handler/fetcher)
            
        Returns:
            Dictionary with normalized fields ready for Paper construction
            
        Example:
            >>> raw = {'title': 'the GREAT study', 'year': '2024'}
            >>> normalized = Normalizer.normalize(raw)
            >>> normalized['title']
            'The Great Study'
        """
        normalizer = Normalizer()
        return {
            'title': normalizer.normalize_title(data.get('title')),
            'abstract': normalizer.normalize_abstract(data.get('abstract')),
            'authors': normalizer.normalize_authors(data.get('authors')),
            'keywords': normalizer.normalize_keywords(data.get('keywords')),
            'journal': normalizer.normalize_journal(data.get('journal')),
            'publisher': normalizer.normalize_publisher(data.get('publisher')),
            'year': normalizer.normalize_year(data.get('year')),
            'doi': normalizer.normalize_doi(data.get('doi')),
            'paper_type': normalizer.normalize_paper_type(data.get('paper_type')),
            # Pass through all other fields unchanged
            **{k: v for k, v in data.items() 
               if k not in ['title', 'abstract', 'authors', 'keywords', 
                           'journal', 'publisher', 'year', 'doi', 'paper_type']}
        }

    @staticmethod
    def normalize_title(title: Optional[str]) -> Optional[str]:
        """
        Normalize paper title.
        
        Process:
        1. Strip leading/trailing whitespace
        2. Remove LaTeX braces
        3. Collapse multiple spaces to single space
        4. Normalize ampersands
        5. Apply smart titlecase with particle handling
        
        Args:
            title: Raw title string
            
        Returns:
            Normalized title or None
            
        Example:
            >>> Normalizer.normalize_title('the great STUDY of Machine Learning')
            'The Great Study of Machine Learning'
            >>> Normalizer.normalize_title('  title with  spaces  ')
            'Title With Spaces'
        """
        if not title:
            return title
        title = title.strip()
        title = Normalizer._clean_markup(title)
        title = Normalizer._collapse_whitespace(title)
        title = Normalizer._normalize_ampersands(title)
        title = Normalizer._smart_titlecase(title)
        return title

    @staticmethod
    def normalize_abstract(abstract: Optional[str]) -> Optional[str]:
        """
        Normalize paper abstract.
        
        Process:
        1. Strip leading/trailing whitespace
        2. Remove LaTeX braces and HTML markup
        3. Normalize ampersands
        4. Collapse multiple spaces/newlines to single space
        
        Args:
            abstract: Raw abstract string
            
        Returns:
            Normalized abstract or None
            
        Example:
            >>> Normalizer.normalize_abstract('We\\&nbsp;tested...\\n\\n')
            'We & tested...'
        """
        if not abstract:
            return abstract
        abstract = abstract.strip()
        abstract = Normalizer._clean_markup(abstract)
        abstract = Normalizer._normalize_ampersands(abstract)
        abstract = Normalizer._normalize_percent(abstract)
        abstract = Normalizer._collapse_whitespace(abstract)
        return abstract

    @staticmethod
    def normalize_authors(authors: Optional[Any]) -> List[str]:
        """
        Normalize author list with smart titlecase.
        
        Handles multiple input formats:
        - String: "Smith, John and Doe, Jane" (BibTeX/RIS)
        - String: "John Smith and Jane Doe" (some APIs)
        - List of strings: ["Smith, John", "Doe, Jane"]
        - List of dicts: [{"given_name": "John", "family_name": "Smith"}]
        - List of Author objects
        
        Process:
        1. Parse input format to list of strings
        2. Apply smart titlecase to each author name
        3. Return list of normalized author strings
        
        Args:
            authors: Raw authors in various formats
            
        Returns:
            List of titlecased author strings (empty list if None/empty)
            
        Example:
            >>> Normalizer.normalize_authors("smith, john and doe, jane")
            ['John Smith', 'Jane Doe']
            >>> Normalizer.normalize_authors([{"given_name": "john", "family_name": "smith"}])
            ['John Smith']
        """
        if not authors:
            return []
        
        parsed = []
        author_list = authors if isinstance(authors, list) else [authors]
        
        for author in author_list:
            if isinstance(author, dict):
                # Dict format: extract given/family names
                given = author.get('given_name', '').strip()
                family = author.get('family_name', '').strip()
                if family:
                    full = f"{given} {family}".strip() if given else family
                    full = Normalizer._smart_titlecase(full)
                    parsed.append(full)
            elif hasattr(author, 'full_name'):
                # Author object: use full_name (should already be normalized)
                parsed.append(author.full_name)
            elif isinstance(author, str):
                # String format: parse and titlecase each author
                author_strings = Normalizer._parse_author_string(author)
                for author_str in author_strings:
                    titlecased = Normalizer._smart_titlecase(author_str)
                    parsed.append(titlecased)
        
        return parsed

    @staticmethod
    def normalize_author_list(authors: Optional[List[Any]]) -> Optional[List[Any]]:
        """
        Normalize a list of Author model objects.
        
        Applies titlecase normalization to the full_name field of each Author,
        preserving the Author object structure. This is the centralized place
        where the decision is made: "Author normalization applies to full_name only".
        
        Args:
            authors: List of Author objects (from paper_scanner.core.models.Author)
            
        Returns:
            List of Author objects with normalized full_name fields, or None if input is None
            
        Note:
            This handles Author MODEL objects (which have full_name, given_name, etc. attributes).
            For string/dict author data, use normalize_authors() instead.
            
        Example:
            >>> from paper_scanner.core.models import Author
            >>> author = Author(given_name="john", family_name="DOE", full_name="john DOE")
            >>> normalized = Normalizer.normalize_author_list([author])
            >>> normalized[0].full_name
            'John Doe'
        """
        if not authors:
            return authors
        
        from paper_scanner.core.models import Author
        
        normalized = []
        for author in authors:
            if isinstance(author, Author):
                # Normalize the full_name field via smart titlecase
                normalized_author = Author(
                    given_name=author.given_name,
                    family_name=author.family_name,
                    full_name=Normalizer._smart_titlecase(author.full_name),
                    affiliation=author.affiliation
                )
                normalized.append(normalized_author)
            else:
                # Preserve non-Author objects as-is (shouldn't happen in normal flow)
                normalized.append(author)
        
        return normalized

    @staticmethod
    def normalize_keywords(keywords: Optional[Any]) -> List[str]:
        """
        Normalize keyword list.
        
        Handles multiple input formats:
        - String with semicolons: "keyword1; keyword2; keyword3"
        - String with commas: "keyword1, keyword2, keyword3"
        - String with 'and': "keyword1 and keyword2"
        - List: ["keyword1", "keyword2"]
        
        Process:
        1. Split by delimiter (priority: ; > , > and)
        2. Strip whitespace from each
        3. Convert to lowercase
        4. Deduplicate while preserving order
        
        Args:
            keywords: Raw keywords in various formats
            
        Returns:
            List of lowercase keyword strings (empty list if None/empty)
            
        Example:
            >>> Normalizer.normalize_keywords("ML; Deep Learning; ml")
            ['ml', 'deep learning']
            >>> Normalizer.normalize_keywords("keyword1, keyword2, keyword1")
            ['keyword1', 'keyword2']
        """
        if not keywords:
            return []
        
        result = []
        kw_list = keywords if isinstance(keywords, list) else [keywords]
        
        for kw in kw_list:
            if isinstance(kw, str):
                # Split by delimiter
                parts = Normalizer._split_keywords(kw)
                for part in parts:
                    part = part.strip().lower()
                    if part and part not in result:
                        result.append(part)
        
        return result

    @staticmethod
    def normalize_journal(journal: Optional[str]) -> Optional[str]:
        """
        Normalize journal name.
        
        Process:
        1. Strip leading/trailing whitespace
        2. Normalize ampersands
        3. Apply smart titlecase with particle handling
        
        Args:
            journal: Raw journal name
            
        Returns:
            Normalized journal name or None
            
        Note:
            This is separate from Journal Screening (spike 015) which enriches
            with ISSN, ISO4, quartile ranking, etc. This only cleans the name string.
            
        Example:
            >>> Normalizer.normalize_journal("the JOURNAL of machine & learning")
            'The Journal of Machine & Learning'
        """
        if not journal:
            return journal
        journal = journal.strip()
        journal = Normalizer._normalize_ampersands(journal)
        journal = Normalizer._smart_titlecase(journal)
        return journal

    @staticmethod
    def normalize_publisher(publisher: Optional[str]) -> Optional[str]:
        """
        Normalize publisher name.
        
        Process:
        1. Strip leading/trailing whitespace
        2. Normalize ampersands
        3. Apply smart titlecase with particle handling
        
        Args:
            publisher: Raw publisher name
            
        Returns:
            Normalized publisher name or None
            
        Example:
            >>> Normalizer.normalize_publisher("academic press & co.")
            'Academic Press & Co.'
        """
        if not publisher:
            return publisher
        publisher = publisher.strip()
        publisher = Normalizer._normalize_ampersands(publisher)
        publisher = Normalizer._smart_titlecase(publisher)
        return publisher

    @staticmethod
    def normalize_year(year: Optional[Any]) -> Optional[int]:
        """
        Normalize publication year.
        
        Handles multiple input formats:
        - Integer: 2024
        - String: "2024"
        - Date string: "2024-01-15"
        
        Process:
        1. Convert string to int if needed
        2. Extract 4-digit year from date strings
        3. Validate range 1000–2100
        4. Return None if invalid
        
        Args:
            year: Raw year in various formats
            
        Returns:
            Integer year (1000–2100) or None if invalid
            
        Example:
            >>> Normalizer.normalize_year("2024-01-15")
            2024
            >>> Normalizer.normalize_year("202a")
            None
            >>> Normalizer.normalize_year(2024)
            2024
        """
        if year is None:
            return None
        
        # Already an int
        if isinstance(year, int):
            if 1000 <= year <= 2100:
                return year
            return None
        
        # String format
        if isinstance(year, str):
            year = year.strip()
            if not year:
                return None
            
            # Try direct int conversion
            try:
                year_int = int(year)
                if 1000 <= year_int <= 2100:
                    return year_int
            except ValueError:
                pass
            
            # Try to extract 4-digit year from date strings
            match = re.search(r'\b(\d{4})\b', year)
            if match:
                year_int = int(match.group(1))
                if 1000 <= year_int <= 2100:
                    return year_int
        
        return None

    @staticmethod
    def normalize_doi(doi: Optional[str]) -> Optional[str]:
        """
        Normalize DOI to standard format.
        
        Handles formats:
        - "10.1234/example"
        - "https://doi.org/10.1234/example"
        - "doi:10.1234/example"
        
        Process:
        1. Use DOI class for standardization (stem extraction)
        2. Return None if invalid
        
        Args:
            doi: Raw DOI string
            
        Returns:
            Normalized DOI string or None if invalid
            
        Example:
            >>> Normalizer.normalize_doi("https://doi.org/10.1234/example")
            '10.1234/example'
        """
        if not doi:
            return None
        
        try:
            normalized = DOI(doi).stem
            return normalized if normalized else None
        except Exception:
            return None

    @staticmethod
    def normalize_paper_type(paper_type: Optional[str]) -> Optional[str]:
        """
        Validate paper type against PaperType enum.
        
        Note: Source-specific type mapping (BibTeX → PaperType, RIS → PaperType, etc.)
        is handled by each source module. This method only validates that the
        resulting value is a valid enum value.
        
        Args:
            paper_type: Paper type string (should be a PaperType enum value)
            
        Returns:
            Valid PaperType value string or None if invalid
            
        Example:
            >>> Normalizer.normalize_paper_type("journal_article")
            'journal_article'
            >>> Normalizer.normalize_paper_type("invalid_type")
            None
        """
        if not paper_type:
            return None
        
        if not isinstance(paper_type, str):
            return None
        
        try:
            # Validate against enum values
            for pt in PaperType:
                if pt.value == paper_type:
                    return paper_type
            return None
        except Exception:
            return None

    # ========== INTERNAL HELPER METHODS ==========

    @staticmethod
    def _smart_titlecase(text: str) -> str:
        """
        Apply titlecase with particle and acronym handling.
        
        Preserves lowercase particles (de, van, von, der, den, el, la, le, di, da, du)
        when not at the start of the text. Preserves proper case for known acronyms
        (business entities, scientific terms) in English, Dutch, French, and German.
        Handles hyphenated words by titlecasing each part separately while preserving hyphens.
        
        Args:
            text: Text to titlecase
            
        Returns:
            Titlecased text with particles and acronyms preserved
            
        Example:
            >>> Normalizer._smart_titlecase("ludwig von beethoven")
            'Ludwig von Beethoven'
            >>> Normalizer._smart_titlecase("jean-claude van damme")
            'Jean-Claude van Damme'
            >>> Normalizer._smart_titlecase("smith & co. ltd")
            'Smith & Co. Ltd'
            >>> Normalizer._smart_titlecase("müller gmbh")
            'Müller GmbH'
        """
        if not text:
            return text

        # Define particles and acronyms
        particles = {'de', 'van', 'von', 'der', 'den', 'el', 'la', 'le', 'di', 'da', 'du', 'the'}
        caps_only = {
            'usa', 'uk', 'eu', 'un',
            'nasa', 'nato',
            "oem", "r&d",
            'ai', 'ml', 'it',
            'b2b', 'b2c', 'b2g',
            'ibm', 'hp', 'amd', 'sap',
            'sql', 'html', 'css', 'json', 'xml', 'soap', 'rest', 'soa','esb'
            'nfv',
            'erp', 'ocr',
            'esg', 'ict', 'cpu', 'gpu', 'ram',
            '3g', '4g', '5g', '6g',
            'uav',
        }
        # Lowercase prepositions, conjunctions and articles to preserve
        # Location/Direction: in, on, at, by, to, from, into, onto, through, across, above, below, under, over, between, among, around, behind, before, after, inside, outside, near, beside, against
        # Time: during, before, after, since, until, throughout, within
        # Relationship: of, with, without, for, about, regarding, concerning, except, besides, like, unlike
        # Other: as, than, or, and, but, yet, so, because, if, unless, while, when
        # APA Style Guide official source:
        # Publication: Publication Manual of the American Psychological Association (7th edition, 2020)
        # Section: Chapter 4, "Formatting and Organization" → Capitalization rules for titles
        # Online: https://apastyle.apa.org/style-grammar-guidelines/capitalization/title-case
        lowercase = {
            # Articles
            'a', 'an', 'the',
            # Conjunctions
            'and', 'or', 'nor', 'but', 'yet', 'so',
            # Location/Direction prepositions
            'in', 'on', 'at', 'by', 'to', 'from', 'into', 'onto', 'through', 'across',
            'above', 'below', 'under', 'over', 'between', 'among', 'around', 'behind',
            'before', 'after', 'inside', 'outside', 'near', 'beside', 'against',
            # Time prepositions
            'during', 'since', 'until', 'throughout', 'within',
            # Relationship prepositions
            'of', 'with', 'without', 'for', 'about', 'regarding', 'concerning',
            'except', 'besides', 'like', 'unlike',
            # Other prepositions/conjunctions
            'as', 'than', 'because', 'if', 'unless', 'while', 'when',
        }

        # Acronyms: map lowercase to proper case
        # Business entities (English, Dutch, French, German)
        # Scientific/academic acronyms
        acronyms = {
            # English
            'ltd': 'Ltd',
            'inc': 'Inc',
            'corp': 'Corp',
            'llc': 'LLC',
            'co': 'Co',
            'plc': 'PLC',
            # Dutch
            'bv': 'BV',
            'nv': 'NV',
            'vof': 'VOF',
            # French
            'sarl': 'SARL',
            'sa': 'SA',
            'sas': 'SAS',
            'eurl': 'EURL',
            # German
            'gmbh': 'GmbH',
            'ag': 'AG',
            'kg': 'KG',
            'ohg': 'oHG',
            # Scientific/Academic
            'phd': 'PhD',
            'mba': 'MBA',
            'bsc': 'BSc',
            'msc': 'MSc',
            'ieee': 'IEEE',
            'aims': 'AIMS',
            'acm': 'ACM',
            'iot': 'IoT',
        }

        # Acronyms that should stay lowercase (even at word start)
        lowercase_acronyms = {'et al', 'vs'}
        
        text_lower = text.lower()
        
        # Pre-process: Replace "et al" with a placeholder to preserve it as a unit
        import re
        et_al_placeholder = '__ET_AL__'
        # Match "et al" with optional punctuation and capture the punctuation
        pattern = r'\bet\s+al(?=[.\s,;:]|$)'
        text_processed = re.sub(pattern, et_al_placeholder, text_lower)
        
        words = text_processed.split()
        result = []

        first_word = False
        for i, word in enumerate(words):
            if i == 0 or first_word:
                first_word = True
            # Handle words that contain the placeholder
            if et_al_placeholder in word:
                # Restore "et al" and preserve any attached punctuation
                restored = word.replace(et_al_placeholder, 'et al')
                result.append(restored)
                continue
            
            if '–' in word:
                word = word.replace('–', '-')
            # Handle hyphenated words
            if '-' in word:
                parts = word.split('-')
                titlecased = []
                for part in parts:
                    part_clean = part.rstrip('.,;:').lower()
                    # Check if it's an acronym first
                    if part_clean in acronyms:
                        titlecased.append(acronyms[part_clean])
                    # always uppercase caps-only acronyms
                    elif part_clean in caps_only:
                        titlecased.append(part.upper())
                    # Capitalize unless it's a particle (and not first word overall)
                    else:
                        titlecased.append(part.capitalize())
                result.append('-'.join(titlecased))
            else:
                word_clean = word.rstrip('.,;:').lower()
                # Check if word is an acronym (preserve original trailing punctuation)
                if word_clean in acronyms:
                    # Preserve trailing punctuation
                    punct = word[len(word_clean):]
                    result.append(acronyms[word_clean] + punct)
                elif word_clean in lowercase:
                    if first_word:
                        result.append(word.capitalize())
                    else:
                        result.append(word)
                elif word_clean in caps_only:
                    result.append(word.upper())
                # First word: capitalize unless it's a lowercase acronym
                # Check if word is a particle (minus trailing punctuation)
                elif word_clean in particles and not first_word:
                    result.append(word)
                # Regular word: capitalize
                else:
                    result.append(word.capitalize())
            first_word = word[-1] == ":"
        return ' '.join(result)

    @staticmethod
    def _collapse_whitespace(text: Optional[str]) -> Optional[str]:
        """
        Collapse multiple spaces and newlines to single space.
        
        Args:
            text: Text to normalize
            
        Returns:
            Text with whitespace collapsed
            
        Example:
            >>> Normalizer._collapse_whitespace("text  with   spaces\\n\\n")
            'text with spaces'
        """
        if not text:
            return text
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _normalize_ampersands(text: Optional[str]) -> Optional[str]:
        """
        Normalize ampersands: \\& and &amp; → &.
        
        Args:
            text: Text to normalize
            
        Returns:
            Text with normalized ampersands
            
        Example:
            >>> Normalizer._normalize_ampersands("Smith \\& Jones & Co.")
            'Smith & Jones & Co.'
        """
        if not text:
            return text
        text = text.replace(r'\&', '&')
        text = text.replace('&amp;', '&')
        return text

    @staticmethod
    def _normalize_percent(text: Optional[str]) -> Optional[str]:
        """
        Normalize percent: \\% and &percnt; → %.
        
        Args:
            text: Text to normalize
            
        Returns:
            Text with normalized ampersands
            
        Example:
            >>> Normalizer._normalize_percent("50\\% of &percnt;")
            '50% of %'
        """
        if not text:
            return text
        text = text.replace(r'\%', '%')
        text = text.replace('&percnt;', '%')
        return text

    @staticmethod
    def _clean_markup(text: Optional[str]) -> Optional[str]:
        """
        Remove LaTeX braces and HTML markup.
        
        Args:
            text: Text to clean
            
        Returns:
            Text with markup removed
            
        Example:
            >>> Normalizer._clean_markup("Title {with} braces <b>and</b> HTML")
            'Title with braces and HTML'
            >>> Normalizer._clean_markup("accuracy of 97.65$%$ during testing")
            'accuracy of 97.65% during testing'
        """
        if not text:
            return text
        # Remove LaTeX math-mode escape patterns (e.g., $%$ -> %, $&$ -> &)
        # These are used to escape special characters that have special meaning in LaTeX
        text = re.sub(r'\$([%&_#])\$', r'\1', text)
        # Remove LaTeX braces
        text = re.sub(r'[{}]', '', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text

    @staticmethod
    def _parse_author_string(author_str: str) -> List[str]:
        """
        Parse author string to list of individual author names.
        
        Handles:
        - "First Last" format
        - "First M. Last" format
        - "Last, First" format (BibTeX)
        - Multiple authors separated by "and"
        
        Args:
            author_str: Author string (possibly multiple authors)
            
        Returns:
            List of individual author name strings
            
        Example:
            >>> Normalizer._parse_author_string("smith, john and doe, jane")
            ['smith, john', 'doe, jane']
        """
        if not author_str:
            return []
        
        # Split by ' and ' (BibTeX style)
        authors = re.split(r'\s+and\s+', author_str, flags=re.IGNORECASE)
        
        # Clean each author
        result = []
        for author in authors:
            author = author.strip()
            if author:
                result.append(author)
        
        return result

    @staticmethod
    def _split_keywords(kw_str: str) -> List[str]:
        """
        Split keyword string by common delimiters.
        
        Priority: semicolon > comma > 'and'
        
        Args:
            kw_str: Keyword string (possibly multiple keywords)
            
        Returns:
            List of individual keyword strings
            
        Example:
            >>> Normalizer._split_keywords("ML; Deep Learning; Neural Networks")
            ['ML', ' Deep Learning', ' Neural Networks']
        """
        if not kw_str:
            return []
        
        if ';' in kw_str:
            return kw_str.split(';')
        elif ',' in kw_str:
            return kw_str.split(',')
        elif ' and ' in kw_str.lower():
            return re.split(r'\s+and\s+', kw_str, flags=re.IGNORECASE)
        else:
            return [kw_str]
