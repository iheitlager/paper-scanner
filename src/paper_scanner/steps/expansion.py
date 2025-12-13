"""
Expansion step for paper scanner - Reference snowballing

Implements backward snowballing to expand paper database by following references.

Features:
- Extract citations from papers in database
- Resolve citations to DOIs
- Fetch metadata for new papers from Crossref
- Link citations to resolved papers
- Track expansion statistics (papers expanded, citations found, new papers added)
- Iterate with saturation detection
"""

import time
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from rich.console import Console
from rich.progress import Progress
from collections import defaultdict

from ..core.models import Paper, Citation, Discovery, ProcessingMetadata
from ..core.database import PapersDatabase, CitationsDatabase
from ..core.enum import DiscoveryMethod
from ..tools.fetcher_handlers.crossref_fetcher import CrossrefReferenceFetcher
from ..tools.documents.paper_type_translator import PaperTypeTranslator

logger = logging.getLogger(__name__)
console = Console(file=sys.stderr)


class ExpansionStatistics:
    """Track expansion statistics"""
    
    def __init__(self):
        self.papers_expanded: int = 0  # Papers we extracted citations from
        self.citations_found: int = 0  # Total citations extracted
        self.new_papers_added: int = 0  # New papers added to database
        self.new_papers_failed: int = 0  # Papers failed to fetch
        self.citations_with_doi: int = 0  # Citations that have DOI
        self.citations_resolved: int = 0  # Citations linked to existing papers
        self.start_time: float = time.time()
    
    def duration_seconds(self) -> float:
        """Get elapsed time"""
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Export statistics as dictionary"""
        return {
            "papers_expanded": self.papers_expanded,
            "citations_found": self.citations_found,
            "new_papers_added": self.new_papers_added,
            "new_papers_failed": self.new_papers_failed,
            "citations_with_doi": self.citations_with_doi,
            "citations_resolved": self.citations_resolved,
            "duration_seconds": self.duration_seconds(),
        }


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate expansion step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    expansion_config = config.get("expansion", config)
    backward = expansion_config.get("backward", {})
    
    # Validate extraction methods
    if "extraction_methods" in backward:
        methods = backward["extraction_methods"]
        if not isinstance(methods, list):
            errors.append("'backward.extraction_methods' must be a list")
        elif "crossref" not in methods:
            errors.append("'crossref' must be in 'backward.extraction_methods'")
    
    # Validate continue_on_not_found (optional, defaults to False)
    if "continue_on_not_found" in backward:
        continue_on_not_found = backward["continue_on_not_found"]
        if not isinstance(continue_on_not_found, bool):
            errors.append("'backward.continue_on_not_found' must be a boolean")
    
    return len(errors) == 0, errors


def _extract_citations_from_paper(paper: Paper, crossref_fetcher: CrossrefReferenceFetcher) -> List[Citation]:
    """
    Extract citations from a paper using Crossref.
    
    Args:
        paper: Paper to extract citations from
        crossref_fetcher: Crossref API client
        
    Returns:
        List of Citation objects
    """
    citations = []
    
    if not paper.doi:
        logger.debug(f"Paper {paper.cite_key} has no DOI, skipping citation extraction")
        console.print(f"[dim]  Skipped: no DOI[/dim]")
        return citations
    
    # Fetch references from Crossref
    console.print(f"[dim]  Fetching from Crossref for DOI: {paper.doi}[/dim]")
    result = crossref_fetcher.fetch_references_for_doi(paper.doi)
    if not result:
        logger.warning(f"Failed to fetch references for DOI {paper.doi}")
        console.print(f"[dim]  Failed to fetch from Crossref[/dim]")
        return citations
    
    references = result.get("references", [])
    console.print(f"[dim]  Got {len(references)} references from Crossref[/dim]")
    logger.debug(f"Extracted {len(references)} raw references from Crossref for {paper.cite_key} ({paper.doi})")
    logger.debug(f"  Result keys: {list(result.keys())}")
    
    # Convert Crossref references to Citation objects
    for ref in references:
        citation = Citation(
            doi=ref.get("DOI"),
            title=ref.get("article-title"),
            authors=[ref.get("author", "")] if "author" in ref else [],
            year=ref.get("year"),
            journal=ref.get("journal-title"),
            volume=ref.get("volume"),
            issue=ref.get("issue"),
            pages=ref.get("first-page"),
            extraction_method="crossref",
            confidence=0.9,
            raw_text=ref.get("unstructured-citation", ""),
        )
        citations.append(citation)
    
    return citations


def _fetch_and_add_paper(
    citation: Citation,
    papers_db: PapersDatabase,
    citations_db: CitationsDatabase,
    crossref_fetcher: CrossrefReferenceFetcher,
    stats: ExpansionStatistics,
    continue_on_not_found: bool = False
) -> Optional[Paper]:
    """
    Fetch paper metadata from Crossref and add to database.
    
    Args:
        citation: Citation to resolve
        papers_db: Papers database
        citations_db: Citations database
        crossref_fetcher: Crossref API client
        stats: Statistics tracker
        continue_on_not_found: If True, continue on 404 errors instead of counting as failed
        
    Returns:
        Added Paper or None if failed
    """
    if not citation.doi:
        return None
    
    # Check if paper already exists by DOI
    existing_papers = papers_db.get_by_doi(citation.doi)
    if existing_papers:
        # Link citation to existing paper
        citation.resolved_paper = existing_papers[0]
        citations_db.update(citation)
        stats.citations_resolved += 1
        logger.debug(f"Citation with DOI {citation.doi} already exists in database")
        return None
    
    # Fetch full paper metadata from Crossref
    try:
        crossref_work = crossref_fetcher.polite_client.get_work(citation.doi)
    except Exception as e:
        # Handle 404s and other HTTP errors
        logger.warning(f"Failed to fetch metadata for DOI {citation.doi}: {e}")
        if not continue_on_not_found:
            stats.new_papers_failed += 1
        return None
    
    if not crossref_work or "message" not in crossref_work:
        logger.warning(f"Failed to fetch metadata for DOI {citation.doi}")
        if not continue_on_not_found:
            stats.new_papers_failed += 1
        return None
    
    message = crossref_work["message"]
    
    # Create Paper object from Crossref metadata
    try:
        # Get paper type from Crossref and translate to standardized format
        crossref_type = message.get("type", "article")
        paper_type = PaperTypeTranslator.from_crossref(crossref_type).value
        
        paper = Paper(
            cite_key=f"crossref_{citation.doi.replace('/', '_')}",
            doi=citation.doi,
            title=message.get("title", [""])[0] if isinstance(message.get("title"), list) else message.get("title", ""),
            abstract=None,  # Crossref doesn't provide abstracts
            year=_extract_year(message),
            journal=message.get("container-title", [None])[0] if isinstance(message.get("container-title"), list) else message.get("container-title"),
            volume=message.get("volume"),
            number=message.get("issue"),
            pages=message.get("page"),
            paper_type=paper_type,  # Use translated paper type
            authors=[],  # Will be populated from Crossref author list
            discovery=Discovery(
                method=DiscoveryMethod.BACKWARD_CITATION,
            ),
        )
        
        # Add authors from Crossref
        for author_data in message.get("author", []):
            from ..core.models import Author
            author = Author(
                given_name=author_data.get("given"),
                family_name=author_data.get("family", "Unknown"),
                full_name=f"{author_data.get('given', '')} {author_data.get('family', '')}".strip(),
                affiliation=None,
            )
            paper.authors.append(author)
        
        # Add to database
        papers_db.add(paper)
        
        # Link citation to paper
        citation.resolved_paper = paper
        citations_db.update(citation)
        
        stats.new_papers_added += 1
        stats.citations_resolved += 1
        
        logger.info(f"Added new paper from citation: {paper.cite_key}")
        return paper
        
    except Exception as e:
        logger.error(f"Failed to create paper from citation with DOI {citation.doi}: {e}")
        stats.new_papers_failed += 1
        return None


def _extract_year(message: Dict[str, Any]) -> Optional[int]:
    """Extract publication year from Crossref work metadata"""
    try:
        if "published-print" in message:
            date_parts = message["published-print"].get("date-parts", [[]])[0]
            if date_parts:
                return int(date_parts[0])
        elif "published-online" in message:
            date_parts = message["published-online"].get("date-parts", [[]])[0]
            if date_parts:
                return int(date_parts[0])
    except (IndexError, ValueError, TypeError):
        pass
    return None


def execute_backward_snowballing(
    papers_db: PapersDatabase,
    citations_db: CitationsDatabase,
    config: Dict[str, Any],
    cache_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Execute backward snowballing on papers in database.
    
    Process:
    1. For each paper in database (with DOI):
       - Extract citations using Crossref
       - For each citation with DOI:
         - Check if paper already exists
         - If not, fetch from Crossref and add to database
    2. Repeat for iterations until saturation or max iterations reached
    
    Args:
        papers_db: Papers database
        citations_db: Citations database
        config: Expansion configuration
        
    Returns:
        Dict with results including statistics
    """
    # Initialize Crossref fetcher with cache_dir
    crossref_fetcher = CrossrefReferenceFetcher(cache_dir=cache_dir)
    
    stats = ExpansionStatistics()
    
    # Get all papers with DOI to expand
    papers_to_expand = [p for p in papers_db.all(primary_only=True) if p.doi]
    
    if not papers_to_expand:
        # Debug output to show why no papers to expand
        all_papers = list(papers_db.all(primary_only=True))
        console.print(f"[yellow]No papers to expand - {len(all_papers)} papers in DB, none have DOI[/yellow]")
        if all_papers:
            logger.debug(f"Papers without DOI: {[(p.cite_key, p.title[:30] if p.title else 'N/A') for p in all_papers[:3]]}")
        return {
            "success": True,
            "statistics": stats.to_dict(),
            "papers_database_count": len(papers_db.papers),
            "citations_database_count": citations_db.count(),
        }
    
    # Debug: show which papers we're expanding
    logger.debug(f"Papers to expand: {len(papers_to_expand)} (DOI: {[p.doi for p in papers_to_expand[:3]]}...)")
    console.print(f"[dim]DEBUG: {len(papers_to_expand)} papers with DOI to expand[/dim]")
    
    # Extract citations from papers
    for paper in papers_to_expand:
        console.print(f"[dim]DEBUG: Extracting citations from {paper.cite_key} ({paper.doi})[/dim]")
        citations = _extract_citations_from_paper(paper, crossref_fetcher)
        
        if citations:
            citations_db.add_many(citations)
            stats.papers_expanded += 1
            stats.citations_found += len(citations)
            stats.citations_with_doi += len([c for c in citations if c.doi])
            console.print(f"Extracting citations from {paper.cite_key}... Found {len(citations)} references")
    
    # Now fetch and add new papers from citations with DOI
    citations_with_doi = [c for c in citations_db.all() if c.doi and not c.resolved_paper]
    
    # Get continue_on_not_found option (defaults to False)
    backward_config = config.get("backward", {})
    continue_on_not_found = backward_config.get("continue_on_not_found", False)
    
    # Show gross/net overview
    total_citations = stats.citations_found
    unique_citations = len([c for c in citations_db.all() if c.doi])
    console.print(f"\n[cyan]Citation Summary:[/cyan] {total_citations} gross references → {unique_citations} unique with DOI → {len(citations_with_doi)} unresolved to fetch")
    
    # Fetch with progress bar
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Fetching metadata...", total=len(citations_with_doi))
        
        for citation in citations_with_doi:
            _fetch_and_add_paper(
                citation,
                papers_db,
                citations_db,
                crossref_fetcher,
                stats=stats,
                continue_on_not_found=continue_on_not_found
            )
            
            progress.update(task, advance=1)
    
    return {
        "success": True,
        "statistics": stats.to_dict(),
        "papers_database_count": len(papers_db.papers),
        "citations_database_count": citations_db.count(),
    }


