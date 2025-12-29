"""
Keyword-based screening step for paper filtering.

Performs automated keyword-based screening with:
- Implicit study type detection (editorial, empirical, literature review, conceptual)
- Inclusion/exclusion keyword matching with wildcard support
- Flexible screening modes (inclusion_required, exclusion_only, soft)
- Scoring mechanism for keyword-based relevance

Outputs screening results to paper.screening.keyword_screening with:
- study_type: Automatically detected from content
- inclusion_keywords: Matched inclusion keywords
- exclusion_keywords: Matched exclusion keywords
- is_empirical: Whether paper is empirical research
- is_conceptual: Whether paper is conceptual/theoretical
- is_literature_review: Whether paper is literature review
- keyword_screening_confidence: Confidence score 0-1
- exclusion_reason: Explanation if paper was excluded
- metadata: Processing timestamp and duration
"""

import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.enum import ScreeningDecision, StepStatus, StudyType
from paper_scanner.core.models import KeywordScreening, Paper, ProcessingMetadata
from paper_scanner.core.step_result import StepResult
from .base import BaseStep

# Initialize rich console for colored output
console = Console(file=sys.stderr)


class KeywordMatcher:
    """
    Keyword matching with wildcard support.
    Supports:
    - Exact match: "keyword"
    - Wildcard suffix: "keyword*" (matches "keywords", "keywording", etc.)
    - Wildcard prefix: "*keyword" (matches "thekeyword", "prekeyword", etc.)
    - Wildcard both: "*keyword*" (matches anywhere)
    """

    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        return text.lower().strip()

    @staticmethod
    def escape_special_chars(text: str) -> str:
        """Escape regex special characters except * which we use for wildcards"""
        escaped = re.escape(text)
        escaped = escaped.replace(r'\*', '*')
        return escaped

    @staticmethod
    def wildcard_to_regex(pattern: str) -> str:
        r"""Convert wildcard pattern to regex
        
        Examples:
            "keyword" -> r"\bkeyword\b" (word boundary)
            "keyword*" -> r"\bkeyword\w*\b"
            "*keyword" -> r"\b\w*keyword\b"
            "*keyword*" -> r"keyword"
        """
        pattern = pattern.lower().strip()

        escaped = KeywordMatcher.escape_special_chars(pattern)

        if escaped.startswith('*') and escaped.endswith('*'):
            core = escaped[1:-1]
            return core
        elif escaped.startswith('*'):
            core = escaped[1:]
            return rf'\w*{core}\b'
        elif escaped.endswith('*'):
            core = escaped[:-1]
            return rf'\b{core}\w*'
        else:
            return rf'\b{escaped}\b'

    @classmethod
    def matches(cls, pattern: str, text: Optional[str]) -> bool:
        """Check if pattern matches text"""
        if not text:
            return False

        text_norm = cls.normalize_text(text)
        regex_pattern = cls.wildcard_to_regex(pattern)

        try:
            return bool(re.search(regex_pattern, text_norm))
        except re.error:
            return pattern.lower().replace('*', '') in text_norm

    @classmethod
    def find_all(cls, pattern: str, text: Optional[str]) -> List[str]:
        """Find all matches of pattern in text"""
        if not text:
            return []

        text_norm = cls.normalize_text(text)
        regex_pattern = cls.wildcard_to_regex(pattern)

        try:
            return re.findall(regex_pattern, text_norm)
        except re.error:
            if pattern.lower().replace('*', '') in text_norm:
                return [pattern.lower().replace('*', '')]
            return []


