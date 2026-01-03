"""
Generate embeddings for papers.

This step generates semantic embeddings for paper titles, abstracts, and keywords
using a sentence transformer model. Embeddings enable semantic search and similarity
matching across papers.

Configuration example:
    - step: generate_embeddings
      config:
        model: "all-mpnet-base-v2"              # Embedding model (default)
        device: "cpu"                           # "cpu" or "cuda" (default: cpu)
        batch_size: 32                          # Batch size for encoding
        fields:                                 # Which fields to embed (default: all)
          - title
          - abstract
          - keywords
        skip_existing: true                     # Skip papers that already have embeddings
        filter:
          included_only: true                   # Only embed included papers
          min_year: 2020                        # Optional year filter
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError
from paper_scanner.core.models import Embedding, Paper
from paper_scanner.core.step_result import StepResult

from .base import BaseStep

logger = logging.getLogger(__name__)


class GenerateEmbeddingsStep(BaseStep):
    """Generate semantic embeddings for paper text fields."""

    # Default configuration
    DEFAULT_MODEL = "all-mpnet-base-v2"
    DEFAULT_DEVICE = "cpu"
    DEFAULT_BATCH_SIZE = 32
    DEFAULT_FIELDS = ["title", "abstract", "keywords"]
    VECTOR_DIM = 768  # all-mpnet-base-v2 output dimension

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

        # Validate device
        if "device" in config:
            device = config["device"]
            if device not in ("cpu", "cuda"):
                errors.append(f"'device' must be 'cpu' or 'cuda', got '{device}'")

        # Validate batch_size
        if "batch_size" in config:
            batch_size = config["batch_size"]
            if not isinstance(batch_size, int) or batch_size < 1:
                errors.append(f"'batch_size' must be a positive integer, got {batch_size}")

        # Validate fields
        if "fields" in config:
            if not isinstance(config["fields"], list):
                errors.append("'fields' must be a list of strings")
            else:
                valid_fields = {"title", "abstract", "keywords", "combined"}
                for field in config["fields"]:
                    if field not in valid_fields:
                        errors.append(
                            f"Invalid field '{field}'. Must be one of {valid_fields}"
                        )

        # Validate skip_existing
        if "skip_existing" in config and not isinstance(config["skip_existing"], bool):
            errors.append("'skip_existing' must be a boolean")

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
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """
        Execute embedding generation for papers.

        Args:
            step_config: Step-specific configuration
            verbose: Enable verbose logging
            dry_run: If True, don't modify database
            debug: Enable debug logging

        Returns:
            StepResult with execution status and statistics
        """
        if verbose or debug:
            logger.setLevel(logging.DEBUG)

        try:
            # Parse configuration
            model_name = step_config.get("model", self.DEFAULT_MODEL)
            device = step_config.get("device", self.DEFAULT_DEVICE)
            batch_size = step_config.get("batch_size", self.DEFAULT_BATCH_SIZE)
            fields = step_config.get("fields", self.DEFAULT_FIELDS)
            skip_existing = step_config.get("skip_existing", True)
            filter_config = step_config.get("filter", {})

            logger.info(f"Loading embedding model: {model_name}")
            try:
                model = SentenceTransformer(model_name, device=device)
                logger.info(f"✓ Model loaded successfully (device: {device})")
            except Exception as e:
                return StepResult(
                    status=StepStatus.ERROR,
                    message=f"Failed to load embedding model: {e}",
                    error=str(e),
                    stats={"papers_count": 0},
                )

            # Get papers from database
            logger.info("Fetching papers from database...")
            papers = self.db.list_papers(limit=None)
            logger.info(f"Found {len(papers)} papers total")

            # Apply filters
            filtered_papers = self._apply_filters(papers, filter_config)
            logger.info(f"After filtering: {len(filtered_papers)} papers")

            # Generate embeddings
            stats = {
                "papers_count": len(papers),
                "papers_processed": len(filtered_papers),
                "embeddings_generated": 0,
                "embeddings_skipped": 0,
                "errors": 0,
            }

            for i, paper in enumerate(filtered_papers, 1):
                try:
                    # Check if we should skip
                    if skip_existing and self._has_embeddings(paper):
                        logger.debug(f"Skipping {paper.cite_key} (already has embeddings)")
                        stats["embeddings_skipped"] += 1
                        continue

                    # Generate embeddings for specified fields
                    embeddings_created = 0

                    if "title" in fields and paper.title:
                        embedding = self._generate_embedding(
                            paper.title, model, batch_size, "title", model_name
                        )
                        if embedding:
                            paper.title_abstract_embedding = embedding
                            embeddings_created += 1

                    if "abstract" in fields and paper.abstract:
                        embedding = self._generate_embedding(
                            paper.abstract, model, batch_size, "abstract", model_name
                        )
                        if embedding:
                            # Store in custom property or use TextChunk
                            paper._abstract_embedding = embedding
                            embeddings_created += 1

                    if "keywords" in fields and paper.keywords:
                        keywords_text = " ".join(paper.keywords)
                        embedding = self._generate_embedding(
                            keywords_text, model, batch_size, "keywords", model_name
                        )
                        if embedding:
                            paper._keywords_embedding = embedding
                            embeddings_created += 1

                    if embeddings_created > 0:
                        if not dry_run:
                            self.db.update_paper(paper)
                        stats["embeddings_generated"] += embeddings_created
                        logger.debug(
                            f"{i}/{len(filtered_papers)}: {paper.cite_key} "
                            f"({embeddings_created} embeddings)"
                        )
                    else:
                        logger.debug(f"{i}/{len(filtered_papers)}: {paper.cite_key} (no text)")

                except Exception as e:
                    logger.error(f"Error processing {paper.cite_key}: {e}")
                    stats["errors"] += 1
                    if debug:
                        raise

            # Prepare result message
            message = (
                f"Generated {stats['embeddings_generated']} embeddings "
                f"for {len(filtered_papers)} papers"
            )
            if stats["embeddings_skipped"] > 0:
                message += f" (skipped {stats['embeddings_skipped']})"
            if stats["errors"] > 0:
                message += f", {stats['errors']} errors"

            status = StepStatus.SUCCESS if stats["errors"] == 0 else StepStatus.WARNING

            details = (
                f"## Embedding Generation Summary\n\n"
                f"- **Model**: {model_name}\n"
                f"- **Device**: {device}\n"
                f"- **Fields embedded**: {', '.join(fields)}\n"
                f"- **Papers processed**: {len(filtered_papers)}\n"
                f"- **Embeddings generated**: {stats['embeddings_generated']}\n"
                f"- **Embeddings skipped**: {stats['embeddings_skipped']}\n"
                f"- **Errors**: {stats['errors']}\n"
                f"- **Vector dimension**: {self.VECTOR_DIM}\n"
            )

            return StepResult(
                status=status,
                message=message,
                stats=stats,
                details=details,
            )

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=debug)
            return StepResult(
                status=StepStatus.ERROR,
                message="Embedding generation failed",
                error=str(e),
                stats={"papers_count": len(papers) if "papers" in locals() else 0},
            )

    def _apply_filters(
        self, papers: List[Paper], filter_config: Dict[str, Any]
    ) -> List[Paper]:
        """Apply filters to paper list."""
        filtered = papers

        # Filter by inclusion status
        if filter_config.get("included_only", False):
            filtered = [p for p in filtered if p.is_included]

        # Filter by year
        min_year = filter_config.get("min_year")
        if min_year:
            filtered = [p for p in filtered if p.year and p.year >= min_year]

        return filtered

    def _has_embeddings(self, paper: Paper) -> bool:
        """Check if paper already has embeddings."""
        return (
            paper.title_abstract_embedding is not None
            or hasattr(paper, "_abstract_embedding")
            or hasattr(paper, "_keywords_embedding")
        )

    def _generate_embedding(
        self,
        text: str,
        model: SentenceTransformer,
        batch_size: int,
        text_source: str,
        model_name: str,
    ) -> Optional[Embedding]:
        """Generate embedding for a text string."""
        if not text or not text.strip():
            return None

        try:
            # Encode the text
            vector = model.encode(text, convert_to_tensor=False, batch_size=batch_size)

            # Ensure it's a list and proper dimensions
            if isinstance(vector, np.ndarray):
                vector = vector.tolist()

            # Validate dimensions
            if len(vector) != self.VECTOR_DIM:
                logger.warning(
                    f"Vector has {len(vector)} dimensions, expected {self.VECTOR_DIM}. "
                    "Padding/truncating."
                )
                if len(vector) < self.VECTOR_DIM:
                    vector = vector + [0.0] * (self.VECTOR_DIM - len(vector))
                else:
                    vector = vector[: self.VECTOR_DIM]

            return Embedding(vector=vector, model=model_name, text_source=text_source)

        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None
