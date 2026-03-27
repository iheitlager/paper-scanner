"""
Fluent/chainable query builder for PapersDatabase.

Provides a builder pattern for constructing complex queries with filters,
sorting, and limiting, with lazy evaluation until terminal operations.
"""

from typing import TYPE_CHECKING, Any, Callable, List, Optional

from paper_scanner.core.models import Paper

if TYPE_CHECKING:
    from paper_scanner.core.database import PapersDatabase


class PapersQuery:
    """
    Fluent query builder for papers database.

    Chains multiple filters and transformations, executing lazily
    when terminal operations like execute(), top(), or list() are called.

    Example:
        >>> papers_db.query().filter_by_topic("AI").top(10).execute()
        >>> papers_db.query().grep("cloud computing").exclude_duplicates().first()
    """

    def __init__(self, db: "PapersDatabase"):
        """Initialize query with database reference"""
        self.db = db
        self._filters: List[Callable[[Paper], bool]] = []
        self._sort_key: Optional[Callable[[Paper], Any]] = None
        self._sort_reverse: bool = False
        self._limit: Optional[int] = None
        self._exclude_duplicates: bool = False

    # ========================================================================
    # FILTER METHODS (chainable)
    # ========================================================================

    def filter(self, predicate: Callable[[Paper], bool]) -> "PapersQuery":
        """
        Add custom filter predicate.

        Args:
            predicate: Function that returns True to keep paper

        Returns:
            Self for chaining
        """
        self._filters.append(predicate)
        return self

    def filter_by_topic(self, topic: str) -> "PapersQuery":
        """
        Filter papers by topic (searches keywords).

        Args:
            topic: Topic keyword to search for

        Returns:
            Self for chaining
        """
        topic_lower = topic.lower()
        def has_topic(p: Paper) -> bool:
            if p.keywords:
                return any(topic_lower in kw.lower() for kw in p.keywords)
            return False

        return self.filter(has_topic)

    def filter_by_year(self, min_year: int, max_year: Optional[int] = None) -> "PapersQuery":
        """
        Filter papers by publication year range.

        Args:
            min_year: Minimum year (inclusive)
            max_year: Maximum year (inclusive), defaults to min_year

        Returns:
            Self for chaining
        """
        if max_year is None:
            max_year = min_year

        def in_year_range(p: Paper) -> bool:
            return p.year is not None and min_year <= p.year <= max_year

        return self.filter(in_year_range)

    def filter_by_author(self, author_name: str) -> "PapersQuery":
        """
        Filter papers by author name (partial match).

        Args:
            author_name: Author name to search for

        Returns:
            Self for chaining
        """
        author_lower = author_name.lower()
        def has_author(p: Paper) -> bool:
            return any(author_lower in a.full_name.lower() for a in (p.authors or []))

        return self.filter(has_author)

    def filter_by_doi(self, doi: str) -> "PapersQuery":
        """
        Filter papers by DOI.

        Args:
            doi: DOI to search for

        Returns:
            Self for chaining
        """
        from paper_scanner.core.doi import DOI
        doi_normalized = DOI(doi).stem
        def has_doi(p: Paper) -> bool:
            return p.doi and DOI(p.doi).stem == doi_normalized

        return self.filter(has_doi)

    def grep(self, text: str) -> "PapersQuery":
        """
        Full-text search in title and abstract.

        Args:
            text: Text to search for

        Returns:
            Self for chaining
        """
        text_lower = text.lower()
        def contains_text(p: Paper) -> bool:
            title_match = p.title and text_lower in p.title.lower()
            abstract_match = p.abstract and text_lower in p.abstract.lower()
            return title_match or abstract_match

        return self.filter(contains_text)

    def exclude_duplicates(self) -> "PapersQuery":
        """
        Only include primary papers (exclude duplicates).

        Returns:
            Self for chaining
        """
        self._exclude_duplicates = True
        return self

    # ========================================================================
    # SORT METHODS (chainable)
    # ========================================================================

    def order_by_year(self, descending: bool = True) -> "PapersQuery":
        """
        Sort by publication year.

        Args:
            descending: Sort newest first if True

        Returns:
            Self for chaining
        """
        self._sort_key = lambda p: p.year or 0
        self._sort_reverse = descending
        return self

    def order_by_title(self, descending: bool = False) -> "PapersQuery":
        """
        Sort by title alphabetically.

        Args:
            descending: Reverse alphabetical if True

        Returns:
            Self for chaining
        """
        self._sort_key = lambda p: (p.title or "").lower()
        self._sort_reverse = descending
        return self

    def order_by(self, key_func: Callable[[Paper], Any], descending: bool = False) -> "PapersQuery":
        """
        Sort by custom key function.

        Args:
            key_func: Function that extracts sort key from Paper
            descending: Sort descending if True

        Returns:
            Self for chaining
        """
        self._sort_key = key_func
        self._sort_reverse = descending
        return self

    # ========================================================================
    # LIMIT METHODS (chainable)
    # ========================================================================

    def top(self, count: int) -> "PapersQuery":
        """
        Limit results to top N papers.

        Args:
            count: Maximum number of papers to return

        Returns:
            Self for chaining
        """
        self._limit = count
        return self

    def limit(self, count: int) -> "PapersQuery":
        """Alias for top()"""
        return self.top(count)

    # ========================================================================
    # TERMINAL OPERATIONS (end chain)
    # ========================================================================

    def execute(self) -> List[Paper]:
        """
        Execute query and return results.

        Returns:
            List of papers matching all filters
        """
        # Start with all papers
        results = (
            self.db.all(primary_only=False)
            if not self._exclude_duplicates
            else self.db.all(primary_only=True)
        )

        # Apply filters
        for predicate in self._filters:
            results = [p for p in results if predicate(p)]

        # Apply sorting
        if self._sort_key:
            results.sort(key=self._sort_key, reverse=self._sort_reverse)

        # Apply limit
        if self._limit:
            results = results[:self._limit]

        return results

    def list(self) -> List[Paper]:
        """Alias for execute()"""
        return self.execute()

    def first(self) -> Optional[Paper]:
        """Get first result or None"""
        results = self.top(1).execute()
        return results[0] if results else None

    def count(self) -> int:
        """Get total count of matching papers"""
        return len(self.execute())

    # ========================================================================
    # MAGIC METHODS FOR IMPLICIT EXECUTION
    # ========================================================================

    def __iter__(self):
        """Allow iteration over results without explicit execute()"""
        return iter(self.execute())

    def __len__(self):
        """Allow len() on query without explicit execute()"""
        return self.count()

    def __getitem__(self, index):
        """Allow indexing without explicit execute() - db.query().filter(...)[0]"""
        results = self.execute()
        return results[index]

    def __bool__(self):
        """Allow bool() check - if db.query().filter(...):"""
        return self.count() > 0
