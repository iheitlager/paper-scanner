"""
Bibtex parser utility for manual handler.

Parses bibtex files with custom citation fields (cites, citedby, studytype, lastchecked)
and converts to Paper/Citation models.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bibtexparser
from rich.console import Console

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import CitationDirection
from paper_scanner.core.models import Citation

console = Console(file=sys.stderr)


class BibtexParseError(Exception):
    """Error parsing bibtex file."""
    pass


class BibtexParser:
    """Parse bibtex files with custom citation fields."""

    # Required fields for Paper model
    REQUIRED_FIELDS = {"title", "abstract", "keywords"}

    # Optional custom fields
    OPTIONAL_CUSTOM_FIELDS = {"cites", "citedby", "studytype", "citedbycount", "lastchecked"}

    @staticmethod
    def parse_file(bibtex_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse bibtex file and extract entries with custom fields.

        Args:
            bibtex_path: Path to bibtex file

        Returns:
            Tuple of (list of valid entries, list of skipped entry keys with reasons)
        """
        if not bibtex_path.exists():
            raise BibtexParseError(f"Bibtex file not found: {bibtex_path}")

        try:
            with open(bibtex_path, "r", encoding="utf-8") as f:
                bib_database = bibtexparser.load(f)
        except Exception as e:
            raise BibtexParseError(f"Failed to parse bibtex file: {e}")

        entries = []
        skipped = []

        for entry in bib_database.entries:
            parsed_entry, skip_reason = BibtexParser._process_entry(entry)
            if parsed_entry:
                entries.append(parsed_entry)
            else:
                if isinstance(entry, dict):
                    key = entry.get("ID", "unknown")
                else:
                    key = entry.key or entry.get("ID", "unknown")
                skipped.append(f"{key}: {skip_reason}")

        return entries, skipped

    @staticmethod
    def _process_entry(entry: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Process a single bibtex entry.

        Args:
            entry: Bibtexparser entry dict

        Returns:
            Tuple of (processed entry dict, skip reason if invalid)
        """
        # Extract DOI - handle both dict and object access
        if isinstance(entry, dict):
            doi_str = entry.get("doi", "").strip()
            title = entry.get("title", "").strip()
            abstract = entry.get("abstract", "").strip()
            keywords_str = entry.get("keywords", "").strip()
            authors_str = entry.get("author", "").strip()
            year_str = entry.get("year", "").strip()
            journal = entry.get("journal", "").strip() or None
            publisher = entry.get("publisher", "").strip() or None
            cites_str = entry.get("cites", "")
            citedby_str = entry.get("citedby", "")
            citedbycount_str = entry.get("citedbycount", "").strip()
            lastchecked_str = entry.get("lastchecked", "").strip()
            studytype = entry.get("studytype", "").strip() or None
            entrytype = entry.get("ENTRYTYPE", "article").lower()
            entry.get("ID", "unknown")
        else:
            doi_str = entry.fields_dict.get("doi", "").strip()
            title = entry.fields_dict.get("title", "").strip()
            abstract = entry.fields_dict.get("abstract", "").strip()
            keywords_str = entry.fields_dict.get("keywords", "").strip()
            authors_str = entry.fields_dict.get("author", "").strip()
            year_str = entry.fields_dict.get("year", "").strip()
            journal = entry.fields_dict.get("journal", "").strip() or None
            publisher = entry.fields_dict.get("publisher", "").strip() or None
            cites_str = entry.fields_dict.get("cites", "")
            citedby_str = entry.fields_dict.get("citedby", "")
            citedbycount_str = entry.fields_dict.get("citedbycount", "").strip()
            lastchecked_str = entry.fields_dict.get("lastchecked", "").strip()
            studytype = entry.fields_dict.get("studytype", "").strip() or None
            entrytype = entry.entry_type.lower() if entry.entry_type else "article"

        if not doi_str:
            return None, "Missing DOI"

        try:
            doi = DOI(doi_str)
        except Exception:
            return None, f"Invalid DOI: {doi_str}"

        # Validate required fields
        if not title:
            return None, "Missing title"
        if not abstract:
            return None, "Missing abstract"
        if not keywords_str:
            return None, "Missing keywords"

        # Parse keywords
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]

        # Extract paper metadata
        authors = BibtexParser._parse_authors(authors_str)
        year = BibtexParser._parse_year(year_str)

        # Parse optional custom fields
        cites = BibtexParser._parse_dois_field(cites_str)
        citedby = BibtexParser._parse_dois_field(citedby_str)

        # citedbycount: use provided or calculate from citedby
        if citedbycount_str:
            try:
                citedbycount = int(citedbycount_str)
            except ValueError:
                citedbycount = len(citedby)
        else:
            citedbycount = len(citedby)

        # lastchecked: respect user value if provided, else use now
        if lastchecked_str:
            lastchecked = lastchecked_str
        else:
            lastchecked = datetime.now().isoformat()

        # studytype: validate if provided
        if studytype:
            # Validate against enum values (basic check)
            valid_types = ["empirical_case_study", "empirical_qualitative", "empirical_quantitative", "theoretical", "literature_review"]
            if studytype not in valid_types:
                console.print(f"[yellow]Warning: Unknown studytype '{studytype}' for {doi}[/yellow]")

        # Create citations
        backward_citations = BibtexParser._create_citations(cites, CitationDirection.BACKWARD)
        forward_citations = BibtexParser._create_citations(citedby, CitationDirection.FORWARD)
        all_citations = backward_citations + forward_citations

        # Map entrytype to paper_type
        paper_type = BibtexParser._map_entrytype_to_papertype(entrytype)

        # Convert Citation objects to dicts for JSON serialization
        citations_dicts = []
        for citation in all_citations:
            if isinstance(citation, Citation):
                citations_dicts.append(citation.model_dump(exclude_none=True))
            else:
                citations_dicts.append(citation)

        processed = {
            "doi": str(doi),
            "title": title,
            "abstract": abstract,
            "keywords": keywords,
            "authors": authors,
            "year": year,
            "journal": journal,
            "publisher": publisher,
            "paper_type": paper_type,
            "entrytype": entrytype,
            "source_key": str(doi),
            "studytype": studytype,
            "citedbycount": citedbycount,
            "lastchecked": lastchecked,
            "citations": citations_dicts,
            "oa_status": None,
            "url": None,
            "isbn": None,
            "issn": None,
            "pmid": None,
            "download_url": None,
            "topics": [],
        }

        return processed, None

    @staticmethod
    def _parse_authors(authors_str: str) -> List[str]:
        """Extract and parse authors field."""
        if not authors_str:
            return []

        # Split by 'and' (case-insensitive)
        author_names = [a.strip() for a in authors_str.replace(" and ", "|").split("|")]
        return [a for a in author_names if a]

    @staticmethod
    def _parse_year(year_str: str) -> Optional[int]:
        """Extract publication year."""
        if year_str:
            try:
                return int(year_str)
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_dois_field(dois_str: str) -> List[str]:
        """
        Parse DOI field (comma-separated or array format).

        Args:
            dois_str: String like "10.1234/a, 10.5678/b" or "{10.1234/a, 10.5678/b}"

        Returns:
            List of DOI strings
        """
        if not dois_str.strip():
            return []

        # Remove braces if present
        dois_str = dois_str.strip().strip("{}").strip()

        # Split by comma and clean
        dois = [doi.strip() for doi in dois_str.split(",") if doi.strip()]
        return dois

    @staticmethod
    def _create_citations(
        dois: List[str], direction: CitationDirection
    ) -> List[Citation]:
        """
        Create Citation objects from list of DOIs.

        Args:
            dois: List of DOI strings
            direction: BACKWARD or FORWARD

        Returns:
            List of Citation objects
        """
        citations = []
        for doi_str in dois:
            try:
                doi = DOI(doi_str)
                citation = Citation(
                    doi=str(doi),
                    direction=direction,
                    title=None,
                    authors=[],
                    year=None,
                    journal=None,
                    volume=None,
                    issue=None,
                    pages=None,
                    publisher=None,
                    extraction_method="manual",
                    confidence=1.0,
                    raw_text=str(doi),
                    raw_json={"doi": str(doi), "source": "manual"},
                )
                citations.append(citation)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to parse DOI '{doi_str}': {e}[/yellow]")
        return citations

    @staticmethod
    def _map_entrytype_to_papertype(entrytype: str) -> Optional[str]:
        """
        Map bibtex entry type to paper_type.

        Uses bibtex_type_mapping.yaml if available, otherwise falls back to simple mapping.

        Args:
            entrytype: Bibtex entry type (e.g., 'article', 'inproceedings')

        Returns:
            PaperType string or None
        """
        # Try to load from bibtex_type_mapping.yaml
        from pathlib import Path

        import yaml

        mapping_file = Path(__file__).parents[4] / "etc" / "bibtex_type_mapping.yaml"
        if mapping_file.exists():
            try:
                with open(mapping_file, "r") as f:
                    mapping = yaml.safe_load(f)
                    bibtex_map = mapping.get("bibtex_to_paper_type", {})
                    return bibtex_map.get(entrytype)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load bibtex_type_mapping.yaml: {e}[/yellow]")

        # Fallback simple mapping
        simple_map = {
            "article": "journal_article",
            "inproceedings": "conference_paper",
            "conference": "conference_paper",
            "book": "book",
            "inbook": "book_chapter",
            "misc": "other",
        }

        return simple_map.get(entrytype.lower())
