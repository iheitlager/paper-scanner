"""Unit tests for ConsoleViewer"""

from unittest.mock import patch

import pytest

from paper_scanner.core.models import Author, Paper
from paper_scanner.viewer.console_viewer import ConsoleViewer


class TestConsoleViewer:
    """Test suite for ConsoleViewer rendering and interaction"""

    @pytest.fixture
    def sample_papers(self):
        """Create sample papers for testing"""
        papers = []
        for i in range(1, 16):  # Create 15 papers for 2 pages (10 per page)
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
                    journal="Test Journal" if i % 2 == 0 else None,
                    volume="45" if i % 2 == 0 else None,
                    number="3" if i % 2 == 0 else None,
                    pages="123-145" if i % 2 == 0 else None,
                    doi="10.1234/test" if i % 3 == 0 else None,
                )
            )
        return papers

    def test_initialization(self, sample_papers):
        """Test ConsoleViewer initialization"""
        viewer = ConsoleViewer(sample_papers, page_size=10)
        assert len(viewer.controller.papers) == 15
        assert viewer.controller.page_size == 10
        assert viewer.controller.total_pages == 2
        assert viewer.running is False

    def test_empty_papers(self):
        """Test with empty paper list"""
        viewer = ConsoleViewer([], page_size=10)
        assert len(viewer.controller.papers) == 0
        assert viewer.controller.total_pages == 1

    def test_render_page_first_page(self, sample_papers):
        """Test rendering first page"""
        viewer = ConsoleViewer(sample_papers, page_size=10)

        # Mock console.print to capture output
        with patch.object(viewer.console, 'print') as mock_print:
            with patch.object(viewer.console, 'clear') as mock_clear:
                viewer.render_page()

                # Verify clear was called
                mock_clear.assert_called_once()

                # Verify print was called multiple times
                assert mock_print.call_count > 0

    def test_render_page_shows_correct_papers(self, sample_papers):
        """Test that render_page displays papers from current page"""
        viewer = ConsoleViewer(sample_papers, page_size=5)

        # Get papers on first page
        viewer.controller.current_page = 0
        papers_page1 = viewer.controller.get_current_page_papers()

        # Render and verify the papers shown are correct
        with patch.object(viewer.console, 'print') as mock_print:
            with patch.object(viewer.console, 'clear'):
                viewer.render_page()

                # Check that the titles are in the printed output (via APA citations)
                printed_text = str(mock_print.call_args_list)
                for paper in papers_page1:
                    # Check for the paper title in the APA citation
                    assert paper.title in printed_text

    def test_render_page_last_page(self, sample_papers):
        """Test rendering last page with fewer papers"""
        viewer = ConsoleViewer(sample_papers, page_size=10)
        viewer.controller.current_page = 1  # Go to last page

        with patch.object(viewer.console, 'print'):
            with patch.object(viewer.console, 'clear'):
                viewer.render_page()

                # Should show 5 papers on last page (15 total, 10 per page)
                papers = viewer.controller.get_current_page_papers()
                assert len(papers) == 5

    def test_controller_integration(self, sample_papers):
        """Test that viewer's controller is properly initialized"""
        viewer = ConsoleViewer(sample_papers, page_size=10)

        assert viewer.controller is not None
        assert viewer.controller.papers == sample_papers
        assert viewer.controller.current_page == 0
        page_info = viewer.controller.get_page_info()
        assert page_info["current_page"] == 1
        assert page_info["total_pages"] == 2

    def test_page_navigation_methods(self, sample_papers):
        """Test that viewer can navigate through pages"""
        viewer = ConsoleViewer(sample_papers, page_size=10)

        assert viewer.controller.current_page == 0

        # Test next page
        viewer.controller.next_page()
        assert viewer.controller.current_page == 1

        # Test prev page
        viewer.controller.prev_page()
        assert viewer.controller.current_page == 0

    def test_viewer_stop(self, sample_papers):
        """Test stopping the viewer"""
        viewer = ConsoleViewer(sample_papers)
        viewer.running = True

        viewer.stop()
        assert viewer.running is False

    def test_viewer_with_papers_without_doi(self, sample_papers):
        """Test viewer handles papers without DOI correctly"""
        papers = [
            Paper(
                cite_key="test1",
                title="Test Paper",
                year=2024,
                authors=[Author(given_name="A", family_name="B", full_name="A B")],
                doi=None,  # No DOI
            )
        ]

        viewer = ConsoleViewer(papers)

        with patch.object(viewer.console, 'print') as mock_print:
            with patch.object(viewer.console, 'clear'):
                viewer.render_page()

                # Should still render without error
                assert mock_print.call_count > 0

    def test_viewer_with_papers_without_journal(self, sample_papers):
        """Test viewer handles papers without journal info"""
        papers = [
            Paper(
                cite_key="test1",
                title="Test Paper",
                year=2024,
                authors=[Author(given_name="A", family_name="B", full_name="A B")],
                journal=None,
                volume=None,
                number=None,
                pages=None,
            )
        ]

        viewer = ConsoleViewer(papers)

        with patch.object(viewer.console, 'print') as mock_print:
            with patch.object(viewer.console, 'clear'):
                viewer.render_page()

                # Should handle gracefully
                assert mock_print.call_count > 0

    def test_multiple_papers_apa_format(self, sample_papers):
        """Test that multiple papers are rendered with APA format"""
        viewer = ConsoleViewer(sample_papers[:3], page_size=10)

        with patch.object(viewer.console, 'print') as mock_print:
            with patch.object(viewer.console, 'clear'):
                viewer.render_page()

                # Verify papers are formatted with index and APA citation
                printed_calls = [str(call_obj) for call_obj in mock_print.call_args_list]
                printed_text = " ".join(printed_calls)

                # Check for indexed papers (red or cyan depending on keywords/abstract)
                assert ("[red]1[/red]" in printed_text or "[cyan]1.[/cyan]" in printed_text) and ("2021" in printed_text or "2022" in printed_text)

    def test_page_size_parameter(self):
        """Test different page sizes"""
        papers = [
            Paper(
                cite_key=f"p{i}",
                title=f"Paper {i}",
                year=2024,
                authors=[Author(given_name="A", family_name="B", full_name="A B")]
            )
            for i in range(1, 21)
        ]

        # Test with page_size=5
        viewer = ConsoleViewer(papers, page_size=5)
        assert viewer.controller.page_size == 5
        assert viewer.controller.total_pages == 4

        # Test with page_size=20
        viewer = ConsoleViewer(papers, page_size=20)
        assert viewer.controller.page_size == 20
        assert viewer.controller.total_pages == 1