class StudyTypeDetector:
    """
    Automatically detect study type from keywords and content.
    Uses sophisticated pattern matching for empirical research detection.
    """

    EDITORIAL_INDICATORS = [
        "editorial",
        "news",
        "commentary",
        "letter",
        "correction",
        "erratum",
    ]

    LITERATURE_REVIEW_INDICATORS = [
        "systematic review",
        "scoping review",
        "narrative review",
        "meta-analysis",
        "metaanalysis",
        "meta analysis",
        "state of the art",
    ]

    CONCEPTUAL_INDICATORS = [
        "conceptual",
        "theoretical",
        "theory",
        "framework",
        "taxonomy",
        "typology",
        "opinion",
        "perspective",
        "model",
    ]

    QUANTITATIVE_PATTERNS = [
        r'\bn\s*=\s*\d+',
        r'survey.*\d+.*participants?',
        r'statistical analysis',
        r'regression|correlation|anova|t[- ]?test|chi[- ]?square',
        r'questionnaire|measurement|hypothesis',
        r'significant.*p\s*[<>]|p\s*[<>]\s*0\.',
        r'quantitative|quantitatively',
        r'numerical',
        r'sample size',
        r'participants?|subjects?|respondents?',
    ]

    QUALITATIVE_PATTERNS = [
        r'interview[s]?.*(?:participant|expert|user|developer)',
        r'interviews?',
        r'survey.*\d+.*participants?|survey of',
        r'ethnograph',
        r'grounded theory',
        r'thematic analysis',
        r'content analysis',
        r'observational study|observation',
        r'field work|fieldwork',
        r'focus group',
        r'phenomenological',
        r'qualitative|qualitatively',
        r'in-depth|in depth',
        r'semi-structured|unstructured',
    ]

    CASESTUDY_INDICATORS = [
        r'case study|case studies|case-study|case[- ]based',
        r'multiple case|single case|comparative case',
    ]

    METHOD_INDICATORS = [
        r'data collection|data gathered|data were collected',
        r'empirical study|empirical investigation',
        r'experimental design|experiment',
        r'quasi-experimental',
        r'study design',
        r'methodology|methods',
        r'longitudinal|cross-sectional',
        r'validation|evaluated',
        r'structural model|path model|SEM|sem|m-TISM|TISM',
        r'modeling approach|model evaluation|model development',
    ]

    @classmethod
    def detect_study_type(cls, text: Optional[str]) -> StudyType:
        """Detect study type from text content with empirical-first priority
        
        Design Decision: Empirical classification takes priority over literature review
        because many academic papers combine literature review WITH empirical research.
        When both are detected, the empirical nature is more important.
        
        Priority Order:
        1. Empirical (pattern-scored: interviews, surveys, case studies, etc.)
        2. Editorial (news, commentary) - highest priority
        3. Literature Review (only explicit review types)
        4. Conceptual/Theoretical (frameworks, opinions, no empirical indicators)
        5. Unknown (default)
        """
        if not text:
            return StudyType.UNKNOWN

        text_lower = text.lower()

        empirical_info = cls._detect_empirical_research(text)
        if empirical_info['is_empirical']:
            return empirical_info['type']  # Return the StudyType enum directly

        if any(cls._has_indicator(text_lower, ind) for ind in cls.EDITORIAL_INDICATORS):
            return StudyType.EDITORIAL

        if any(cls._has_indicator(text_lower, ind) for ind in cls.LITERATURE_REVIEW_INDICATORS):
            return StudyType.LITERATURE_REVIEW

        if any(cls._has_indicator(text_lower, ind) for ind in cls.CONCEPTUAL_INDICATORS):
            return StudyType.CONCEPTUAL

        return StudyType.UNKNOWN

    @classmethod
    def _detect_empirical_research(cls, text: str) -> Dict[str, Any]:
        """Detect empirical research with sophisticated pattern matching"""
        text_lower = text.lower()

        quant_score = sum(1 for p in cls.QUANTITATIVE_PATTERNS 
                         if re.search(p, text_lower))
        qual_score = sum(1 for p in cls.QUALITATIVE_PATTERNS 
                        if re.search(p, text_lower))
        case_score = sum(1 for p in cls.CASESTUDY_INDICATORS 
                        if re.search(p, text_lower))
        method_score = sum(1 for p in cls.METHOD_INDICATORS 
                          if re.search(p, text_lower))

        total_score = quant_score + qual_score + case_score + method_score
        is_empirical = total_score >= 2

        # Determine type as StudyType enum
        if case_score > 0:
            study_type = StudyType.EMPIRICAL_QUALITATIVE
        elif quant_score > qual_score:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        elif qual_score > quant_score:
            study_type = StudyType.EMPIRICAL_QUALITATIVE
        elif quant_score > 0 and qual_score > 0:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        else:
            study_type = StudyType.UNKNOWN

        confidence = min(total_score / 10.0, 1.0)

        return {
            'is_empirical': is_empirical,
            'type': study_type,
            'confidence': confidence,
            'quant_score': quant_score,
            'qual_score': qual_score,
            'case_score': case_score,
            'method_score': method_score,
            'total_score': total_score
        }

    @staticmethod
    def _has_indicator(text: str, indicator: str) -> bool:
        """Check if text contains indicator"""
        return indicator.lower() in text


