"""
Publisher direct access handler - downloads PDFs directly from publisher sites.

Resolves DOIs to publisher landing pages and downloads PDFs directly,
leveraging institutional access (e.g., via VPN) where available.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from rich.console import Console

from paper_scanner.core.doi import DOI
from paper_scanner.core.models import Citation, PDFInfo
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler

console = Console(file=sys.stderr)

# Contact email for polite identification with publishers
EMAIL = "i.heitlager@tue.nl"

# Publisher templates - maps domain/DOI patterns to PDF download URL templates
PUBLISHER_TEMPLATES = {
    "tandfonline.com": {
        "domain": "www.tandfonline.com",
        "pdf_template": "https://www.tandfonline.com/doi/pdf/{doi}?download=true",
        "name": "Taylor & Francis",
    },
    "springer.com": {
        "domain": "link.springer.com",
        "pdf_template": "https://link.springer.com/content/pdf/{doi}.pdf",
        "name": "Springer",
    },
    "sciencedirect.com": {
        "domain": "www.sciencedirect.com",
        "pdf_template": "https://www.sciencedirect.com/science/article/pii/{pii}/pdf?isDTMRedir=true",
        "name": "Elsevier",
    },
    "wiley.com": {
        "domain": "onlinelibrary.wiley.com",
        "pdf_template": "https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",
        "name": "Wiley",
    },
    "ieee.org": {
        "domain": "ieeexplore.ieee.org",
        "pdf_template": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={ieee_id}",
        "name": "IEEE",
    },
    "arxiv.org": {
        "pattern": r"10\.48550/arxiv\.(\d+\.\d+)",
        "domain": "arxiv.org",
        "pdf_template": "https://arxiv.org/pdf/{}.pdf",
        "name": "arXiv",
        "doi_extract_group": 1,
    },
    "plos.org": {
        "pattern": r"10\.1371/journal",
        "domain": "journals.plos.org",
        "pdf_template": "https://journals.plos.org/plosone/article/file?id={}&type=printable",
        "name": "PLOS",
    },
    "mdpi.com": {
        "pattern": r"10\.3390/",
        "domain": "www.mdpi.com",
        "pdf_template": "https://www.mdpi.com/{}/pdf",
        "name": "MDPI",
    },
}

# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 15


class PublisherHandler(BaseFetcherHandler):
    """Downloads PDFs directly from publisher websites via DOI resolution."""

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False):
        """
        Initialize Publisher handler.

        Args:
            cache_dir: Cache directory
            debug: Enable debug output
            verbose: Enable verbose output
        """
        super().__init__(cache_dir, debug=debug, verbose=verbose)
        self.session = requests.Session()
        # Set polite headers with identification
        self.session.headers.update({
            "User-Agent": f"Automated Literature Review Scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})"
        })

    @property
    def name(self) -> str:
        """Fetcher name."""
        return "publisher"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Not implemented for publisher handler.

        Publisher handler works directly with DOI resolution, not via API metadata.
        """
        raise NotImplementedError("PublisherHandler does not use API metadata fetching")

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract metadata")

    def _extract_citations(self, api_data: Dict[str, Any]) -> list:
        """Not implemented."""
        raise NotImplementedError("PublisherHandler does not extract citations")

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Not implemented - use fetch_pdf instead."""
        raise NotImplementedError("PublisherHandler uses fetch_pdf directly")

    def _resolve_doi_to_landing_page(self, doi: str) -> Optional[str]:
        """
        Resolve DOI to publisher landing page.

        Follows redirects from https://doi.org/{doi} to final landing page.

        Args:
            doi: Digital Object Identifier

        Returns:
            Final landing page URL, or None if resolution fails
        """
        try:
            normalized = DOI(doi).stem
            doi_url = f"https://doi.org/{normalized}"

            if self.debug:
                console.print(f"  [dim]Resolving DOI: {doi_url}[/dim]")

            response = self.session.get(
                doi_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()

            final_url = response.url
            if self.debug:
                console.print(f"  [dim]Resolved to: {final_url}[/dim]")

            return final_url

        except Exception as e:
            if self.debug:
                console.print(f"  [yellow]Failed to resolve DOI {doi}: {e}[/yellow]")
            return None

    def _detect_publisher(self, landing_url: str, doi: Optional[str] = None) -> Optional[str]:
        """
        Detect publisher from landing page URL or DOI pattern.

        Args:
            landing_url: URL of the landing page
            doi: Digital Object Identifier for pattern-based detection

        Returns:
            Publisher key from PUBLISHER_TEMPLATES, or None if not recognized
        """
        # First try domain-based detection for web publishers
        for publisher_key, config in PUBLISHER_TEMPLATES.items():
            if "domain" in config and config["domain"] in landing_url:
                if self.debug:
                    console.print(f"  [green]Detected publisher: {config['name']}[/green]")
                return publisher_key

        # Then try DOI pattern-based detection for publishers like arXiv, PLOS, MDPI
        if doi:
            for publisher_key, config in PUBLISHER_TEMPLATES.items():
                if "pattern" in config:
                    pattern = config["pattern"]
                    match = re.search(pattern, doi)
                    if match:
                        if self.debug:
                            console.print(f"  [green]Detected publisher by DOI pattern: {config['name']}[/green]")
                        return publisher_key

        return None

    def _extract_pdf_url_from_landing_page(self, landing_url: str, publisher_key: str, doi: str) -> Optional[str]:
        """
        Extract or construct PDF download URL for the publisher.

        Args:
            landing_url: URL of the landing page
            publisher_key: Publisher identifier from PUBLISHER_TEMPLATES
            doi: Digital Object Identifier

        Returns:
            PDF download URL, or None if not available
        """
        template = PUBLISHER_TEMPLATES[publisher_key]
        pdf_template = template["pdf_template"]

        # Construct PDF URL from template
        try:
            # For pattern-based publishers (arXiv, PLOS, MDPI)
            if "pattern" in template:
                pattern = template["pattern"]
                match = re.search(pattern, doi)
                if not match:
                    return None

                # If doi_extract_group is specified, extract that group; otherwise use full DOI
                if "doi_extract_group" in template:
                    extracted_value = match.group(template["doi_extract_group"])
                    pdf_url = pdf_template.format(extracted_value)
                else:
                    # Use full DOI for template with {} placeholder
                    pdf_url = pdf_template.format(doi)
            else:
                # Standard DOI-based URL construction
                pdf_url = pdf_template.format(doi=doi)

            if self.debug:
                console.print(f"[blue]Generated PDF URL: {pdf_url}[/blue]")

            return pdf_url

        except (KeyError, IndexError) as e:
            # Some publishers need additional parameters (like PII for ScienceDirect)
            if self.debug:
                console.print(f"  [yellow]Template requires parameter: {e}[/yellow]")
            return None

    def fetch_pdf(self, doi: str, timeout: int = 30) -> Optional[PDFInfo]:
        """
        Download PDF directly from publisher via DOI resolution.

        Process:
        1. Resolve DOI to publisher landing page (or detect by DOI pattern)
        2. Detect publisher from URL or DOI pattern
        3. Construct PDF download URL using publisher template
        4. Download PDF with institutional access headers

        Args:
            doi: Digital Object Identifier

        Returns:
            PDFInfo with file path and metadata, or None if download fails
        """
        import tempfile

        # Try pattern-based detection first (for arXiv, PLOS, MDPI)
        publisher_key = None
        for pk, config in PUBLISHER_TEMPLATES.items():
            if "pattern" in config:
                pattern = config["pattern"]
                match = re.search(pattern, doi)
                if match:
                    publisher_key = pk
                    if self.debug:
                        console.print(f"  [green]Detected {config['name']} by DOI pattern[/green]")
                    break

        # If not pattern-based, resolve DOI to landing page and detect by domain
        landing_url = None
        if not publisher_key:
            landing_url = self._resolve_doi_to_landing_page(doi)
            if not landing_url:
                if self.debug:
                    console.print(f"  [yellow]Could not resolve DOI: {doi}[/yellow]")
                return None

            publisher_key = self._detect_publisher(landing_url, doi)

        if not publisher_key:
            if self.debug:
                if landing_url:
                    console.print(f"  [yellow]Unsupported publisher for: {landing_url}[/yellow]")
                else:
                    console.print(f"  [yellow]Unsupported publisher for DOI: {doi}[/yellow]")
            return None

        publisher_name = PUBLISHER_TEMPLATES[publisher_key]["name"]

        # Step 3: Construct PDF URL
        pdf_url = self._extract_pdf_url_from_landing_page(landing_url or "", publisher_key, doi)
        if not pdf_url:
            if self.debug:
                console.print(f"  [yellow]Could not construct PDF URL for {publisher_name}[/yellow]")
            return None

        # Step 4: Download PDF
        try:
            response = self.session.get(
                pdf_url,
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                if self.debug:
                    console.print(f"  [yellow]Got HTML instead of PDF from {publisher_name}[/yellow]")
                return None

            if 'pdf' not in content_type and 'octet-stream' not in content_type:
                if self.debug:
                    console.print(f"  [yellow]Unexpected content type: {content_type}[/yellow]")
                return None

            # Write to temporary file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(response.content)
                pdf_path = Path(tmp_file.name)

                if self.debug:
                    console.print(
                        f" [dim]Downloaded PDF from {publisher_name} ({len(response.content)} bytes)[/dim]"
                    )

                return PDFInfo(
                    file_path=str(pdf_path),
                    file_size_bytes=pdf_path.stat().st_size,
                    download_source=self.name,
                    download_url=pdf_url,
                )

        except Exception as e:
            if self.debug:
                console.print(f"  [yellow]Failed to download from {publisher_name}: {e}[/yellow]")
            return None


    ###################################################################################
    # Not implemented methods for citations fetching
    # PublisherHandler only downloads PDFs via fetch_pdf
    ###################################################################################
    def fetch_cited_by(self, doi: str, limit: int = 100) -> Tuple[List[Citation], bool]:
        """Not implemented - publisher handler only downloads PDFs."""
        raise NotImplementedError("PublisherHandler only downloads PDFs via fetch_pdf")

    def fetch_metadata(self, doi: str) -> Optional[Dict[str, Any]]:
        """Not implemented - publisher handler only downloads PDFs."""
        raise NotImplementedError("PublisherHandler only downloads PDFs via fetch_pdf")

    def fetch_paper(self, doi: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Not implemented - publisher handler only downloads PDFs."""
        raise NotImplementedError("PublisherHandler only downloads PDFs via fetch_pdf")

    def fetch_citations(self, doi: str) -> Tuple[List[Citation], bool]:
        """Not implemented - publisher handler only downloads PDFs."""
        raise NotImplementedError("PublisherHandler only downloads PDFs via fetch_pdf")
