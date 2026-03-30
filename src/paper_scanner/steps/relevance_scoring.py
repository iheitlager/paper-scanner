"""
LLM-based relevance scoring step.

Uses Claude to score how well each paper fits a given research question
and keyword set. Produces relevance and confidence scores stored in
Screening.relevance_scoring.

Configuration options:
  - model: Claude model to use (default: claude-haiku-4-5-20251001)
  - prompt: Path to prompt template (default: src/prompts/score-relevance.md)
  - use_pdf: Send PDF natively to Claude when available (default: true)
  - cache: Whether to store LLM responses in cache (default: true)
  - use_cache: Whether to check cache before calling the LLM (default: true)

Environment:
  - ANTHROPIC_API_KEY: Anthropic API key

Example YAML:
  - step: "Relevance Scoring"
    builtin.relevance_scoring:
      model: "claude-sonnet-4-5-20250929"
      prompt: "src/prompts/score-relevance.md"
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.cache import JSONFileCache
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import Paper, ProcessingMetadata, RelevanceScore
from paper_scanner.core.paths import get_json_cache_dir
from paper_scanner.core.step_result import StepResult
from paper_scanner.models.anthropic import ClaudeHandler

from ._llm_helpers import resolve_llm_input, validate_use_pdf
from .base import BaseStep

logging.getLogger("anthropic").setLevel(logging.WARNING)

DEFAULT_PROMPT_PATH = "src/prompts/score-relevance.md"

JSON_SCHEMA = """{
    "relevance": 0.75,
    "confidence": 0.85,
    "justification": "string",
    "matching_keywords": ["keyword1", "keyword2"],
    "research_question_alignment": "string"
}"""


class RelevanceScoringStep(BaseStep):
    """LLM-based relevance scoring using Claude."""

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

        if "cache" in config and not isinstance(config["cache"], bool):
            errors.append("'cache' must be a boolean")

        if "use_cache" in config and not isinstance(config["use_cache"], bool):
            errors.append("'use_cache' must be a boolean")

        validate_use_pdf(config, errors)

        return len(errors) == 0, errors

    def _load_prompt(self, config: Dict[str, Any]) -> str:
        """Load and prepare the prompt template with research question and keywords."""
        prompt_path = Path(config.get("prompt", DEFAULT_PROMPT_PATH))
        if not prompt_path.exists():
            raise ConfigurationError(f"Prompt file not found: {prompt_path}")

        research_question = self.general_config.get("research_question", "")
        keywords = self.general_config.get("keywords", [])
        if isinstance(keywords, list):
            keywords_str = ", ".join(keywords)
        else:
            keywords_str = str(keywords)

        template = prompt_path.read_text(encoding="utf-8")
        return (
            template
            .replace("{json_schema}", JSON_SCHEMA)
            .replace("{research_question}", research_question)
            .replace("{keywords}", keywords_str)
        )

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        model_name = config.get("model", "claude-haiku-4-5-20251001")
        use_pdf = config.get("use_pdf", True)
        cache_enabled = config.get("cache", True)
        use_cache = config.get("use_cache", True)

        research_question = self.general_config.get("research_question", "")
        if not research_question:
            raise ConfigurationError("research_question must be set in project configuration")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY environment variable is not set")

        system_prompt = self._load_prompt(config)

        try:
            claude = ClaudeHandler(api_key=api_key, model=model_name)
        except Exception as e:
            raise StepFatalError(f"Failed to initialize ClaudeHandler: {e}", e)

        # Initialize LLM response cache
        cache: Optional[JSONFileCache] = None
        if cache_enabled or use_cache:
            cache_dir = get_json_cache_dir() / "llm" / "relevance_scoring"
            cache = JSONFileCache(cache_dir=cache_dir, default_ttl=None)

        def predicate(p: Paper) -> bool:
            return p.screening.relevance_scoring is None and not p.is_excluded

        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        stats = {
            "total_papers": paper_count,
            "scored": 0,
            "errors": 0,
            "cache_hits": 0,
            "total_tokens": 0,
            "avg_relevance": 0.0,
        }

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers to score",
                step="relevance_scoring",
                stats=stats,
            )

        relevance_sum = 0.0

        for i, paper in enumerate(all_papers, 1):
            if i % 10 == 1:
                self.callback(f"Scoring relevance {i}/{paper_count}: {paper.cite_key}")

            start_time = datetime.now(timezone.utc)
            cache_key = paper.doi if paper.doi else None

            # Try cache first
            if use_cache and cache and cache_key:
                cached = cache.get(cache_key)
                if cached is not None:
                    relevance = _parse_relevance(cached, model_name, start_time)
                    if relevance is not None:
                        if not dry_run:
                            paper.screening.relevance_scoring = relevance
                            self.db.update(paper)
                        relevance_sum += relevance.relevance
                        stats["cache_hits"] += 1
                        stats["scored"] += 1
                        continue

            text_input = resolve_llm_input(paper, use_pdf, _format_paper_text)

            parsed_response, token_usage = claude.call(
                text=text_input,
                system_prompt=system_prompt,
                max_tokens=1024,
            )

            if not parsed_response:
                stats["errors"] += 1
                continue

            stats["total_tokens"] += token_usage.get("output_tokens", 0)

            # Store in cache
            if cache_enabled and cache and cache_key:
                cache.set(cache_key, parsed_response)

            relevance = _parse_relevance(parsed_response, model_name, start_time)
            if relevance is None:
                stats["errors"] += 1
                continue

            relevance_sum += relevance.relevance

            if not dry_run:
                paper.screening.relevance_scoring = relevance
                self.db.update(paper)

            stats["scored"] += 1

        if stats["scored"] > 0:
            stats["avg_relevance"] = round(relevance_sum / stats["scored"], 3)

        cache_msg = f", {stats['cache_hits']} from cache" if stats["cache_hits"] else ""
        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Scored {stats['scored']} papers (avg relevance: {stats['avg_relevance']}, {stats['errors']} errors{cache_msg})",
            step="relevance_scoring",
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


def _parse_relevance(
    response: Dict[str, Any],
    model_name: str,
    start_time: datetime,
) -> Optional[RelevanceScore]:
    """Parse LLM response into a RelevanceScore model."""
    try:
        relevance = float(response.get("relevance", -1))
        confidence = float(response.get("confidence", -1))

        if not (0 <= relevance <= 1) or not (0 <= confidence <= 1):
            return None

        metadata = ProcessingMetadata(
            timestamp=start_time,
            duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
            model_name=model_name,
            success=True,
        )

        return RelevanceScore(
            relevance=relevance,
            confidence=confidence,
            justification=response.get("justification", ""),
            matching_keywords=response.get("matching_keywords", []),
            research_question_alignment=response.get("research_question_alignment"),
            metadata=metadata,
        )
    except (ValueError, TypeError):
        return None
