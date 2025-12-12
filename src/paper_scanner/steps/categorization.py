"""
Paper categorization step for quality filtering and classification.

Performs Stage 1 screening:
1. Validates paper type (keeps only peer-reviewed journal articles)
2. Detects study type (empirical vs conceptual/review)
3. Assigns quality tier based on publication venue
4. Makes include/exclude decision for downstream processing

Outputs comprehensive categorization results to screening.categorization with:
- paper_type: JOURNAL_ARTICLE, CONFERENCE, BOOK, etc.
- study_type: EMPIRICAL, REVIEW, CONCEPTUAL
- quality_tier: TIER_1, TIER_2, TIER_3
- is_empirical: boolean flag for empirical papers
- is_peer_reviewed: boolean flag for peer-reviewed venues
- reasoning: explanation of categorization decision
- metadata: processing timestamp and duration
"""

import time
import sys
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from rich.console import Console

from ..core.models import Paper, Categorization, ProcessingMetadata
from ..core.database import PapersDatabase
from ..core.enum import PaperType, StudyType, QualityTier, ScreeningDecision

# Initialize rich console for colored output
console = Console(file=sys.stderr)


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate categorization step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check enabled flag
    if "enabled" in config and not isinstance(config["enabled"], bool):
        errors.append("'enabled' must be a boolean")
    
    # Check exclude_types flag
    if "exclude_types" in config and not isinstance(config["exclude_types"], bool):
        errors.append("'exclude_types' must be a boolean")
    
    # Check exclude_reviews flag
    if "exclude_reviews" in config and not isinstance(config["exclude_reviews"], bool):
        errors.append("'exclude_reviews' must be a boolean")
    
    return len(errors) == 0, errors


# ============================================================================
# CATEGORIZATION RULES
# ============================================================================

# Paper types that are considered acceptable (peer-reviewed journal articles)
ACCEPTABLE_PAPER_TYPES = {
    'journal_article',
    'journal article',
    'article',
    'research article',
    'original article',
    'empirical article',
}

# Paper types to reject (non-peer-reviewed or conference)
REJECT_PAPER_TYPES = {
    'conference_paper',
    'conference paper',
    'conference review',
    'proceeding',
    'proceedings',
    'proceedings-article',
    'inproceedings',
    'inprocedings',  # Common typo in BibTeX
    'book',
    'inbook',
    'book_chapter',
    'book chapter',
    'book-chapter',
    'editorial',
    'editorial material',
    'commentary',
    'news',
    'erratum',
    'corrigendum',
    'retraction',
    'correction',
    'letter',
    'note',
}

# Keywords indicating literature review (reject)
REVIEW_KEYWORDS = [
    'literature review',
    'systematic review',
    'scoping review',
    'narrative review',
    'meta-analysis',
    'meta analysis',
    'metaanalysis',
    'survey',
    'overview',
    'state of the art',
    'state-of-the-art',
]

# Keywords indicating conceptual/theoretical work (reject)
CONCEPTUAL_KEYWORDS = [
    'conceptual framework',
    'conceptual model',
    'theoretical',
    'theory',
    'framework',
    'taxonomy',
    'typology',
    'opinion',
    'perspective',
    'commentary',
    'editorial',
]

# Keywords indicating empirical work (keep)
EMPIRICAL_KEYWORDS = [
    'empirical',
    'experiment',
    'experimental',
    'study',
    'evaluation',
    'analysis',
    'dataset',
    'data collection',
    'survey',
    'field study',
    'case study',
    'measurement',
    'quantitative',
    'qualitative',
    'mixed methods',
    'evaluation',
    'empirical study',
]


def _normalize_text(text: Optional[str]) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    return text.lower().strip()


def _normalize_paper_type(paper_type: Optional[str]) -> str:
    """Normalize paper type."""
    if not paper_type:
        return ""
    return _normalize_text(paper_type)


def _check_paper_type(paper_type: Optional[str]) -> Tuple[PaperType, bool, Optional[str]]:
    """
    Check paper type and determine if it's acceptable.
    
    Returns:
        (paper_type_enum, is_peer_reviewed, rejection_reason)
    """
    if not paper_type:
        # No type specified - be lenient, assume journal article
        return PaperType.ARTICLE, True, None

    normalized_type = _normalize_paper_type(paper_type)

    # Check if explicitly rejected
    if normalized_type in REJECT_PAPER_TYPES:
        if 'conference' in normalized_type or 'proceeding' in normalized_type:
            return PaperType.CONFERENCE, False, "Conference papers excluded"
        elif 'book' in normalized_type:
            return PaperType.BOOK, False, "Books excluded"
        elif 'review' in normalized_type:
            return PaperType.OTHER, False, "Review papers excluded"
        else:
            return PaperType.OTHER, False, f"Paper type '{paper_type}' excluded"

    # Check if acceptable
    if normalized_type in ACCEPTABLE_PAPER_TYPES:
        return PaperType.ARTICLE, True, None

    # Unknown type - be lenient and assume journal article
    return PaperType.ARTICLE, True, None


