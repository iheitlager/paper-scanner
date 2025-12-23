#!/usr/bin/env python3
"""
Download Papers - Batch PDF Download for Screened Papers

Downloads PDFs for papers that passed screening stages (stage2_pass/stage2_review)
from multiple sources in order of preference.

Usage:
    python download_papers.py [-o/--out-dir <dir>] [--db-url <url>] [--dry-run]

Default output: ../papers (~/wc/papers when run from spike directory)

Sources (in order of preference):
    1. Unpaywall (legal, free, open access)
    2. OpenAlex (legal, free, indexed papers)
    3. CORE (legal, free, requires API key)
    4. Publisher (via institutional access)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# Load environment
load_dotenv()

# Initialize console
console = Console()

# Cache file for tracking visited DOIs
CACHE_FILE = Path.home() / ".pdf_downloader"


class MultiSourcePDFDownloader:
    """
    Try multiple sources in order of preference:
    1. Unpaywall (legal, free)
    2. OpenAlex (legal, free)
    3. CORE (legal, free, requires API key)
    4. Publisher (via institutional access)
    """

    def __init__(self, email: str, download_dir: str = "./pdfs"):
        self.email = email
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'PDFDownloader/1.0 (mailto:{email})'
        })

        self.stats = {
            'unpaywall': 0,
            'openalex': 0,
            'core': 0,
            'publisher': 0,
            'publisher_scrape': 0,
            'semantic_scholar': 0,
            'pmc': 0,
            'europe_pmc': 0,
            'arxiv': 0,
            'base': 0,
            'crossref_metadata': 0,
            'failed': 0,
            'skipped': 0
        }

        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, List[str]]:
        """Load cache of visited DOIs and their attempted sources."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save cache of visited DOIs and attempted sources."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            console.print(f"[yellow]⚠️  Warning: Could not save cache file: {e}[/yellow]")

    def _get_attempted_sources(self, doi: str) -> List[str]:
        """Get list of sources already attempted for a DOI."""
        return self.cache.get(doi, [])

    def _record_attempt(self, doi: str, source: str) -> None:
        """Record that a source was attempted for a DOI."""
        if doi not in self.cache:
            self.cache[doi] = []
        if source not in self.cache[doi]:
            self.cache[doi].append(source)
        self._save_cache()

    def download_pdf(self, doi: str, title: str = None, paper_id: int = None, progress_callback=None) -> dict:
        """
        Try all methods to download PDF

        Args:
            doi: DOI of the paper
            title: Title of the paper
            paper_id: ID in database
            progress_callback: Optional callback to report current source being tried

        Returns:
            dict with success, method, filepath
        """

        result = {
            'doi': doi,
            'title': title,
            'paper_id': paper_id,
            'success': False,
            'method': None,
            'filepath': None,
            'error': None
        }

        # Check if file already exists
        filename = doi.replace('/', '_').replace('.', '_') + '.pdf'
        filepath = self.download_dir / filename

        if filepath.exists():
            result.update({
                'success': True,
                'method': 'cached',
                'filepath': str(filepath)
            })
            self.stats['skipped'] += 1
            return result

        # Try all methods with progress callback
        methods = [
            ('unpaywall', self._try_unpaywall),
            ('openalex', self._try_openalex),
            ('semantic_scholar', self._try_semantic_scholar),
            ('pmc', self._try_pmc),
            ('europe_pmc', self._try_europe_pmc),
            ('arxiv', self._try_arxiv),
            ('core', self._try_core),
            ('base', self._try_base),
            ('crossref_metadata', self._try_crossref_metadata),
            ('publisher_scrape', self._try_publisher_scrape),
            ('publisher', self._try_publisher),
        ]

        for method_name, method_func in methods:
            if progress_callback:
                progress_callback(method_name)

            filepath = method_func(doi)
            if filepath:
                self._record_attempt(doi, method_name)
                result.update({
                    'success': True,
                    'method': method_name,
                    'filepath': filepath
                })
                self.stats[method_name] += 1
                return result
            self._record_attempt(doi, method_name)

        result['error'] = 'No PDF found via any method'
        self.stats['failed'] += 1
        return result

    def _try_unpaywall(self, doi: str) -> Optional[str]:
        """Try Unpaywall"""
        try:
            url = f"https://api.unpaywall.org/v2/{doi}"
            response = self.session.get(url, params={'email': self.email}, timeout=10)

            if response.status_code == 200:
                data = response.json()
                oa_location = data.get('best_oa_location')

                if oa_location:
                    pdf_url = oa_location.get('url_for_pdf') or oa_location.get('url')
                    if pdf_url:
                        return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_openalex(self, doi: str) -> Optional[str]:
        """Try OpenAlex"""
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Check for open access PDF
                oa_url = data.get('open_access', {}).get('oa_url')
                if oa_url:
                    return self._download_from_url(oa_url, doi)

                # Check primary location
                primary = data.get('primary_location', {})
                pdf_url = primary.get('pdf_url')
                if pdf_url:
                    return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_core(self, doi: str) -> Optional[str]:
        """Try CORE (requires API key)"""
        # CORE requires API key - skip if not available
        core_api_key = os.environ.get("CORE_API_KEY")
        if not core_api_key:
            return None

        try:
            url = f"https://api.core.ac.uk/v3/works/search/doi:{doi}"
            headers = {'Authorization': f'Bearer {core_api_key}'}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                if results:
                    work = results[0]
                    pdf_url = work.get('fileLocation') or work.get('downloadUrl')
                    if pdf_url:
                        return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_publisher(self, doi: str) -> Optional[str]:
        """Try publisher site (requires institutional access)"""
        try:
            doi_url = f"https://doi.org/{doi}"
            response = self.session.get(doi_url, timeout=30, allow_redirects=True)

            # Try to find PDF URL in page
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')

                # Look for PDF meta tag
                pdf_meta = soup.find('meta', {'name': 'citation_pdf_url'})
                if pdf_meta:
                    pdf_url = pdf_meta.get('content')
                    return self._download_from_url(pdf_url, doi)
            except ImportError:
                pass

        except Exception:
            pass

        return None

    def _try_semantic_scholar(self, doi: str) -> Optional[str]:
        """Try Semantic Scholar - has PDF links for many papers"""
        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            params = {'fields': 'openAccessPdf,isOpenAccess'}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                oa_pdf = data.get('openAccessPdf')
                if oa_pdf and oa_pdf.get('url'):
                    return self._download_from_url(oa_pdf['url'], doi)
        except Exception:
            pass

        return None

    def _try_pmc(self, doi: str) -> Optional[str]:
        """Try PubMed Central - free full-text repository"""
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                'db': 'pmc',
                'term': f'{doi}[DOI]',
                'retmode': 'json'
            }
            response = self.session.get(search_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                id_list = data.get('esearchresult', {}).get('idlist', [])

                if id_list:
                    pmc_id = id_list[0]
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                    return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_europe_pmc(self, doi: str) -> Optional[str]:
        """Try Europe PMC - European PubMed Central"""
        try:
            search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            params = {
                'query': f'DOI:"{doi}"',
                'format': 'json',
                'resultType': 'core'
            }
            response = self.session.get(search_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get('resultList', {}).get('result', [])

                if results:
                    result = results[0]
                    if result.get('isOpenAccess') == 'Y':
                        pmcid = result.get('pmcid')
                        if pmcid:
                            pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render"
                            return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_arxiv(self, doi: str) -> Optional[str]:
        """Try arXiv - preprint repository"""
        try:
            search_url = "http://export.arxiv.org/api/query"
            params = {
                'search_query': f'doi:{doi}',
                'max_results': 1
            }
            response = self.session.get(search_url, params=params, timeout=10)

            if response.status_code == 200 and 'entry' in response.text:
                match = re.search(r'arxiv.org/abs/([0-9.]+)', response.text)
                if match:
                    arxiv_id = match.group(1)
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    return self._download_from_url(pdf_url, doi)
        except Exception:
            pass

        return None

    def _try_base(self, doi: str) -> Optional[str]:
        """Try BASE - Bielefeld Academic Search Engine"""
        try:
            search_url = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"
            params = {
                'func': 'PerformSearch',
                'query': f'dcdoi:{doi}',
                'format': 'json'
            }
            response = self.session.get(search_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                docs = data.get('response', {}).get('docs', [])

                for doc in docs:
                    urls = doc.get('dclink', [])
                    for url in urls:
                        if url.endswith('.pdf'):
                            result = self._download_from_url(url, doi)
                            if result:
                                return result
        except Exception:
            pass

        return None

    def _try_publisher_scrape(self, doi: str) -> Optional[str]:
        """Try publisher site with improved HTML scraping for PDF links"""
        try:
            doi_url = f"https://doi.org/{doi}"
            response = self.session.get(doi_url, timeout=30, allow_redirects=True)

            if response.status_code == 200:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Try multiple patterns to find PDF link
                    pdf_patterns = [
                        # Meta tags
                        soup.find('meta', {'name': 'citation_pdf_url'}),
                        soup.find('meta', {'property': 'citation_pdf_url'}),

                        # Common link patterns
                        soup.find('a', {'class': lambda x: x and 'pdf' in x.lower()}),
                        soup.find('a', {'id': lambda x: x and 'pdf' in x.lower()}),

                        # Links with href containing 'pdf'
                        soup.find('a', href=lambda x: x and ('.pdf' in x.lower() or 'pdf' in x.lower())),

                        # Direct PDF endpoint patterns
                        soup.find('a', {'class': 'pdf-download'}),
                        soup.find('a', {'class': 'download-pdf'}),
                    ]

                    for element in pdf_patterns:
                        if element:
                            pdf_url = None
                            if element.name == 'meta':
                                pdf_url = element.get('content')
                            else:
                                pdf_url = element.get('href')

                            if pdf_url:
                                # Make absolute URL
                                if pdf_url.startswith('/'):
                                    from urllib.parse import urljoin
                                    pdf_url = urljoin(response.url, pdf_url)
                                elif not pdf_url.startswith('http'):
                                    from urllib.parse import urljoin
                                    pdf_url = urljoin(response.url, pdf_url)

                                result = self._download_from_url(pdf_url, doi)
                                if result:
                                    return result
                except ImportError:
                    pass

        except Exception:
            pass

        return None

    def _try_crossref_metadata(self, doi: str) -> Optional[str]:
        """Try Crossref metadata for PDF links"""
        try:
            url = f"https://api.crossref.org/works/{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()['message']

                # Check for links
                links = data.get('link', [])
                for link in links:
                    if link.get('content-type') == 'application/pdf':
                        pdf_url = link.get('URL')
                        result = self._download_from_url(pdf_url, doi)
                        if result:
                            return result
        except Exception:
            pass

        return None

    def _download_from_url(self, url: str, doi: str) -> Optional[str]:
        """Download PDF from URL"""
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)

            if response.status_code == 200:
                # Verify it's a PDF
                if not response.content.startswith(b'%PDF'):
                    return None

                filename = doi.replace('/', '_').replace('.', '_') + '.pdf'
                filepath = self.download_dir / filename

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return str(filepath)
        except Exception:
            pass

        return None


class PaperDownloader:
    """Manage batch paper downloads from database."""

    def __init__(self, db_url: str, download_dir: str = "../papers"):
        self.db_url = db_url
        self.download_dir = Path(download_dir)
        self.conn = None
        self.downloader = None

    def connect(self) -> bool:
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            return True
        except psycopg2.Error as e:
            console.print(f"[red]❌ Connection failed: {e}[/red]")
            return False

    def disconnect(self) -> None:
        """Close connection."""
        if self.conn:
            self.conn.close()

    def get_papers_to_download(self, include_cached: bool = False) -> tuple:
        """
        Get papers with stage2_pass or stage2_review status.

        Args:
            include_cached: If False, exclude papers with file_path already set

        Returns:
            Tuple of (papers_to_download, papers_cached)
        """
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT 
            p.id, 
            p.citekey, 
            p.doi, 
            p.title, 
            p.year,
            p.file_path,
            ps.screening_stage,
            ps.semantic_similarity
        FROM papers p
        JOIN paper_screening ps ON p.id = ps.paper_id
        WHERE ps.screening_stage IN ('stage2_pass', 'stage2_review')
          AND p.doi IS NOT NULL
        ORDER BY ps.semantic_similarity DESC NULLS LAST
        """

        cursor.execute(query)
        papers = cursor.fetchall()
        cursor.close()

        papers = [dict(row) for row in papers]

        # Separate papers with and without file_path
        cached = [p for p in papers if p.get('file_path')]
        to_download = [p for p in papers if not p.get('file_path')]

        if include_cached:
            return papers, []
        else:
            return to_download, cached

    def download_papers(self, dry_run: bool = False) -> dict:
        """
        Download all papers with stage2_pass or stage2_review status.

        Args:
            dry_run: If True, don't actually download, just show what would happen

        Returns:
            Summary statistics
        """
        to_download, cached = self.get_papers_to_download(include_cached=False)

        if not to_download and not cached:
            console.print(f"[yellow]⚠️  No papers found for {stage}[/yellow]")
            return {}

        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print("[bold cyan]📥 PAPER DOWNLOAD MANAGER[/bold cyan]")
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print()

        # Show overview
        total = len(to_download) + len(cached)
        abs_path = self.download_dir.resolve()
        console.print("[bold]Source:[/bold] [cyan]stage2_pass / stage2_review[/cyan]")
        console.print(f"[bold]Destination:[/bold] [yellow]{abs_path}[/yellow]")
        console.print(f"[bold]Papers to process:[/bold] [green]{total}[/green]")
        console.print(f"  [green]✓ Need download:[/green] {len(to_download)} papers")
        console.print(f"  [blue]✓ Already cached:[/blue] {len(cached)} papers")
        console.print()

        if not to_download:
            console.print("[bold green]✓ All papers already downloaded![/bold green]")
            self._display_cached_overview(cached)
            return {}

        # Initialize downloader
        email = os.environ.get("RESEARCHER_EMAIL", "iheitlager@tue.nl")
        self.downloader = MultiSourcePDFDownloader(
            email=email,
            download_dir=str(self.download_dir)
        )

        # Show cache status
        cache_size = len(self.downloader.cache)
        if cache_size > 0:
            console.print(f"[blue]📋 Cache loaded:[/blue] {cache_size} DOIs from previous attempts")

        if dry_run:
            console.print("[bold yellow]⚠️  DRY RUN MODE - No files will be downloaded[/bold yellow]")
            console.print()

        # Progress bar for downloads
        download_stats = {
            'visited': 0,
            'downloaded': 0,
            'not_found': 0,
            'skipped_cached': 0
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("", total=len(to_download))

            for i, paper in enumerate(to_download, 1):
                citekey = paper['citekey']
                download_stats['visited'] += 1

                doi = paper['doi']

                # Skip if already visited in previous runs (all sources attempted)
                attempted_sources = self.downloader._get_attempted_sources(doi)
                if attempted_sources and len(attempted_sources) >= 11:  # All 11 sources tried
                    download_stats['skipped_cached'] += 1
                    sources_str = ", ".join(attempted_sources[:3])
                    if len(attempted_sources) > 3:
                        sources_str += f", +{len(attempted_sources)-3} more"
                    status_text = f"""[cyan]{citekey:<35}[/cyan] ({i}/{len(to_download)})
  [dim]DOI:[/dim] {doi[:50] if doi else 'N/A'}
  [yellow]⊘ Skipped[/yellow] (tried: {sources_str})"""
                    progress.update(task, description=status_text)
                    progress.advance(task)
                    time.sleep(0.1)
                    continue

                # Multiline status update
                status_text = f"""[cyan]{citekey:<35}[/cyan] ({i}/{len(to_download)})
  [dim]DOI:[/dim] {paper['doi'][:50] if paper['doi'] else 'N/A'}
  [dim]Status:[/dim] Searching sources... [blue]({download_stats['downloaded']} downloaded so far)[/blue]"""

                progress.update(task, description=status_text)

                if dry_run:
                    progress.advance(task)
                    time.sleep(0.1)
                    continue

                doi = paper['doi']

                # Create callback to update progress with current source
                current_source = {'name': 'initializing'}
                def progress_callback(source_name):
                    current_source['name'] = source_name
                    status_text = f"""[cyan]{citekey:<35}[/cyan] ({i}/{len(to_download)})
  [dim]DOI:[/dim] {paper['doi'][:50] if paper['doi'] else 'N/A'}
  [dim]Trying:[/dim] {source_name}... [blue]({download_stats['downloaded']} downloaded so far)[/blue]"""
                    progress.update(task, description=status_text)

                result = self.downloader.download_pdf(
                    doi,
                    title=paper['title'],
                    paper_id=paper['id'],
                    progress_callback=progress_callback
                )

                if result['success']:
                    download_stats['downloaded'] += 1

                    # Update database with file_path
                    cursor = self.conn.cursor()
                    cursor.execute("""
                        UPDATE papers
                        SET file_path = %s
                        WHERE id = %s
                    """, (result['filepath'], paper['id']))
                    self.conn.commit()
                    cursor.close()

                    # Success status
                    status_text = f"""[cyan]{citekey:<35}[/cyan] ({i}/{len(to_download)})
  [dim]DOI:[/dim] {paper['doi'][:50] if paper['doi'] else 'N/A'}
  [green]✓ Downloaded via {result['method']}[/green] [blue]({download_stats['downloaded']}/{len(to_download)} total)[/blue]"""
                else:
                    download_stats['not_found'] += 1

                    # Failed status
                    status_text = f"""[cyan]{citekey:<35}[/cyan] ({i}/{len(to_download)})
  [dim]DOI:[/dim] {paper['doi'][:50] if paper['doi'] else 'N/A'}
  [red]✗ Not found via any source[/red] [blue]({download_stats['downloaded']}/{len(to_download)} total)[/blue]"""

                progress.update(task, description=status_text)
                progress.advance(task)
                time.sleep(1)  # Be polite - wait 1 second between downloads

        # Display summary
        self._display_summary(to_download, cached, dry_run, download_stats)

        return self.downloader.stats

    def _display_cached_overview(self, cached: List[dict]) -> None:
        """Display overview of cached papers."""
        if not cached:
            return

        console.print()
        console.print("[bold green]📦 ALREADY CACHED PAPERS[/bold green]")
        console.print(f"[dim]{len(cached)} paper(s) already have file_path set[/dim]")
        console.print()

        # Create table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Citekey", style="cyan")
        table.add_column("DOI", style="dim")
        table.add_column("Title", style="white")
        table.add_column("Year", justify="right", style="yellow")

        for paper in cached[:10]:  # Show first 10
            title = (paper['title'][:40] + "...") if len(paper['title']) > 40 else paper['title']
            table.add_row(
                paper['citekey'],
                paper['doi'][:30] if paper['doi'] else "-",
                title,
                str(paper['year']) if paper['year'] else "-"
            )

        if len(cached) > 10:
            table.add_row("[dim]...[/dim]", "[dim]...[/dim]", f"[dim]and {len(cached)-10} more[/dim]", "")

        console.print(table)
        console.print()

    def _display_summary(self, to_download: List[dict], cached: List[dict], dry_run: bool, download_stats: Dict = None) -> None:
        """Display download summary with colorful overview."""
        if download_stats is None:
            download_stats = {'visited': 0, 'downloaded': 0, 'not_found': 0}

        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print("[bold cyan]📊 DOWNLOAD SUMMARY[/bold cyan]")
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print()

        if dry_run:
            console.print("[bold yellow]DRY RUN RESULTS[/bold yellow]")
            abs_path = self.download_dir.resolve()
            console.print(f"Would download {len(to_download)} papers to:")
            console.print(f"  [yellow]{abs_path}[/yellow]")
            if cached:
                console.print(f"Already cached: {len(cached)} papers")
            console.print()
            return

        # Display tracking stats
        console.print("[bold]Processing Stats:[/bold]")
        console.print(f"  [cyan]Papers Visited:[/cyan]          {download_stats['visited']:3d}")
        console.print(f"  [green]Papers Downloaded:[/green]     {download_stats['downloaded']:3d}")
        console.print(f"  [blue]Already Cached:[/blue]         {len(cached):3d}")
        console.print(f"  [yellow]Skipped (Tried Before):[/yellow] {download_stats.get('skipped_cached', 0):3d}")
        console.print(f"  [red]Not Found:[/red]                {download_stats['not_found']:3d}")
        console.print()

        stats = self.downloader.stats
        total_success = sum(v for k, v in stats.items() if k != 'failed' and k != 'skipped')
        total_attempted = len(to_download)

        # Success rate indicators
        if total_attempted > 0:
            success_rate = 100 * total_success / total_attempted
            if success_rate >= 80:
                success_color = "green"
                success_emoji = "✓"
            elif success_rate >= 50:
                success_color = "yellow"
                success_emoji = "⚠"
            else:
                success_color = "red"
                success_emoji = "✗"
        else:
            success_rate = 0
            success_color = "dim"
            success_emoji = "-"

        # Create summary table
        summary_table = Table(show_header=False, border_style="blue")
        summary_table.add_column("Metric", style="cyan", width=25)
        summary_table.add_column("Count", justify="right", style="bold")
        summary_table.add_column("Percentage", justify="right", style="yellow")

        summary_table.add_row(
            "[bold]Total Attempted[/bold]",
            str(total_attempted),
            "-"
        )

        summary_table.add_row(
            f"[{success_color}]{success_emoji} Successfully Downloaded[/{success_color}]",
            f"[{success_color}]{total_success}[/{success_color}]",
            f"[{success_color}]{success_rate:.1f}%[/{success_color}]"
        )

        if stats['failed'] > 0:
            console.print(summary_table)

        summary_table.add_row(
            "[red]✗ Failed[/red]",
            f"[red]{stats['failed']}[/red]",
            f"[red]{100*stats['failed']/total_attempted:.1f}%[/red]"
        )

        summary_table.add_row(
            "[blue]✓ Cached (skipped)[/blue]",
            f"[blue]{stats['skipped']}[/blue]",
            "-"
        )

        console.print(summary_table)

        # Download methods breakdown
        console.print()
        console.print("[bold]Download Methods Breakdown:[/bold]")
        console.print()

        methods_table = Table(show_header=True, header_style="bold magenta", border_style="magenta")
        methods_table.add_column("Source", style="cyan")
        methods_table.add_column("Count", justify="right", style="yellow")
        methods_table.add_column("Percentage", justify="right")
        methods_table.add_column("Bar", width=30)

        sources = [
            ('unpaywall', '[cyan]Unpaywall[/cyan]'),
            ('openalex', '[green]OpenAlex[/green]'),
            ('core', '[yellow]CORE[/yellow]'),
            ('publisher', '[magenta]Publisher[/magenta]'),
        ]

        max_count = max([stats[s[0]] for s in sources] + [1])

        for key, label in sources:
            count = stats[key]
            if total_success > 0:
                pct = 100 * count / total_success
            else:
                pct = 0

            # Create bar
            bar_length = int(count * 20 / max_count) if max_count > 0 else 0
            if key == 'unpaywall':
                bar = '[cyan]' + '█' * bar_length + '[/cyan]' + '░' * (20 - bar_length)
            elif key == 'openalex':
                bar = '[green]' + '█' * bar_length + '[/green]' + '░' * (20 - bar_length)
            elif key == 'core':
                bar = '[yellow]' + '█' * bar_length + '[/yellow]' + '░' * (20 - bar_length)
            else:
                bar = '[magenta]' + '█' * bar_length + '[/magenta]' + '░' * (20 - bar_length)

            methods_table.add_row(
                label,
                str(count),
                f"{pct:.1f}%" if total_success > 0 else "-",
                bar
            )

        console.print(methods_table)

        # Files location - prominently displayed
        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        abs_path = self.download_dir.resolve()
        console.print("[bold green]✓ DOWNLOAD COMPLETE[/bold green]")
        console.print("[bold]Files saved to:[/bold]")
        console.print(f"  [yellow]{abs_path}[/yellow]")
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")

        # Additional info
        if cached:
            console.print(f"[bold]Already cached:[/bold] [blue]{len(cached)}[/blue] papers (not re-downloaded)")

        console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Download PDFs for screened papers (stage2_pass/stage2_review)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all stage2_pass/stage2_review papers
  python download_papers.py
  
  # Download to specific directory
  python download_papers.py -o ~/downloads/papers
  
  # Dry run to see what would be downloaded
  python download_papers.py --dry-run
        """
    )

    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfuser@localhost/pdfdb"),
        help="PostgreSQL connection URL (default: env DATABASE_URL or localhost)"
    )

    parser.add_argument(
        "-o", "--out-dir",
        default="../papers",
        help="Output directory for downloaded PDFs (default: ../papers - one level up from spike directory)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading"
    )

    parser.add_argument(
        "-c", "--clear-cache",
        action="store_true",
        help="Clear the DOI cache file (~/.pdf_downloader) and exit"
    )

    args = parser.parse_args()

    load_dotenv()

    # Handle --clear-cache option
    if args.clear_cache:
        if CACHE_FILE.exists():
            try:
                CACHE_FILE.unlink()
                console.print(f"[green]✓ Cache cleared:[/green] {CACHE_FILE}")
            except IOError as e:
                console.print(f"[red]✗ Error clearing cache:[/red] {e}")
                sys.exit(1)
        else:
            console.print(f"[dim]Cache file does not exist:[/dim] {CACHE_FILE}")
        sys.exit(0)

    # Create output directory
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    downloader = PaperDownloader(args.db_url, args.out_dir)

    try:
        if not downloader.connect():
            sys.exit(1)

        downloader.download_papers(dry_run=args.dry_run)

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]⏸️  Download interrupted by user (CTRL-C)[/bold yellow]")
        abs_path = downloader.download_dir.resolve()
        console.print("[dim]Papers downloaded so far are saved to:[/dim]")
        console.print(f"  [yellow]{abs_path}[/yellow]")
        console.print("[dim]You can resume downloading the remaining papers later.[/dim]")
        console.print()
        sys.exit(0)

    finally:
        downloader.disconnect()


if __name__ == "__main__":
    main()
