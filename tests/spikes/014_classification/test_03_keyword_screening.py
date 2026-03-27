"""
Keyword Screening - Test
Tests keyword-based screening with scoring mechanism and implicit study_type detection

Run with:
    pytest test_03_keyword_screening.py -v
    or
    python test_03_keyword_screening.py --manual
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from paper_scanner.core.enum import ScreeningDecision, StudyType
from paper_scanner.core.models import KeywordScreening, ProcessingMetadata


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
        # Escape all special chars except *
        escaped = re.escape(text)
        # Unescape * since we use it for wildcards
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

        # Escape special regex chars (but keep * for wildcard conversion)
        escaped = KeywordMatcher.escape_special_chars(pattern)

        # Convert wildcards to regex
        if escaped.startswith("*") and escaped.endswith("*"):
            # *keyword* - match anywhere
            core = escaped[1:-1]
            return core
        elif escaped.startswith("*"):
            # *keyword - match end
            core = escaped[1:]
            return rf"\w*{core}\b"
        elif escaped.endswith("*"):
            # keyword* - match beginning
            core = escaped[:-1]
            return rf"\b{core}\w*"
        else:
            # keyword - exact match with word boundaries
            return rf"\b{escaped}\b"

    @classmethod
    def matches(cls, pattern: str, text: Optional[str]) -> bool:
        """Check if pattern matches text

        Args:
            pattern: Keyword pattern (may include wildcards)
            text: Text to match against

        Returns:
            True if pattern matches
        """
        if not text:
            return False

        text_norm = cls.normalize_text(text)
        regex_pattern = cls.wildcard_to_regex(pattern)

        try:
            return bool(re.search(regex_pattern, text_norm))
        except re.error:
            # Fallback to simple substring match if regex fails
            return pattern.lower().replace("*", "") in text_norm

    @classmethod
    def find_all(cls, pattern: str, text: Optional[str]) -> List[str]:
        """Find all matches of pattern in text

        Args:
            pattern: Keyword pattern (may include wildcards)
            text: Text to search

        Returns:
            List of matched substrings
        """
        if not text:
            return []

        text_norm = cls.normalize_text(text)
        regex_pattern = cls.wildcard_to_regex(pattern)

        try:
            return re.findall(regex_pattern, text_norm)
        except re.error:
            # Fallback: return the pattern itself if it matches
            if pattern.lower().replace("*", "") in text_norm:
                return [pattern.lower().replace("*", "")]
            return []


class StudyTypeDetector:
    """
    Automatically detect study type from keywords and content.
    Uses sophisticated pattern matching for empirical research detection.

    Rules (implicit, applied in order):
    1. If has "editorial", "news", "commentary" → EDITORIAL
    2. If has literature review keywords → LITERATURE_REVIEW
    3. If has conceptual keywords (and no empirical indicators) → CONCEPTUAL
    4. If has empirical keywords/patterns → EMPIRICAL_QUANTITATIVE/QUALITATIVE
    5. Default → UNKNOWN
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

    # Regex patterns for quantitative empirical research
    QUANTITATIVE_PATTERNS = [
        r"\bn\s*=\s*\d+",  # sample size: n = 123
        r"survey.*\d+.*participants?",  # survey with 50 participants
        r"statistical analysis",
        r"regression|correlation|anova|t[- ]?test|chi[- ]?square",
        r"questionnaire|measurement|hypothesis",
        r"significant.*p\s*[<>]|p\s*[<>]\s*0\.",  # p < 0.05
        r"quantitative|quantitatively",
        r"numerical",
        r"sample size",
        r"participants?|subjects?|respondents?",
    ]

    # Regex patterns for qualitative empirical research
    QUALITATIVE_PATTERNS = [
        r"interview[s]?.*(?:participant|expert|user|developer)",
        r"interviews?",
        r"survey.*\d+.*participants?|survey of",  # Survey as empirical method (often quantitative but can be qual)
        r"case study|case studies|case-study",
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
    ]

    # General method indicators (for both quant and qual)
    METHOD_INDICATORS = [
        r"data collection|data gathered|data were collected",
        r"empirical study|empirical investigation",
        r"experimental design|experiment",
        r"quasi-experimental",
        r"study design",
        r"methodology|methods",
        r"longitudinal|cross-sectional",
        r"validation|evaluated",
    ]

    @classmethod
    def detect_study_type(cls, text: Optional[str]) -> StudyType:
        """Detect study type from text content with empirical-first priority

        Design Decision: Empirical classification takes priority over literature review
        because many academic papers combine literature review WITH empirical research.
        When both are detected (e.g., "systematic review of empirical studies"),
        the empirical nature is more important for screening purposes.

        Priority Order:
        1. Editorial (news, commentary) - highest priority, excludes all else
        2. Empirical (pattern-scored: interviews, surveys, case studies, etc.)
           - More specific and actionable for research synthesis
        3. Literature Review (only explicit review types like "systematic review")
           - Lower priority because empirical + review is classified as empirical
        4. Conceptual/Theoretical (frameworks, opinions, no empirical indicators)
        5. Unknown (default when no patterns match)

        Args:
            text: Combined text (title + abstract + keywords)

        Returns:
            StudyType enum
        """
        if not text:
            return StudyType.UNKNOWN

        text_lower = text.lower()

        # 1. Check editorial (highest priority)
        if any(cls._has_indicator(text_lower, ind) for ind in cls.EDITORIAL_INDICATORS):
            return StudyType.EDITORIAL

        # 2. Check empirical BEFORE literature review (check scored patterns)
        empirical_info = cls._detect_empirical_research(text)
        if empirical_info["is_empirical"]:
            return empirical_info["type"]  # Return the StudyType enum directly

        # 3. Check literature review (after empirical check)
        if any(cls._has_indicator(text_lower, ind) for ind in cls.LITERATURE_REVIEW_INDICATORS):
            return StudyType.LITERATURE_REVIEW

        # 4. Check conceptual (only if no empirical indicators found)
        if any(cls._has_indicator(text_lower, ind) for ind in cls.CONCEPTUAL_INDICATORS):
            return StudyType.CONCEPTUAL

        return StudyType.UNKNOWN

    @classmethod
    def _detect_empirical_research(cls, text: str) -> Dict[str, Any]:
        """Detect empirical research with sophisticated pattern matching

        Uses regex patterns to find:
        - Quantitative indicators (sample size, statistics, etc.)
        - Qualitative indicators (interviews, case studies, etc.)
        - Method indicators (data collection, experimental design, etc.)

        Returns:
            Dict with:
            - is_empirical: bool
            - type: 'quantitative', 'qualitative', 'mixed', 'unknown'
            - confidence: float 0-1
            - quant_score: int
            - qual_score: int
            - method_score: int
        """
        text_lower = text.lower()

        # Count pattern matches
        quant_score = sum(1 for p in cls.QUANTITATIVE_PATTERNS if re.search(p, text_lower))
        qual_score = sum(1 for p in cls.QUALITATIVE_PATTERNS if re.search(p, text_lower))
        method_score = sum(1 for p in cls.METHOD_INDICATORS if re.search(p, text_lower))

        total_score = quant_score + qual_score + method_score

        # Determine empirical status (need at least 2 matching patterns)
        is_empirical = total_score >= 2

        # Calculate confidence
        confidence = min(total_score / 10.0, 1.0)

        # Determine type based on ratio
        if quant_score > qual_score:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE
        elif qual_score > quant_score:
            study_type = StudyType.EMPIRICAL_QUALITATIVE
        elif quant_score > 0 and qual_score > 0:
            study_type = StudyType.EMPIRICAL_QUANTITATIVE  # Default to quantitative for mixed
        else:
            study_type = StudyType.UNKNOWN

        return {
            "is_empirical": is_empirical,
            "type": study_type,
            "confidence": confidence,
            "quant_score": quant_score,
            "qual_score": qual_score,
            "method_score": method_score,
            "total_score": total_score,
        }

    @staticmethod
    def _has_indicator(text: str, indicator: str) -> bool:
        """Check if text contains indicator"""
        return indicator.lower() in text


