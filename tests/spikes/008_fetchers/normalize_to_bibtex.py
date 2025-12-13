#!/usr/bin/env python3
"""
API Response to Paper Model Converter

Converts various API JSON responses to the Paper Pydantic model,
then optionally exports to BibTeX format.

Supports: Crossref, OpenAlex, CORE, Semantic Scholar, Unpaywall, IEEE Xplore

Usage:
    uv run tests/spikes/008_fetchers/normalize_to_bibtex.py <input.json> [--format bibtex|json|model]
    
Example:
    uv run tests/spikes/008_fetchers/normalize_to_bibtex.py tests/data/crossref_msg.json
    uv run tests/spikes/008_fetchers/normalize_to_bibtex.py tests/data/openalex_msg.json --format bibtex
"""

import json
import sys
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone

# Import Paper model
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from paper_scanner.core.models import Paper, Author, Discovery, DiscoveryMethod


class APIResponseNormalizer:
    """Normalize various API JSON responses to Paper model and BibTeX."""
    
    @staticmethod
    def extract_doi(data: Dict[str, Any]) -> Optional[str]:
        """Extract DOI from various API response formats."""
        if "doi" in data:
            doi = data["doi"]
            if isinstance(doi, str):
                return doi.replace("https://doi.org/", "")
        if "externalIds" in data and "DOI" in data["externalIds"]:
            return data["externalIds"]["DOI"]
        if "DOI" in data:
            return data["DOI"]
        return None
    
    @staticmethod
    def extract_cite_key(data: Dict[str, Any]) -> str:
        """Generate cite_key from DOI or title."""
        doi = APIResponseNormalizer.extract_doi(data)
        if doi:
            return doi
        title = APIResponseNormalizer.extract_title(data) or "untitled"
        year = APIResponseNormalizer.extract_year(data) or "xxxx"
        simplified = title.split()[0].lower()
        return f"{simplified}{year}"
    
    @staticmethod
    def extract_title(data: Dict[str, Any]) -> Optional[str]:
        """Extract title from various API response formats."""
        if "title" in data:
            title = data["title"]
            if isinstance(title, list):
                return title[0] if title else None
            return title
        if "display_name" in data:
            return data["display_name"]
        return None
    
    @staticmethod
    def extract_authors(data: Dict[str, Any]) -> List[str]:
        """Extract authors from various API response formats."""
        authors = []
        
        # Crossref format: array with given/family
        if "author" in data and isinstance(data["author"], list):
            for author in data["author"]:
                if isinstance(author, dict):
                    family = author.get("family", "")
                    given = author.get("given", "")
                    if family:
                        name = family
                        if given:
                            name = f"{family}, {given}"
                        authors.append(name)
        
        # OpenAlex format: authorships with author.display_name
        elif "authorships" in data and isinstance(data["authorships"], list):
            for authorship in data["authorships"]:
                if "author" in authorship and isinstance(authorship["author"], dict):
                    name = authorship["author"].get("display_name")
                    if name:
                        authors.append(name)
        
        # CORE format: authors array with name
        elif "authors" in data and isinstance(data["authors"], list):
            for author in data["authors"]:
                if isinstance(author, dict) and "name" in author:
                    authors.append(author["name"])
        
        return authors
    
    @staticmethod
    def extract_year(data: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from various API response formats."""
        if "year" in data:
            year = data["year"]
            if isinstance(year, int):
                return year
        if "publication_year" in data:
            return data["publication_year"]
        if "yearPublished" in data:
            return data["yearPublished"]
        if "issued" in data and isinstance(data["issued"], dict):
            date_parts = data["issued"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                if isinstance(date_parts[0], list) and len(date_parts[0]) > 0:
                    return date_parts[0][0]
        if "published" in data and isinstance(data["published"], dict):
            date_parts = data["published"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                if isinstance(date_parts[0], list) and len(date_parts[0]) > 0:
                    return date_parts[0][0]
        if "publishedDate" in data:
            try:
                return int(data["publishedDate"][:4])
            except (ValueError, TypeError, IndexError):
                pass
        return None
    
    @staticmethod
    def extract_journal(data: Dict[str, Any]) -> Optional[str]:
        """Extract journal name from various API response formats."""
        if "container-title" in data:
            titles = data["container-title"]
            if isinstance(titles, list):
                return titles[0] if titles else None
            return titles
        if "primary_location" in data:
            source = data["primary_location"].get("source")
            if isinstance(source, dict):
                return source.get("display_name")
        if "journals" in data and isinstance(data["journals"], list):
            if len(data["journals"]) > 0:
                return data["journals"][0].get("title")
        if "journal_name" in data:
            return data["journal_name"]
        return None
    
    @staticmethod
    def extract_publisher(data: Dict[str, Any]) -> Optional[str]:
        """Extract publisher from various API response formats."""
        if "publisher" in data:
            return data["publisher"]
        if "primary_location" in data:
            source = data["primary_location"].get("source")
            if isinstance(source, dict):
                return source.get("host_organization_name")
        return None
    
    @staticmethod
    def extract_abstract(data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract from various API response formats."""
        if "abstract" in data and data["abstract"]:
            abstract = data["abstract"]
            if isinstance(abstract, str):
                abstract = re.sub(r"<[^>]+>", "", abstract)
                abstract = re.sub(r"</?jats:[^>]+>", "", abstract)
                return abstract.strip()
        return None
    
    @staticmethod
    def extract_volume(data: Dict[str, Any]) -> Optional[str]:
        """Extract volume from various API response formats."""
        if "volume" in data:
            return str(data["volume"])
        if "biblio" in data and isinstance(data["biblio"], dict):
            vol = data["biblio"].get("volume")
            if vol:
                return str(vol)
        if "journals" in data and isinstance(data["journals"], list):
            if len(data["journals"]) > 0:
                vol = data["journals"][0].get("volume")
                if vol:
                    return str(vol)
        return None
    
    @staticmethod
    def extract_issue(data: Dict[str, Any]) -> Optional[str]:
        """Extract issue/number from various API response formats."""
        if "issue" in data:
            return str(data["issue"])
        if "biblio" in data and isinstance(data["biblio"], dict):
            issue = data["biblio"].get("issue")
            if issue:
                return str(issue)
        if "journals" in data and isinstance(data["journals"], list):
            if len(data["journals"]) > 0:
                issue = data["journals"][0].get("issue")
                if issue:
                    return str(issue)
        return None
    
    @staticmethod
    def extract_keywords(data: Dict[str, Any]) -> List[str]:
        """Extract keywords from various API response formats."""
        keywords = []
        
        # OpenAlex keywords (best source)
        if "keywords" in data and isinstance(data["keywords"], list):
            for keyword in data["keywords"]:
                if isinstance(keyword, dict):
                    name = keyword.get("display_name")
                    if name:
                        keywords.append(name)
        
        # OpenAlex topics (if no keywords, use topics)
        if not keywords and "topics" in data and isinstance(data["topics"], list):
            for topic in data["topics"]:
                if isinstance(topic, dict):
                    name = topic.get("display_name")
                    if name:
                        keywords.append(name)
        
        # Crossref subjects
        if not keywords and "subject" in data and isinstance(data["subject"], list):
            keywords = [s for s in data["subject"] if isinstance(s, str)]
        
        return keywords
    
    @staticmethod
        """Extract URL from various API response formats."""
        if "primary_location" in data:
            url = data["primary_location"].get("landing_page_url")
            if url:
                return url
        if "best_oa_location" in data:
            url = data["best_oa_location"].get("url")
            if url:
                return url
        if "doi_url" in data:
            return data["doi_url"]
        if doi:
            return f"https://doi.org/{doi}"
        return None
    
    @staticmethod
    def to_paper(data: Dict[str, Any]) -> Paper:
        """Convert API response to Paper model."""
        title = APIResponseNormalizer.extract_title(data)
        if not title:
            raise ValueError("Title is required for Paper model")
        
        # Create Author objects
        authors = []
        for author_str in APIResponseNormalizer.extract_authors(data):
            if "," in author_str:
        paper = Paper(
            cite_key=cite_key,
            title=title,
            authors=authors,
            keywords=APIResponseNormalizer.extract_keywords(data),
            doi=APIResponseNormalizer.extract_doi(data),
            journal=APIResponseNormalizer.extract_journal(data),
            publisher=APIResponseNormalizer.extract_publisher(data),
            volume=APIResponseNormalizer.extract_volume(data),
            number=APIResponseNormalizer.extract_issue(data),
            abstract=APIResponseNormalizer.extract_abstract(data),
            year=year,
            url=APIResponseNormalizer.extract_url(data, APIResponseNormalizer.extract_doi(data)),
            publication_date=publication_date,
            discovery=Discovery(method=DiscoveryMethod.API),
            raw_json=data
        )
        cite_key = APIResponseNormalizer.extract_cite_key(data)
        
        publication_date = None
        year = APIResponseNormalizer.extract_year(data)
        if year:
            try:
                publication_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
        
        paper = Paper(
            cite_key=cite_key,
            title=title,
            authors=authors,
            doi=APIResponseNormalizer.extract_doi(data),
            journal=APIResponseNormalizer.extract_journal(data),
            publisher=APIResponseNormalizer.extract_publisher(data),
            volume=APIResponseNormalizer.extract_volume(data),
            number=APIResponseNormalizer.extract_issue(data),
            abstract=APIResponseNormalizer.extract_abstract(data),
            year=year,
            url=APIResponseNormalizer.extract_url(data, APIResponseNormalizer.extract_doi(data)),
            publication_date=publication_date,
            discovery=Discovery(method=DiscoveryMethod.API),
            raw_json=data
        )
        
        return paper
    
    @staticmethod
    def paper_to_bibtex(paper: Paper) -> str:
        """Convert Paper model to BibTeX format."""
        cite_key = paper.doi if paper.doi else paper.cite_key
        bibtex = f"@article{{{cite_key},\n"
        
        fields = []
        
        if paper.abstract:
            abstract = paper.abstract.replace('"', '\\"')
            fields.append(f'  abstract = "{abstract}"')
        
        if paper.authors:
            author_strs = []
            for author in paper.authors:
                if author.given_name:
                    author_strs.append(f"{author.family_name}, {author.given_name}")
                else:
                    author_strs.append(author.family_name)
            author_str = " and ".join(author_strs)
            fields.append(f'  author = {{{author_str}}}')
        
        if paper.doi:
            fields.append(f'  doi = {{{paper.doi}}}')
        
        if paper.journal:
            fields.append(f'  journal = {{{paper.journal}}}')
        
        if paper.number:
            fields.append(f'  number = {{{paper.number}}}')
        
        if paper.publisher:
            fields.append(f'  publisher = {{{paper.publisher}}}')
        
        fields.append(f'  title = {{{paper.title}}}')
        
        if paper.url:
            fields.append(f'  url = {{{paper.url}}}')
        
        if paper.volume:
            fields.append(f'  volume = {{{paper.volume}}}')
        
        if paper.year:
            fields.append(f'  year = {{{paper.year}}}')
        
        bibtex += ",\n".join(fields)
        bibtex += "\n}\n"
        
        return bibtex


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python normalize_to_bibtex.py <input.json> [--format bibtex|json|model]")
        print("\nExamples:")
        print("  python normalize_to_bibtex.py tests/data/crossref_msg.json")
        print("  python normalize_to_bibtex.py tests/data/openalex_msg.json --format bibtex")
        print("  python normalize_to_bibtex.py tests/data/core_msg.json --format json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_format = "json"
    
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            output_format = sys.argv[idx + 1]
    
    if not input_file.exists():
        print(f"Error: File {input_file} not found", file=sys.stderr)
        sys.exit(1)
    
    with open(input_file) as f:
        data = json.load(f)
    
    try:
        paper = APIResponseNormalizer.to_paper(data)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    if output_format == "bibtex":
        print(APIResponseNormalizer.paper_to_bibtex(paper))
    elif output_format == "json":
        print(json.dumps(paper.model_dump(mode="json"), indent=2))
    elif output_format == "model":
        print(paper)
    else:
        print(f"Error: Unknown format '{output_format}'. Use: bibtex, json, or model", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
