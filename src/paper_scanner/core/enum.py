from enum import Enum

# ============================================================================
# ENUMS
# ============================================================================

class PaperType(str, Enum):
    """Types of publications"""
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    THESIS = "thesis"
    TECHNICAL_REPORT = "technical_report"
    WORKING_PAPER = "working_paper"
    PREPRINT = "preprint"
    PATENT = "patent"
    REPORT = "report"
    DATASET = "dataset"
    OTHER = "other"


class StudyType(str, Enum):
    """Research methodology types"""
    EMPIRICAL_QUALITATIVE = "empirical_qualitative"
    EMPIRICAL_QUANTITATIVE = "empirical_quantitative"
    EMPIRICAL_MIXED = "empirical_mixed"
    LITERATURE_REVIEW = "literature_review"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    CONCEPTUAL = "conceptual"
    THEORETICAL = "theoretical"
    CASE_STUDY = "case_study"
    UNKNOWN = "unknown"


class QualityTier(str, Enum):
    """Publication quality indicators"""
    PEER_REVIEWED_JOURNAL = "peer_reviewed_journal"
    PEER_REVIEWED_CONFERENCE = "peer_reviewed_conference"
    BOOK_CHAPTER = "book_chapter"
    WORKING_PAPER = "working_paper"
    PREPRINT = "preprint"
    GREY_LITERATURE = "grey_literature"
    UNKNOWN = "unknown"


class DiscoveryMethod(str, Enum):
    """How paper was discovered"""
    FILE_PATH = "file_path"
    KEYWORD_SEARCH = "keyword_search"
    BACKWARD_CITATION = "backward_citation"
    FORWARD_CITATION = "forward_citation"
    LITERATURE_REVIEW_MINING = "literature_review_mining"
    RECOMMENDATION = "recommendation"
    MANUAL = "manual" # Default
    API = "api"


class ScreeningDecision(str, Enum):
    """Screening decisions"""
    INCLUDED = "included"
    EXCLUDED = "excluded"
    PENDING = "pending"
    MANUAL_REVIEW = "manual_review"
    UNCERTAIN = "uncertain"
    EXCLUDED_DUPLICATE = "excluded_duplicate"
    EXCLUDED_MANUAL = "excluded_manual"


class CitationDirection(str, Enum):
    """Direction of citation fetching"""
    FORWARD = "forward"
    BACKWARD = "backward"


class StepStatus(str, Enum):
    """Status of a processing step

    Returned by BaseStep.execute() in StepResult.status field. Only SUCCESS, WARNING,
    ERROR, and HALTED are in active use. READY and SKIPPED are reserved for future use.

    Values:
        SUCCESS: Step completed successfully with no issues (value: "ok")
        WARNING: Step completed with partial success or recoverable issues (value: "warning")
        ERROR: Step failed to achieve its objective (value: "error")
        HALTED: Pipeline intentionally halted via halt step (value: "halted")
        READY: Reserved for future use (value: "ready")
        SKIPPED: Reserved for future use (value: "skipped")
        FINAL: Last step in pipeline, internal use only (value: "final")
    """
    SUCCESS = "ok"
    WARNING = "warning"
    ERROR = "error"
    HALTED = "halted"
    READY = "ready"
    SKIPPED = "skipped"
    FINAL = "final"  # Internal use only