class KeywordScreener:
    """Keyword-based screening with scoring mechanism and study type detection"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with screening config"""
        self.config = config
        self.mode = config.get("mode", "inclusion_required")

        self.exclusion_keywords = self._flatten_keywords(
            config.get("exclude", {}).get("keywords", {})
        )
        self.inclusion_keywords = self._flatten_keywords(
            config.get("include", {}).get("keywords", {})
        )
        self.excluded_study_types = config.get("exclude", {}).get("study_types", [])

    @staticmethod
    def _flatten_keywords(keywords_config: Any) -> List[str]:
        """Flatten nested keyword structure into flat list"""
        if isinstance(keywords_config, dict):
            result = []
            for category, values in keywords_config.items():
                if isinstance(values, list):
                    result.extend(values)
                elif isinstance(values, str):
                    result.append(values)
            return result
        elif isinstance(keywords_config, list):
            return keywords_config
        return []

    def screen_paper(
        self,
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> Tuple[KeywordScreening, bool, Optional[str]]:
        """Screen paper based on keywords
        
        Returns:
            (KeywordScreening model, should_include, exclusion_reason)
        """
        start_time = datetime.now(timezone.utc)

        combined_text = " ".join(filter(None, [title, abstract, " ".join(keywords or [])]))

        # 1. DETECT STUDY TYPE (implicit)
        detected_study_type = StudyTypeDetector.detect_study_type(combined_text)

        # Check if excluded by study_type
        study_type_exclusion = None
        if detected_study_type.value in self.excluded_study_types:
            study_type_exclusion = f"study_type '{detected_study_type.value}' is excluded"

        # 2. CHECK EXCLUSION KEYWORDS
        matched_exclusion_keywords = []
        for keyword in self.exclusion_keywords:
            if KeywordMatcher.matches(keyword, combined_text):
                matched_exclusion_keywords.append(keyword)

        exclusion_reason = None
        if matched_exclusion_keywords:
            exclusion_reason = f"excluded keywords found: {', '.join(matched_exclusion_keywords[:3])}"
        elif study_type_exclusion:
            exclusion_reason = study_type_exclusion

        # 3. CALCULATE INCLUSION SCORE
        inclusion_score = 0
        matched_inclusion_keywords = []

        for keyword in self.inclusion_keywords:
            if KeywordMatcher.matches(keyword, combined_text):
                inclusion_score += 1
                matched_inclusion_keywords.append(keyword)

        # 4. DETERMINE INCLUSION
        should_include = True
        final_exclusion_reason = None

        if self.mode == "inclusion_required":
            if matched_exclusion_keywords or study_type_exclusion:
                should_include = False
                final_exclusion_reason = exclusion_reason
            elif inclusion_score == 0 and self.inclusion_keywords:
                should_include = False
                final_exclusion_reason = "no inclusion keywords matched"
        elif self.mode == "exclusion_only":
            if matched_exclusion_keywords or study_type_exclusion:
                should_include = False
                final_exclusion_reason = exclusion_reason
        elif self.mode == "soft":
            should_include = True

        # 5. BUILD KEYWORD SCREENING MODEL
        duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        keyword_screening = KeywordScreening(
            passed=should_include,
            study_type=detected_study_type,
            inclusion_keywords=matched_inclusion_keywords,
            inclusion_threshold=len(self.inclusion_keywords) if self.inclusion_keywords else None,
            exclusion_keywords=matched_exclusion_keywords,
            is_empirical=detected_study_type in [StudyType.EMPIRICAL_QUALITATIVE, StudyType.EMPIRICAL_QUANTITATIVE, StudyType.CASE_STUDY],
            is_conceptual=detected_study_type == StudyType.CONCEPTUAL,
            is_literature_review=detected_study_type == StudyType.LITERATURE_REVIEW,
            keyword_screening_confidence=min(1.0, inclusion_score / max(1, len(self.inclusion_keywords))),
            exclusion_reason=final_exclusion_reason,
            inclusion_reason=f"matched {inclusion_score} inclusion keywords" if inclusion_score > 0 else None,
            metadata=ProcessingMetadata(
                duration_seconds=duration_seconds,
                success=True
            )
        )

        return keyword_screening, should_include, final_exclusion_reason


class KeywordScreeningStep(BaseStep):
    """Keyword-based screening step with implicit study type detection"""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate keyword_screening step configuration"""
        errors = []

        if "enabled" in config and not isinstance(config["enabled"], bool):
            errors.append("'enabled' must be a boolean")

        if "mode" in config:
            mode = config["mode"]
            if mode not in ["inclusion_required", "exclusion_only", "soft"]:
                errors.append(f"'mode' must be one of: inclusion_required, exclusion_only, soft (got {mode})")

        if "exclude" in config:
            exclude = config["exclude"]
            if not isinstance(exclude, dict):
                errors.append("'exclude' must be a dictionary")

        if "include" in config:
            include = config["include"]
            if not isinstance(include, dict):
                errors.append("'include' must be a dictionary")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Execute keyword screening step"""

        screener = KeywordScreener(config)

        self.callback(
             "Keyword Screening\n"
            f" * Exclusion keywords: {len(screener.exclusion_keywords)}\n"
            f" * Inclusion keywords: {len(screener.inclusion_keywords)}\n"
            f" * Mode: {screener.mode}\n"
            f" * Processing {self.db.count(primary_only=False)} papers...\n", debug=True
        )

        results = {
            "total_papers": self.db.count(primary_only=False),
            "screened": 0,
            "passed": 0,
            "failed": 0,
            "study_types": {},
            "exclusion_reasons": {},
        }

        all_papers = self.db.find(
            predicate=lambda p: not p.is_excluded,
            primary_only=True
        )

        for i, paper in enumerate(all_papers):
            screening, passed, exclusion_reason = screener.screen_paper(
                title=paper.title,
                abstract=paper.abstract,
                keywords=paper.keywords,
            )

            if not dry_run:
                paper.screening.keyword_screening = screening
                paper.screening.current_stage="keyword_screening passed"

                if not passed and paper.screening.final_decision == ScreeningDecision.PENDING:
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED
                    paper.screening.final_decision_by = "automated:keyword_screening"

                self.db.update(paper)

            results["screened"] += 1

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                if exclusion_reason:
                    results["exclusion_reasons"][exclusion_reason] = (
                        results["exclusion_reasons"].get(exclusion_reason, 0) + 1
                    )

            study_type = screening.study_type.value
            results["study_types"][study_type] = results["study_types"].get(study_type, 0) + 1

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Screened {results['screened']} papers: {results['passed']} passed, {results['failed']} failed",
            stats=results,
        )