def execute(config: Dict[str, Any], papers_db: PapersDatabase, verbose: bool = False, dry_run: bool = False, debug: bool = False, cache_dir: Optional[Path] = None, **kwargs) -> Dict[str, Any]:
    """
    Execute expansion step.
    
    Args:
        config: Step configuration
        papers_db: Papers database to expand
        verbose: Enable verbose output
        dry_run: Don't modify papers (not used for expansion, but kept for consistency)
        debug: Enable debug output for detailed information
        cache_dir: Cache directory for storing API responses
        **kwargs: Additional arguments (e.g., step_name, step_index, etc.)
        
    Returns:
        Execution result
    """
    # Validate config
    is_valid, errors = validate(config)
    if not is_valid:
        return {
            "success": False,
            "error": f"Invalid configuration: {', '.join(errors)}"
        }
    
    # Handle config structure - might be nested under 'expansion' or flat
    expansion_config = config.get("expansion", config)
    
    # Create citations database
    citations_db = CitationsDatabase()
    
    # Debug output
    if debug:
        console.print(f"[dim]DEBUG: Starting expansion step[/dim]")
        console.print(f"[dim]  Papers in database: {len(papers_db.papers)}[/dim]")
        console.print(f"[dim]  Configuration: {expansion_config}[/dim]")
    
    # Execute backward snowballing if configured
    backward_config = expansion_config.get("backward")
    if backward_config is not None:
        if debug:
            console.print(f"[dim]DEBUG: Executing backward snowballing[/dim]")
        result = execute_backward_snowballing(papers_db, citations_db, expansion_config, cache_dir=cache_dir)
        if debug:
            console.print(f"[dim]DEBUG: Backward snowballing completed[/dim]")
        return result
    
    return {
        "success": False,
        "error": "No backward snowballing configuration found"
    }