class KeywordScreener:
    """
    Keyword-based screening with scoring mechanism.

    Scoring:
    - Exclusion keywords: if ANY match, score = 0 (excluded)
    - Inclusion keywords: score = count of matched keywords
    - Score distribution: papers with higher scores are more relevant
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize with screening config

        Config structure:
        {
            "exclude": {
                "keywords": {
                    "domains": ["medical", "healthcare", ...],
                    "other": ["agriculture", "education", ...]
                },
                "study_types": ["editorial", ...]
            },
            "include": {
                "keywords": {
                    "domains": ["software", "technology", ...],
                    "practices": ["agile", "lean", ...]
                }
            },
            "mode": "inclusion_required" | "exclusion_only" | "soft"
        }
        """
        self.config = config
        self.mode = config.get("mode", "inclusion_required")

        # Parse exclusion keywords (flatten nested structure)
        self.exclusion_keywords = self._flatten_keywords(config.get("exclude", {}).get("keywords", {}))

        # Parse inclusion keywords (flatten nested structure)
        self.inclusion_keywords = self._flatten_keywords(config.get("include", {}).get("keywords", {}))

        # Study type exclusions
        self.excluded_study_types = config.get("exclude", {}).get("study_types", [])

    @staticmethod
    def _flatten_keywords(keywords_config: Any) -> List[str]:
        """Flatten nested keyword structure into flat list

        Input can be:
        - Dict of categories with lists: {"domains": ["a", "b"], "other": ["c"]}
        - List of strings: ["a", "b", "c"]

        Output: flat list ["a", "b", "c"]
        """
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
        study_type_explicit: Optional[str] = None,
        verbose: bool = False,
    ) -> Tuple[KeywordScreening, bool, Optional[str]]:
        """Screen paper based on keywords

        Returns:
            (KeywordScreening model, should_include, exclusion_reason)
        """
        start_time = datetime.now(timezone.utc)

        # Combine all text
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
            # Must pass both gates: no exclusions AND has inclusions
            if matched_exclusion_keywords or study_type_exclusion:
                should_include = False
                final_exclusion_reason = exclusion_reason
            elif inclusion_score == 0 and self.inclusion_keywords:
                should_include = False
                final_exclusion_reason = "no inclusion keywords matched"

        elif self.mode == "exclusion_only":
            # Only filter out exclusions
            if matched_exclusion_keywords or study_type_exclusion:
                should_include = False
                final_exclusion_reason = exclusion_reason

        elif self.mode == "soft":
            # Keywords for ranking only, always include
            should_include = True

        # 5. BUILD KEYWORD SCREENING MODEL
        duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        keyword_screening = KeywordScreening(
            passed=should_include,
            study_type=detected_study_type,
            screening_decision=ScreeningDecision.INCLUDED if should_include else ScreeningDecision.EXCLUDED,
            inclusion_keywords=matched_inclusion_keywords,
            inclusion_threshold=len(self.inclusion_keywords) if self.inclusion_keywords else None,
            exclusion_keywords=matched_exclusion_keywords,
            is_empirical=detected_study_type in [StudyType.EMPIRICAL_QUALITATIVE, StudyType.EMPIRICAL_QUANTITATIVE],
            is_conceptual=detected_study_type == StudyType.CONCEPTUAL,
            is_literature_review=detected_study_type == StudyType.LITERATURE_REVIEW,
            keyword_screening_confidence=min(1.0, inclusion_score / max(1, len(self.inclusion_keywords))),
            exclusion_reason=final_exclusion_reason,
            inclusion_reason=f"matched {inclusion_score} inclusion keywords" if inclusion_score > 0 else None,
            metadata=ProcessingMetadata(duration_seconds=duration_seconds, success=True),
        )

        return keyword_screening, should_include, final_exclusion_reason