def _is_review_paper(title: Optional[str], abstract: Optional[str]) -> bool:
    """Check if paper is a review based on keywords."""
    combined_text = _normalize_text(f"{title or ''} {abstract or ''}")

    for keyword in REVIEW_KEYWORDS:
        if keyword.lower() in combined_text:
            return True

    return False


def _is_conceptual_paper(title: Optional[str], abstract: Optional[str]) -> bool:
    """Check if paper is conceptual/theoretical."""
    combined_text = _normalize_text(f"{title or ''} {abstract or ''}")

    # Count conceptual keywords
    conceptual_count = 0
    for keyword in CONCEPTUAL_KEYWORDS:
        if keyword.lower() in combined_text:
            conceptual_count += 1

    # Count empirical keywords to offset
    empirical_count = 0
    for keyword in EMPIRICAL_KEYWORDS:
        if keyword.lower() in combined_text:
            empirical_count += 1

    # If more conceptual than empirical, likely conceptual
    return conceptual_count > empirical_count


def _assign_quality_tier(journal: Optional[str], year: Optional[int]) -> QualityTier:
    """Assign quality tier based on journal/venue."""
    if not journal:
        return QualityTier.UNKNOWN

    journal_lower = journal.lower()

    # Tier 1: Top-tier journals in relevant fields
    tier1_keywords = [
        'nature', 'science', 'pnas', 'proceedings of the national',
        'journal of management', 'strategic management journal',
        'information systems research', 'mis quarterly',
        'journal of strategic information systems',
        'european journal of information systems',
    ]

    for keyword in tier1_keywords:
        if keyword in journal_lower:
            return QualityTier.PEER_REVIEWED_JOURNAL

    # Tier 2: Well-established journals
    tier2_keywords = [
        'journal of', 'international journal',
        'transactions on',
        'ieee',
        'acm',
        'association for computing machinery',
    ]

    for keyword in tier2_keywords:
        if keyword in journal_lower:
            return QualityTier.PEER_REVIEWED_JOURNAL

    # Default to unknown
    return QualityTier.UNKNOWN


