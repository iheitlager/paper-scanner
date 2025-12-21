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
    MANUAL = "manual"
    API = "api"


class ScreeningDecision(str, Enum):
    """Screening decisions"""
    INCLUDED = "included"
    EXCLUDED = "excluded"
    PENDING = "pending"
    MANUAL_REVIEW = "manual_review"
    UNCERTAIN = "uncertain"

class CitationDirection(str, Enum):
    """Direction of citation fetching"""
    FORWARD = "forward"
    BACKWARD = "backward"