# ============================================================================
# TESTS
# ============================================================================


class TestKeywordMatcher:
    """Tests for wildcard keyword matching"""

    def test_exact_match(self):
        """Should match exact keywords"""
        assert KeywordMatcher.matches("software", "The software tool")
        assert KeywordMatcher.matches("software", "This is software")
        assert not KeywordMatcher.matches("software", "softness is good")

    def test_wildcard_suffix(self):
        """Should match keyword* patterns"""
        assert KeywordMatcher.matches("test*", "testing is important")
        assert KeywordMatcher.matches("test*", "tests are good")
        assert not KeywordMatcher.matches("test*", "contest is fun")

    def test_wildcard_prefix(self):
        """Should match *keyword patterns"""
        assert KeywordMatcher.matches("*test", "contest is fun")
        assert KeywordMatcher.matches("*test", "pretest phase")
        assert not KeywordMatcher.matches("*test", "testing begins")

    def test_wildcard_both(self):
        """Should match *keyword* patterns"""
        assert KeywordMatcher.matches("*test*", "testing contest pretest")
        assert KeywordMatcher.matches("*test*", "attest to the value")

    def test_case_insensitive(self):
        """Should match case-insensitively"""
        assert KeywordMatcher.matches("software", "SOFTWARE")
        assert KeywordMatcher.matches("software", "SoftWare")

    def test_no_match(self):
        """Should not match unrelated text"""
        assert not KeywordMatcher.matches("software", "hardware is fun")


