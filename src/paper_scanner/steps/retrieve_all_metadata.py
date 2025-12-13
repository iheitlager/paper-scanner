"""
Step definitions for external metadata retrieval pipeline.

These steps use the fetcher interfaces to retrieve metadata, citations,
and PDFs in a structured workflow.

Usage in workflow:
  - load_files: Load existing PDFs and create Paper records
  - retrieve_metadata: Enrich existing Paper records with metadata
  - retrieve_citations: Fetch backward references, create Citation + Paper records
  - retrieve_from_literature: Specialized citation retrieval for lit reviews
  - retrieve_pdfs: Download PDFs for existing Paper records
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from paper_scanner.core.models import Paper, Citation
from paper_scanner.core.database import PapersDatabase
from paper_scanner.tools.fetchers.base import (
    MetadataFetcher,
    CitationFetcher,
    CitedByFetcher,
    PDFFetcher,
    FetcherConfig,
    FallbackFetcher,
)


# ============================================================================
# CONFIGURATION STRUCTURES
# ============================================================================

@dataclass
class RetrieveMetadataConfig:
    """Configuration for retrieve_metadata step"""
    
    fetcher_config: FetcherConfig
    """Which metadata fetchers to use and in what priority"""
    
    overwrite_existing: bool = False
    """If True, fetch fresh metadata even if Paper record already has most fields"""
    
    required_fields: List[str] = None
    """Only fetch if these fields are missing (default: abstract, keywords)"""
    
    batch_size: int = 100
    """Process papers in batches to manage memory"""


@dataclass
class RetrieveCitationsConfig:
    """Configuration for retrieve_citations step"""
    
    citation_fetcher: CitationFetcher
    """Which service to use for fetching citations"""
    
    metadata_fetcher_config: FetcherConfig
    """Fetchers to use for resolving citations to full Paper models"""
    
    max_citations_per_paper: Optional[int] = None
    """Limit citations per paper (None = all)"""
    
    deduplicate: bool = True
    """Check if citation already exists in database before creating"""
    
    create_missing_papers: bool = True
    """Create Paper records for cited papers (vs just Citation records)"""
    
    apply_screening: bool = True
    """Apply keyword screening to newly created papers"""


@dataclass
class RetrievePDFsConfig:
    """Configuration for retrieve_pdfs step"""
    
    fetcher_config: FetcherConfig
    """PDF fetchers in priority order"""
    
    output_folder: Path
    """Base folder for storing PDFs (organized by DOI or author)"""
    
    skip_existing: bool = True
    """Don't re-download if PDF already exists"""
    
    max_concurrent_downloads: int = 4
    """Limit parallel downloads to respect rate limits"""


# ============================================================================
# STEP IMPLEMENTATIONS
# ============================================================================

