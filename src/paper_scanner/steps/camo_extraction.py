"""
LLM-based CAMO statement extraction step.

Uses Claude to extract Context-Agency-Mechanism-Outcome statements from
academic papers. Results are stored in Paper.conceptual_analysis.

Configuration options:
  - model: Claude model to use (default: claude-sonnet-4-5-20250929)
  - prompt: Path to prompt template (default: src/prompts/extract-camo.md)

Environment:
  - ANTHROPIC_API_KEY: Anthropic API key

Example YAML:
  - step: "CAMO Extraction"
    builtin.camo_extraction:
      model: "claude-sonnet-4-5-20250929"
      prompt: "src/prompts/extract-camo.md"
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import (
    CAMOStatement,
    ConceptualAnalysis,
    Paper,
    ProcessingMetadata,
)
from paper_scanner.core.step_result import StepResult
from paper_scanner.models.anthropic import ClaudeHandler

from .base import BaseStep

logging.getLogger("anthropic").setLevel(logging.WARNING)

DEFAULT_PROMPT_PATH = "src/prompts/extract-camo.md"

JSON_SCHEMA = """{
    "camo_statements": [
        {
            "context": "string",
            "agency": "string",
            "mechanism": "string",
            "outcome": "string",
            "full_statement": "string",
            "confidence": 0.85,
            "innovation_type": "string or null",
            "it_suppliers": ["string"],
            "regular_suppliers": ["string"]
        }
    ]
}"""


class CAMOExtractionStep(BaseStep):
    """LLM-based CAMO statement extraction using Claude."""

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
        model_name = config.get("model", "claude-sonnet-4-5-20250929")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY environment variable is not set")

        system_prompt = self._load_prompt(config)

        try:
            claude = ClaudeHandler(api_key=api_key, model=model_name)
        except Exception as e:
            raise StepFatalError(f"Failed to initialize ClaudeHandler: {e}", e)

        def predicate(p: Paper) -> bool:
            return p.is_included and (
                p.conceptual_analysis is None
                or len(p.conceptual_analysis.camo_statements) == 0
            )

        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        stats = {
            "total_papers": paper_count,
            "extracted": 0,
            "total_statements": 0,
            "errors": 0,
            "total_tokens": 0,
        }

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers to extract CAMO statements from",
                step="camo_extraction",
                stats=stats,
            )

        for i, paper in enumerate(all_papers, 1):
            if i % 10 == 1:
                self.callback(f"Extracting CAMO {i}/{paper_count}: {paper.cite_key}")

            start_time = datetime.now(timezone.utc)

            paper_text = _format_paper_text(paper)
            parsed_response, token_usage = claude.call(
                text=paper_text,
                system_prompt=system_prompt,
                max_tokens=4096,
            )

            if not parsed_response:
                stats["errors"] += 1
                continue

            stats["total_tokens"] += token_usage.get("output_tokens", 0)

            statements = _parse_camo_statements(parsed_response, model_name, start_time)

            if not dry_run:
                if paper.conceptual_analysis is None:
                    paper.conceptual_analysis = ConceptualAnalysis()

                paper.conceptual_analysis.camo_statements = statements
                paper.conceptual_analysis.metadata = ProcessingMetadata(
                    timestamp=start_time,
                    duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                    model_name=model_name,
                    success=True,
                )
                self.db.update(paper)

            stats["extracted"] += 1
            stats["total_statements"] += len(statements)

        avg = round(stats["total_statements"] / max(stats["extracted"], 1), 1)
        return StepResult(
            status=StepStatus.SUCCESS,
            message=(
                f"CAMO extraction: {stats['extracted']} papers, "
                f"{stats['total_statements']} statements (avg {avg}/paper, "
                f"{stats['errors']} errors)"
            ),
            step="camo_extraction",
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


def _parse_camo_statements(
    response: Dict[str, Any],
    model_name: str,
    start_time: datetime,
) -> List[CAMOStatement]:
    """Parse LLM response into CAMOStatement models."""
    raw_statements = response.get("camo_statements", [])
    if not isinstance(raw_statements, list):
        return []

    metadata = ProcessingMetadata(
        timestamp=start_time,
        duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
        model_name=model_name,
        success=True,
    )

    statements = []
    for raw in raw_statements:
        if not isinstance(raw, dict):
            continue

        # All four CAMO components are required
        context = raw.get("context", "")
        agency = raw.get("agency", "")
        mechanism = raw.get("mechanism", "")
        outcome = raw.get("outcome", "")

        if not all([context, agency, mechanism, outcome]):
            continue

        confidence = raw.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            confidence = 0.5

        statements.append(CAMOStatement(
            context=context,
            agency=agency,
            mechanism=mechanism,
            outcome=outcome,
            full_statement=raw.get("full_statement", f"{context} {agency} {mechanism} {outcome}"),
            confidence=confidence,
            innovation_type=raw.get("innovation_type"),
            it_suppliers=raw.get("it_suppliers", []),
            regular_suppliers=raw.get("regular_suppliers", []),
            metadata=metadata,
        ))

    return statements