class TestStudyTypeDetector:
    """Tests for implicit study type detection with regex patterns"""

    def test_detect_editorial(self):
        """Should detect editorial study type"""
        text = "Editorial: The state of the art in software engineering"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EDITORIAL

    def test_detect_literature_review(self):
        """Should detect literature review"""
        text = "A systematic review of agile practices in software development"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.LITERATURE_REVIEW

    def test_detect_conceptual(self):
        """Should detect conceptual/theoretical paper"""
        text = "A theoretical framework for understanding organizational change"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.CONCEPTUAL

    def test_detect_empirical_qualitative(self):
        """Should detect qualitative empirical paper"""
        text = "A qualitative case study examining interviews with agile practitioners. We conducted interviews with 12 participants using thematic analysis."
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUALITATIVE

    def test_detect_empirical_quantitative(self):
        """Should detect quantitative empirical paper"""
        text = "An empirical study of agile adoption. Survey of 200 participants. Statistical analysis using t-test (p < 0.05) showed significant correlation."
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUANTITATIVE

    def test_detect_unknown(self):
        """Should default to UNKNOWN for unclear papers"""
        text = "Something about computers and innovation"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.UNKNOWN

    def test_detect_empirical_with_sample_size(self):
        """Should detect empirical from sample size notation"""
        text = "A study with n = 150 participants using regression analysis"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUANTITATIVE

    def test_detect_empirical_with_interviews(self):
        """Should detect empirical from interview keywords"""
        text = "We conducted interviews with 15 software developers and performed content analysis on the transcripts"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUALITATIVE

    def test_detect_empirical_case_study(self):
        """Should detect empirical from case study keyword"""
        text = "A case study of agile adoption in a large organization. We gathered data through observational study over 18 months."
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUALITATIVE

    def test_detect_empirical_statistical_test(self):
        """Should detect empirical from statistical analysis keywords"""
        text = "ANOVA analysis of variance showed significant results (p < 0.001)"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EMPIRICAL_QUANTITATIVE

    def test_empirical_research_detection_scores(self):
        """Should calculate empirical research scores correctly"""
        # High confidence quantitative
        text1 = "Survey of n = 500. Regression analysis. Hypothesis testing. p < 0.05"
        info1 = StudyTypeDetector._detect_empirical_research(text1)
        assert info1["is_empirical"] is True
        assert info1["type"] == StudyType.EMPIRICAL_QUANTITATIVE
        assert info1["quant_score"] >= 3
        assert info1["confidence"] > 0.3

        # High confidence qualitative
        text2 = "Interviews with 20 experts. Thematic analysis. Phenomenological approach."
        info2 = StudyTypeDetector._detect_empirical_research(text2)
        assert info2["is_empirical"] is True
        assert info2["type"] == StudyType.EMPIRICAL_QUALITATIVE
        assert info2["qual_score"] >= 3

        # Mixed methods
        text3 = "Survey (n=100) with interviews. Both statistical analysis and thematic analysis."
        info3 = StudyTypeDetector._detect_empirical_research(text3)
        assert info3["is_empirical"] is True
        # Type is StudyType enum now

    def test_empirical_requires_minimum_threshold(self):
        """Should require at least 2 matching patterns for empirical classification"""
        # Single keyword shouldn't trigger empirical
        text_weak = "empirical"
        info_weak = StudyTypeDetector._detect_empirical_research(text_weak)
        assert info_weak["is_empirical"] is False

        # Multiple patterns should trigger
        text_strong = "empirical study with data collection"
        info_strong = StudyTypeDetector._detect_empirical_research(text_strong)
        assert info_strong["is_empirical"] is True

    def test_study_type_priority_order(self):
        """Editorial should take priority over other types"""
        # Editorial takes priority
        text = "Editorial discussing empirical case study of agile"
        study_type = StudyTypeDetector.detect_study_type(text)
        assert study_type == StudyType.EDITORIAL

        # Literature review takes priority over empirical
        text2 = "A systematic review of empirical studies on agile adoption"
        study_type2 = StudyTypeDetector.detect_study_type(text2)
        assert study_type2 == StudyType.LITERATURE_REVIEW

    def test_conceptual_vs_empirical_distinction(self):
        """Should distinguish between conceptual and empirical"""
        # Purely conceptual
        text_concept = "A theoretical framework for understanding innovation adoption"
        study_type_concept = StudyTypeDetector.detect_study_type(text_concept)
        assert study_type_concept == StudyType.CONCEPTUAL

        # Empirical despite framework mention
        text_empirical = "A case study testing our framework through interviews with 30 practitioners"
        study_type_empirical = StudyTypeDetector.detect_study_type(text_empirical)
        assert study_type_empirical == StudyType.EMPIRICAL_QUALITATIVE


