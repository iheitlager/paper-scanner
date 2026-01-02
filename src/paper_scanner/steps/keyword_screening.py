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


def is_substantive_abstract(abstract: str) -> bool:
    """
    Check if abstract is substantive enough for analysis.

    Filters out:
    - Very short abstracts (< 20 characters)
    - Pure boilerplate statements (conflicts of interest, author declarations, etc.)

    Args:
        abstract: Abstract text to validate

    Returns:
        True if abstract is substantive, False otherwise
    """
    if not abstract or len(abstract.strip()) < 20:
        return False

    # only check the beginning (first 25 words) of the abstract for boilerplate
    abstract_lower = " ".join(abstract.lower().split()[:25])

    # Check for conflict of interest / competing interests boilerplate
    conflict_phrases = [
        "authors declare no",
        "no conflicts of interest",
        "conflict of interest",
        "no competing interests",
        "competing interests",
        "authors would like to thank",
    ]

    if any(phrase in abstract_lower for phrase in conflict_phrases):
        return False

    # For acknowledgements - only reject if combined with funding/thanks keywords
    if any(word in abstract_lower for word in ("acknowledge", "acknowledgements", "acknowledgments")):
        if any(keyword in abstract_lower for keyword in ("funding", "thank", "support", "gratitude")):
            return False

    return True


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
        escaped = escaped.replace(r"\*", "*")
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

        if escaped.startswith("*") and escaped.endswith("*"):
            core = escaped[1:-1]
            return core
        elif escaped.startswith("*"):
            core = escaped[1:]
            return rf"\w*{core}\b"
        elif escaped.endswith("*"):
            core = escaped[:-1]
            return rf"\b{core}\w*"
        else:
            return rf"\b{escaped}\b"

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
            return pattern.lower().replace("*", "") in text_norm

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
            if pattern.lower().replace("*", "") in text_norm:
                return [pattern.lower().replace("*", "")]
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
        "systematic literature review",
        "literature review",
        "scoping review",
        "narrative review",
        "meta-analysis",
        "metaanalysis",
        "meta analysis",
        "state of the art",
        "bibliometric",
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
        r"\bn\s*=\s*\d+",
        r"survey.*\d+.*participants?",
        r"statistical analysis",
        r"regression|correlation|anova|t[- ]?test|chi[- ]?square",
        r"questionnaire|measurement|hypothesis",
        r"significant.*p\s*[<>]|p\s*[<>]\s*0\.",
        r"quantitative|quantitatively",
        r"survey",
        r"numerical",
        r"sample size|sample",
        r"participants?|subjects?|respondents?",
        r"data from[\s\S]*?(?:firm|company|provider|organization|source)",
        r"significant[\s\S]*?(?:impact|effect|relationship)",
        r"sensitivity (?:test|analysis)",
        r"heterogeneity analysis",
        r"sample[\s\S]*?(?:\d+|firms?|companies?|organizations?|pairs?)",
        r"empirical data|empirical (?:evidence|findings)",
        r"results (?:imply|show|indicate|suggest|reveal)",
        r"analyze[\s\S]{0,100}?(?:data|firms?|companies?|organizations?)",
        r"(?:\d+)\s+(?:firms?|companies?|organizations?|respondents?|participants?|subjects?)",
        r"affects?[\s\S]{0,100}?(?:volume|quality|performance|outcome)",
        r"configuration.*affects?|affects?.*configuration",
    ]

    QUALITATIVE_PATTERNS = [
        r"interview[s]?.*(?:participant|expert|user|developer)",
        r"interviews?",
        r"survey.*\d+.*participants?|survey of",
        r"ethnograph",
        r"grounded theory",
        r"thematic analysis",
        r"content analysis",
        r"observational study|observation",
        r"field work|fieldwork",
        r"focus group",
        r"phenomenological",
        r"qualitative|qualitatively",
        r"in-depth|in depth",
        r"semi-structured|unstructured",
        r"evaluate[\s\S]*?(?:with|of|for)[\s\S]*?(?:\d+|organization|company|firm|provider|practitioner)",
        r"assess(?:ed|ment|ments?)[\s\S]*?(?:organization|company|firm|provider|case)",
        r"(?:study|research)[\s\S]*?(?:investigated|examined|analyzed|explored)",
        r"examines[\s\S]*?(?:case|firm|company|scenario)",
    ]

    CASESTUDY_INDICATORS = [
        r"case study|case studies|case-study|case[- ]based",
        r"multiple[- ]case|single[- ]case|comparative[- ]case",
        r"study of (?:two|three|four|five|six|seven|eight|nine|ten|\d+)[\s\S]*?(?:cases?|firms?|companies?|organizations?|relationships?)",
    ]

    METHOD_INDICATORS = [
        r"data collection|data gathered|data were collected",
        r"empirical study|empirical investigation",
        r"experimental design|experiment",
        r"quasi-experimental",
        r"study design",
        r"methodology|methods",
        r"longitudinal|cross-sectional",
        r"validation|evaluated",
        r"structural model|path model|SEM|sem|m-TISM|TISM",
        r"modeling approach|model evaluation|model development",
        r"text mining|data mining|machine learning|computational",
        r"validated (?:by|using|with) real|real (?:data|information)",
        r"evolutionary (?:algorithm|heuristic)",
        r"process view|process approach|process model",
    ]

    @classmethod
    def detect_study_type(cls, title: Optional[str], abstract: Optional[str], keywords: Optional[str]) -> StudyType:
        """Detect study type from text content with empirical-first priority

        Design Decisions:
        - Empirical classification has priority because many papers combine literature
          reviews WITH empirical research (e.g., building model from lit review, then
          validating with case studies). The empirical nature is more important.
        - Special case: Pure literature review studies (e.g., bibliometric, systematic
          review) with weak empirical signals are classified as LITERATURE_REVIEW to
          avoid false positives.
        - Case studies are given separate category (CASE_STUDY) from other empirical types.

        Priority Order:
        1. Editorial (news, commentary) - most specific
        2. Empirical (pattern-scored: interviews, surveys, case studies, etc.)
        3. Literature Review (explicit review types - checked if no strong empirical signals)
        4. Conceptual/Theoretical (frameworks, opinions, no empirical indicators)
        5. Unknown (default)

        Example Classifications:
        - "A literature review building a model, validated via 4 case studies" → CASE_STUDY
        - "A bibliometric analysis of 200 publications" → LITERATURE_REVIEW (weak empirical)
        - "Interviews with 12 managers about digital transformation" → EMPIRICAL_QUALITATIVE
        """
        # We can assume that title and abstract are already normalized
        # These words in the title is always decisive for literature review
        if "systematic literature review" in title or "systematic review" in title or "literature review" in title:
            return StudyType.LITERATURE_REVIEW

        combined_text = " ".join(filter(None, [title, abstract, " ".join(keywords or [])]))

        if not combined_text:
            return StudyType.UNKNOWN

        text_lower = combined_text.lower()

        # Check explicit editorial first
        if any(cls._has_indicator(text_lower, ind) for ind in cls.EDITORIAL_INDICATORS):
            return StudyType.EDITORIAL

        # Check empirical
        empirical_info = cls._detect_empirical_research(text_lower)

        # Special case: Pure literature review studies (e.g., bibliometric, systematic reviews)
        # may have weak quantitative pattern matches (e.g., "analyzed 200 publications") but are
        # fundamentally literature reviews, not empirical studies. If explicit literature review
        # indicators exist AND total empirical score is weak (≤3), classify as LITERATURE_REVIEW.
        # This avoids misclassifying bibliometric analyses as empirical research.
        has_explicit_lit_review = any(cls._has_indicator(text_lower, ind) for ind in cls.LITERATURE_REVIEW_INDICATORS)
        if has_explicit_lit_review and empirical_info["total_score"] <= 2:
            return StudyType.LITERATURE_REVIEW

        if empirical_info["is_empirical"]:
            return empirical_info["type"]  # Return the StudyType enum directly

        # Check for ambiguous papers with some empirical signals but below threshold
        if empirical_info["total_score"] > 0 and empirical_info["total_score"] < 2:
            return StudyType.UNKNOWN

        # Fall back to literature review if explicit indicators exist
        if has_explicit_lit_review:
            return StudyType.LITERATURE_REVIEW

        if any(cls._has_indicator(text_lower, ind) for ind in cls.CONCEPTUAL_INDICATORS):
            return StudyType.CONCEPTUAL

        return StudyType.UNKNOWN

    @classmethod
    def _detect_empirical_research(cls, text: str) -> Dict[str, Any]:
        """Detect empirical research with sophisticated pattern matching"""
        text_lower = text.lower()

        quant_score = sum(1 for p in cls.QUANTITATIVE_PATTERNS if re.search(p, text_lower))
        qual_score = sum(1 for p in cls.QUALITATIVE_PATTERNS if re.search(p, text_lower))
        case_score = sum(1 for p in cls.CASESTUDY_INDICATORS if re.search(p, text_lower))
        method_score = sum(1 for p in cls.METHOD_INDICATORS if re.search(p, text_lower))

        total_score = quant_score + qual_score + case_score + method_score
        # Case studies are definitively empirical, even if only case_score > 0
        is_empirical = case_score > 0 or total_score >= 2

        # Determine type as StudyType enum
        if case_score > 0:
            study_type = StudyType.CASE_STUDY
        elif quant_score > qual_score:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        elif qual_score > quant_score:
            study_type = StudyType.EMPIRICAL_QUALITATIVE
        elif quant_score > 0 and qual_score > 0:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        elif method_score > 0:
            # Default to quantitative for empirical papers identified by methodology indicators
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        elif total_score > 0 and total_score < 2:
            # Has some empirical indicators but below threshold - needs manual review
            study_type = StudyType.UNKNOWN
        else:
            study_type = StudyType.UNKNOWN

        confidence = min(total_score / 10.0, 1.0)

        return {
            "is_empirical": is_empirical,
            "type": study_type,
            "confidence": confidence,
            "quant_score": quant_score,
            "qual_score": qual_score,
            "case_score": case_score,
            "method_score": method_score,
            "total_score": total_score,
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
        self.complete = config.get("complete", "strict")

        self.exclusion_keywords = self._flatten_keywords(config.get("exclude", {}).get("keywords", {}))
        self.inclusion_keywords = config.get("include", {}).get("keywords", {})

        self.inclusion_thresholds = config.get("include", {}).get("thresholds", {})
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

    @staticmethod
    def _calculate_inclusion_score(matches: Dict[str, list], keywords: Dict[str, list]) -> float:
        """
        Calculate inclusion score requiring matches from ALL groups.

        Args:
            matches: dict like {"innovation": 2, "organization": 1, "collaboration": 0}
                    where keys are group names and values are match counts

        Returns:
            float between 0.0 and 1.0
        """
        if not matches:
            return 0.0

        total_groups = len(keywords)
        max_possible_matches = sum(len(v) for v in keywords.values())
        # Count how many groups have at least one match
        groups_with_matches = sum(1 for match in matches.values() if len(match) > 0)

        # Score: what fraction of groups are represented?
        group_coverage = groups_with_matches / total_groups

        # Also count total matches (more matches = higher score)
        total_matches = sum(len(v) for v in matches.values())
        match_density = min(total_matches / max_possible_matches, 1.0)

        # Combine: require ALL groups (70%) + reward more matches (30%)
        final_score = (0.7 * group_coverage) + (0.3 * match_density)

        return final_score

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

        # 1. CHECK COMPLETENESS: Exclude if title, abstract, or keywords missing
        # Also validate that abstract is substantive (not just boilerplate)
        # Title/Abstract must always be there, keywords required if complete=="strict"
        title = title.strip() if title else ""
        abstract = abstract.strip() if abstract else ""

        has_title = title
        has_abstract = abstract and is_substantive_abstract(abstract)
        has_keywords = self.complete != "strict" or (
            keywords and len(keywords) > 0 and any(k.strip() for k in keywords)
        )

        if not (has_title and has_abstract and has_keywords):
            # Return EXCLUDED_INCOMPLETE decision
            missing_parts = []
            if not has_title:
                missing_parts.append("title")
            if not abstract or not abstract.strip() or abstract.strip().upper() == "N/A":
                missing_parts.append("abstract")
            elif not is_substantive_abstract(abstract):
                missing_parts.append("abstract (boilerplate)")
            if not has_keywords:
                missing_parts.append("keywords")

            reason = f"incomplete metadata: missing '{', '.join(missing_parts)}'"
            excluded_incomplete = KeywordScreening(
                passed=False,
                study_type=StudyType.UNKNOWN,
                screening_decision=ScreeningDecision.EXCLUDED_INCOMPLETE,
                is_empirical=False,
                is_conceptual=False,
                is_literature_review=False,
                keyword_screening_confidence=1.0,
                exclusion_reason=reason,
                metadata=ProcessingMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    duration=0,
                ),
            )
            return (excluded_incomplete, False, reason)

        combined_text = " ".join(filter(None, [title, abstract, " ".join(keywords or [])]))
        screening_decision = ScreeningDecision.PENDING

        # 2. DETECT STUDY TYPE (implicit)
        # CHECK FOR SYSTEMATIC/LITERATURE REVIEW (priority over all other screening)
        # If title contains review-type keywords, automatically include with high confidence
        # Matches: "systematic literature review", "systematic review", "literature review"

        # If abstract is missing, force UNKNOWN study type
        detected_study_type = StudyTypeDetector.detect_study_type(title, abstract, keywords)

        # Check if excluded by study_type
        study_type_exclusion = None
        if detected_study_type.value in self.excluded_study_types:
            study_type_exclusion = f"study_type: '{detected_study_type.value}' is excluded"

        # 3. CHECK EXCLUSION KEYWORDS
        matched_exclusion_keywords = []
        for keyword in self.exclusion_keywords:
            if KeywordMatcher.matches(keyword, combined_text):
                matched_exclusion_keywords.append(keyword)

        exclusion_reason = None
        if matched_exclusion_keywords:
            exclusion_reason = f"excluded keywords found: {', '.join(matched_exclusion_keywords[:3])}"
        elif study_type_exclusion:
            exclusion_reason = study_type_exclusion

        # 4. CALCULATE INCLUSION SCORE
        matched_inclusion_keywords_grouped = {}

        for group, keywords in self.inclusion_keywords.items():
            for keyword in keywords:
                if KeywordMatcher.matches(keyword, combined_text):
                    matched_inclusion_keywords_grouped[group] = matched_inclusion_keywords_grouped.get(group, []) + [keyword]
        
        # Flatten to list for KeywordScreening model
        matched_inclusion_keywords = sum(matched_inclusion_keywords_grouped.values(), [])
        inclusion_score = self._calculate_inclusion_score(matched_inclusion_keywords_grouped, self.inclusion_keywords)

        # 5. DETERMINE SCREENING DECISION
        should_include = True
        final_exclusion_reason = None

        if study_type_exclusion:
            final_exclusion_reason = exclusion_reason
            screening_decision = ScreeningDecision.EXCLUDED
        elif self.mode == "soft":
            should_include = True
        elif matched_exclusion_keywords:
            should_include = False
            final_exclusion_reason = exclusion_reason
            screening_decision = ScreeningDecision.EXCLUDED
        elif self.mode == "inclusion_required":
            if inclusion_score == 0 or not self.inclusion_keywords:
                should_include = False
                final_exclusion_reason = "no inclusion keywords matched"
                screening_decision = ScreeningDecision.EXCLUDED
            elif inclusion_score > self.inclusion_thresholds["auto_accept"]:
                should_include = True
                screening_decision = ScreeningDecision.INCLUDED
            elif inclusion_score > self.inclusion_thresholds["manual_review"]:
                should_include = False
                screening_decision = ScreeningDecision.MANUAL_REVIEW
            else:
                should_include = False
                final_exclusion_reason = "inclusion score below threshold"
                screening_decision = ScreeningDecision.EXCLUDED
    
        # 6. BUILD KEYWORD SCREENING MODEL
        duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Set inclusion_reason to reflect systematic review preference
        inclusion_reason = None
        if inclusion_score > 0:
            inclusion_reason = f"matched {len(matched_inclusion_keywords)} inclusion keywords, score {inclusion_score:.2f}"

        keyword_screening = KeywordScreening(
            passed=should_include,
            screening_decision=screening_decision,
            study_type=detected_study_type,
            inclusion_keywords=matched_inclusion_keywords,
            inclusion_threshold=len(self.inclusion_keywords) if self.inclusion_keywords else None,
            exclusion_keywords=matched_exclusion_keywords,
            is_empirical=detected_study_type
                in [StudyType.EMPIRICAL_QUALITATIVE, StudyType.EMPIRICAL_QUANTITATIVE, StudyType.CASE_STUDY],
            is_conceptual=detected_study_type in [StudyType.CONCEPTUAL, StudyType.EDITORIAL, StudyType.THEORETICAL],
            is_literature_review=detected_study_type == StudyType.LITERATURE_REVIEW,
            keyword_screening_confidence=min(
                1.0 if self.complete != "strict" else 0.8, inclusion_score / max(1, len(self.inclusion_keywords))
            ),
            exclusion_reason=final_exclusion_reason,
            inclusion_reason=inclusion_reason,
            metadata=ProcessingMetadata(duration_seconds=duration_seconds, success=True),
        )

        return keyword_screening, should_include, final_exclusion_reason