def _categorize_paper(
    paper: Paper,
    verbose: bool = False
) -> Tuple[Categorization, bool, Optional[str]]:
    """
    Categorize a paper and determine if it should be included.

    Returns:
        (categorization_result, should_include, exclusion_reason)
    """
    step_start_time = time.time()

    # 1. Check paper type (from Paper.paper_type if available)
    paper_type, is_peer_reviewed, type_rejection = _check_paper_type(
        getattr(paper, 'paper_type', None)
    )

    # 2. Check if review paper
    is_review = _is_review_paper(paper.title, paper.abstract)

    # 3. Check if conceptual paper
    is_conceptual = _is_conceptual_paper(paper.title, paper.abstract)

    # 4. Determine study type
    if is_review:
        study_type = StudyType.LITERATURE_REVIEW
    elif is_conceptual:
        study_type = StudyType.CONCEPTUAL
    else:
        study_type = StudyType.EMPIRICAL_QUANTITATIVE  # Default empirical type

    # 5. Assign quality tier
    quality_tier = _assign_quality_tier(paper.journal, paper.year)

    # 6. Determine inclusion
    should_include = True
    exclusion_reason = None

    # Reject non-peer-reviewed papers
    if not is_peer_reviewed and type_rejection:
        should_include = False
        exclusion_reason = type_rejection

    # Reject review papers
    if is_review:
        should_include = False
        exclusion_reason = "Review paper excluded (literature review detected)"

    # Reject purely conceptual papers
    if is_conceptual and not (study_type in [
        StudyType.EMPIRICAL_QUALITATIVE,
        StudyType.EMPIRICAL_QUANTITATIVE,
        StudyType.EMPIRICAL_MIXED,
        StudyType.CASE_STUDY
    ]):
        should_include = False
        exclusion_reason = "Conceptual paper excluded (no empirical component)"

    # Create categorization result
    duration = time.time() - step_start_time

    # Confidence based on availability of paper_type
    paper_type_confidence = 0.95 if paper.paper_type else 0.7
    study_type_confidence = 0.85 if study_type != StudyType.CONCEPTUAL else 0.6

    # Determine if empirical
    is_empirical = study_type in [
        StudyType.EMPIRICAL_QUALITATIVE,
        StudyType.EMPIRICAL_QUANTITATIVE,
        StudyType.EMPIRICAL_MIXED,
        StudyType.CASE_STUDY
    ]

    categorization = Categorization(
        paper_type=paper_type,
        study_type=study_type,
        quality_tier=quality_tier,
        paper_type_confidence=paper_type_confidence,
        study_type_confidence=study_type_confidence,
        is_empirical=is_empirical,
        is_peer_reviewed=is_peer_reviewed,
        is_open_access=False,  # Would need additional metadata
        reasoning=f"Type: {paper_type.value}, Study: {study_type.value}, Tier: {quality_tier.value}",
        metadata=ProcessingMetadata(
            timestamp=datetime.now(timezone.utc),
            duration_seconds=duration,
            success=True
        )
    )

    return categorization, should_include, exclusion_reason


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute categorization step.

    Args:
        config: Step configuration with options:
            - enabled: bool (default: True) - Run categorization
            - exclude_types: bool (default: True) - Exclude non-article types (conferences, books, etc.)
            - exclude_reviews: bool (default: True) - Exclude literature reviews
        papers_db: Current papers database (PapersDatabase instance)
        verbose: Enable verbose output
        dry_run: Don't actually modify papers

    Returns:
        Dictionary with execution results
    """
    step_start_time = time.time()
    
    # Get configuration options
    exclude_types = config.get("exclude_types", True)
    exclude_reviews = config.get("exclude_reviews", True)

    results = {
        "step": "categorization",
        "total_papers": papers_db.count(primary_only=False),
        "categorized": 0,
        "included": 0,
        "excluded": 0,
        "exclusions": {
            "wrong_type": 0,
            "review_paper": 0,
            "conceptual_paper": 0,
        },
        "study_types": {},
        "quality_tiers": {},
    }

    if verbose:
        console.print(f"\n  [bold cyan]Categorizing {papers_db.count(primary_only=False)} papers[/bold cyan]")

    # Process each paper
    all_papers = papers_db.to_list(primary_only=False)
    for i, paper in enumerate(all_papers):
        # Show progress every 100 papers
        if verbose and (i + 1) % 100 == 0:
            import sys
            sys.stdout.write(f"\r    Processed {i + 1}/{len(all_papers)} papers... Included: {results['included']}, Excluded: {results['excluded']}")
            sys.stdout.flush()
        
        categorization, should_include, exclusion_reason = _categorize_paper(
            paper,
            verbose=verbose
        )

        if not dry_run:
            # Set categorization in screening model
            paper.screening.categorization = categorization

            # Set current stage
            paper.screening.current_stage = "categorization_complete"

            # Apply exclude_types filter
            if not should_include:
                if exclude_types and ("Type" in exclusion_reason or "type" in exclusion_reason):
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED
                    paper.screening.notes = exclusion_reason
                elif exclude_reviews and "review" in exclusion_reason.lower():
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED
                    paper.screening.notes = exclusion_reason
            
            # Update paper in database
            papers_db.update(paper)

        results["categorized"] += 1

        # Track statistics
        study_type_key = categorization.study_type.value
        if study_type_key not in results["study_types"]:
            results["study_types"][study_type_key] = 0
        results["study_types"][study_type_key] += 1

        tier_key = categorization.quality_tier.value
        if tier_key not in results["quality_tiers"]:
            results["quality_tiers"][tier_key] = 0
        results["quality_tiers"][tier_key] += 1

        if should_include:
            results["included"] += 1
        else:
            results["excluded"] += 1
            if exclusion_reason:
                if "Type" in exclusion_reason or "type" in exclusion_reason:
                    results["exclusions"]["wrong_type"] += 1
                elif "review" in exclusion_reason.lower():
                    results["exclusions"]["review_paper"] += 1
                elif "conceptual" in exclusion_reason.lower():
                    results["exclusions"]["conceptual_paper"] += 1

    duration = time.time() - step_start_time

    if verbose:
        # Clear the progress line and print final result
        import sys
        sys.stdout.write("\r" + " " * 100 + "\r")  # Clear the line
        sys.stdout.flush()
        console.print(f"    [green]✓ Categorization complete[/green] - Included: [cyan]{results['included']}[/cyan], Excluded: [cyan]{results['excluded']}[/cyan]")

    return results