class RetrieveMetadataStep:
    """
    Enrich existing Paper records with complete metadata.
    
    For papers that exist in the database but have incomplete metadata,
    fetch and update from external sources. Updates DOI, abstract,
    keywords, publication details, etc.
    
    Example workflow:
        1. load_files created Paper records with DOI
        2. retrieve_metadata fetches complete metadata
        3. Keyword screening uses full abstract/keywords
    """
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate retrieve_metadata step configuration.
        
        Required config:
        - fetcher_config: FetcherConfig with metadata fetchers
        - database_path: Path to papers database
        
        Optional config:
        - overwrite_existing: bool (default: False)
        - required_fields: List[str] (default: ["abstract", "keywords"])
        - batch_size: int (default: 100)
        """
        errors = []
        
        if "fetcher_config" not in config:
            errors.append("'fetcher_config' is required - must specify metadata fetchers")
        
        if "database_path" not in config:
            errors.append("'database_path' is required")
        
        if config.get("fetcher_config") is not None:
            fc = config["fetcher_config"]
            if not isinstance(fc, FetcherConfig):
                errors.append("'fetcher_config' must be FetcherConfig instance")
            elif len(fc.metadata_fetchers_ordered()) == 0:
                errors.append("'fetcher_config' must have at least one metadata fetcher")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def execute(config: Dict[str, Any], db: PapersDatabase) -> Dict[str, Any]:
        """
        Execute metadata retrieval for papers in database.
        
        Returns:
            {
                "total_papers": int,
                "updated_papers": int,
                "skipped": int,
                "failed": int,
                "errors": List[str]
            }
        """
        fetcher_config = config["fetcher_config"]
        overwrite = config.get("overwrite_existing", False)
        required_fields = config.get("required_fields", ["abstract", "keywords"])
        batch_size = config.get("batch_size", 100)
        
        # Get papers needing metadata
        papers_needing_metadata = _get_papers_needing_metadata(
            db, 
            required_fields if not overwrite else [],
            batch_size
        )
        
        results = {
            "total_papers": len(papers_needing_metadata),
            "updated_papers": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }
        
        for paper in papers_needing_metadata:
            if not paper.doi:
                results["skipped"] += 1
                continue
            
            try:
                enriched_paper, fetcher_name = FallbackFetcher.fetch_metadata_with_fallback(
                    fetcher_config.metadata_fetchers_ordered(),
                    paper.doi
                )
                
                if enriched_paper:
                    # Merge fetched metadata into existing Paper record
                    _merge_paper_metadata(paper, enriched_paper)
                    db.update_paper(paper)
                    results["updated_papers"] += 1
                else:
                    results["skipped"] += 1
            
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error fetching {paper.doi}: {str(e)}")
        
        return results


class RetrieveCitationsStep:
    """
    Fetch citations (backward references) for papers.
    
    Creates Citation records for each reference, optionally resolves to
    full Paper models for cited papers. Creates new Paper records for
    papers not yet in database.
    
    Example workflow:
        1. retrieve_metadata has enriched papers with full metadata
        2. retrieve_citations fetches references
        3. New papers are screened with keyword screening
        4. Selected papers move to full review
    """
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate retrieve_citations step configuration.
        
        Required config:
        - citation_fetcher: CitationFetcher instance
        - metadata_fetcher_config: FetcherConfig (for resolving citations)
        - database_path: Path to papers database
        
        Optional config:
        - max_citations_per_paper: int (default: None = unlimited)
        - deduplicate: bool (default: True)
        - create_missing_papers: bool (default: True)
        - apply_screening: bool (default: True)
        """
        errors = []
        
        if "citation_fetcher" not in config:
            errors.append("'citation_fetcher' is required")
        
        if "metadata_fetcher_config" not in config:
            errors.append("'metadata_fetcher_config' is required for resolving citations")
        
        if "database_path" not in config:
            errors.append("'database_path' is required")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def execute(config: Dict[str, Any], db: PapersDatabase) -> Dict[str, Any]:
        """
        Execute citation retrieval for papers in database.
        
        Returns:
            {
                "papers_processed": int,
                "citations_found": int,
                "new_papers_created": int,
                "duplicates_skipped": int,
                "failed": int,
                "errors": List[str]
            }
        """
        citation_fetcher = config["citation_fetcher"]
        metadata_fetcher_config = config["metadata_fetcher_config"]
        max_citations = config.get("max_citations_per_paper")
        deduplicate = config.get("deduplicate", True)
        create_papers = config.get("create_missing_papers", True)
        
        results = {
            "papers_processed": 0,
            "citations_found": 0,
            "new_papers_created": 0,
            "duplicates_skipped": 0,
            "failed": 0,
            "errors": []
        }
        
        # Get papers to fetch citations for
        papers = db.get_papers(filter_dict={"citations": {"$size": 0}})  # Papers without citations
        
        for paper in papers:
            if not paper.doi:
                continue
            
            results["papers_processed"] += 1
            
            try:
                citations = citation_fetcher.fetch_citations(paper.doi, max_citations)
                results["citations_found"] += len(citations)
                
                for citation in citations:
                    # Check if citation already exists
                    if deduplicate and db.citation_exists(citation):
                        results["duplicates_skipped"] += 1
                        continue
                    
                    # Add citation to paper
                    paper.citations.append(citation)
                    
                    # Optionally create Paper record for cited paper
                    if create_papers and citation.doi:
                        cited_paper, _ = FallbackFetcher.fetch_metadata_with_fallback(
                            metadata_fetcher_config.metadata_fetchers_ordered(),
                            citation.doi
                        )
                        if cited_paper and not db.paper_exists(citation.doi):
                            db.add_paper(cited_paper)
                            results["new_papers_created"] += 1
                
                db.update_paper(paper)
            
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error fetching citations for {paper.doi}: {str(e)}")
        
        return results


