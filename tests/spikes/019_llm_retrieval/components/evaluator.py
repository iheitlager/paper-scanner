"""Evaluator: Quality assessment of retrieval results."""
from typing import Any, Dict, List, Optional
from .common import QualityScore, RetrievalResult


class Evaluator:
    """Assesses quality of retrieval results."""

    def __init__(self, 
                 min_coverage: float = 50.0,
                 min_relevance: float = 50.0,
                 min_freshness: float = 30.0):
        """
        Initialize Evaluator with quality thresholds.
        
        Args:
            min_coverage: Minimum % of papers required
            min_relevance: Minimum relevance score required
            min_freshness: Minimum freshness score required
        """
        self.min_coverage = min_coverage
        self.min_relevance = min_relevance
        self.min_freshness = min_freshness

    def evaluate(self, 
                 result: RetrievalResult,
                 question: str,
                 all_papers: List[Dict[str, Any]],
                 current_year: int = 2024) -> QualityScore:
        """
        Evaluate retrieval result quality.
        
        Args:
            result: RetrievalResult from Tool
            question: Original question for relevance context
            all_papers: All papers in corpus for coverage calculation
            current_year: Current year for freshness calculation
            
        Returns:
            QualityScore with detailed assessment
        """
        # Coverage: % of papers represented in results
        coverage = (result.paper_count / len(all_papers) * 100) if all_papers else 0
        coverage = min(coverage, 100)
        
        # Relevance: based on average similarity scores
        if result.chunks:
            avg_similarity = result.total_similarity / len(result.chunks)
            # Map [0, 1] similarity to [0, 100] relevance
            relevance = avg_similarity * 100
        else:
            relevance = 0
        
        # Freshness: based on year distribution of papers
        if result.chunks:
            years = [c.get('year', current_year) for c in result.chunks]
            avg_year = sum(years) / len(years)
            years_old = current_year - avg_year
            # Recent papers (< 3 years old): 100, old papers (> 10 years): 30
            freshness = max(30, 100 - (years_old / 10 * 70))
        else:
            freshness = 0
        
        # Determine if adequate
        is_adequate = (
            coverage >= self.min_coverage and
            relevance >= self.min_relevance and
            freshness >= self.min_freshness and
            len(result.chunks) > 0
        )
        
        feedback = self._generate_feedback(
            coverage, relevance, freshness, result, is_adequate
        )
        
        return QualityScore(
            coverage=coverage,
            relevance=relevance,
            freshness=freshness,
            is_adequate=is_adequate,
            feedback=feedback
        )

    def _generate_feedback(self,
                          coverage: float,
                          relevance: float,
                          freshness: float,
                          result: RetrievalResult,
                          is_adequate: bool) -> str:
        """Generate human-readable feedback."""
        issues = []
        
        if coverage < self.min_coverage:
            issues.append(f"Low coverage ({coverage:.0f}%)")
        
        if relevance < self.min_relevance:
            issues.append(f"Low relevance ({relevance:.0f}%)")
        
        if freshness < self.min_freshness:
            issues.append(f"Low freshness ({freshness:.0f}%)")
        
        if not result.chunks:
            issues.append("No chunks found")
        
        if is_adequate:
            return f"✓ Adequate results: {len(result.chunks)} chunks from {result.paper_count} papers"
        else:
            return f"⚠ Issues: {', '.join(issues) if issues else 'Unknown'}"
