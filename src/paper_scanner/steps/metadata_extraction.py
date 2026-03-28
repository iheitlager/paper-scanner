"""
LLM-based metadata extraction step.

Uses Claude to extract bibliographic metadata verbatim from papers and classify
research methods. Updates Paper fields and sets ResearchMethodClassification.

Configuration options:
  - model: Claude model to use (default: claude-haiku-4-5-20251001)
  - prompt: Path to prompt template (default: src/prompts/extract-metadata.md)
  - overwrite: Whether to overwrite existing metadata (default: false)
  - use_pdf: Send PDF natively to Claude when available (default: true)

Environment:
  - ANTHROPIC_API_KEY: Anthropic API key

Example YAML:
  - step: "Metadata Extraction"
    builtin.metadata_extraction:
      model: "claude-haiku-4-5-20251001"
      prompt: "src/prompts/extract-metadata.md"
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import (
    Author,
    Paper,
    ProcessingMetadata,
    ResearchMethodClassification,
)
from paper_scanner.core.step_result import StepResult
from paper_scanner.models.anthropic import ClaudeHandler

from .base import BaseStep
from ._llm_helpers import resolve_llm_input, validate_use_pdf

logging.getLogger("anthropic").setLevel(logging.WARNING)

DEFAULT_PROMPT_PATH = "src/prompts/extract-metadata.md"

JSON_SCHEMA = """{
    "title": "string",
    "authors": [{"given_name": "string", "family_name": "string"}],
    "abstract": "string",
    "keywords": ["string"],
    "year": 2024,
    "research_method": {
        "empirical": true,
        "approach": "quantitative | qualitative | mixed",
        "industry": "string or null"
    }
}"""


class MetadataExtractionStep(BaseStep):
    """LLM-based metadata extraction using Claude."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []

        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        if "prompt" in config:
            if not isinstance(config["prompt"], str):
                errors.append("'prompt' must be a string path")
            else:
                prompt_path = Path(config["prompt"])
                if not prompt_path.exists():
                    errors.append(f"Prompt file not found: {config['prompt']}")

        if "overwrite" in config and not isinstance(config["overwrite"], bool):
            errors.append("'overwrite' must be a boolean")

        validate_use_pdf(config, errors)

        return len(errors) == 0, errors

    def _load_prompt(self, config: Dict[str, Any]) -> str:
        """Load and prepare the prompt template."""
        prompt_path = Path(config.get("prompt", DEFAULT_PROMPT_PATH))
        if not prompt_path.exists():
            raise ConfigurationError(f"Prompt file not found: {prompt_path}")

        template = prompt_path.read_text(encoding="utf-8")
        return template.replace("{json_schema}", JSON_SCHEMA)

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        model_name = config.get("model", "claude-haiku-4-5-20251001")
        overwrite = config.get("overwrite", False)
        use_pdf = config.get("use_pdf", True)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY environment variable is not set")

        system_prompt = self._load_prompt(config)

        try:
            claude = ClaudeHandler(api_key=api_key, model=model_name)
        except Exception as e:
            raise StepFatalError(f"Failed to initialize ClaudeHandler: {e}", e)

        def predicate(p: Paper) -> bool:
            if overwrite:
                return p.title is not None or p.abstract is not None
            return p.research_method is None

        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        stats = {
            "total_papers": paper_count,
            "extracted": 0,
            "skipped": 0,
            "errors": 0,
            "total_tokens": 0,
        }

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers to extract metadata from",
                step="metadata_extraction",
                stats=stats,
            )

        for i, paper in enumerate(all_papers, 1):
            if i % 10 == 1:
                self.callback(f"Extracting metadata {i}/{paper_count}: {paper.cite_key}")

            start_time = datetime.now(timezone.utc)

            text_input = resolve_llm_input(paper, use_pdf, _format_paper_text)

            parsed_response, token_usage = claude.call(
                text=text_input,
                system_prompt=system_prompt,
                max_tokens=2048,
            )

            if not parsed_response:
                stats["errors"] += 1
                continue

            stats["total_tokens"] += token_usage.get("output_tokens", 0)

            if not dry_run:
                _apply_metadata(paper, parsed_response, model_name, start_time)
                self.db.update(paper)

            stats["extracted"] += 1

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Metadata extracted for {stats['extracted']} papers ({stats['errors']} errors)",
            step="metadata_extraction",
            stats=stats,
        )


def _format_paper_text(paper: Paper) -> str:
    """Format paper details for LLM input."""
    lines = []
    if paper.title:
        lines.append(f"TITLE: {paper.title}")
    if paper.abstract:
        lines.append(f"ABSTRACT: {paper.abstract}")
    if paper.keywords:
        lines.append(f"KEYWORDS: {', '.join(paper.keywords)}")
    if paper.year:
        lines.append(f"YEAR: {paper.year}")
    if paper.authors:
        author_names = [a.full_name for a in paper.authors[:10]]
        lines.append(f"AUTHORS: {', '.join(author_names)}")
    return "\n".join(lines)


def _apply_metadata(
    paper: Paper,
    response: Dict[str, Any],
    model_name: str,
    start_time: datetime,
) -> None:
    """Apply extracted metadata to paper model."""
    metadata = ProcessingMetadata(
        timestamp=start_time,
        duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
        model_name=model_name,
        success=True,
    )

    # Update verbatim fields only if currently missing
    if not paper.title and response.get("title"):
        paper.title = response["title"]

    if not paper.abstract and response.get("abstract"):
        paper.abstract = response["abstract"]

    if not paper.keywords and response.get("keywords"):
        paper.keywords = response["keywords"]

    if not paper.year and response.get("year"):
        paper.year = int(response["year"])

    if not paper.authors and response.get("authors"):
        paper.authors = [
            Author(
                given_name=a.get("given_name"),
                family_name=a.get("family_name", "Unknown"),
                full_name=f"{a.get('given_name', '')} {a.get('family_name', '')}".strip(),
            )
            for a in response["authors"]
            if isinstance(a, dict)
        ]

    # Always set research method classification
    rm = response.get("research_method", {})
    if isinstance(rm, dict) and "empirical" in rm:
        approach = rm.get("approach")
        if approach and approach not in ("quantitative", "qualitative", "mixed"):
            approach = None

        paper.research_method = ResearchMethodClassification(
            empirical=bool(rm["empirical"]),
            approach=approach,
            industry=rm.get("industry"),
            metadata=metadata,
        )
