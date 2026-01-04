"""
Generate hierarchical embeddings for papers using 3-level structure.

This step generates semantic embeddings for paper sections and paragraphs
using a sentence transformer model with multi-pass processing:
- Pass 1: Extract text and create hierarchical TextChunk structure
- Pass 2: Generate embeddings for Level 1 (sections) and Level 2 (paragraphs)
- Aggregation: Combine paragraph embeddings to create section-level embeddings

Configuration example:
    - step: generate_embeddings
      config:
        model: "all-mpnet-base-v2"              # Embedding model (default)
        device: "mps"                           # "cpu", "cuda", or "mps" (auto-detect if not specified)
        batch_size: 32                          # Batch size for encoding
        filter:
          included_only: true                   # Only embed included papers
          min_year: 2020                        # Optional year filter
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Embedding, Paper, TextChunk
from paper_scanner.core.step_result import StepResult
from paper_scanner.tools.embedding.citation_remover import CitationRemover
from paper_scanner.tools.embedding.extractor import PDFExtractor

from .base import BaseStep


class GenerateEmbeddingsStep(BaseStep):
    """Generate hierarchical embeddings using 3-level TextChunk structure."""

    # Default configuration
    DEFAULT_MODEL = "all-mpnet-base-v2"
    DEFAULT_BATCH_SIZE = 32
    VECTOR_DIM = 768  # all-mpnet-base-v2 output dimension

    def __init__(
        self,
        general_config: Optional[Dict[str, Any]] = None,
        executor=None,
        db=None,
        cache_dir: Optional[str] = None,
        on_event=None,
    ):
        """Initialize embedding step with extraction tools."""
        super().__init__(
            general_config=general_config,
            executor=executor,
            db=db,
            cache_dir=cache_dir,
            on_event=on_event,
        )
        self.extractor = PDFExtractor()
        self.citation_remover = CitationRemover()

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate generate_embeddings step configuration.

        Args:
            config: Step configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate model name
        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        # Validate device (optional, will auto-detect)
        if "device" in config:
            device = config["device"]
            if device not in ("cpu", "cuda", "mps"):
                errors.append(f"'device' must be 'cpu', 'cuda', or 'mps', got '{device}'")

        # Validate batch_size
        if "batch_size" in config:
            batch_size = config["batch_size"]
            if not isinstance(batch_size, int) or batch_size < 1:
                errors.append(f"'batch_size' must be a positive integer, got {batch_size}")

        # Validate filter
        if "filter" in config:
            if not isinstance(config["filter"], dict):
                errors.append("'filter' must be a dictionary")
            else:
                filter_config = config["filter"]
                if "included_only" in filter_config:
                    if not isinstance(filter_config["included_only"], bool):
                        errors.append("'filter.included_only' must be a boolean")
                if "min_year" in filter_config:
                    if not isinstance(filter_config["min_year"], int):
                        errors.append("'filter.min_year' must be an integer")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """
        Execute hierarchical embedding generation with multi-pass approach.

        Pass 1: Extract text and create hierarchical TextChunk structure
        Pass 2: Generate embeddings for sections (Level 1) and paragraphs (Level 2)

        Args:
            config: Step-specific configuration
            verbose: Enable verbose logging
            dry_run: If True, don't modify database
            debug: Enable debug logging

        Returns:
            StepResult with execution status and statistics
        """
        included_only = config.get("included_only", True)
        min_year = config.get("min_year", None)

        try:
            # Parse configuration
            model_name = config.get("model", self.DEFAULT_MODEL)
            device = self._select_device(config.get("device"))
            batch_size = config.get("batch_size", self.DEFAULT_BATCH_SIZE)
            filter_config = config.get("filter", {})

            self.callback(f"Loading embedding model: {model_name}", debug=True)
            self.callback(f"Device: {device}", debug=True)
            try:
                model = SentenceTransformer(model_name)
                model.to(device)
            except Exception as e:
                return StepResult(
                    status=StepStatus.ERROR,
                    message=f"Failed to load embedding model: {e}",
                    error=str(e),
                    stats={"papers_count": 0},
                )

            def predicate(p: Paper) -> bool:
                if p.pdf_info is None or p.pdf_info.file_path is None:
                    return False
                if included_only and not p.is_included:
                    return False
                if min_year and p.year < min_year:
                    return False

                return True

            # Get papers from database
            papers = self.db.find(predicate=predicate, primary_only=True)

            # PASS 1: Create hierarchical TextChunk structure
            self.callback("PASS 1: Creating hierarchical chunk structure...", debug=True)
            pass1_stats = {
                "papers_processed": 0,
                "papers_failed": 0,
                "chunks_created": 0,
            }

            for idx, paper in enumerate(papers, 1):
                if idx % 10 == 1:
                    self.callback(f"Chunking paper {idx}/{len(papers)}: {paper.cite_key}", debug=True)

                try:
                    if not paper.pdf_info or not paper.pdf_info.file_path:
                        continue

                    chunks = self._create_chunks(paper)
                    if chunks:
                        # Attach chunks to paper immediately
                        paper.text_chunks = chunks
                        pass1_stats["papers_processed"] += 1
                        pass1_stats["chunks_created"] += len(chunks)

                        # Save paper with chunks
                        if not dry_run:
                            self.db.update(paper)

                except Exception as e:
                    pass1_stats["papers_failed"] += 1
                    if verbose:
                        self.callback(f"Failed to create chunks for {paper.source_key}: {e}", debug=True)

            # PASS 2: Generate embeddings
            self.callback("PASS 2: Generating embeddings for chunks...", debug=True)
            pass2_stats = {
                "sections_embedded": 0,
                "paragraphs_embedded": 0,
                "section_aggregations": 0,
                "errors": 0,
            }

            for idx, paper in enumerate(papers, 1):
                if idx % 10 == 1:
                    self.callback(f"Embedding paper {idx}/{len(papers)}: {paper.cite_key}", debug=True)

                try:
                    # Skip papers without chunks
                    if not paper.text_chunks:
                        continue

                    chunks = paper.text_chunks

                    # Generate embeddings for Level 1 (sections) and Level 2 (paragraphs)
                    embeddable = [c for c in chunks if c.hierarchy_level in (1, 2)]

                    for chunk in embeddable:
                        if chunk.text and len(chunk.text) > 5:
                            embedding = self._generate_embedding(chunk.text, model, batch_size, model_name)
                            if embedding:
                                chunk.embedding = embedding
                                if chunk.hierarchy_level == 1:
                                    pass2_stats["sections_embedded"] += 1
                                else:
                                    pass2_stats["paragraphs_embedded"] += 1

                    # Aggregate: Create section embeddings from paragraph embeddings
                    section_aggs = self._aggregate_embeddings(chunks)
                    pass2_stats["section_aggregations"] += section_aggs

                    # Save paper with embedded chunks
                    if not dry_run:
                        self.db.update(paper)

                except Exception as e:
                    pass2_stats["errors"] += 1
                    if verbose:
                        self.callback(f"Error processing paper {paper.source_key}: {e}", debug=True)

            # Combine statistics
            total_stats = {
                "papers_count": len(papers),
                "papers_processed": pass1_stats["papers_processed"],
                "papers_failed": pass1_stats["papers_failed"],
                "chunks_created": pass1_stats["chunks_created"],
                "sections_embedded": pass2_stats["sections_embedded"],
                "paragraphs_embedded": pass2_stats["paragraphs_embedded"],
                "section_aggregations": pass2_stats["section_aggregations"],
                "errors": pass2_stats["errors"],
            }

            # Prepare result
            message = (
                f"Generated embeddings for {total_stats['sections_embedded']} sections "
                f"and {total_stats['paragraphs_embedded']} paragraphs "
                f"across {total_stats['papers_processed']} papers"
            )
            if total_stats["section_aggregations"] > 0:
                message += f" (with {total_stats['section_aggregations']} aggregations)"
            if total_stats["errors"] > 0:
                message += f", {total_stats['errors']} errors"

            status = StepStatus.SUCCESS if total_stats["errors"] == 0 else StepStatus.WARNING

            details = (
                f"## Hierarchical Embedding Generation Summary\n\n"
                f"### Configuration\n"
                f"- **Model**: {model_name}\n"
                f"- **Device**: {device}\n"
                f"- **Vector dimension**: {self.VECTOR_DIM}\n"
                f"- **Batch size**: {batch_size}\n\n"
                f"### Pass 1: Chunk Structure\n"
                f"- **Papers processed**: {total_stats['papers_processed']}\n"
                f"- **Total chunks created**: {total_stats['chunks_created']}\n"
                f"- **Chunk structure**: Level 0 (Paper) → Level 1 (Sections) → Level 2 (Paragraphs)\n\n"
                f"### Pass 2: Embedding Generation\n"
                f"- **Sections embedded**: {total_stats['sections_embedded']}\n"
                f"- **Paragraphs embedded**: {total_stats['paragraphs_embedded']}\n"
                f"- **Section aggregations**: {total_stats['section_aggregations']}\n"
                f"- **Processing errors**: {total_stats['errors']}\n"
            )

            return StepResult(
                status=status,
                message=message,
                stats=total_stats,
                details=details,
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.ERROR,
                message="Hierarchical embedding generation failed",
                error=str(e),
                stats={"papers_count": len(papers) if "papers" in locals() else 0},
            )

    def _select_device(self, user_device: Optional[str]) -> str:
        """Select compute device with MPS priority for Apple Silicon."""
        if user_device:
            return user_device

        # Prioritize MPS for Apple Silicon
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        else:
            return "cpu"

    def _create_chunks(self, paper: Paper) -> List[TextChunk]:
        """
        Create hierarchical TextChunk structure for a paper (Pass 1).

        Uses citation_remover and extractor from library to create
        3-level hierarchy without sentence-level chunks.
        """
        try:
            # Extract text and hierarchical sections
            result = self.extractor.extract(paper.pdf_info.file_path)
            if not result:
                return []

            hierarchical = result.get("hierarchical_sections", {})
            chunks = []
            chunk_index = 0

            # Root chunk (Level 0)
            paper_chunk = TextChunk(
                chunk_index=chunk_index,
                text="[Paper root]",
                section=None,
                hierarchy_level=0,
                paper=paper,  # Direct reference to paper
                parent_chunk=None,
                word_count=0,
            )
            chunks.append(paper_chunk)
            chunk_index += 1

            # Process canonical sections
            for section_name, section_list in hierarchical.items():
                if not isinstance(section_list, list):
                    continue

                for section_item in section_list:
                    if not isinstance(section_item, dict):
                        continue

                    section_content = section_item.get("content", "").strip()
                    if not section_content:
                        continue

                    # Remove citations using library function (returns tuple)
                    cleaned_content, _ = self.citation_remover.remove_citations(section_content)
                    if not cleaned_content:
                        cleaned_content = section_content

                    # Section chunk (Level 1)
                    section_chunk = TextChunk(
                        chunk_index=chunk_index,
                        text=cleaned_content[:100] + "..." if len(cleaned_content) > 100 else cleaned_content,
                        section=section_name,
                        hierarchy_level=1,
                        paper=paper,  # Direct reference to paper
                        parent_chunk=paper_chunk,  # Direct reference to parent
                        word_count=len(cleaned_content.split()),
                    )
                    chunks.append(section_chunk)
                    paper_chunk.children_chunks.append(section_chunk)  # Build hierarchy
                    chunk_index += 1

                    # Paragraph chunks (Level 2)
                    paragraphs = self._split_paragraphs(cleaned_content)
                    for paragraph in paragraphs:
                        para_chunk = TextChunk(
                            chunk_index=chunk_index,
                            text=paragraph.strip(),
                            section=section_name,
                            hierarchy_level=2,
                            paper=paper,  # Direct reference to paper
                            parent_chunk=section_chunk,  # Direct reference to parent section
                            word_count=len(paragraph.split()),
                        )
                        chunks.append(para_chunk)
                        section_chunk.children_chunks.append(para_chunk)  # Build hierarchy
                        chunk_index += 1

            return chunks

        except Exception as e:
            self.callback(f"Error creating chunks for paper {paper.id}: {e}", debug=True)
            return []

    @staticmethod
    def _split_paragraphs(text: str) -> List[str]:
        """Split text into paragraphs by double newlines or heuristic."""
        paragraphs = []
        current = ""

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                if current.strip():
                    paragraphs.append(current.strip())
                    current = ""
            else:
                current += " " + line if current else line

        if current.strip():
            paragraphs.append(current.strip())

        # Filter out very short paragraphs
        return [p for p in paragraphs if len(p) > 20]

    def _generate_embedding(
        self,
        text: str,
        model: SentenceTransformer,
        batch_size: int,
        model_name: str,
    ) -> Optional[Embedding]:
        """Generate embedding for a text chunk."""
        if not text or not text.strip():
            return None

        try:
            # Encode the text
            vector = model.encode(text, convert_to_tensor=False, batch_size=batch_size)

            # Convert to list
            if isinstance(vector, np.ndarray):
                vector = vector.tolist()

            # Validate dimensions
            if len(vector) != self.VECTOR_DIM:
                if len(vector) < self.VECTOR_DIM:
                    vector = vector + [0.0] * (self.VECTOR_DIM - len(vector))
                else:
                    vector = vector[: self.VECTOR_DIM]

            return Embedding(vector=vector, model=model_name, text_source="section")

        except Exception as e:
            self.callback(f"Error generating embedding: {e}", debug=True)
            return None

    def _aggregate_embeddings(self, chunks: List[TextChunk]) -> int:
        """
        Aggregate paragraph-level embeddings to create section embeddings.

        For each section (Level 1), average its paragraph embeddings.
        Returns count of successful aggregations.
        """
        count = 0

        # Get all section chunks
        sections = [c for c in chunks if c.hierarchy_level == 1]

        # For each section, aggregate its paragraph embeddings
        for section in sections:
            # Get paragraph embeddings from section's children
            para_embeddings = [
                np.array(p.embedding.vector)
                for p in section.children_chunks
                if p.embedding and hasattr(p.embedding, "vector")
            ]

            # Average embeddings
            if para_embeddings:
                aggregated = np.mean(para_embeddings, axis=0).tolist()
                section.embedding = Embedding(
                    vector=aggregated,
                    model=section.embedding.model if section.embedding else "all-mpnet-base-v2",
                    text_source="aggregated_paragraphs",
                )
                count += 1

        return count