class KeywordScreeningStep(BaseStep):
    """Keyword-based screening step with implicit study type detection"""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate keyword_screening step configuration"""
        errors = []

        if "mode" in config:
            mode = config["mode"]
            if mode not in ["inclusion_required", "exclusion_only", "soft"]:
                errors.append(f"'mode' must be one of: inclusion_required, exclusion_only, soft (got {mode})")

        if "complete" in config:
            complete = config["complete"]
            if complete not in ["strict"]:
                errors.append("'complete' must be one of: strict")

        if "inclusion_is_final" in config:
            inclusion_is_final = config["inclusion_is_final"]
            if not isinstance(inclusion_is_final, bool):
                errors.append("'inclusion_is_final' must be a boolean")

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

        self.inclusion_is_final = config.get("inclusion_is_final", False)

        screener = KeywordScreener(config)

        results = {
            "total_papers": self.db.count(primary_only=False),
            "screened": 0,
            "passed": 0,
            "failed": 0,
            "study_types": {},
            "exclusion_reasons": {},
        }

        # Process each non duplicate paper, this is idempotent
        all_papers = self.db.find(
            predicate=lambda p: not p.is_excluded and not p.is_included and not p.screening.keyword_screening,
            primary_only=True,
        )

        for i, paper in enumerate(all_papers):
            screening, passed, exclusion_reason = screener.screen_paper(
                title=paper.title,
                abstract=paper.abstract,
                keywords=paper.keywords,
            )

            if not dry_run:
                paper.screening.keyword_screening = screening
                paper.screening.current_stage = "keyword_screening passed"

                if (
                    paper.screening.keyword_screening.screening_decision != ScreeningDecision.PENDING
                    and paper.screening.final_decision == ScreeningDecision.PENDING
                ):
                    if paper.screening.keyword_screening.screening_decision in [
                        ScreeningDecision.EXCLUDED,
                        ScreeningDecision.EXCLUDED_INCOMPLETE,
                    ]:
                        paper.screening.final_decision = paper.screening.keyword_screening.screening_decision
                        paper.screening.final_decision_by = "automated:keyword_screening"
                    elif (
                        self.inclusion_is_final
                        and paper.screening.keyword_screening.screening_decision == ScreeningDecision.INCLUDED
                    ):
                        paper.screening.final_decision = paper.screening.keyword_screening.screening_decision
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
