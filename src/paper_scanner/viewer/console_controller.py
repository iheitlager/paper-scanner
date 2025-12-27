"""PaperListController - MVC Controller for paginated paper viewing"""

import json
from typing import List, Optional
from paper_scanner.core.models import Paper
from paper_scanner.io.json import paper_to_json
from paper_scanner.io.bibtex import papers_to_bibtex


class PaperListController:
    """Controller managing paper list state and pagination"""

    def __init__(self, papers: List[Paper], page_size: int = 10):
        """Initialize controller with papers and page size"""
        self.papers = papers
        self.page_size = page_size
        self.current_page = 0
        self.total_pages = (len(self.papers) + page_size - 1) // page_size if papers else 1
        self.selected_index: int | None = None  # Index within current page (-1 to page_size-1)

    def get_current_page_papers(self) -> List[Paper]:
        """Get papers for the current page"""
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.papers))
        return self.papers[start_idx:end_idx]

    def get_page_info(self) -> dict:
        """Get info about current page"""
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.papers))
        return {
            "current_page": self.current_page + 1,
            "total_pages": self.total_pages,
            "papers_shown": len(self.get_current_page_papers()),
            "papers_total": len(self.papers),
            "start_index": start_idx + 1 if self.papers else 0,
            "end_index": end_idx,
        }

    def next_page(self) -> bool:
        """Move to next page. Returns True if successful"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.clear_selection()
            return True
        return False

    def prev_page(self) -> bool:
        """Move to previous page. Returns True if successful"""
        if self.current_page > 0:
            self.current_page -= 1
            self.clear_selection()
            return True
        return False

    def has_next(self) -> bool:
        """Check if there's a next page"""
        return self.current_page < self.total_pages - 1

    def has_prev(self) -> bool:
        """Check if there's a previous page"""
        return self.current_page > 0

    def select_down(self) -> bool:
        """Move selection down. Returns True if page changed"""
        current_papers = self.get_current_page_papers()
        page_changed = False

        if self.selected_index is None:
            # No selection, start from top
            self.selected_index = 0
        elif self.selected_index < len(current_papers) - 1:
            # Move down within page
            self.selected_index += 1
        elif self.has_next():
            # At bottom, scroll to next page
            self.next_page()
            self.selected_index = 0
            page_changed = True
        # Else: at bottom of last page, stay selected

        return page_changed

    def select_up(self) -> bool:
        """Move selection up. Returns True if page changed"""
        page_changed = False

        if self.selected_index is None:
            # No selection, start from bottom
            current_papers = self.get_current_page_papers()
            self.selected_index = len(current_papers) - 1 if current_papers else None
        elif self.selected_index > 0:
            # Move up within page
            self.selected_index -= 1
        elif self.has_prev():
            # At top, scroll to previous page
            self.prev_page()
            current_papers = self.get_current_page_papers()
            self.selected_index = len(current_papers) - 1 if current_papers else None
            page_changed = True
        # Else: at top of first page, stay selected

        return page_changed

    def clear_selection(self) -> None:
        """Clear the current selection"""
        self.selected_index = None

    def get_selected_paper(self) -> Paper | None:
        """Get the currently selected paper, or None if nothing selected"""
        if self.selected_index is None:
            return None
        papers = self.get_current_page_papers()
        if 0 <= self.selected_index < len(papers):
            return papers[self.selected_index]
        return None

    def get_selected_as_bibtex(self) -> Optional[str]:
        """Export selected paper as BibTeX"""
        paper = self.get_selected_paper()
        if not paper:
            return None
        # Use the papers_to_bibtex utility which handles list of papers
        return papers_to_bibtex([paper])

    def _paper_to_bibtex(self, paper: Paper) -> Optional[str]:
        """Convert a single paper to BibTeX string"""
        if not paper:
            return None
        return papers_to_bibtex([paper])

    def get_selected_as_json(self) -> Optional[str]:
        """Export selected paper as JSON"""
        paper = self.get_selected_paper()
        if not paper:
            return None
        # Use the paper_to_json utility which handles serialization
        return paper_to_json(paper, exclude_none=True, indent=2)

    def _paper_to_json(self, paper: Paper) -> Optional[str]:
        """Convert a single paper to JSON string"""
        if not paper:
            return None
        return paper_to_json(paper, exclude_none=True, indent=2)

    def get_selected_doi(self) -> Optional[str]:
        """Get DOI of selected paper"""
        paper = self.get_selected_paper()
        return paper.doi if paper else None

    def search_papers(self, query: str) -> List[int]:
        """Search papers by title, authors, or keywords
        Returns list of indices of matching papers"""
        if not query:
            return list(range(len(self.papers)))

        query_lower = query.lower()
        matches = []

        for idx, paper in enumerate(self.papers):
            # Search in title
            if paper.title and query_lower in paper.title.lower():
                matches.append(idx)
            # Search in authors
            elif any(query_lower in author.full_name.lower() for author in paper.authors):
                matches.append(idx)
            # Search in keywords
            elif any(query_lower in keyword.lower() for keyword in paper.keywords):
                matches.append(idx)

        return matches