class TestKeywordScreener:
    """Tests for keyword screening with scoring"""

    def test_flatten_keywords_dict(self):
        """Should flatten nested keyword dict"""
        config = {
            "exclude": {"keywords": {"domains": ["medical", "healthcare"], "other": ["agriculture"]}},
            "include": {},
        }
        screener = KeywordScreener(config)
        assert "medical" in screener.exclusion_keywords
        assert "healthcare" in screener.exclusion_keywords
        assert "agriculture" in screener.exclusion_keywords

    def test_flatten_keywords_list(self):
        """Should handle flat list of keywords"""
        config = {"exclude": {"keywords": ["medical", "healthcare"]}, "include": {}}
        screener = KeywordScreener(config)
        assert "medical" in screener.exclusion_keywords
        assert "healthcare" in screener.exclusion_keywords

    def test_exclusion_hard_reject(self):
        """Should hard exclude papers with exclusion keywords"""
        config = {
            "exclude": {"keywords": {"domains": ["medical", "healthcare"]}},
            "include": {},
            "mode": "inclusion_required",
        }
        screener = KeywordScreener(config)

        screening, should_include, reason = screener.screen_paper(
            title="Healthcare system improvement", abstract="A study of patient outcomes"
        )

        assert should_include is False
        assert "healthcare" in reason.lower() or "medical" in reason.lower()
        assert len(screening.exclusion_keywords) > 0

    def test_inclusion_score_matching(self):
        """Should score based on inclusion keyword matches"""
        config = {
            "exclude": {"keywords": {}},
            "include": {"keywords": {"practices": ["agile", "scrum", "lean"]}},
            "mode": "soft",
        }
        screener = KeywordScreener(config)

        screening, should_include, _ = screener.screen_paper(
            title="Agile and Scrum in practice", abstract="We studied agile teams using lean principles"
        )

        # All three inclusion keywords match
        assert len(screening.inclusion_keywords) >= 2
        assert screening.keyword_screening_confidence > 0

    def test_implicit_study_type_detection(self):
        """Should implicitly detect study type"""
        config = {"exclude": {"keywords": {}, "study_types": ["editorial"]}, "include": {}}
        screener = KeywordScreener(config)

        # Editorial paper
        screening1, should_include1, _ = screener.screen_paper(title="Editorial: Future of software engineering")
        assert screening1.study_type == StudyType.EDITORIAL
        assert should_include1 is False

        # Empirical paper
        screening2, should_include2, _ = screener.screen_paper(
            title="Empirical study of agile adoption", abstract="We conducted a case study evaluation of agile teams"
        )
        assert screening2.study_type in [StudyType.EMPIRICAL_QUALITATIVE, StudyType.EMPIRICAL_QUANTITATIVE]
        assert screening2.is_empirical is True

    def test_mode_inclusion_required(self):
        """Mode: inclusion_required requires both inclusion keywords and no exclusions"""
        config = {
            "exclude": {"keywords": {"domains": ["medical"]}},
            "include": {"keywords": {"practices": ["agile", "scrum"]}},
            "mode": "inclusion_required",
        }
        screener = KeywordScreener(config)

        # Has inclusion keywords, no exclusions → PASS
        screening1, should_include1, _ = screener.screen_paper(title="Agile adoption in software teams")
        assert should_include1 is True

        # Has inclusion keywords but also has exclusions → FAIL
        screening2, should_include2, _ = screener.screen_paper(
            title="Agile adoption in healthcare", abstract="Medical teams using scrum"
        )
        assert should_include2 is False

        # No inclusion keywords → FAIL
        screening3, should_include3, _ = screener.screen_paper(title="Software teams work together")
        assert should_include3 is False

    def test_mode_exclusion_only(self):
        """Mode: exclusion_only only filters exclusions, includes everything else"""
        config = {
            "exclude": {"keywords": {"domains": ["medical"]}},
            "include": {"keywords": {"practices": ["agile"]}},
            "mode": "exclusion_only",
        }
        screener = KeywordScreener(config)

        # No exclusions → PASS (even without inclusion keywords)
        screening1, should_include1, _ = screener.screen_paper(title="Software team collaboration")
        assert should_include1 is True

        # Has exclusions → FAIL
        screening2, should_include2, _ = screener.screen_paper(title="Medical research teams")
        assert should_include2 is False

    def test_mode_soft(self):
        """Mode: soft uses keywords for ranking, never excludes"""
        config = {
            "exclude": {"keywords": {"domains": ["medical"]}},
            "include": {"keywords": {"practices": ["agile"]}},
            "mode": "soft",
        }
        screener = KeywordScreener(config)

        # Always include, but track scores
        screening1, should_include1, _ = screener.screen_paper(title="Medical teams using agile")
        assert should_include1 is True
        assert len(screening1.exclusion_keywords) > 0  # Still tracks matches
        assert len(screening1.inclusion_keywords) > 0

    def test_study_type_exclusion(self):
        """Should exclude by study_type even without keyword matches"""
        config = {
            "exclude": {"keywords": {}, "study_types": ["editorial"]},
            "include": {},
            "mode": "inclusion_required",
        }
        screener = KeywordScreener(config)

        screening, should_include, reason = screener.screen_paper(title="Editorial: The future of AI")

        assert should_include is False
        assert "editorial" in reason.lower()

    def test_keyword_screening_model_fields(self):
        """Should populate KeywordScreening model correctly"""
        config = {
            "exclude": {"keywords": {}},
            "include": {"keywords": {"practices": ["agile", "scrum"]}},
            "mode": "soft",
        }
        screener = KeywordScreener(config)

        screening, _, _ = screener.screen_paper(
            title="Agile software development practices",
            abstract="A study of agile adoption",
            keywords=["agile", "software", "teams"],
        )

        # Check model fields populated
        assert screening.study_type is not None
        assert isinstance(screening.inclusion_keywords, list)
        assert isinstance(screening.exclusion_keywords, list)
        assert screening.keyword_screening_confidence >= 0
        assert screening.is_empirical in [True, False]
        assert screening.is_conceptual in [True, False]
        assert screening.is_literature_review in [True, False]
        assert screening.metadata is not None
        assert screening.metadata.success is True


