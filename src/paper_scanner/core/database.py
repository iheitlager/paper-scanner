"""
Indexed Paper Database for efficient CRUD and search operations.

Provides PapersDatabase class with:
- DOI indexing for fast duplicate detection
- Full CRUD operations
- Filtering by primary papers (excluding duplicates)
- Hook-based DOI updates to maintain index consistency

Indexes maintained:
- _doi_index: Dict[str, List[Paper]] - DOI to papers (supports duplicates)
- _cite_key_index: Dict[str, Paper] - Unique citation keys
- _id_index: Dict[str, Paper] - Unique paper IDs
"""

from typing import List, Dict, Optional, Set, Any
from collections import defaultdict

from paper_scanner.core.models import Paper, Citation


class PapersDatabase:
    """
    Indexed paper database with fast lookup capabilities.
    
    Public Attributes:
        papers: List[Paper] - All papers in database (both primary and duplicates)
    
    Private Indexes (maintained automatically):
        _doi_index: Dict[str, List[Paper]] - Maps DOI (normalized lowercase) to list of papers
                                             (multiple papers can share same DOI if duplicates)
        _cite_key_index: Dict[str, Paper] - Maps citation key to paper (unique constraint)
        _id_index: Dict[str, Paper] - Maps paper ID to paper (unique constraint)
    
    All indexes are automatically updated during add, update, and delete operations
    to maintain consistency and enable O(1) lookups.
    """
    
    def __init__(self):
        """Initialize empty database with indexes"""
        self.papers: List[Paper] = []
        self._doi_index: Dict[str, List[Paper]] = defaultdict(list)
        self._cite_key_index: Dict[str, Paper] = {}
        self._id_index: Dict[str, Paper] = {}
    
    # ========================================================================
    # INDEX MANAGEMENT
    # ========================================================================
    
    def _index_paper(self, paper: Paper) -> None:
        """
        Add paper to all indexes.
        
        Args:
            paper: Paper to index
        """
        # Index by cite_key (primary unique identifier)
        self._cite_key_index[paper.cite_key] = paper
        
        # Index by ID
        self._id_index[paper.id] = paper
        
        # Index by DOI (may have duplicates)
        if paper.doi:
            doi_key = paper.doi.lower().strip()
            if paper not in self._doi_index[doi_key]:
                self._doi_index[doi_key].append(paper)
    
    def _unindex_paper(self, paper: Paper) -> None:
        """
        Remove paper from all indexes.
        
        Args:
            paper: Paper to unindex
        """
        # Unindex from cite_key
        if paper.cite_key in self._cite_key_index:
            if self._cite_key_index[paper.cite_key] is paper:
                del self._cite_key_index[paper.cite_key]
        
        # Unindex from ID
        if paper.id in self._id_index:
            if self._id_index[paper.id] is paper:
                del self._id_index[paper.id]
        
        # Unindex from DOI
        if paper.doi:
            doi_key = paper.doi.lower().strip()
            if doi_key in self._doi_index:
                self._doi_index[doi_key] = [
                    p for p in self._doi_index[doi_key] if p is not paper
                ]
                if not self._doi_index[doi_key]:
                    del self._doi_index[doi_key]
    
    def _update_doi_index(self, paper: Paper, old_doi: Optional[str]) -> None:
        """
        Update DOI index when a paper's DOI changes.
        
        This is called from Paper model via field_validator hook.
        
        Args:
            paper: Paper with updated DOI
            old_doi: Previous DOI value
        """
        # Remove old paper from old DOI index
        if old_doi:
            old_doi_key = old_doi.lower().strip()
            if old_doi_key in self._doi_index:
                # Filter out papers with matching ID (not the same object reference)
                self._doi_index[old_doi_key] = [
                    p for p in self._doi_index[old_doi_key] if p.id != paper.id
                ]
                if not self._doi_index[old_doi_key]:
                    del self._doi_index[old_doi_key]
        
        # Add to new DOI index
        if paper.doi:
            doi_key = paper.doi.lower().strip()
            # Check if already exists by ID, if so remove it first
            if doi_key in self._doi_index:
                self._doi_index[doi_key] = [p for p in self._doi_index[doi_key] if p.id != paper.id]
            if paper not in self._doi_index[doi_key]:
                self._doi_index[doi_key].append(paper)
    
    # ========================================================================
    # CREATE OPERATIONS
    # ========================================================================
    
    def add(self, paper: Paper) -> None:
        """
        Add a paper to the database.
        
        Args:
            paper: Paper to add
            
        Raises:
            ValueError: If cite_key already exists or ID already exists
        """
        # Check for duplicates
        if paper.cite_key in self._cite_key_index:
            raise ValueError(f"Paper with cite_key '{paper.cite_key}' already exists")
        
        if paper.id in self._id_index:
            raise ValueError(f"Paper with id '{paper.id}' already exists")
        
        # Add to list and indexes
        self.papers.append(paper)
        self._index_paper(paper)
    
    def add_many(self, papers: List[Paper]) -> None:
        """
        Add multiple papers to the database.
        
        Args:
            papers: List of papers to add
            
        Raises:
            ValueError: If any paper has duplicate cite_key or id
        """
        for paper in papers:
            self.add(paper)
    
    # ========================================================================
    # READ OPERATIONS
    # ========================================================================
    
    def all(self, primary_only: bool = False) -> List[Paper]:
        """
        Get all papers in database.
        
        Args:
            primary_only: If True, only return papers where duplicate_of is None.
                         If False, return all papers.
        
        Returns:
            List of papers
        """
        if not primary_only:
            return list(self.papers)
        
        return [p for p in self.papers if p.duplicate_of is None]
    
    def get_by_id(self, paper_id: str) -> Optional[Paper]:
        """
        Get paper by ID.
        
        Args:
            paper_id: Paper ID
            
        Returns:
            Paper or None if not found
        """
        return self._id_index.get(paper_id)
    
    def get_by_cite_key(self, cite_key: str) -> Optional[Paper]:
        """
        Get paper by cite_key.
        
        Args:
            cite_key: Citation key
            
        Returns:
            Paper or None if not found
        """
        return self._cite_key_index.get(cite_key)
    
    def get_by_doi(self, doi: str, primary_only: bool = False) -> List[Paper]:
        """
        Get all papers with given DOI.
        
        Note: Multiple papers can have the same DOI (they are typically duplicates).
        
        Args:
            doi: DOI to search for
            primary_only: If True, only return primary papers (duplicate_of is None)
            
        Returns:
            List of papers with matching DOI
        """
        doi_key = doi.lower().strip()
        papers = self._doi_index.get(doi_key, [])
        
        if not primary_only:
            return list(papers)
        
        return [p for p in papers if p.duplicate_of is None]
    
    def find(
        self,
        predicate,
        primary_only: bool = False
    ) -> List[Paper]:
        """
        Find papers matching a predicate function.
        
        Args:
            predicate: Function that takes Paper and returns bool
            primary_only: If True, only search primary papers
            
        Returns:
            List of matching papers
            
        Example:
            # Find papers from 2020
            db.find(lambda p: p.year == 2020)
            
            # Find papers by author
            db.find(lambda p: any(a.family_name == "Smith" for a in p.authors))
        """
        papers = self.all(primary_only=primary_only)
        return [p for p in papers if predicate(p)]
    
    # ========================================================================
    # UPDATE OPERATIONS
    # ========================================================================
    
    def update(self, paper: Paper) -> None:
        """
        Update a paper in the database.
        
        Note: If the cite_key changed, the paper must not conflict with existing cite_key.
        If the DOI changed, the index is automatically updated via _update_doi_index.
        
        Args:
            paper: Updated paper (must already be in database)
            
        Raises:
            ValueError: If paper not in database or cite_key conflicts with existing
        """
        # Find existing paper
        existing = self._id_index.get(paper.id)
        if existing is None:
            raise ValueError(f"Paper with id '{paper.id}' not found in database")
        
        # Check cite_key conflict (if it changed)
        if paper.cite_key != existing.cite_key:
            if paper.cite_key in self._cite_key_index:
                raise ValueError(
                    f"Cannot update: cite_key '{paper.cite_key}' conflicts with existing paper"
                )
            # Remove old cite_key from index
            del self._cite_key_index[existing.cite_key]
            # Add new cite_key to index
            self._cite_key_index[paper.cite_key] = paper
        
        # Update DOI index if DOI changed
        if paper.doi != existing.doi:
            self._update_doi_index(paper, existing.doi)
        
        # Replace in list (find and update) and in ID index
        for i, p in enumerate(self.papers):
            if p.id == paper.id:
                self.papers[i] = paper
                self._id_index[paper.id] = paper
                break
    
    def update_many(self, papers: List[Paper]) -> None:
        """
        Update multiple papers in the database.
        
        Args:
            papers: List of updated papers
        """
        for paper in papers:
            self.update(paper)
    
    # ========================================================================
    # DELETE OPERATIONS
    # ========================================================================
    
    def delete_by_id(self, paper_id: str) -> bool:
        """
        Delete a paper by ID.
        
        Args:
            paper_id: Paper ID
            
        Returns:
            True if deleted, False if not found
        """
        paper = self._id_index.get(paper_id)
        if paper is None:
            return False
        
        self._unindex_paper(paper)
        self.papers = [p for p in self.papers if p.id != paper_id]
        return True
    
    def delete_by_cite_key(self, cite_key: str) -> bool:
        """
        Delete a paper by cite_key.
        
        Args:
            cite_key: Citation key
            
        Returns:
            True if deleted, False if not found
        """
        paper = self._cite_key_index.get(cite_key)
        if paper is None:
            return False
        
        return self.delete_by_id(paper.id)
    
    def delete_many_by_id(self, paper_ids: List[str]) -> int:
        """
        Delete multiple papers by ID.
        
        Args:
            paper_ids: List of paper IDs to delete
            
        Returns:
            Number of papers deleted
        """
        count = 0
        for paper_id in paper_ids:
            if self.delete_by_id(paper_id):
                count += 1
        return count
    
    def clear(self) -> None:
        """Clear all papers and indexes from database"""
        self.papers.clear()
        self._doi_index.clear()
        self._cite_key_index.clear()
        self._id_index.clear()
    
    # ========================================================================
    # QUERY OPERATIONS
    # ========================================================================
    
    def count(self, primary_only: bool = False) -> int:
        """
        Count papers in database.
        
        Args:
            primary_only: If True, only count primary papers
            
        Returns:
            Number of papers
        """
        if not primary_only:
            return len(self.papers)
        
        return len([p for p in self.papers if p.duplicate_of is None])
    
    def count_duplicates(self, doi: str) -> int:
        """
        Count papers with a specific DOI.
        
        Args:
            doi: DOI to count
            
        Returns:
            Number of papers with this DOI
        """
        return len(self.get_by_doi(doi, primary_only=False))
    
    def get_duplicate_groups(self) -> Dict[str, List[Paper]]:
        """
        Get all papers grouped by DOI.
        
        Returns:
            Dict mapping DOI -> List of papers with that DOI
        """
        groups = {}
        for doi_key, papers in self._doi_index.items():
            if len(papers) > 1:
                groups[doi_key] = papers
        return groups
    
    def exists_by_id(self, paper_id: str) -> bool:
        """
        Check if paper exists by ID.
        
        Args:
            paper_id: Paper ID
            
        Returns:
            True if paper exists
        """
        return paper_id in self._id_index
    
    def exists_by_cite_key(self, cite_key: str) -> bool:
        """
        Check if paper exists by cite_key.
        
        Args:
            cite_key: Citation key
            
        Returns:
            True if paper exists
        """
        return cite_key in self._cite_key_index
    
    def exists_by_doi(self, doi: str) -> bool:
        """
        Check if any paper with DOI exists.
        
        Args:
            doi: DOI to check
            
        Returns:
            True if at least one paper with this DOI exists
        """
        doi_key = doi.lower().strip()
        return doi_key in self._doi_index
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    def to_list(self, primary_only: bool = False) -> List[Paper]:
        """
        Convert database to list (alias for all()).
        
        Args:
            primary_only: If True, only return primary papers
            
        Returns:
            List of papers
        """
        return self.all(primary_only=primary_only)
    
    def from_list(self, papers: List[Paper]) -> None:
        """
        Load papers from list (replaces current database).
        
        Args:
            papers: List of papers to load
        """
        self.clear()
        self.add_many(papers)
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats
        """
        total_papers = len(self.papers)
        primary_papers = len([p for p in self.papers if p.duplicate_of is None])
        duplicate_papers = total_papers - primary_papers
        
        papers_with_doi = len([p for p in self.papers if p.doi])
        unique_dois = len(self._doi_index)
        
        duplicate_groups = self.get_duplicate_groups()
        max_duplicates = max(
            (len(papers) for papers in duplicate_groups.values()),
            default=1
        )
        
        return {
            "total_papers": total_papers,
            "primary_papers": primary_papers,
            "duplicate_papers": duplicate_papers,
            "papers_with_doi": papers_with_doi,
            "unique_dois": unique_dois,
            "duplicate_groups": len(duplicate_groups),
            "max_duplicates_per_doi": max_duplicates,
        }
    
    # ========================================================================
    # SPECIAL OPERATIONS
    # ========================================================================
    
    def mark_duplicate(self, paper_id: str, duplicate_of_id: str) -> None:
        """
        Mark a paper as duplicate of another.
        
        Args:
            paper_id: ID of paper to mark as duplicate
            duplicate_of_id: ID of primary paper
            
        Raises:
            ValueError: If either paper not found
        """
        paper = self._id_index.get(paper_id)
        if paper is None:
            raise ValueError(f"Paper '{paper_id}' not found")
        
        primary = self._id_index.get(duplicate_of_id)
        if primary is None:
            raise ValueError(f"Primary paper '{duplicate_of_id}' not found")
        
        # Update the duplicate reference
        paper.duplicate_of = primary
        self.update(paper)
    
    def get_duplicates_of(self, paper_id: str) -> List[Paper]:
        """
        Get all papers marked as duplicates of a given paper.
        
        Args:
            paper_id: ID of primary paper
            
        Returns:
            List of duplicate papers
        """
        primary = self._id_index.get(paper_id)
        if primary is None:
            return []
        
        return [p for p in self.papers if p.duplicate_of is primary]
    
    def remove_duplicate_marking(self, paper_id: str) -> None:
        """
        Remove duplicate marking from a paper (make it primary again).
        
        Args:
            paper_id: ID of paper to un-mark as duplicate
            
        Raises:
            ValueError: If paper not found
        """
        paper = self._id_index.get(paper_id)
        if paper is None:
            raise ValueError(f"Paper '{paper_id}' not found")
        
        paper.duplicate_of = None
        self.update(paper)


# ============================================================================
# CITATIONS DATABASE
# ============================================================================

class CitationsDatabase:
    """
    Indexed citations database for managing bibliographic references.
    
    Provides fast lookup of citations by DOI and maintains a hashmap of
    citations for efficient duplicate detection and linking.
    
    Public Attributes:
        citations: List[Citation] - All citations in database
    
    Private Indexes:
        _doi_index: Dict[str, List[Citation]] - Maps DOI to citations (can have duplicates)
        _id_index: Dict[str, Citation] - Maps citation ID to citation (unique)
    """
    
    def __init__(self):
        """Initialize empty citations database with indexes"""
        self.citations: List[Citation] = []
        self._doi_index: Dict[str, List[Citation]] = defaultdict(list)
        self._id_index: Dict[str, Citation] = {}
    
    # ========================================================================
    # INDEX MANAGEMENT
    # ========================================================================
    
    def _index_citation(self, citation: Citation) -> None:
        """
        Add citation to all indexes.
        
        Args:
            citation: Citation to index
        """
        # Index by ID
        self._id_index[citation.id] = citation
        
        # Index by DOI (may have duplicates)
        if citation.doi:
            doi_key = citation.doi.lower().strip()
            if citation not in self._doi_index[doi_key]:
                self._doi_index[doi_key].append(citation)
    
    def _unindex_citation(self, citation: Citation) -> None:
        """
        Remove citation from all indexes.
        
        Args:
            citation: Citation to unindex
        """
        # Unindex from ID
        if citation.id in self._id_index:
            if self._id_index[citation.id] is citation:
                del self._id_index[citation.id]
        
        # Unindex from DOI
        if citation.doi:
            doi_key = citation.doi.lower().strip()
            if doi_key in self._doi_index:
                self._doi_index[doi_key] = [
                    c for c in self._doi_index[doi_key] if c is not citation
                ]
                if not self._doi_index[doi_key]:
                    del self._doi_index[doi_key]
    
    # ========================================================================
    # CREATE OPERATIONS
    # ========================================================================
    
    def add(self, citation: Citation) -> None:
        """
        Add a citation to the database.
        
        Args:
            citation: Citation to add
            
        Raises:
            ValueError: If citation ID already exists
        """
        if citation.id in self._id_index:
            raise ValueError(f"Citation with id '{citation.id}' already exists")
        
        self.citations.append(citation)
        self._index_citation(citation)
    
    def add_many(self, citations: List[Citation]) -> None:
        """
        Add multiple citations to the database.
        
        Args:
            citations: List of citations to add
        """
        for citation in citations:
            self.add(citation)
    
    # ========================================================================
    # READ OPERATIONS
    # ========================================================================
    
    def all(self) -> List[Citation]:
        """
        Get all citations in database.
        
        Returns:
            List of citations
        """
        return list(self.citations)
    
    def get_by_id(self, citation_id: str) -> Optional[Citation]:
        """
        Get citation by ID.
        
        Args:
            citation_id: Citation ID
            
        Returns:
            Citation or None if not found
        """
        return self._id_index.get(citation_id)
    
    def get_by_doi(self, doi: str) -> List[Citation]:
        """
        Get all citations with given DOI.
        
        Args:
            doi: DOI to search for
            
        Returns:
            List of citations with matching DOI
        """
        doi_key = doi.lower().strip()
        return list(self._doi_index.get(doi_key, []))
    
    # ========================================================================
    # UPDATE OPERATIONS
    # ========================================================================
    
    def update(self, citation: Citation) -> None:
        """
        Update a citation in the database.
        
        Args:
            citation: Updated citation (must already be in database)
            
        Raises:
            ValueError: If citation not in database
        """
        existing = self._id_index.get(citation.id)
        if existing is None:
            raise ValueError(f"Citation with id '{citation.id}' not found in database")
        
        # Since citation and existing point to the same object, we must capture old DOI before proceeding
        # Get the old DOI from the citations list to ensure we have the right value
        old_doi = None
        for c in self.citations:
            if c.id == citation.id:
                old_doi = c.doi
                break
        
        # Update DOI index if DOI changed
        if citation.doi != old_doi:
            # Remove from old DOI index
            if old_doi:
                old_doi_key = old_doi.lower().strip()
                if old_doi_key in self._doi_index:
                    self._doi_index[old_doi_key] = [
                        c for c in self._doi_index[old_doi_key] if c.id != citation.id
                    ]
                    if not self._doi_index[old_doi_key]:
                        del self._doi_index[old_doi_key]
            
            # Add to new DOI index
            if citation.doi:
                new_doi_key = citation.doi.lower().strip()
                if new_doi_key not in self._doi_index:
                    self._doi_index[new_doi_key] = []
                # Check if citation is already in the list (by ID to avoid duplicates)
                if not any(c.id == citation.id for c in self._doi_index[new_doi_key]):
                    self._doi_index[new_doi_key].append(citation)
        
        # Replace in list and ID index
        for i, c in enumerate(self.citations):
            if c.id == citation.id:
                self.citations[i] = citation
                self._id_index[citation.id] = citation
                break
    
    # ========================================================================
    # DELETE OPERATIONS
    # ========================================================================
    
    def delete_by_id(self, citation_id: str) -> bool:
        """
        Delete a citation by ID.
        
        Args:
            citation_id: Citation ID
            
        Returns:
            True if deleted, False if not found
        """
        citation = self._id_index.get(citation_id)
        if citation is None:
            return False
        
        self._unindex_citation(citation)
        self.citations = [c for c in self.citations if c.id != citation_id]
        return True
    
    def delete_many_by_id(self, citation_ids: List[str]) -> int:
        """
        Delete multiple citations by ID.
        
        Args:
            citation_ids: List of citation IDs to delete
            
        Returns:
            Number of citations deleted
        """
        count = 0
        for citation_id in citation_ids:
            if self.delete_by_id(citation_id):
                count += 1
        return count
    
    def clear(self) -> None:
        """Clear all citations and indexes from database"""
        self.citations.clear()
        self._doi_index.clear()
        self._id_index.clear()
    
    # ========================================================================
    # QUERY OPERATIONS
    # ========================================================================
    
    def count(self) -> int:
        """
        Count citations in database.
        
        Returns:
            Number of citations
        """
        return len(self.citations)
    
    def exists_by_id(self, citation_id: str) -> bool:
        """
        Check if citation exists by ID.
        
        Args:
            citation_id: Citation ID
            
        Returns:
            True if citation exists
        """
        return citation_id in self._id_index
    
    def exists_by_doi(self, doi: str) -> bool:
        """
        Check if any citation with DOI exists.
        
        Args:
            doi: DOI to check
            
        Returns:
            True if at least one citation with this DOI exists
        """
        doi_key = doi.lower().strip()
        return doi_key in self._doi_index
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    def to_list(self) -> List[Citation]:
        """
        Convert database to list (alias for all()).
        
        Returns:
            List of citations
        """
        return self.all()
    
    def from_list(self, citations: List[Citation]) -> None:
        """
        Load citations from list (replaces current database).
        
        Args:
            citations: List of citations to load
        """
        self.clear()
        self.add_many(citations)
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats
        """
        total_citations = len(self.citations)
        citations_with_doi = len([c for c in self.citations if c.doi])
        resolved_citations = len([c for c in self.citations if c.resolved_paper is not None])
        
        return {
            "total_citations": total_citations,
            "citations_with_doi": citations_with_doi,
            "resolved_citations": resolved_citations,
            "unresolved_citations": total_citations - resolved_citations,
        }
