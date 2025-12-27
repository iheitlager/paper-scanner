"""
Load files step - Load PDF files from folder, extract DOI, fetch metadata from Crossref

Processes PDF files:
1. Scans folder for PDF files
2. Extracts DOI from each PDF
3. Stores papers in database
4. caches PDF in pdf store
5. Copies PDF to store_path with DOI-based filename
6. Updates PDFInfo with file details
"""
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from paper_scanner.core.cache import PDFCache

from ..core.enum import DiscoveryMethod, StepStatus
from ..core.doi import DOI
from ..core.exceptions import ConfigurationError, StepFatalError
from ..core.models import Discovery, Paper, PDFInfo
from ..core.step_result import StepResult
from ..tools.documents import FileReader
from .base import BaseStep

console = Console(file=sys.stderr)



# Class-based step interface (new architecture)
class LoadFilesStep(BaseStep):
    """Wrapper for load_files step (legacy function-based)."""

    @staticmethod
    def validate(config):
        """
        Validate load_files step configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        if "file_path" not in config:
            errors.append("'file_path' is required")
        if "store_path" not in config:
            errors.append("'store_path' is required")

        for key in config.keys():
            if key == "limit":
                limit = config["limit"]
                if not isinstance(limit, int) or limit <= 0:
                    errors.append("'limit' must be a positive integer")
            elif key == "randomize":
                randomize = config["randomize"]
                if not isinstance(randomize, bool):
                    errors.append("'randomize' must be a boolean")
            elif key == "random_seed":
                seed = config["random_seed"]
                if not isinstance(seed, int):
                    errors.append("'random_seed' must be an integer")
            elif key == "file_path":
                file_path = config.get("file_path")
                if not isinstance(file_path, str):
                    errors.append("'file_path' must be a string")
            elif key == "store_path":
                store_path = config.get("store_path")
                if not isinstance(store_path, str):
                    errors.append("'store_path' must be a string")
            elif key == "expected_count":
                expected = config["expected_count"]
                if not isinstance(expected, int) or expected < 0:
                    errors.append("'expected_count' must be a non-negative integer")
            else:
                errors.append(f"Unknown configuration key: {key}")

        return len(errors) == 0, errors


    def execute(self, config, verbose=False, dry_run=False, debug=False):
        """
        Execute load_files step

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't actually store files or modify database
            debug: Enable debug output

        Returns:
            StepResult with execution results

        Raises:
            ConfigurationError: Invalid file path configuration
            StepFatalError: File system or database errors
        """

        file_path = Path(config.get("file_path", "")).expanduser()
        randomize = config.get("randomize", False)
        random_seed = config.get("random_seed", None)
        limit = config.get("limit", None)
        store_path = Path(config.get("store_path", "")).expanduser()
        expected_count = config.get("expected_count")

        # Validate paths exist and are accessible
        if not file_path.exists() or not file_path.is_dir():
            raise ConfigurationError(f"File path does not exist or is not a directory: {file_path}")
        
        # Create store path if needed
        try:
            store_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Cannot create store path {store_path}: {e}")
        
        if not store_path.is_dir():
            raise ConfigurationError(f"Store path is not a directory: {store_path}")


        # Scan for PDF files
        pdf_files = sorted(file_path.glob("*.pdf"))

        self.callback(f" Loading {len(pdf_files)} PDF files from: {file_path}", debug=True)
        self.callback(f" Storing files to: {store_path}", debug=True)

        if not pdf_files:
            return StepResult(
                status=StepStatus.WARNING,
                message=f"No PDF files found in {file_path}",
                stats={
                    "total_files": 0,
                    "files_processed": 0,
                    "papers_loaded": 0,
                    "papers_failed": 0,
                    "files_copied": 0,
                }
            )

        # Randomize papers if limit is set
        if limit and randomize:
            if random_seed is not None:
                random.seed(random_seed)
            random.shuffle(pdf_files)
            seed_display = f" (seed={random_seed})" if random_seed is not None else ""
            self.callback(f" [cyan]✓[/cyan] Randomized files{seed_display}", debug=True)

        # Apply limit after randomization
        if limit:
            pdf_files = pdf_files[:limit]
            self.callback(f" [dim]✓ Limited to {limit} papers[/dim]", debug=True)

        pdf_cache = PDFCache(cache_dir=self.cache_dir / "pdfs")

        # Track results
        stats = {
            "total_files": len(pdf_files),
            "files_processed": 0,
            "papers_loaded": 0,
            "papers_failed": 0,
            "files_copied": 0,
        }
        details = []

        # Process each PDF
        for i, pdf_path in enumerate(pdf_files, 1):
            file_result = {
                "filename": pdf_path.name,
                "success": False,
                "doi": None,
                "cite_key": None,
                "title": None,
                "error": None,
            }

            try:
                # Step 1: Read file
                file_reader = FileReader(pdf_path)
                if not file_reader.exists():
                    file_result["error"] = "PDF file not found"
                    stats["papers_failed"] += 1
                    self.callback(f" [yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: file not found")
                    details.append(file_result)
                    continue

                file_info = file_reader.get_file_info()

                # Step 2: Extract DOI
                doi = file_reader.extract_doi()
                if not doi:
                    file_result["error"] = "No DOI extracted"
                    stats["papers_failed"] += 1
                    self.callback(f" [yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: no DOI")
                    details.append(file_result)
                    continue

                file_result["doi"] = doi

                # Step 3: Store Paper in cache (we keep everything)
                pdf_cache.set(doi, pdf_path, move=False)

                # Step 4: Create Discovery object
                discovery = Discovery(
                    method=DiscoveryMethod.FILE_PATH,
                    source_database="file_path"
                )

                paper = Paper(
                    source_key=doi,
                    cite_key=pdf_path.stem,
                    doi=doi,
                    discovery=discovery,
                )

                # Step 7: Store in database
                if not dry_run:
                    self.db.add(paper)

                # Step 8: Copy file to store_path
                reformatted_doi = DOI(doi).safe
                new_filename = f"{reformatted_doi}.pdf"
                new_filepath = store_path / new_filename

                if not dry_run:
                    try:
                        shutil.copy2(pdf_path, new_filepath)
                        stats["files_copied"] += 1
                    except Exception as e:
                        raise StepFatalError(f"Failed to copy file to store path: {new_filepath}")

                # Step 6: Add PDFInfo to paper
                created_time = file_info.get("file_created_time")
                if isinstance(created_time, str):
                    # Try to parse if it's a string
                    try:
                        created_time = datetime.fromisoformat(created_time)
                    except (ValueError, TypeError):
                        created_time = None

                paper.pdf_info = PDFInfo(
                    file_path=str(new_filepath),
                    file_name=new_filename,
                    file_hash=file_info.get("file_hash", None),
                    file_size_bytes=file_info.get("file_size_bytes"),
                    download_source="file_path",
                    download_url="file://" + str(file_info.get("file_path", "")),
                    downloaded_at=created_time,
                )

                # Success!
                file_result["success"] = True
                stats["papers_loaded"] += 1
                stats["files_processed"] += 1

                self.callback(f" [green]✓[/green] {i}/{len(pdf_files)} {pdf_path.name} → {new_filename}")

            except StepFatalError:
                # Re-raise fatal errors
                raise
            except Exception as e:
                file_result["error"] = str(e)
                file_result["success"] = False
                stats["papers_failed"] += 1
                self.callback(f" [red]✗[/red] {i}/{len(pdf_files)} {pdf_path.name}: {str(e)[:50]}")

            details.append(file_result)

        # Determine final status
        if stats["papers_failed"] == 0:
            status = StepStatus.SUCCESS
            message = f"Loaded {stats['papers_loaded']} papers from {stats['files_processed']}/{stats['total_files']} files"
        else:
            status = StepStatus.WARNING
            message = f"Loaded {stats['papers_loaded']} papers but {stats['papers_failed']} failed"

        return StepResult(
            status=status,
            message=message,
            stats=stats,
            details="\n".join([f"{d['filename']}: {d['error']}" for d in details if d.get('error')])
        )