class RetrievePDFsStep:
    """
    Download PDFs for existing Paper records.
    
    Searches multiple sources (publisher, repositories, preprints) for
    openly available PDFs. Updates Paper.pdf_info and OpenAccessStatus.
    
    Example workflow:
        1. Papers selected after screening (final_decision == INCLUDED)
        2. retrieve_pdfs downloads PDFs
        3. PDFs available for text extraction and analysis
    """
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate retrieve_pdfs step configuration.
        
        Required config:
        - fetcher_config: FetcherConfig with PDF fetchers
        - output_folder: Path to store PDFs
        - database_path: Path to papers database
        
        Optional config:
        - skip_existing: bool (default: True)
        - max_concurrent_downloads: int (default: 4)
        """
        errors = []
        
        if "fetcher_config" not in config:
            errors.append("'fetcher_config' is required - must specify PDF fetchers")
        
        if "output_folder" not in config:
            errors.append("'output_folder' is required for storing PDFs")
        
        if "database_path" not in config:
            errors.append("'database_path' is required")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def execute(config: Dict[str, Any], db: PapersDatabase) -> Dict[str, Any]:
        """
        Execute PDF retrieval for papers in database.
        
        Returns:
            {
                "total_papers": int,
                "pdfs_downloaded": int,
                "already_exists": int,
                "not_found": int,
                "failed": int,
                "errors": List[str]
            }
        """
        fetcher_config = config["fetcher_config"]
        output_folder = Path(config["output_folder"])
        skip_existing = config.get("skip_existing", True)
        
        results = {
            "total_papers": 0,
            "pdfs_downloaded": 0,
            "already_exists": 0,
            "not_found": 0,
            "failed": 0,
            "errors": []
        }
        
        # Get papers to fetch PDFs for (included papers without PDFs)
        papers = db.get_papers(filter_dict={"screening.final_decision": "INCLUDED"})
        
        for paper in papers:
            if not paper.doi:
                continue
            
            results["total_papers"] += 1
            
            # Check if PDF already exists
            if skip_existing and paper.pdf_info and paper.pdf_info.file_path:
                results["already_exists"] += 1
                continue
            
            # Determine output path (e.g., output_folder/lastname_year.pdf)
            pdf_filename = _generate_pdf_filename(paper)
            output_path = output_folder / pdf_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                success, oa_status, error, fetcher_name = FallbackFetcher.fetch_pdf_with_fallback(
                    fetcher_config.pdf_fetchers_ordered(),
                    paper.doi,
                    output_path
                )
                
                if success:
                    # Update paper with PDF info and OA status
                    _update_paper_pdf_info(paper, output_path, oa_status, fetcher_name)
                    db.update_paper(paper)
                    results["pdfs_downloaded"] += 1
                else:
                    results["not_found"] += 1
                    if error:
                        results["errors"].append(f"{paper.doi}: {error}")
            
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error downloading {paper.doi}: {str(e)}")
        
        return results


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_papers_needing_metadata(
    db: PapersDatabase,
    required_fields: List[str],
    batch_size: int
) -> List[Paper]:
    """Get papers from database that are missing specified fields"""
    # Implementation depends on database query capabilities
    # Placeholder for actual implementation
    pass


def _merge_paper_metadata(target: Paper, source: Paper) -> None:
    """Merge metadata from source Paper into target Paper"""
    if not target.abstract and source.abstract:
        target.abstract = source.abstract
    if not target.keywords and source.keywords:
        target.keywords = source.keywords
    if not target.journal and source.journal:
        target.journal = source.journal
    if not target.year and source.year:
        target.year = source.year
    if not target.authors and source.authors:
        target.authors = source.authors
    # ... merge other fields


def _generate_pdf_filename(paper: Paper) -> str:
    """Generate meaningful filename for PDF (e.g., lastname_year.pdf)"""
    if paper.authors:
        lastname = paper.authors[0].family_name.lower().replace(" ", "_")
    else:
        lastname = "unknown"
    
    year = paper.year or "undated"
    return f"{lastname}_{year}.pdf"


def _update_paper_pdf_info(
    paper: Paper,
    file_path: Path,
    oa_status: Any,
    fetcher_name: str
) -> None:
    """Update Paper record with PDF file and OA information"""
    if not paper.pdf_info:
        from paper_scanner.core.models import PDFInfo
        paper.pdf_info = PDFInfo()
    
    paper.pdf_info.file_path = str(file_path)
    paper.pdf_info.file_name = file_path.name
    paper.pdf_info.download_source = fetcher_name
    paper.oa_status = oa_status