def run_manual_tests():
    """Run tests manually for debugging"""
    print("=" * 80)
    print("Keyword Screening Tests")
    print("=" * 80)

    # Test 1: Wildcard matching
    print("\n[Test 1] Wildcard keyword matching")
    assert KeywordMatcher.matches("test*", "testing is important")
    assert KeywordMatcher.matches("*test", "contest is fun")
    assert KeywordMatcher.matches("*test*", "attest to the value")
    print("  ✓ All wildcard patterns work")

    # Test 2: Study type detection
    print("\n[Test 2] Implicit study type detection")
    editorial_study = StudyTypeDetector.detect_study_type("Editorial: state of the art")
    empirical_study = StudyTypeDetector.detect_study_type("Empirical case study evaluation with data collection")
    review_study = StudyTypeDetector.detect_study_type("Systematic review meta-analysis")
    print(f"  Editorial: {editorial_study.value}")
    print(f"  Empirical: {empirical_study.value}")
    print(f"  Review: {review_study.value}")
    assert editorial_study == StudyType.EDITORIAL
    assert empirical_study in [StudyType.EMPIRICAL_QUALITATIVE, StudyType.EMPIRICAL_QUANTITATIVE]
    assert review_study == StudyType.LITERATURE_REVIEW
    print("  ✓ All study types detected correctly")

    # Test 3: Keyword screening with scoring
    print("\n[Test 3] Keyword screening with scoring")
    config = {
        "exclude": {"keywords": {"domains": ["medical", "healthcare"]}},
        "include": {"keywords": {"practices": ["agile", "scrum", "lean"]}},
        "mode": "inclusion_required",
    }
    screener = KeywordScreener(config)

    screening, include, reason = screener.screen_paper(
        title="Agile and Scrum adoption in software teams",
        abstract="An empirical case study examining agile adoption with data collection from development teams",
    )
    print(f"  Inclusion keywords matched: {screening.inclusion_keywords}")
    print(f"  Study type detected: {screening.study_type.value}")
    print(f"  Is empirical: {screening.is_empirical}")
    print(f"  Confidence: {screening.keyword_screening_confidence:.2f}")
    print(f"  Should include: {include}")
    assert include is True
    assert screening.is_empirical is True
    print("  ✓ Screening logic works correctly")

    # Test 4: Hard exclusion
    print("\n[Test 4] Hard exclusion by keywords")
    screening2, include2, reason2 = screener.screen_paper(
        title="Agile adoption in healthcare systems", abstract="A medical study of scrum teams"
    )
    print(f"  Exclusion keywords matched: {screening2.exclusion_keywords}")
    print(f"  Should include: {include2}")
    print(f"  Reason: {reason2}")
    assert include2 is False
    assert "healthcare" in screening2.exclusion_keywords or "medical" in str(reason2).lower()
    print("  ✓ Hard exclusion works correctly")

    print("\n" + "=" * 80)
    print("All manual tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    import sys

    if "--manual" in sys.argv:
        run_manual_tests()
    else:
        pytest.main([__file__, "-v"])
