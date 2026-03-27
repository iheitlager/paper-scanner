"""Unit tests for PaperListController"""

import pytest

from paper_scanner.core.models import Author, Paper
from paper_scanner.viewer.console_controller import PaperListController


class TestPaperListController:
    """Test suite for PaperListController pagination and state management"""

    @pytest.fixture
    def sample_papers(self):
        """Create sample papers for testing"""
        papers = []
        for i in range(1, 26):  # Create 25 papers
            papers.append(
                Paper(
                    cite_key=f"paper{i}",
                    title=f"Paper {i}: Research Study",
                    year=2020 + (i % 5),
                    authors=[
                        Author(
                            given_name="Author",
                            family_name=f"Test{i}",
                            full_name=f"Author Test{i}"
                        )
                    ],
                )
            )
        return papers

    def test_initialization(self, sample_papers):
        """Test controller initialization"""
        controller = PaperListController(sample_papers, page_size=10)
        assert controller.papers == sample_papers
        assert controller.page_size == 10
        assert controller.current_page == 0
        assert controller.total_pages == 3  # 25 papers / 10 per page = 3 pages

    def test_empty_papers(self):
        """Test with empty paper list"""
        controller = PaperListController([], page_size=10)
        assert len(controller.papers) == 0
        assert controller.total_pages == 1
        assert controller.current_page == 0

    def test_single_page(self):
        """Test with papers fitting on single page"""
        papers = [
            Paper(
                cite_key=f"paper{i}",
                title=f"Paper {i}",
                year=2024,
                authors=[Author(given_name="A", family_name="B", full_name="A B")]
            )
            for i in range(1, 6)
        ]
        controller = PaperListController(papers, page_size=10)
        assert controller.total_pages == 1
        assert not controller.has_next()
        assert not controller.has_prev()

    def test_get_current_page_papers_first_page(self, sample_papers):
        """Test getting papers from first page"""
        controller = PaperListController(sample_papers, page_size=10)
        papers = controller.get_current_page_papers()
        assert len(papers) == 10
        assert papers[0].cite_key == "paper1"
        assert papers[-1].cite_key == "paper10"

    def test_get_current_page_papers_last_page(self, sample_papers):
        """Test getting papers from last page"""
        controller = PaperListController(sample_papers, page_size=10)
        controller.current_page = 2  # Go to last page (0-indexed)
        papers = controller.get_current_page_papers()
        assert len(papers) == 5  # Only 5 papers on last page
        assert papers[0].cite_key == "paper21"
        assert papers[-1].cite_key == "paper25"

    def test_get_page_info(self, sample_papers):
        """Test page info retrieval"""
        controller = PaperListController(sample_papers, page_size=10)
        info = controller.get_page_info()

        assert info["current_page"] == 1
        assert info["total_pages"] == 3
        assert info["papers_shown"] == 10
        assert info["papers_total"] == 25
        assert info["start_index"] == 1
        assert info["end_index"] == 10

    def test_page_info_last_page(self, sample_papers):
        """Test page info on last page"""
        controller = PaperListController(sample_papers, page_size=10)
        controller.current_page = 2

        info = controller.get_page_info()
        assert info["current_page"] == 3
        assert info["total_pages"] == 3
        assert info["papers_shown"] == 5
        assert info["papers_total"] == 25
        assert info["start_index"] == 21
        assert info["end_index"] == 25

    def test_next_page(self, sample_papers):
        """Test navigating to next page"""
        controller = PaperListController(sample_papers, page_size=10)
        assert controller.current_page == 0

        success = controller.next_page()
        assert success is True
        assert controller.current_page == 1

        success = controller.next_page()
        assert success is True
        assert controller.current_page == 2

        # Try to go beyond last page
        success = controller.next_page()
        assert success is False
        assert controller.current_page == 2

    def test_prev_page(self, sample_papers):
        """Test navigating to previous page"""
        controller = PaperListController(sample_papers, page_size=10)
        controller.current_page = 2

        success = controller.prev_page()
        assert success is True
        assert controller.current_page == 1

        success = controller.prev_page()
        assert success is True
        assert controller.current_page == 0

        # Try to go before first page
        success = controller.prev_page()
        assert success is False
        assert controller.current_page == 0

    def test_has_next(self, sample_papers):
        """Test has_next() state check"""
        controller = PaperListController(sample_papers, page_size=10)

        assert controller.has_next() is True
        controller.current_page = 1
        assert controller.has_next() is True
        controller.current_page = 2
        assert controller.has_next() is False

    def test_has_prev(self, sample_papers):
        """Test has_prev() state check"""
        controller = PaperListController(sample_papers, page_size=10)

        assert controller.has_prev() is False
        controller.current_page = 1
        assert controller.has_prev() is True
        controller.current_page = 2
        assert controller.has_prev() is True

    def test_different_page_sizes(self):
        """Test with different page sizes"""
        papers = [
            Paper(
                cite_key=f"p{i}",
                title=f"Paper {i}",
                year=2024,
                authors=[Author(given_name="A", family_name="B", full_name="A B")]
            )
            for i in range(1, 11)
        ]

        # Page size 5
        controller = PaperListController(papers, page_size=5)
        assert controller.total_pages == 2
        assert len(controller.get_current_page_papers()) == 5

        # Page size 3
        controller = PaperListController(papers, page_size=3)
        assert controller.total_pages == 4
        assert len(controller.get_current_page_papers()) == 3

    def test_page_navigation_boundary(self, sample_papers):
        """Test page navigation at boundaries"""
        controller = PaperListController(sample_papers, page_size=10)

        # Navigate through all pages
        for page_num in range(controller.total_pages):
            info = controller.get_page_info()
            assert info["current_page"] == page_num + 1
            if page_num < controller.total_pages - 1:
                assert controller.next_page() is True
            else:
                assert controller.next_page() is False

    def test_selection_initialization(self, sample_papers):
        """Test that selection starts as None"""
        controller = PaperListController(sample_papers, page_size=10)
        assert controller.selected_index is None

    def test_select_down_from_no_selection(self, sample_papers):
        """Test selecting down from no selection starts at top"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.select_down()
        assert controller.selected_index == 0
        assert controller.get_selected_paper() == sample_papers[0]

    def test_select_up_from_no_selection(self, sample_papers):
        """Test selecting up from no selection starts at bottom"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.select_up()
        # Should select last paper on page (10 papers on first page)
        assert controller.selected_index == 9
        assert controller.get_selected_paper() == sample_papers[9]

    def test_select_down_within_page(self, sample_papers):
        """Test selecting down within a page"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.selected_index = 3
        page_changed = controller.select_down()

        assert page_changed is False
        assert controller.selected_index == 4

    def test_select_up_within_page(self, sample_papers):
        """Test selecting up within a page"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.selected_index = 5
        page_changed = controller.select_up()

        assert page_changed is False
        assert controller.selected_index == 4

    def test_select_down_to_next_page(self, sample_papers):
        """Test selecting down at bottom scrolls to next page"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.current_page = 0
        controller.selected_index = 9  # Last item on page 1

        page_changed = controller.select_down()

        assert page_changed is True
        assert controller.current_page == 1
        assert controller.selected_index == 0

    def test_select_up_to_prev_page(self, sample_papers):
        """Test selecting up at top scrolls to previous page"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.current_page = 1
        controller.selected_index = 0  # First item on page 2

        page_changed = controller.select_up()

        assert page_changed is True
        assert controller.current_page == 0
        assert controller.selected_index == 9  # Last item on previous page

    def test_clear_selection(self, sample_papers):
        """Test clearing selection"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.selected_index = 5
        controller.clear_selection()

        assert controller.selected_index is None
        assert controller.get_selected_paper() is None

    def test_next_page_clears_selection(self, sample_papers):
        """Test that next_page clears selection"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.selected_index = 5
        controller.next_page()

        assert controller.selected_index is None

    def test_prev_page_clears_selection(self, sample_papers):
        """Test that prev_page clears selection"""
        controller = PaperListController(sample_papers, page_size=10)

        controller.current_page = 1
        controller.selected_index = 3
        controller.prev_page()

        assert controller.selected_index is None

    def test_get_selected_paper(self, sample_papers):
        """Test getting the selected paper"""
        controller = PaperListController(sample_papers, page_size=10)

        # No selection
        assert controller.get_selected_paper() is None

        # Select paper
        controller.selected_index = 2
        selected = controller.get_selected_paper()
        assert selected == sample_papers[2]
